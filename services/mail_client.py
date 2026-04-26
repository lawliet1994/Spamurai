import contextlib
import imaplib
import email
from email.header import decode_header
from html.parser import HTMLParser

from config import IMAP_HOST, IMAP_USER, IMAP_PASS, IMAP_MAILBOX
from services.ai_service import analyze_email
from database import email_exists, insert_email


MAX_ATTACHMENT_TEXT_CHARS = 6000
MAX_TOTAL_ATTACHMENT_TEXT_CHARS = 12000
READABLE_ATTACHMENT_TYPES = {
    "application/json",
    "application/xml",
    "text/csv",
    "text/markdown",
    "text/plain",
}


class _HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        text = data.strip()
        if text:
            self.parts.append(text)

    def text(self):
        return "\n".join(self.parts)


def _format_imap_response(data):
    if not data:
        return ""

    parts = []
    for item in data:
        if isinstance(item, bytes):
            parts.append(item.decode("utf-8", errors="ignore"))
        else:
            parts.append(str(item))

    return "; ".join(parts)


def _require_ok(status, data, action):
    if status != "OK":
        message = _format_imap_response(data)
        raise RuntimeError(f"IMAP {action}: {message}")


def _send_imap_id(mail):
    payload = '("name" "MailAssistant" "version" "0.1.0" "vendor" "MailAssistant")'
    imaplib.Commands.setdefault("ID", ("AUTH", "SELECTED"))
    with contextlib.suppress(imaplib.IMAP4.error, AttributeError, KeyError, OSError):
        mail._simple_command("ID", payload)


def decode_text(value):
    if not value:
        return ""

    parts = decode_header(value)
    result = ""

    for text, charset in parts:
        if isinstance(text, bytes):
            result += text.decode(charset or "utf-8", errors="ignore")
        else:
            result += text

    return result


def _attachment_filename(part):
    return decode_text(part.get_filename()) or "未命名附件"


def _decode_part_payload(part):
    payload = part.get_payload(decode=True)
    if not payload:
        return ""
    return payload.decode(part.get_content_charset() or "utf-8", errors="ignore")


def _html_to_text(value: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(value)
    return parser.text()


def extract_attachment_texts(msg):
    attachments = []
    total_chars = 0

    for part in msg.walk():
        content_disposition = str(part.get("Content-Disposition", ""))
        filename = _attachment_filename(part)
        if "attachment" not in content_disposition and not part.get_filename():
            continue

        content_type = part.get_content_type()
        if content_type == "text/html":
            text = _html_to_text(_decode_part_payload(part))
        elif content_type.startswith("text/") or content_type in READABLE_ATTACHMENT_TYPES:
            text = _decode_part_payload(part)
        else:
            text = f"暂不支持读取此类型附件：{content_type}"

        text = text.strip()
        if not text:
            continue

        remaining_chars = MAX_TOTAL_ATTACHMENT_TEXT_CHARS - total_chars
        if remaining_chars <= 0:
            break

        clipped = text[:min(MAX_ATTACHMENT_TEXT_CHARS, remaining_chars)]
        total_chars += len(clipped)
        attachments.append(f"附件：{filename}\n{clipped}")

    return attachments


def extract_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))

            if content_type == "text/plain" and "attachment" not in content_disposition:
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(
                        part.get_content_charset() or "utf-8",
                        errors="ignore",
                    )

    payload = msg.get_payload(decode=True)
    if payload:
        return payload.decode(msg.get_content_charset() or "utf-8", errors="ignore")

    return ""


def combine_body_and_attachments(body, attachment_texts):
    if not attachment_texts:
        return body

    sections = [body.strip(), "附件内容：", *attachment_texts]
    return "\n\n".join(section for section in sections if section)


def _parse_email_record(num, raw):
    msg = email.message_from_bytes(raw)
    body = extract_body(msg)
    attachment_texts = extract_attachment_texts(msg)

    return {
        "uid": num.decode(),
        "sender": decode_text(msg.get("From")),
        "subject": decode_text(msg.get("Subject")),
        "received_at": msg.get("Date", ""),
        "body": combine_body_and_attachments(body, attachment_texts),
    }


def sync_emails(limit=20):
    records = []
    mail = imaplib.IMAP4_SSL(IMAP_HOST)
    try:
        status, data = mail.login(IMAP_USER, IMAP_PASS)
        _require_ok(status, data, "login failed")

        _send_imap_id(mail)

        status, data = mail.select(IMAP_MAILBOX)
        _require_ok(status, data, f"select failed for mailbox {IMAP_MAILBOX!r}")

        status, data = mail.search(None, "ALL")
        _require_ok(status, data, "search failed")
        ids = data[0].split()[-limit:]

        for num in ids:
            status, msg_data = mail.fetch(num, "(RFC822)")
            _require_ok(status, msg_data, f"fetch failed for message {num!r}")

            raw = msg_data[0][1]
            record = _parse_email_record(num, raw)
            if not email_exists(record["uid"]):
                records.append(record)
    finally:
        with contextlib.suppress(imaplib.IMAP4.error, OSError):
            mail.logout()

    count = 0

    for record in records:
        ai = analyze_email(record["subject"], record["body"])

        insert_email({
            "uid": record["uid"],
            "sender": record["sender"],
            "subject": record["subject"],
            "body": record["body"],
            "received_at": record["received_at"],
            "category": ai["category"],
            "summary": ai["summary"],
            "priority": ai["priority"],
            "meeting_time": ai.get("meeting_time", ""),
            "meeting_location": ai.get("meeting_location", ""),
            "suggested_action": ai.get("suggested_action", ""),
        })

        count += 1

    return count
