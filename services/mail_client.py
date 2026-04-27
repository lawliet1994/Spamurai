import contextlib
import email
import poplib
from email.header import decode_header
from html.parser import HTMLParser
from pathlib import Path
import re

from config import DATA_DIR, POP3_HOST, POP3_USER, POP3_PASS
from services.ai_service import analyze_email
from database import email_exists, insert_email, insert_email_attachments


MAX_ATTACHMENT_TEXT_CHARS = 6000
MAX_TOTAL_ATTACHMENT_TEXT_CHARS = 12000
ATTACHMENT_DIR = DATA_DIR / "attachments"
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


def _is_attachment_part(part):
    content_disposition = str(part.get("Content-Disposition", ""))
    return "attachment" in content_disposition or bool(part.get_filename())


def _safe_filename(filename: str) -> str:
    name = Path(filename).name.strip() or "未命名附件"
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = name.rstrip(" .")
    return name or "未命名附件"


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
        filename = _attachment_filename(part)
        if not _is_attachment_part(part):
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


def save_original_attachments(uid: str, msg):
    attachments = []
    target_dir = ATTACHMENT_DIR / _safe_filename(uid)
    used_names = set()

    for part in msg.walk():
        if not _is_attachment_part(part):
            continue

        payload = part.get_payload(decode=True)
        if not payload:
            continue

        filename = _safe_filename(_attachment_filename(part))
        stem = Path(filename).stem or "attachment"
        suffix = Path(filename).suffix
        candidate = filename
        index = 2
        while candidate in used_names:
            candidate = f"{stem}-{index}{suffix}"
            index += 1

        used_names.add(candidate)
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / candidate
        path.write_bytes(payload)
        attachments.append({
            "filename": candidate,
            "content_type": part.get_content_type(),
            "path": str(path),
            "size": len(payload),
        })

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


def _parse_email_record(uid, raw):
    msg = email.message_from_bytes(raw)
    body = extract_body(msg)
    attachment_texts = extract_attachment_texts(msg)
    attachments = save_original_attachments(uid, msg)

    return {
        "uid": uid,
        "sender": decode_text(msg.get("From")),
        "subject": decode_text(msg.get("Subject")),
        "received_at": msg.get("Date", ""),
        "body": combine_body_and_attachments(body, attachment_texts),
        "attachments": attachments,
    }


def sync_emails(limit=20):
    records = []
    mail = poplib.POP3(POP3_HOST)
    try:
        try:
            mail.user(POP3_USER)
            mail.pass_(POP3_PASS)
        except poplib.error_proto as exc:
            raise RuntimeError(f"POP3 login failed: {exc}") from exc

        try:
            _, uid_lines, _ = mail.uidl()
        except poplib.error_proto as exc:
            raise RuntimeError(f"POP3 uidl failed: {exc}") from exc

        for line in uid_lines[-limit:]:
            parts = line.decode("utf-8", errors="ignore").split(maxsplit=1)
            if len(parts) != 2:
                continue

            message_number, uid = parts
            if email_exists(uid):
                continue

            try:
                _, lines, _ = mail.retr(message_number)
            except poplib.error_proto as exc:
                raise RuntimeError(f"POP3 retr failed for message {message_number!r}: {exc}") from exc

            raw = b"\r\n".join(lines)
            records.append(_parse_email_record(uid, raw))
    finally:
        with contextlib.suppress(poplib.error_proto, OSError):
            mail.quit()

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
        insert_email_attachments(record["uid"], record.get("attachments", []))

        count += 1

    return count
