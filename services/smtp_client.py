import smtplib
from email.message import EmailMessage
from email.utils import parseaddr

from config import SMTP_FROM, SMTP_HOST, SMTP_PASS, SMTP_PORT, SMTP_USER


def _reply_subject(subject: str | None) -> str:
    clean_subject = (subject or "无主题").strip() or "无主题"
    if clean_subject.lower().startswith("re:"):
        return clean_subject
    return f"Re: {clean_subject}"


def _recipient_from_sender(sender: str | None) -> str:
    name, address = parseaddr(sender or "")
    if not address:
        raise ValueError("无法从发件人中解析回复地址")
    return address


def _require_smtp_config():
    missing = [
        name for name, value in {
            "SMTP_HOST": SMTP_HOST,
            "SMTP_USER": SMTP_USER,
            "SMTP_PASS": SMTP_PASS,
            "SMTP_FROM": SMTP_FROM,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(f"缺少 SMTP 配置：{', '.join(missing)}")


def build_reply_message(email_data: dict, body: str) -> EmailMessage:
    if not (body or "").strip():
        raise ValueError("回复内容不能为空")

    recipient = _recipient_from_sender(email_data.get("sender"))
    message = EmailMessage()
    message["From"] = SMTP_FROM
    message["To"] = recipient
    message["Subject"] = _reply_subject(email_data.get("subject"))
    message.set_content(body.strip())
    return message


def send_reply(email_data: dict, body: str) -> dict:
    _require_smtp_config()
    message = build_reply_message(email_data, body)

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.send_message(message)

    return {
        "to": message["To"],
        "subject": message["Subject"],
    }
