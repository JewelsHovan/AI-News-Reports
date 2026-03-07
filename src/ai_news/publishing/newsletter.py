"""Send newsletter to subscribers via Microsoft Graph."""

import asyncio
import base64
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
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


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class NewsletterResult:
    sent_count: int
    skipped_count: int
    errors: list[str]


@dataclass
class _Recipient:
    name: str
    email: str
    active: bool = True


@dataclass
class _RecipientWithUnsubscribe:
    recipient: _Recipient
    unsubscribe_url: str


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return ""


# =============================================================================
# HTML to Text Conversion
# =============================================================================


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


def _html_to_text(html: str) -> str:
    """Convert HTML to plain text for multipart/alternative emails."""
    parser = _TextExtractor()
    parser.feed(html)
    text = unescape(parser.text())
    lines = [line.strip() for line in text.splitlines()]
    filtered = [line for line in lines if line]
    return "\n\n".join(filtered).strip()


# =============================================================================
# File & Config Loading
# =============================================================================


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


def _load_recipients(path: Path) -> list[_Recipient]:
    data = _load_json(path)
    if not isinstance(data, list):
        raise ValueError("recipients.json must be a JSON array")
    recipients: list[_Recipient] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        email = (entry.get("email") or "").strip()
        if not email:
            continue
        recipients.append(
            _Recipient(
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
        raise ValueError(
            f"API URL must use HTTPS for security, got: {parsed.scheme}://{parsed.netloc}"
        )
    if not parsed.netloc:
        raise ValueError("API URL must include a hostname")


def _load_recipients_from_api(url: str, secret: str) -> list[_RecipientWithUnsubscribe]:
    """Fetch subscribers from the API endpoint."""
    _validate_api_url(url)
    api_url = f"{url}?secret={secret}"

    req = request.Request(
        api_url,
        headers={
            "Accept": "application/json",
            "User-Agent": "AI-News-Newsletter/1.0",
        },
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

    recipients: list[_RecipientWithUnsubscribe] = []
    for entry in subscribers:
        if not isinstance(entry, dict):
            continue
        email = (entry.get("email") or "").strip()
        if not email:
            continue
        if not entry.get("active", True):
            continue
        unsubscribe_url = (entry.get("unsubscribeUrl") or "").strip()
        recipients.append(
            _RecipientWithUnsubscribe(
                recipient=_Recipient(
                    name=(entry.get("name") or "").strip() or email,
                    email=email,
                    active=True,
                ),
                unsubscribe_url=unsubscribe_url,
            )
        )
    return recipients


def _personalize_html(html: str, unsubscribe_url: str) -> str:
    """Replace the {UNSUBSCRIBE_LINK} placeholder with the actual unsubscribe URL."""
    return html.replace("{UNSUBSCRIBE_LINK}", unsubscribe_url)


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


# =============================================================================
# Auth & Keychain
# =============================================================================


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
        app = msal.PublicClientApplication(
            client_id=client_id,
            authority=authority,
        )
        accounts = app.get_accounts()
        if accounts:
            result = app.acquire_token_silent(scopes=scopes, account=accounts[0])
            if result and "access_token" in result:
                if verbose:
                    sys.stderr.write("info: using cached token\n")
                return result["access_token"]
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


# =============================================================================
# MIME & Sending
# =============================================================================


def _build_mime_message(
    sender_email: str,
    recipient: _Recipient,
    subject: str,
    html_body: str,
    text_body: str,
) -> str:
    """Build a proper MIME multipart/alternative message with both text and HTML."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = formataddr((str(Header(recipient.name, 'utf-8')), recipient.email))
    msg["Date"] = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")

    text_part = MIMEText(text_body, "plain", "utf-8")
    msg.attach(text_part)

    html_part = MIMEText(html_body, "html", "utf-8")
    msg.attach(html_part)

    return msg.as_string()


def _send_message(
    token: str,
    endpoint: str,
    sender_email: str,
    recipient: _Recipient,
    subject: str,
    html_body: str,
    text_body: str,
    dry_run: bool,
    verbose: bool,
    use_mime: bool = True,
) -> None:
    """Send a single email message via Microsoft Graph API."""
    if dry_run:
        sys.stderr.write(
            f"dry-run: would send to {recipient.email} via {endpoint}\n"
        )
        return

    if use_mime and text_body:
        mime_content = _build_mime_message(
            sender_email, recipient, subject, html_body, text_body
        )
        mime_b64 = base64.b64encode(mime_content.encode("utf-8")).decode("ascii")

        req = request.Request(
            endpoint,
            data=mime_b64.encode("ascii"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "text/plain",
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


# =============================================================================
# Public API
# =============================================================================


def _send_newsletter_sync(
    report_html_path: Path,
    manifest_path: Path,
    email_config_path: Path,
    api_url: str | None,
    api_secret: str | None,
    dry_run: bool,
    test_email: str | None,
    force: bool,
) -> NewsletterResult:
    """Synchronous implementation of the newsletter sending logic."""
    config = _load_json(email_config_path)

    # Determine recipient source: API or file-based
    use_api = bool(api_url)
    recipients_with_unsubscribe: list[_RecipientWithUnsubscribe] = []
    recipients: list[_Recipient] = []

    if use_api:
        if not api_secret:
            raise RuntimeError("api_secret is required when using api_url")
        recipients_with_unsubscribe = _load_recipients_from_api(api_url, api_secret)  # type: ignore[arg-type]  # guarded by bool check above

    if test_email:
        recipients = [_Recipient(name=test_email, email=test_email, active=True)]
        recipients_with_unsubscribe = []
        use_api = False
    elif not use_api:
        # File-based loading: look for recipients config path from email config
        # or use a default relative to the config file
        recipients_path_str = config.get("recipients_path")
        if recipients_path_str:
            recipients_path = _resolve_path(recipients_path_str)
        else:
            recipients_path = email_config_path.parent / "recipients.json"
        recipients = [rec for rec in _load_recipients(recipients_path) if rec.active]

    if not recipients and not recipients_with_unsubscribe:
        raise RuntimeError("no active recipients")

    # Load report HTML
    if not report_html_path.exists():
        raise FileNotFoundError(f"report not found: {report_html_path}")

    html_body = report_html_path.read_text(encoding="utf-8")
    text_body = _html_to_text(html_body)

    # Read manifest for subject line context
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
    verbose = True  # Always verbose when used as a library (logs go to stderr)
    use_mime = True  # Always use MIME for multipart/alternative

    # Authenticate
    token = ""
    if not dry_run:
        keychain_service = config.get("keychain_service", "")
        keychain_account = config.get("keychain_account", "")
        client_secret = _get_keychain_secret(
            keychain_service, keychain_account or None, verbose
        )
        token = _get_access_token(config, client_secret, verbose)

    auth_flow = (config.get("auth_flow") or "device_code").lower()
    endpoint = config.get("graph_endpoint", "https://graph.microsoft.com/v1.0/me/sendMail")
    if auth_flow == "client_credentials" and "/me/" in endpoint:
        endpoint = endpoint.replace(
            "/me/sendMail", f"/users/{sender_email}/sendMail"
        )

    # Sent log to avoid duplicate sends
    today = datetime.now().strftime("%Y-%m-%d")
    log_dir = email_config_path.parent
    log_path = log_dir / f"sent_log_{today}.txt"
    sent_emails: set[str] = set()
    if log_path.exists():
        sent_emails = {
            line.strip().lower()
            for line in log_path.read_text().splitlines()
            if line.strip()
        }

    sent_count = 0
    skipped_count = 0
    errors: list[str] = []

    if use_api:
        total = len(recipients_with_unsubscribe)
        for idx, rec_with_unsub in enumerate(recipients_with_unsubscribe):
            recipient = rec_with_unsub.recipient
            email_key = recipient.email.lower()
            if email_key in sent_emails and not force:
                skipped_count += 1
                continue

            personalized_html = _personalize_html(html_body, rec_with_unsub.unsubscribe_url)
            personalized_text = _html_to_text(personalized_html)

            try:
                _send_message(
                    token,
                    endpoint,
                    sender_email,
                    recipient,
                    subject,
                    personalized_html,
                    personalized_text,
                    dry_run,
                    verbose,
                    use_mime=use_mime,
                )
                sent_count += 1
                if not dry_run:
                    _log_sent(log_path, recipient.email)
            except Exception as exc:
                errors.append(f"{recipient.email}: {exc}")

            if idx < total - 1:
                time.sleep(2)
    else:
        total = len(recipients)
        for idx, recipient in enumerate(recipients):
            email_key = recipient.email.lower()
            if email_key in sent_emails and not force:
                skipped_count += 1
                continue

            try:
                _send_message(
                    token,
                    endpoint,
                    sender_email,
                    recipient,
                    subject,
                    html_body,
                    text_body,
                    dry_run,
                    verbose,
                    use_mime=use_mime,
                )
                sent_count += 1
                if not dry_run:
                    _log_sent(log_path, recipient.email)
            except Exception as exc:
                errors.append(f"{recipient.email}: {exc}")

            if idx < total - 1:
                time.sleep(2)

    return NewsletterResult(
        sent_count=sent_count,
        skipped_count=skipped_count,
        errors=errors,
    )


async def send_newsletter(
    report_html_path: Path,
    manifest_path: Path,
    email_config_path: Path,
    api_url: str | None = None,
    api_secret: str | None = None,
    dry_run: bool = False,
    test_email: str | None = None,
    force: bool = False,
) -> NewsletterResult:
    """Send newsletter to subscribers via Microsoft Graph.

    Supports two recipient sources:
    - API-based: Fetch subscribers from a Cloudflare Worker API (with personalized
      unsubscribe URLs).
    - File-based: Load recipients from a local JSON file (backwards compatible).

    Args:
        report_html_path: Path to the rendered HTML report to send.
        manifest_path: Path to manifest.jsonl for subject line metadata.
        email_config_path: Path to email_config.json with MSAL/Graph settings.
        api_url: Optional URL to fetch subscribers from (enables API mode).
        api_secret: Secret for API authentication (required if api_url is set).
        dry_run: If True, log what would be sent without actually sending.
        test_email: If set, send only to this email address (overrides recipients).
        force: If True, ignore the sent log and re-send to all recipients.

    Returns:
        NewsletterResult with sent count, skipped count, and any errors.

    Raises:
        FileNotFoundError: If report HTML or config files are missing.
        RuntimeError: If authentication fails or no active recipients found.
    """
    return await asyncio.to_thread(
        _send_newsletter_sync,
        report_html_path,
        manifest_path,
        email_config_path,
        api_url,
        api_secret,
        dry_run,
        test_email,
        force,
    )
