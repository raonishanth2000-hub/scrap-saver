"""Read receipt-like emails from Gmail over IMAP (needs a Google App password)."""

import email
import imaplib
import re
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime
from urllib.parse import quote

from bs4 import BeautifulSoup

from . import config

# Gmail search used to find payment emails (same syntax as the Gmail search box).
RECEIPT_QUERY = (
    "(category:purchases OR subject:(receipt OR invoice OR payment OR paid OR bill OR order "
    "OR subscription OR renewal OR renewed OR fee OR fees OR transaction OR successful))"
)


class GmailError(RuntimeError):
    pass


def _decode(value) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:  # noqa: BLE001
        return str(value)


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "head"]):
        tag.decompose()
    return soup.get_text(" ", strip=True)


def _body_and_attachments(msg) -> tuple[str, list[str]]:
    plain, html, attachments = [], [], []
    for part in msg.walk() if msg.is_multipart() else [msg]:
        if part.get_content_maintype() == "multipart":
            continue
        filename = part.get_filename()
        disposition = (part.get("Content-Disposition") or "").lower()
        if filename or "attachment" in disposition:
            if filename:
                attachments.append(_decode(filename))
            continue
        try:
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            continue
        ctype = part.get_content_type()
        if ctype == "text/plain":
            plain.append(text)
        elif ctype == "text/html":
            html.append(text)
    body = "\n".join(plain).strip()
    if len(body) < 40 and html:
        body = _html_to_text("\n".join(html))
    body = re.sub(r"\s+", " ", body)
    return body[:5000], attachments


def gmail_link(message_id: str) -> str:
    mid = message_id.strip("<>")
    return "https://mail.google.com/mail/u/0/#search/" + quote(f"rfc822msgid:{mid}")


def fetch_receipt_emails(limit: int | None = None, lookback_days: int | None = None, skip_ids: set[str] | None = None) -> list[dict]:
    """Return the newest receipt-like emails as dicts: id, subject, sender, date, body, attachments, link."""
    if not config.has_gmail():
        raise GmailError("Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD in your .env file first.")
    limit = limit or config.MAX_EMAILS
    lookback_days = lookback_days or config.LOOKBACK_DAYS
    skip_ids = skip_ids or set()
    since = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime("%Y/%m/%d")
    query = f"{RECEIPT_QUERY} after:{since}"

    try:
        imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        imap.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
    except imaplib.IMAP4.error as err:
        raise GmailError(
            "Gmail login failed. Use a Google App password (Google Account > Security > "
            "2-Step Verification > App passwords), not your normal password."
        ) from err
    except OSError as err:
        raise GmailError(f"Could not reach Gmail: {err}") from err

    results = []
    try:
        # "[Gmail]/All Mail" also finds archived receipts; fall back to INBOX.
        status, _ = imap.select('"[Gmail]/All Mail"', readonly=True)
        if status != "OK":
            imap.select("INBOX", readonly=True)
        status, data = imap.uid("SEARCH", "X-GM-RAW", f'"{query}"'.encode())
        if status != "OK" or not data or not data[0]:
            return []
        uids = data[0].split()[::-1][: limit * 2]  # newest first
        for uid in uids:
            if len(results) >= limit:
                break
            status, msg_data = imap.uid("FETCH", uid, "(RFC822)")
            if status != "OK" or not msg_data or not isinstance(msg_data[0], tuple):
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            message_id = (msg.get("Message-ID") or f"uid-{uid.decode()}").strip()
            if message_id in skip_ids:
                continue
            try:
                date = parsedate_to_datetime(msg.get("Date")).date().isoformat()
            except Exception:  # noqa: BLE001
                date = ""
            body, attachments = _body_and_attachments(msg)
            results.append(
                {
                    "id": message_id,
                    "subject": _decode(msg.get("Subject")),
                    "sender": _decode(msg.get("From")),
                    "date": date,
                    "body": body,
                    "attachments": attachments,
                    "link": gmail_link(message_id),
                }
            )
    finally:
        try:
            imap.logout()
        except Exception:  # noqa: BLE001
            pass
    return results
