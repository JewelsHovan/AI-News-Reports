#!/usr/bin/env python3
import argparse
import base64
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib import error, request

try:
    import msal
except ImportError:  # pragma: no cover - runtime guard
    msal = None

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
DEFAULT_CONFIG = CONFIG_DIR / "email_config.json"
DEFAULT_RECIPIENTS = CONFIG_DIR / "recipients.json"


@dataclass
class Recipient:
    name: str
    email: str
    active: bool = True


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"p", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if data:
            self._parts.append(data)

    def text(self) -> str:
        return "".join(self._parts)


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return ""


def _load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"missing config file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _resolve_path(path_str: str) -> Path:
    path = Path(os.path.expanduser(path_str))
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path


def _load_recipients(path: Path) -> list[Recipient]:
    data = _load_json(path)
    if not isinstance(data, list):
        raise ValueError("recipients.json must be a JSON array")
    recipients: list[Recipient] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        email = (entry.get("email") or "").strip()
        if not email:
            continue
        recipients.append(
            Recipient(
                name=(entry.get("name") or "").strip() or email,
                email=email,
                active=bool(entry.get("active", True)),
            )
        )
    return recipients


def _html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    text = unescape(parser.text())
    # Normalize whitespace while keeping paragraphs.
    lines = [line.strip() for line in text.splitlines()]
    filtered = [line for line in lines if line]
    return "\n\n".join(filtered).strip()


