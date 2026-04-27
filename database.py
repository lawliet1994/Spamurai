from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
import sqlite3
from zoneinfo import ZoneInfo

from config import DB_PATH, get_default_category


LOCAL_TIMEZONE = ZoneInfo("Asia/Shanghai")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()

    conn.execute("""
    CREATE TABLE IF NOT EXISTS emails (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uid TEXT UNIQUE,
        sender TEXT,
        subject TEXT,
        body TEXT,
        received_at TEXT,
        category TEXT,
        summary TEXT,
        priority TEXT,
        meeting_time TEXT,
        meeting_location TEXT,
        suggested_action TEXT,
        is_read INTEGER DEFAULT 0,
        is_deleted INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.execute("""
    CREATE INDEX IF NOT EXISTS idx_emails_category
    ON emails(category)
    """)

    conn.execute("""
    CREATE INDEX IF NOT EXISTS idx_emails_read_deleted
    ON emails(is_read, is_deleted)
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS email_attachments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email_uid TEXT,
        filename TEXT,
        content_type TEXT,
        path TEXT,
        size INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.execute("""
    CREATE INDEX IF NOT EXISTS idx_email_attachments_email_uid
    ON email_attachments(email_uid)
    """)

    conn.commit()
    conn.close()


def insert_email(data: dict):
    conn = get_conn()
    conn.execute("""
    INSERT OR IGNORE INTO emails (
        uid, sender, subject, body, received_at,
        category, summary, priority,
        meeting_time, meeting_location, suggested_action
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["uid"],
        data["sender"],
        data["subject"],
        data["body"],
        data["received_at"],
        data["category"],
        data["summary"],
        data["priority"],
        data.get("meeting_time", ""),
        data.get("meeting_location", ""),
        data.get("suggested_action", ""),
    ))
    conn.commit()
    conn.close()


def email_exists(uid: str) -> bool:
    conn = get_conn()
    row = conn.execute("SELECT 1 FROM emails WHERE uid = ? LIMIT 1", (uid,)).fetchone()
    conn.close()
    return row is not None


def update_email_analysis(email_id: int, analysis: dict):
    conn = get_conn()
    conn.execute("""
    UPDATE emails
    SET category = ?,
        summary = ?,
        priority = ?,
        meeting_time = ?,
        meeting_location = ?,
        suggested_action = ?
    WHERE id = ?
    """, (
        analysis.get("category", get_default_category()),
        analysis.get("summary", "无摘要"),
        analysis.get("priority", "低"),
        analysis.get("meeting_time", ""),
        analysis.get("meeting_location", ""),
        analysis.get("suggested_action", ""),
        email_id,
    ))
    conn.commit()
    conn.close()


def _parse_received_at(value: str):
    try:
        received_at = parsedate_to_datetime(value or "")
        if received_at.tzinfo is None:
            received_at = received_at.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None

    return received_at


def _email_sort_key(row: dict):
    received_at = _parse_received_at(row.get("received_at"))
    if received_at is None:
        received_at = datetime.min.replace(tzinfo=timezone.utc)

    return received_at.timestamp(), row.get("id") or 0


def list_emails(category=None, include_deleted=False):
    conn = get_conn()

    sql = """
    SELECT * FROM emails
    WHERE 1=1
    """
    params = []

    if category:
        sql += " AND category = ?"
        params.append(category)

    if not include_deleted:
        sql += " AND is_deleted = 0"

    rows = conn.execute(sql, params).fetchall()
    conn.close()
    items = [dict(row) for row in rows]
    return sorted(items, key=_email_sort_key, reverse=True)


def list_emails_on_date(target_date: date | None = None, include_deleted=False):
    target_date = target_date or datetime.now(LOCAL_TIMEZONE).date()
    rows = list_emails(include_deleted=include_deleted)

    result = []
    for row in rows:
        received_at = _parse_received_at(row.get("received_at"))
        if received_at and received_at.astimezone(LOCAL_TIMEZONE).date() == target_date:
            result.append(row)

    return result


def _is_meeting_email(row: dict) -> bool:
    return bool((row.get("meeting_time") or "").strip()) or row.get("category") == "会议邀约"


def list_meeting_emails(include_deleted=False):
    return [
        row for row in list_emails(include_deleted=include_deleted)
        if _is_meeting_email(row)
    ]


def list_meeting_emails_on_date(target_date: date | None = None, include_deleted=False):
    return [
        row for row in list_emails_on_date(target_date, include_deleted=include_deleted)
        if _is_meeting_email(row)
    ]


def _matches_filter(row: dict, filter_key: str | None) -> bool:
    if not filter_key or filter_key == "all":
        return True
    if filter_key == "high":
        return row.get("priority") == "高"
    if filter_key == "reply":
        return row.get("category") == "待我回复"
    if filter_key == "meeting":
        return _is_meeting_email(row)
    if filter_key == "risk":
        return row.get("category") == "风险警示"
    if filter_key == "unread":
        return not row.get("is_read")
    return True


def list_filtered_emails(
    scope: str | None = None,
    filter_key: str | None = None,
    category: str | None = None,
    target_date: date | None = None,
    include_deleted=False,
):
    if scope == "today":
        rows = list_emails_on_date(target_date, include_deleted=include_deleted)
    elif category:
        rows = list_emails(category=category, include_deleted=include_deleted)
    else:
        rows = list_emails(include_deleted=include_deleted)

    return [
        row for row in rows
        if _matches_filter(row, filter_key)
    ]


def _needs_analysis(row: dict) -> bool:
    category = row.get("category") or ""
    summary = row.get("summary") or ""
    priority = row.get("priority") or ""

    return (
        not category.strip()
        or not summary.strip()
        or not priority.strip()
        or summary == "AI 分析失败，建议人工查看"
    )


def list_emails_needing_analysis_on_date(target_date: date | None = None):
    return [
        row for row in list_emails_on_date(target_date)
        if _needs_analysis(row)
    ]


def get_email(email_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM emails WHERE id = ?", (email_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_email_status(email_id: int, is_read=None, is_deleted=None):
    conn = get_conn()

    if is_read is not None:
        conn.execute("UPDATE emails SET is_read = ? WHERE id = ?", (is_read, email_id))

    if is_deleted is not None:
        conn.execute("UPDATE emails SET is_deleted = ? WHERE id = ?", (is_deleted, email_id))

    conn.commit()
    conn.close()


def insert_email_attachments(email_uid: str, attachments: list[dict]):
    if not attachments:
        return

    conn = get_conn()
    conn.executemany("""
    INSERT INTO email_attachments (
        email_uid, filename, content_type, path, size
    )
    VALUES (?, ?, ?, ?, ?)
    """, [
        (
            email_uid,
            attachment["filename"],
            attachment.get("content_type", ""),
            attachment["path"],
            attachment.get("size", 0),
        )
        for attachment in attachments
    ])
    conn.commit()
    conn.close()


def list_email_attachments(email_id: int):
    conn = get_conn()
    rows = conn.execute("""
    SELECT a.id, a.filename, a.content_type, a.size
    FROM email_attachments a
    JOIN emails e ON e.uid = a.email_uid
    WHERE e.id = ?
    ORDER BY a.id
    """, (email_id,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_email_attachment(email_id: int, attachment_id: int):
    conn = get_conn()
    row = conn.execute("""
    SELECT a.*
    FROM email_attachments a
    JOIN emails e ON e.uid = a.email_uid
    WHERE e.id = ? AND a.id = ?
    """, (email_id, attachment_id)).fetchone()
    conn.close()
    return dict(row) if row else None
