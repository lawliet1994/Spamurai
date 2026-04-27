from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse
from nicegui import app

from config import get_categories, save_categories
from database import (
    list_emails,
    get_email,
    update_email_status,
    get_email_attachment,
)
from services.mail_client import sync_emails
from services.template_service import (
    get_template,
    save_template,
    render_template,
)
from services.ai_service import suggest_template
from services.smtp_client import send_reply
from models import (
    EmailStatusUpdateDTO,
    TemplateUpdateDTO,
    TemplateSuggestDTO,
    CategoriesUpdateDTO,
    ReplySendDTO,
)


@app.get("/api/categories")
def api_categories():
    return {
        "categories": get_categories()
    }


@app.put("/api/categories")
def api_save_categories(payload: CategoriesUpdateDTO):
    return {
        "ok": True,
        "categories": save_categories(payload.categories),
    }


@app.post("/api/sync")
def api_sync(limit: int = 20):
    count = sync_emails(limit=limit)
    return {
        "ok": True,
        "synced": count,
    }


@app.get("/api/emails")
def api_list_emails(category: str | None = None, include_deleted: bool = False):
    return {
        "items": list_emails(
            category=category,
            include_deleted=include_deleted,
        )
    }


@app.get("/api/emails/{email_id}")
def api_get_email(email_id: int):
    data = get_email(email_id)
    if not data:
        return {
            "ok": False,
            "message": "邮件不存在",
        }

    return {
        "ok": True,
        "item": data,
    }


@app.get("/api/emails/{email_id}/attachments/{attachment_id}")
def api_download_attachment(email_id: int, attachment_id: int):
    attachment = get_email_attachment(email_id, attachment_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="附件不存在")

    path = Path(attachment["path"])
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="附件文件不存在")

    return FileResponse(
        path,
        media_type=attachment.get("content_type") or "application/octet-stream",
        filename=attachment["filename"],
    )


@app.patch("/api/emails/{email_id}/status")
def api_update_email_status(email_id: int, payload: EmailStatusUpdateDTO):
    update_email_status(
        email_id=email_id,
        is_read=payload.is_read,
        is_deleted=payload.is_deleted,
    )
    return {
        "ok": True,
    }


@app.get("/api/templates/{category}")
def api_get_template(category: str):
    return {
        "category": category,
        "content": get_template(category),
    }


@app.put("/api/templates")
def api_save_template(payload: TemplateUpdateDTO):
    save_template(payload.category, payload.content)
    return {
        "ok": True,
    }


@app.post("/api/templates/suggest")
def api_suggest_template(payload: TemplateSuggestDTO):
    content = suggest_template(
        category=payload.category,
        current_template=payload.current_template,
        sample_summary=payload.sample_summary,
    )
    return {
        "ok": True,
        "content": content,
    }


@app.get("/api/emails/{email_id}/reply-draft")
def api_reply_draft(email_id: int):
    email_data = get_email(email_id)

    if not email_data:
        return {
            "ok": False,
            "message": "邮件不存在",
        }

    template = get_template(email_data["category"])
    draft = render_template(template, email_data)

    return {
        "ok": True,
        "category": email_data["category"],
        "template": template,
        "draft": draft,
    }


@app.post("/api/emails/{email_id}/send-reply")
def api_send_reply(email_id: int, payload: ReplySendDTO):
    email_data = get_email(email_id)

    if not email_data:
        return {
            "ok": False,
            "message": "邮件不存在",
        }

    sent = send_reply(email_data, payload.body)
    return {
        "ok": True,
        **sent,
    }