def _read_manifest_tail(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    last_line = ""
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                last_line = line.strip()
    if not last_line:
        return None
    try:
        return json.loads(last_line)
    except json.JSONDecodeError:
        return None


def _build_subject(template: str, context: dict[str, str]) -> str:
    rendered = template.format_map(_SafeDict(context)).strip()
    return rendered or context.get("title", "AI News Report")


def _get_keychain_secret(service: str, account: str | None, verbose: bool) -> str | None:
    if not service:
        return None
    command = ["security", "find-generic-password", "-s", service, "-w"]
    if account:
        command.extend(["-a", account])
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
        secret = result.stdout.strip()
        if verbose:
            sys.stderr.write("info: loaded client secret from keychain\n")
        return secret or None
    except subprocess.CalledProcessError:
        if verbose:
            sys.stderr.write("warning: client secret not found in keychain\n")
        return None


def _get_access_token(config: dict[str, Any], client_secret: str | None, verbose: bool) -> str:
    if msal is None:
        raise RuntimeError("msal is required (install with: uv pip install msal)")

    tenant_id = config.get("tenant_id")
    client_id = config.get("client_id")
    if not tenant_id or not client_id:
        raise ValueError("tenant_id and client_id must be set in email_config.json")

    authority = f"https://login.microsoftonline.com/{tenant_id}"
    auth_flow = (config.get("auth_flow") or "device_code").lower()
    scopes = config.get("scopes") or ["Mail.Send"]

    if auth_flow == "client_credentials":
        if not client_secret:
            raise RuntimeError("client_credentials flow requires a client secret")
        app = msal.ConfidentialClientApplication(
            client_id=client_id,
            authority=authority,
            client_credential=client_secret,
        )
        cc_scopes = config.get("client_credentials_scopes") or [
            "https://graph.microsoft.com/.default"
        ]
        result = app.acquire_token_for_client(scopes=cc_scopes)
    elif auth_flow == "interactive":
        # Interactive browser flow - opens browser automatically
        app = msal.PublicClientApplication(
            client_id=client_id,
            authority=authority,
        )
        # Try to get cached token first
        accounts = app.get_accounts()
        if accounts:
            result = app.acquire_token_silent(scopes=scopes, account=accounts[0])
            if result and "access_token" in result:
                if verbose:
                    sys.stderr.write("info: using cached token\n")
                return result["access_token"]
        # No cached token, do interactive login
        if verbose:
            sys.stderr.write("info: opening browser for sign-in...\n")
        result = app.acquire_token_interactive(scopes=scopes)
    else:
        # Device code flow (fallback)
        app = msal.PublicClientApplication(
            client_id=client_id,
            authority=authority,
        )
        flow = app.initiate_device_flow(scopes=scopes)
        if "message" not in flow:
            raise RuntimeError("failed to start device code flow")
        sys.stderr.write(flow["message"] + "\n")
        result = app.acquire_token_by_device_flow(flow)

    token = result.get("access_token")
    if not token:
        raise RuntimeError(f"token acquisition failed: {result}")
    if verbose:
        sys.stderr.write("info: acquired access token\n")
    return token


def _send_message(
    token: str,
    endpoint: str,
    sender_email: str,
    recipient: Recipient,
    subject: str,
    html_body: str,
    text_body: str,
    dry_run: bool,
    verbose: bool,
) -> None:
    payload: dict[str, Any] = {
        "message": {
            "subject": subject,
            "body": {"contentType": "HTML", "content": html_body},
            "toRecipients": [
                {
                    "emailAddress": {
                        "address": recipient.email,
                        "name": recipient.name,
                    }
                }
            ],
        },
        "saveToSentItems": True,
    }

    if sender_email:
        payload["message"]["from"] = {
            "emailAddress": {"address": sender_email}
        }

    if text_body:
        payload["message"]["attachments"] = [
            {
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": "report.txt",
                "contentType": "text/plain",
                "contentBytes": base64.b64encode(text_body.encode("utf-8")).decode(
                    "ascii"
                ),
            }
        ]

    if dry_run:
        sys.stderr.write(
            f"dry-run: would send to {recipient.email} via {endpoint}\n"
        )
        return

    data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    req = request.Request(
        endpoint,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(req) as resp:
            status = resp.getcode()
            body = resp.read().decode("utf-8")
    except error.HTTPError as exc:
        status = exc.code
        body = exc.read().decode("utf-8")
        raise RuntimeError(f"Graph API error {status}: {body}") from exc

    if status not in {200, 201, 202, 204}:
        raise RuntimeError(f"unexpected Graph API status {status}: {body}")

    if verbose:
        sys.stderr.write(f"info: sent to {recipient.email} (status {status})\n")


def _log_sent(log_path: Path, email: str) -> None:
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(email + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Send latest AI news report via Microsoft Graph."
    )
    parser.add_argument("--dry-run", action="store_true", help="Do not send mail")
    parser.add_argument("--test-email", help="Send only to this email")
    parser.add_argument("--force", action="store_true", help="Ignore sent log")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help="Path to email_config.json",
    )
    parser.add_argument(
        "--recipients",
        default=str(DEFAULT_RECIPIENTS),
        help="Path to recipients.json",
    )

    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    recipients_path = Path(args.recipients).resolve()

    config = _load_json(config_path)
    recipients = _load_recipients(recipients_path)

    if args.test_email:
        recipients = [Recipient(name=args.test_email, email=args.test_email, active=True)]
    else:
        recipients = [rec for rec in recipients if rec.active]

    if not recipients:
        raise RuntimeError("no active recipients")

    report_path = _resolve_path(config.get("report_path", "reports/latest.html"))
    if not report_path.exists():
        raise FileNotFoundError(f"report not found: {report_path}")

    html_body = report_path.read_text(encoding="utf-8")
    text_body = _html_to_text(html_body)

    manifest_path = _resolve_path(config.get("manifest_path", "reports/manifest.jsonl"))
    manifest = _read_manifest_tail(manifest_path) or {}

    start_date = manifest.get("date_range_start", "")
    end_date = manifest.get("date_range_end", "")
    date_range = ""
    if start_date and end_date:
        date_range = f"{start_date} to {end_date}"

    title = "AI News Report"
    subject_template = config.get("subject_template", "AI News Report")
    subject = _build_subject(
        subject_template,
        {
            "title": title,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "date_range": date_range,
            "start_date": start_date,
            "end_date": end_date,
            "generated_at": manifest.get("generated_at", ""),
        },
    )

    sender_email = config.get("sender_email", "")

    token = ""
    if not args.dry_run:
        keychain_service = config.get("keychain_service", "")
        keychain_account = config.get("keychain_account", "")
        client_secret = _get_keychain_secret(
            keychain_service, keychain_account or None, args.verbose
        )
        token = _get_access_token(config, client_secret, args.verbose)

    auth_flow = (config.get("auth_flow") or "device_code").lower()
    endpoint = config.get("graph_endpoint", "https://graph.microsoft.com/v1.0/me/sendMail")
    if auth_flow == "client_credentials" and "/me/" in endpoint:
        endpoint = endpoint.replace(
            "/me/sendMail", f"/users/{sender_email}/sendMail"
        )
        if args.verbose:
            sys.stderr.write("info: using /users/{sender}/sendMail for app-only token\n")

    today = datetime.now().strftime("%Y-%m-%d")
    log_path = CONFIG_DIR / f"sent_log_{today}.txt"
    sent_emails: set[str] = set()
    if log_path.exists():
        sent_emails = {line.strip().lower() for line in log_path.read_text().splitlines() if line.strip()}

    for idx, recipient in enumerate(recipients):
        email_key = recipient.email.lower()
        if email_key in sent_emails and not args.force:
            if args.verbose:
                sys.stderr.write(f"info: skipping {recipient.email} (already sent)\n")
            continue

        _send_message(
            token,
            endpoint,
            sender_email,
            recipient,
            subject,
            html_body,
            text_body,
            args.dry_run,
            args.verbose,
        )

        if not args.dry_run:
            _log_sent(log_path, recipient.email)

        if idx < len(recipients) - 1:
            time.sleep(2)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - user-facing error handling
        sys.stderr.write(f"error: {exc}\n")
        raise SystemExit(1)
