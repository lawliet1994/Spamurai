from nicegui import ui

from config import NICEGUI_STORAGE_SECRET
from database import init_db
from services.template_service import init_templates

import api
import ui_pages


def startup():
    init_db()
    init_templates()


startup()

ui.run(
    title="AI 邮箱助手",
    host="0.0.0.0",
    port=8080,
    storage_secret=NICEGUI_STORAGE_SECRET,
    # reload=False,
)
