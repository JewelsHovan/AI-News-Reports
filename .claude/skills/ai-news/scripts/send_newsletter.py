#!/usr/bin/env python3
import argparse
import base64
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib import error, request
from urllib.parse import urlparse

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


@dataclass
class RecipientWithUnsubscribe:
    recipient: Recipient
    unsubscribe_url: str


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


def _validate_api_url(url: str) -> None:
    """Validate that the API URL uses HTTPS."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"API URL must use HTTPS for security, got: {parsed.scheme}://{parsed.netloc}")
    if not parsed.netloc:
        raise ValueError("API URL must include a hostname")


def _load_recipients_from_api(url: str, secret: str) -> list[RecipientWithUnsubscribe]:
    """Fetch subscribers from the API endpoint.

    Args:
        url: Base URL of the subscribers API (e.g., https://worker.dev/api/subscribers)
        secret: API secret for authentication

    Returns:
        List of RecipientWithUnsubscribe objects for active subscribers

    Raises:
        RuntimeError: If the API request fails or returns an error
        ValueError: If the API URL does not use HTTPS
    """
    _validate_api_url(url)
    api_url = f"{url}?secret={secret}"

    req = request.Request(
        api_url,
        headers={"Accept": "application/json"},
        method="GET",
    )

    try:
        with request.urlopen(req, timeout=30) as resp:
            status = resp.getcode()
            body = resp.read().decode("utf-8")
    except error.HTTPError as exc:
        status = exc.code
        body = exc.read().decode("utf-8")
        raise RuntimeError(f"API error {status}: {body}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Failed to connect to API: {exc.reason}") from exc

    if status != 200:
        raise RuntimeError(f"Unexpected API status {status}: {body}")

    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON response from API: {exc}") from exc

    if not data.get("success"):
        raise RuntimeError(f"API returned error: {data}")

    subscribers = data.get("data", [])
    if not isinstance(subscribers, list):
        raise RuntimeError("API response 'data' field must be an array")

    recipients: list[RecipientWithUnsubscribe] = []
    for entry in subscribers:
        if not isinstance(entry, dict):
            continue
        email = (entry.get("email") or "").strip()
        if not email:
            continue
        # Only include active subscribers
        if not entry.get("active", True):
            continue
        unsubscribe_url = (entry.get("unsubscribeUrl") or "").strip()
        recipients.append(
            RecipientWithUnsubscribe(
                recipient=Recipient(
                    name=(entry.get("name") or "").strip() or email,
                    email=email,
                    active=True,
                ),
                unsubscribe_url=unsubscribe_url,
            )
        )
    return recipients


def _personalize_html(html: str, unsubscribe_url: str) -> str:
    """Replace the {UNSUBSCRIBE_LINK} placeholder with the actual unsubscribe URL.

    Args:
        html: HTML content with optional {UNSUBSCRIBE_LINK} placeholder
        unsubscribe_url: The personalized unsubscribe URL for this recipient

    Returns:
        HTML with the placeholder replaced
    """
    return html.replace("{UNSUBSCRIBE_LINK}", unsubscribe_url)


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


def _build_mime_message(
    sender_email: str,
    recipient: Recipient,
    subject: str,
    html_body: str,
    text_body: str,
) -> str:
    """Build a proper MIME multipart/alternative message with both text and HTML."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = f"{recipient.name} <{recipient.email}>"
    msg["Date"] = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")

    # Plain text part (comes first, lower priority)
    text_part = MIMEText(text_body, "plain", "utf-8")
    msg.attach(text_part)

    # HTML part (comes second, higher priority - email clients prefer last)
    html_part = MIMEText(html_body, "html", "utf-8")
    msg.attach(html_part)

    return msg.as_string()


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
    use_mime: bool = True,
) -> None:
    if dry_run:
        sys.stderr.write(
            f"dry-run: would send to {recipient.email} via {endpoint}\n"
        )
        return

    if use_mime and text_body:
        # Build proper MIME multipart/alternative message
        mime_content = _build_mime_message(
            sender_email, recipient, subject, html_body, text_body
        )
        mime_b64 = base64.b64encode(mime_content.encode("utf-8")).decode("ascii")

        # Send raw MIME directly via /sendMail - only requires Mail.Send permission
        req = request.Request(
            endpoint,
            data=mime_b64.encode("ascii"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "text/plain",  # MS Graph expects base64 MIME as text/plain
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=30) as resp:
                status = resp.getcode()
        except error.HTTPError as exc:
            status = exc.code
            resp_body = exc.read().decode("utf-8")
            raise RuntimeError(f"Graph API error {status}: {resp_body}") from exc

        if status not in {200, 202}:
            raise RuntimeError(f"unexpected Graph API status {status}")

        if verbose:
            sys.stderr.write(f"info: sent MIME message to {recipient.email} (status {status})\n")
    else:
        # Fallback to JSON API (HTML only)
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
            with request.urlopen(req, timeout=30) as resp:
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
        "--no-mime",
        action="store_true",
        help="Use JSON API instead of MIME (no multipart/alternative)",
    )
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
    parser.add_argument(
        "--api-url",
        help="URL to fetch subscribers from (e.g., https://worker.dev/api/subscribers)",
    )
    parser.add_argument(
        "--api-secret",
        help="Secret for API authentication (passed as ?secret= query param)",
    )

    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    recipients_path = Path(args.recipients).resolve()

    config = _load_json(config_path)

    # Determine recipient source: API or file-based
    use_api = bool(args.api_url)
    recipients_with_unsubscribe: list[RecipientWithUnsubscribe] = []
    recipients: list[Recipient] = []

    if use_api:
        if not args.api_secret:
            raise RuntimeError("--api-secret is required when using --api-url")
        recipients_with_unsubscribe = _load_recipients_from_api(args.api_url, args.api_secret)
        if args.verbose:
            sys.stderr.write(f"info: loaded {len(recipients_with_unsubscribe)} subscribers from API\n")
    else:
        # File-based loading (backwards compat for POC/testing)
        recipients = _load_recipients(recipients_path)

    if args.test_email:
        # Test mode overrides both API and file-based recipients
        recipients = [Recipient(name=args.test_email, email=args.test_email, active=True)]
        recipients_with_unsubscribe = []
        use_api = False
    elif not use_api:
        recipients = [rec for rec in recipients if rec.active]

    if not recipients and not recipients_with_unsubscribe:
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

    if use_api:
        # API-sourced recipients: personalize HTML with unsubscribe URL
        total = len(recipients_with_unsubscribe)
        for idx, rec_with_unsub in enumerate(recipients_with_unsubscribe):
            recipient = rec_with_unsub.recipient
            email_key = recipient.email.lower()
            if email_key in sent_emails and not args.force:
                if args.verbose:
                    sys.stderr.write(f"info: skipping {recipient.email} (already sent)\n")
                continue

            # Personalize HTML with recipient's unsubscribe URL
            personalized_html = _personalize_html(html_body, rec_with_unsub.unsubscribe_url)
            personalized_text = _html_to_text(personalized_html)

            _send_message(
                token,
                endpoint,
                sender_email,
                recipient,
                subject,
                personalized_html,
                personalized_text,
                args.dry_run,
                args.verbose,
                use_mime=not args.no_mime,
            )

            if not args.dry_run:
                _log_sent(log_path, recipient.email)

            if idx < total - 1:
                time.sleep(2)
    else:
        # File-sourced recipients: use HTML as-is (no unsubscribe link)
        total = len(recipients)
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
                use_mime=not args.no_mime,
            )

            if not args.dry_run:
                _log_sent(log_path, recipient.email)

            if idx < total - 1:
                time.sleep(2)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - user-facing error handling
        sys.stderr.write(f"error: {exc}\n")
        raise SystemExit(1)
