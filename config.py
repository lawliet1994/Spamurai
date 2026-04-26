import json
import os
from pathlib import Path
import re

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
TEMPLATE_DIR = BASE_DIR / "templates"
CATEGORIES_PATH = DATA_DIR / "categories.json"

DATA_DIR.mkdir(exist_ok=True)
TEMPLATE_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "mail_assistant.db"

IMAP_HOST = os.getenv("IMAP_HOST", "imap.163.com")
IMAP_USER = os.getenv("IMAP_USER", "")
IMAP_PASS = os.getenv("IMAP_PASS", "")
IMAP_MAILBOX = os.getenv("IMAP_MAILBOX", "INBOX")

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", IMAP_USER)
SMTP_PASS = os.getenv("SMTP_PASS", IMAP_PASS)
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5")
NICEGUI_STORAGE_SECRET = os.getenv("NICEGUI_STORAGE_SECRET", "dev-storage-secret")

DEFAULT_CATEGORIES = [
    "今日要务",
    "会议邀约",
    "待我回复",
    "系统通知",
    "账单票据",
    "项目进展",
    "低优先级",
    "风险警示",
]
DEFAULT_CATEGORY = "低优先级"


def _clean_categories(categories) -> list[str]:
    cleaned = []
    seen = set()

    for category in categories or []:
        if not isinstance(category, str):
            continue

        value = category.strip()
        if (
            not value
            or len(value) > 50
            or re.search(r"[/\\:]", value)
            or value in seen
        ):
            continue

        cleaned.append(value)
        seen.add(value)

    return cleaned


def get_categories() -> list[str]:
    if not CATEGORIES_PATH.exists():
        save_categories(DEFAULT_CATEGORIES)

    try:
        data = json.loads(CATEGORIES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return DEFAULT_CATEGORIES.copy()

    categories = _clean_categories(data.get("categories") if isinstance(data, dict) else data)
    return categories or DEFAULT_CATEGORIES.copy()


def save_categories(categories) -> list[str]:
    cleaned = _clean_categories(categories)
    if not cleaned:
        raise ValueError("至少需要保留一个分类")

    DATA_DIR.mkdir(exist_ok=True)
    CATEGORIES_PATH.write_text(
        json.dumps({"categories": cleaned}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return cleaned


def get_default_category() -> str:
    categories = get_categories()
    if DEFAULT_CATEGORY in categories:
        return DEFAULT_CATEGORY
    return categories[0]


CATEGORIES = get_categories()
