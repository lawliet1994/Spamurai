import asyncio
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

from fastapi import Request
from nicegui import ui

from config import get_categories, save_categories
from database import (
    list_emails,
    list_filtered_emails,
    list_emails_on_date,
    list_meeting_emails,
    list_meeting_emails_on_date,
    list_emails_needing_analysis_on_date,
    list_email_attachments,
    get_email,
    update_email_status,
    update_email_analysis,
)
from services.mail_client import sync_emails
from services.smtp_client import send_reply
from services.template_service import get_template, init_templates, save_template, render_template
from services.ai_service import analyze_email, suggest_template


LOCAL_TIMEZONE = ZoneInfo("Asia/Shanghai")


def apply_style():
    ui.colors(
        primary="#1f1a14",
        secondary="#b99b5f",
        accent="#8a6d3b",
        positive="#5f6f52",
        warning="#b99b5f",
        negative="#7f1d1d",
        info="#8a6d3b",
    )
    ui.add_head_html("""
    <script>
    (function () {
        if (localStorage.getItem("mailAssistantTheme") === "dark") {
            document.documentElement.dataset.theme = "dark";
        }
    })();
    </script>
    <style>
    :root {
        --ma-ink: #1f1a14;
        --ma-ink-soft: #3b3125;
        --ma-gold: #b99b5f;
        --ma-gold-deep: #8a6d3b;
        --ma-gold-soft: #efe4c8;
        --ma-paper: #fffdf8;
        --ma-panel: #f7f3ea;
        --ma-line: #e6dcc8;
        --ma-danger: #7f1d1d;
        --ma-text: #2f2f2f;
        --ma-text-muted: #7d705e;
        --ma-side: linear-gradient(180deg, #f2ead8 0%, #ebe0c8 100%);
        --ma-side-border: #dfd1b8;
        --ma-read-paper: #fbf8f0;
        --ma-card-shadow: rgba(80, 60, 30, 0.06);
    }

    :root[data-theme="dark"] {
        --ma-ink: #f8edda;
        --ma-ink-soft: #e2c27d;
        --ma-gold: #f0c86a;
        --ma-gold-deep: #f2d486;
        --ma-gold-soft: #332414;
        --ma-paper: #1f1a15;
        --ma-panel: #11100f;
        --ma-line: #5b4a36;
        --ma-danger: #9f3030;
        --ma-text: #f4eee3;
        --ma-text-muted: #d2c3ab;
        --ma-side: linear-gradient(180deg, #211912 0%, #17130f 100%);
        --ma-side-border: #5b4a36;
        --ma-read-paper: #181411;
        --ma-card-shadow: rgba(0, 0, 0, 0.34);
    }

    body {
        background: var(--ma-panel);
        color: var(--ma-text);
        font-family: "Inter", "Microsoft YaHei", sans-serif;
    }

    .side {
        background: var(--ma-side);
        border-right: 1px solid var(--ma-side-border);
        box-shadow: inset -1px 0 0 rgba(255, 253, 248, 0.5);
    }

    .side-title {
        color: var(--ma-ink);
        font-weight: 800;
        letter-spacing: 0;
    }

    .side-caption {
        color: var(--ma-text-muted);
    }

    .q-btn.category-nav-button {
        width: 100%;
        min-height: 40px;
        justify-content: flex-start;
        border-radius: 8px;
        color: var(--ma-ink) !important;
        background: transparent !important;
        border: 1px solid transparent;
        box-shadow: none !important;
    }

    .q-btn.category-nav-button:hover {
        background: rgba(255, 253, 248, 0.58) !important;
        border-color: rgba(185, 155, 95, 0.28);
    }

    .q-btn.category-nav-button.category-nav-button-active {
        background: linear-gradient(135deg, var(--ma-ink), var(--ma-ink-soft)) !important;
        color: var(--ma-gold-soft) !important;
        border-color: rgba(185, 155, 95, 0.5);
    }

    .q-btn.category-nav-button.category-nav-button-active .q-icon,
    .q-btn.category-nav-button.category-nav-button-active .q-btn__content,
    .q-btn.category-nav-button.category-nav-button-active .block {
        color: var(--ma-gold) !important;
    }

    .unread-count-badge {
        background: var(--ma-paper) !important;
        color: var(--ma-ink) !important;
        border: 1px solid rgba(31, 26, 20, 0.18);
        font-weight: 700;
        min-width: 22px;
    }

    .q-btn.category-nav-button .unread-count-badge,
    .q-btn.category-nav-button .unread-count-badge .block,
    .q-btn.category-nav-button.category-nav-button-active .unread-count-badge,
    .q-btn.category-nav-button.category-nav-button-active .unread-count-badge .block {
        background: var(--ma-paper) !important;
        color: var(--ma-ink) !important;
    }

    .category-nav-item {
        width: 100%;
        min-height: 40px;
        padding: 0 10px;
        border-radius: 8px;
        color: var(--ma-ink);
        border: 1px solid transparent;
        cursor: pointer;
    }

    .category-nav-item:hover {
        background: rgba(255, 253, 248, 0.58);
        border-color: rgba(185, 155, 95, 0.28);
    }

    .category-nav-item-active {
        background: linear-gradient(135deg, var(--ma-ink), var(--ma-ink-soft));
        color: var(--ma-gold-soft);
        border-color: rgba(185, 155, 95, 0.5);
    }

    .category-nav-item-active .category-nav-icon,
    .category-nav-item-active .category-nav-label {
        color: var(--ma-gold);
    }

    .q-badge.unread-count-badge,
    .q-badge.unread-count-badge.bg-primary,
    .q-badge.unread-count-badge .block {
        background: var(--ma-paper) !important;
        color: var(--ma-ink) !important;
    }

    .panel {
        background: var(--ma-paper);
        border: 1px solid var(--ma-line);
        border-radius: 18px;
        box-shadow: 0 8px 24px var(--ma-card-shadow);
    }

    .gold-title {
        color: var(--ma-gold-deep);
        font-weight: 700;
    }

    .brand-word {
        color: var(--ma-ink);
        font-weight: 900;
        letter-spacing: 0;
        line-height: 1;
        text-shadow:
            0.35px 0 0 var(--ma-ink),
            -0.35px 0 0 var(--ma-ink),
            0 0.35px 0 var(--ma-ink);
    }

    .brand-ai {
        color: var(--ma-gold);
        font-weight: 900;
        letter-spacing: 0;
        line-height: 1;
        margin-left: 1px;
        text-shadow:
            0.4px 0 0 var(--ma-gold),
            -0.4px 0 0 var(--ma-gold),
            0 0.4px 0 var(--ma-gold),
            0 1px 0 rgba(31, 26, 20, 0.14);
    }

    .ai-analysis-button,
    .ai-analysis-button .q-icon {
        color: var(--ma-gold);
    }

    .q-btn.bg-primary,
    .q-btn.q-btn--standard.bg-primary {
        background: linear-gradient(135deg, var(--ma-ink), var(--ma-ink-soft)) !important;
        color: var(--ma-gold-soft) !important;
        border: 1px solid rgba(185, 155, 95, 0.38);
        box-shadow: 0 5px 16px rgba(31, 26, 20, 0.14);
    }

    .q-btn.q-btn--flat.text-primary,
    .q-btn.q-btn--outline.text-primary {
        color: var(--ma-ink) !important;
    }

    .q-btn.bg-negative {
        background: var(--ma-danger) !important;
        color: #fff8ed !important;
    }

    .q-field--focused .q-field__control {
        color: var(--ma-gold-deep) !important;
    }

    .q-field--focused .q-field__label {
        color: var(--ma-gold-deep) !important;
    }

    .elegant-badge {
        border: 1px solid rgba(185, 155, 95, 0.42);
        box-shadow: inset 0 0 0 1px rgba(255, 253, 248, 0.08);
        font-weight: 600;
    }

    .category-badge {
        background: var(--ma-ink) !important;
        color: var(--ma-gold-soft) !important;
    }

    .priority-badge-high {
        background: #b91c1c !important;
        color: #fff8ed !important;
    }

    .priority-badge-medium {
        background: #d6a300 !important;
        color: #2f2618 !important;
    }

    .priority-badge-low {
        background: #2f7d4f !important;
        color: #f4fff8 !important;
    }

    .priority-badge-default {
        background: #4b4338 !important;
        color: #f7ead0 !important;
    }

    .mail-card {
        background: var(--ma-paper);
        border: 1px solid var(--ma-line);
        border-radius: 18px;
        padding: 14px;
        margin-bottom: 12px;
        box-shadow: 0 8px 24px var(--ma-card-shadow);
    }

    .mail-card:hover {
        border-color: var(--ma-gold);
    }

    .mail-card-unread {
        border-left: 4px solid var(--ma-gold);
    }

    .mail-card-read {
        background: var(--ma-read-paper);
    }

    .app-header {
        background: var(--ma-paper);
        border-bottom: 1px solid var(--ma-line);
    }

    :root[data-theme="dark"] .text-gray-500,
    :root[data-theme="dark"] .text-gray-600,
    :root[data-theme="dark"] .text-gray-700 {
        color: var(--ma-text-muted) !important;
    }

    :root[data-theme="dark"] .text-amber-800,
    :root[data-theme="dark"] .text-amber-900 {
        color: #d6b875 !important;
    }

    :root[data-theme="dark"] .q-field__control,
    :root[data-theme="dark"] .q-field__native,
    :root[data-theme="dark"] .q-field__label,
    :root[data-theme="dark"] textarea {
        color: var(--ma-text) !important;
    }

    :root[data-theme="dark"] .q-field__control {
        background: #15120f;
    }

    :root[data-theme="dark"] .q-field--outlined .q-field__control::before {
        border-color: #6a563c !important;
    }

    :root[data-theme="dark"] .q-field--outlined .q-field__control:hover::before,
    :root[data-theme="dark"] .q-field--focused .q-field__control::after {
        border-color: var(--ma-gold) !important;
    }

    :root[data-theme="dark"] .q-separator {
        background: #5b4a36 !important;
    }

    :root[data-theme="dark"] .q-btn.q-btn--flat {
        color: var(--ma-text) !important;
    }

    :root[data-theme="dark"] .q-btn.q-btn--flat .q-icon {
        color: var(--ma-gold) !important;
    }

    :root[data-theme="dark"] .q-menu,
    :root[data-theme="dark"] .q-list {
        background: var(--ma-paper);
        color: var(--ma-text);
        border: 1px solid var(--ma-line);
    }

    :root[data-theme="dark"] .q-item {
        color: var(--ma-text);
    }
    </style>
    """)


def render_header(active: str, on_sync=None):
    def toggle_theme():
        ui.run_javascript("""
        const root = document.documentElement;
        const next = root.dataset.theme === "dark" ? "light" : "dark";
        if (next === "dark") {
            root.dataset.theme = "dark";
        } else {
            delete root.dataset.theme;
        }
        localStorage.setItem("mailAssistantTheme", next);
        """)

    with ui.row().classes("app-header w-full h-16 px-5 items-center justify-between no-wrap"):
        with ui.row().classes("w-40 shrink-0 items-baseline gap-0 no-wrap"):
            ui.label("Spamur").classes("text-2xl brand-word")
            ui.label("AI").classes("text-2xl brand-ai")
        with ui.row().classes("items-center justify-center gap-2 flex-1"):
            ui.button("今日首页", on_click=lambda: ui.navigate.to("/")).props(
                "flat" if active != "home" else "unelevated"
            )
            ui.button("邮件工作台", on_click=lambda: ui.navigate.to("/mail")).props(
                "flat" if active != "mail" else "unelevated"
            )
            ui.button("模板管理", on_click=lambda: ui.navigate.to("/templates")).props(
                "flat" if active != "templates" else "unelevated"
            )
        with ui.row().classes("w-44 shrink-0 justify-end items-center gap-1 no-wrap"):
            if on_sync:
                ui.button("同步并分析", on_click=on_sync)
            with ui.button(icon="dark_mode", on_click=toggle_theme).props("flat dense round"):
                ui.tooltip("切换暗黑模式")


DASHBOARD_FILTERS = {
    "all": "今日邮件",
    "high": "高优先级",
    "reply": "待回复",
    "meeting": "会议邀约",
    "risk": "风险警示",
    "unread": "未读",
}

def dashboard_filter_url(filter_key: str) -> str:
    return f"/mail?scope=today&filter={filter_key}"


def render_priority_badge(priority: str | None):
    colors = {
        "高": "red",
        "中": "yellow",
        "低": "green",
    }
    ui.badge(priority or "未定", color=colors.get(priority or "", "grey")).classes("elegant-badge")


def render_category_badge(category: str | None):
    ui.badge(category or "未分类").classes("elegant-badge category-badge")


def unread_counts_by_category(rows: list[dict]) -> tuple[int, dict[str, int]]:
    counts = {}
    total = 0

    for row in rows:
        if row.get("is_read") or row.get("is_deleted"):
            continue

        total += 1
        category = row.get("category") or "未分类"
        counts[category] = counts.get(category, 0) + 1

    return total, counts


def format_email_time(value: str | None) -> str:
    if not value:
        return ""

    try:
        received_at = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError, AttributeError):
        return value

    if received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=LOCAL_TIMEZONE)

    return received_at.astimezone(LOCAL_TIMEZONE).strftime("%Y-%m-%d %H:%M")


def render_sender_summary(row: dict, on_click=None):
    sender = row.get("sender") or "未知发件人"
    summary = row.get("summary") or "无摘要"
    received_at = format_email_time(row.get("received_at"))
    time_part = f" · {received_at}" if received_at else ""
    tone_class = "text-gray-500" if row.get("is_read") else "text-gray-700"
    label = ui.label(f"{sender}{time_part} · {summary}").classes(f"text-sm {tone_class} truncate w-full")
    if on_click:
        label.classes("cursor-pointer")
        label.on("click", lambda: on_click(row))
    return label


def render_clickable_label(text: str, classes: str, row: dict, on_click=None):
    label = ui.label(text).classes(classes)
    if on_click:
        label.classes("cursor-pointer")
        label.on("click", lambda: on_click(row))
    return label


def stop_card_click(element):
    element.on("click", js_handler="(event) => event.stopPropagation()")
    return element


def mail_card_classes(row: dict, clickable: bool = False) -> str:
    read_class = "mail-card-read" if row.get("is_read") else "mail-card-unread"
    cursor_class = "cursor-pointer" if clickable else ""
    return f"mail-card {read_class} w-full {cursor_class}".strip()


def mail_subject_classes(row: dict) -> str:
    weight_class = "font-medium text-gray-600" if row.get("is_read") else "font-bold"
    return f"text-lg {weight_class} flex-1 min-w-0 truncate cursor-pointer"


def analyze_rows(rows):
    analyzed = 0
    for row in rows:
        analysis = analyze_email(row["subject"] or "", row["body"] or "")
        update_email_analysis(row["id"], analysis)
        analyzed += 1
    return analyzed


def sync_and_analyze_today(limit=20):
    synced = sync_emails(limit=limit)
    rows = list_emails_needing_analysis_on_date()
    analyzed = analyze_rows(rows)
    return synced, analyzed


async def run_home_background_sync(sync_status):
    sync_status.text = "已触发后台同步和分析..."
    try:
        count, analyzed = await asyncio.to_thread(sync_and_analyze_today, limit=20)
    except Exception as exc:
        sync_status.text = f"后台同步或分析失败：{exc}"
        sync_status.classes("text-red-700")
        return

    sync_status.text = f"后台同步完成：新增 {count} 封，补分析 {analyzed} 封"


@ui.page("/")
async def home_page():
    apply_style()

    async def do_sync():
        ui.notify("开始同步并补齐今日 AI 分析")
        try:
            count, analyzed = await asyncio.to_thread(sync_and_analyze_today, limit=20)
        except Exception as exc:
            ui.notify(f"同步或分析失败：{exc}", type="negative")
            return

        ui.notify(f"同步完成：新增 {count} 封，补分析 {analyzed} 封")
        ui.navigate.reload()

    render_header("home", do_sync)
    sync_status = ui.label("已触发后台同步和分析...").classes("px-5 py-2 text-sm text-gray-600")
    asyncio.create_task(run_home_background_sync(sync_status))

    with ui.row().classes("w-full h-[calc(100vh-6.5rem)] no-wrap"):
        today_rows = list_emails_on_date()
        high_rows = [row for row in today_rows if row.get("priority") == "高"]
        meeting_rows = list_meeting_emails_on_date()
        meeting_timeline_rows = [row for row in meeting_rows if row.get("meeting_time")]
        reply_rows = [row for row in today_rows if row.get("category") == "待我回复"]
        risk_rows = [row for row in today_rows if row.get("category") == "风险警示"]
        unread_rows = [row for row in today_rows if not row.get("is_read")]
        focus_rows = [
            row for row in today_rows
            if row in high_rows or row in reply_rows or row in risk_rows or row in meeting_rows
        ][:8]

        category_counts = {}
        for row in today_rows:
            category = row.get("category") or "未分类"
            category_counts[category] = category_counts.get(category, 0) + 1

        with ui.column().classes("flex-1 h-full p-4 overflow-auto"):
            ui.label("今日邮件简报").classes("text-2xl gold-title")
            ui.label("领导每日概览").classes("text-sm text-gray-500 mb-3")

            with ui.row().classes("w-full gap-3"):
                for title, value, filter_key in [
                    ("今日邮件", len(today_rows), "all"),
                    ("高优先级", len(high_rows), "high"),
                    ("待回复", len(reply_rows), "reply"),
                    ("会议邀约", len(meeting_rows), "meeting"),
                    ("风险警示", len(risk_rows), "risk"),
                    ("未读", len(unread_rows), "unread"),
                ]:
                    with ui.card().classes("panel min-w-[130px] p-3 cursor-pointer").on(
                        "click",
                        lambda _, key=filter_key: ui.navigate.to(dashboard_filter_url(key)),
                    ):
                        ui.label(str(value)).classes("text-3xl gold-title")
                        ui.label(title).classes("text-sm text-gray-600")

            with ui.card().classes("panel w-full p-4 mt-4"):
                if today_rows:
                    summary = (
                        f"今天共收到 {len(today_rows)} 封邮件，"
                        f"其中 {len(high_rows)} 封高优先级，{len(reply_rows)} 封建议回复，"
                        f"{len(meeting_rows)} 封会议相关，{len(risk_rows)} 封风险警示。"
                    )
                else:
                    summary = "今天暂未同步到邮件。"
                ui.label(summary).classes("text-base")

            ui.label("今日重点").classes("text-xl gold-title mt-5")
            if focus_rows:
                for row in focus_rows:
                    with ui.card().classes(mail_card_classes(row)):
                        with ui.row().classes("items-center justify-between w-full"):
                            ui.label(row["subject"] or "无主题").classes(mail_subject_classes(row))
                            with ui.row():
                                render_category_badge(row.get("category"))
                                render_priority_badge(row.get("priority"))
                        render_sender_summary(row)
                        if row.get("suggested_action"):
                            ui.label(f"建议：{row['suggested_action']}").classes("text-sm text-amber-900")
            else:
                ui.label("暂无需要重点关注的邮件。").classes("text-sm text-gray-500")

            ui.label("分类分布").classes("text-xl gold-title mt-5")
            with ui.row().classes("gap-2"):
                for category, count in sorted(category_counts.items(), key=lambda item: item[1], reverse=True):
                    render_category_badge(f"{category} {count}")

        with ui.column().classes("w-[380px] h-full p-4 overflow-auto"):
            ui.label("会议时间线").classes("text-xl gold-title")
            if meeting_timeline_rows:
                for row in meeting_timeline_rows:
                    with ui.card().classes("panel w-full p-3 mb-2"):
                        ui.label(row["subject"] or "会议").classes("font-bold")
                        ui.label(f"时间：{row['meeting_time']}").classes("text-sm")
                        if row.get("meeting_location"):
                            ui.label(f"地点：{row['meeting_location']}").classes("text-sm")
            else:
                ui.label("今天暂无会议邀约。").classes("text-sm text-gray-500")

            ui.separator().classes("my-4")
            ui.label("风险与异常").classes("text-xl gold-title")
            if risk_rows:
                for row in risk_rows[:5]:
                    with ui.card().classes("panel w-full p-3 mb-2"):
                        ui.label(row["subject"] or "风险邮件").classes("font-bold")
                        ui.label(row["summary"]).classes("text-sm")
            else:
                ui.label("暂未发现风险警示邮件。").classes("text-sm text-gray-500")


@ui.page("/mail")
def index_page(request: Request):
    apply_style()
    categories = get_categories()
    initial_scope = request.query_params.get("scope")
    initial_filter = request.query_params.get("filter")
    if initial_filter not in DASHBOARD_FILTERS:
        initial_scope = None
        initial_filter = None

    selected_category = {"value": None}
    selected_scope = {"value": initial_scope if initial_scope == "today" else None}
    selected_filter = {"value": initial_filter}
    selected_email = {"value": None}
    selected_template_category = {"value": None}

    async def do_sync():
        ui.notify("开始同步并补齐今日 AI 分析")
        try:
            count, analyzed = await asyncio.to_thread(sync_and_analyze_today, limit=20)
        except Exception as exc:
            ui.notify(f"同步或分析失败：{exc}", type="negative")
            return

        ui.notify(f"同步完成：新增 {count} 封，补分析 {analyzed} 封")
        render_email_list()
        render_meetings()

    render_header("mail", do_sync)

    with ui.row().classes("w-full h-[calc(100vh-4rem)] no-wrap"):
        with ui.column().classes("side w-64 h-full p-4 gap-1") as side_area:
            def choose_category(cat):
                selected_category["value"] = cat
                selected_scope["value"] = None
                selected_filter["value"] = None
                render_sidebar()
                render_email_list()

            def render_category_nav_button(label, category, icon, unread_count=0):
                is_active = (
                    selected_scope["value"] is None
                    and selected_filter["value"] is None
                    and selected_category["value"] == category
                )
                active_class = "category-nav-item-active" if is_active else ""
                with ui.row().classes(
                    f"category-nav-item {active_class} items-center justify-between no-wrap"
                ).on("click", lambda c=category: choose_category(c), args=[]):
                    with ui.row().classes("items-center gap-2 min-w-0 no-wrap"):
                        ui.icon(icon).classes("category-nav-icon shrink-0")
                        ui.label(label).classes("category-nav-label truncate")
                    if unread_count:
                        ui.badge(str(unread_count), color="white").classes("unread-count-badge shrink-0")

            def render_sidebar():
                total_unread, category_unread = unread_counts_by_category(list_emails())
                side_area.clear()
                with side_area:
                    ui.label("邮件分类").classes("side-title text-base px-2 mb-0")
                    ui.label("按 AI 分类快速筛选").classes("side-caption text-xs px-2 mb-3")
                    render_category_nav_button("全部邮件", None, "inbox", total_unread)
                    ui.separator().classes("my-3")

                    for cat in categories:
                        render_category_nav_button(cat, cat, "label", category_unread.get(cat, 0))

                    ui.space()

            render_sidebar()

        with ui.column().classes("flex-1 h-full p-4 overflow-auto"):
            page_title = ui.label("全部邮件").classes("text-xl gold-title mb-2")
            mail_area = ui.column().classes("w-full")

        with ui.column().classes("w-[440px] h-full p-4 overflow-auto"):
            with ui.column().classes("w-full") as reply_panel:
                reply_panel.visible = False
                ui.label("AI 回复助手").classes("text-xl gold-title")

                reply_subject = ui.label("请选择一封邮件").classes("text-sm text-gray-500 mb-2")
                reply_received_at = ui.label("").classes("text-xs text-gray-500 mb-2")

                body_viewer = ui.textarea(
                    label="邮件正文与附件",
                    placeholder="点击邮件后显示正文和可读取附件内容"
                ).classes("w-full").props("rows=8 outlined readonly")

                ui.label("附件").classes("text-sm font-medium text-gray-600")
                attachment_area = ui.column().classes("w-full gap-1 mb-2")

                reply_editor = ui.textarea(
                    label="回复草稿",
                    placeholder="点击邮件的“回复”后自动生成"
                ).classes("w-full").props("rows=9 outlined")

                async def send_current_reply():
                    row = selected_email["value"]
                    draft = reply_editor.value or ""
                    if not row:
                        ui.notify("请先选择一封邮件", type="warning")
                        return
                    if not draft.strip():
                        ui.notify("回复草稿不能为空", type="warning")
                        return

                    send_dialog.close()
                    try:
                        sent = await asyncio.to_thread(send_reply, row, draft)
                    except Exception as exc:
                        ui.notify(f"发送失败：{exc}", type="negative")
                        return

                    ui.notify(f"回复已发送给 {sent['to']}")

                with ui.dialog() as send_dialog, ui.card().classes("panel w-[420px] p-4"):
                    ui.label("确认发送回复").classes("text-lg gold-title")
                    send_confirm_text = ui.label("").classes("text-sm text-gray-600")
                    with ui.row().classes("justify-end w-full"):
                        ui.button("取消", on_click=send_dialog.close).props("flat")
                        ui.button("确认发送", on_click=send_current_reply)

                def confirm_send_reply():
                    row = selected_email["value"]
                    if not row:
                        ui.notify("请先选择一封邮件", type="warning")
                        return
                    send_confirm_text.text = (
                        f"将向 {row.get('sender') or '未知发件人'} 发送当前回复草稿。"
                    )
                    send_dialog.open()

                with ui.row().classes("justify-end w-full"):
                    ui.button("发送回复", on_click=confirm_send_reply)

                ui.separator().classes("my-4")

                ui.label("分类模板").classes("text-lg gold-title")

                template_editor = ui.textarea(
                    label="Markdown 模板",
                    placeholder="这里展示当前分类的 md 模板"
                ).classes("w-full").props("rows=9 outlined")

                def save_current_template():
                    category = selected_template_category["value"]
                    if not category:
                        ui.notify("请先选择一封邮件", type="warning")
                        return

                    save_template(category, template_editor.value or "")
                    ui.notify(f"已保存 {category} 模板")

                async def suggest_current_template():
                    row = selected_email["value"]
                    category = selected_template_category["value"]

                    if not row or not category:
                        ui.notify("请先选择一封邮件", type="warning")
                        return

                    content = await asyncio.to_thread(
                        suggest_template,
                        category=category,
                        current_template=template_editor.value or "",
                        sample_summary=row.get("summary", ""),
                    )

                    if content:
                        template_editor.value = content
                        ui.notify("AI 已生成优化模板，可检查后保存")

                with ui.row():
                    ui.button("保存模板", on_click=save_current_template)
                    ui.button("AI 优化模板", on_click=suggest_current_template)

            ui.separator().classes("my-4")

            ui.label("会议时间线").classes("text-lg gold-title")
            meeting_area = ui.column().classes("w-full")

    def open_reply(row):
        if not row.get("is_read"):
            update_email_status(row["id"], is_read=1)
            row = get_email(row["id"]) or row
            render_sidebar()
            render_email_list()

        reply_panel.visible = True
        selected_email["value"] = row
        category = row["category"]
        selected_template_category["value"] = category

        raw_template = get_template(category)
        draft = render_template(raw_template, row)

        reply_subject.text = f"回复：{row['subject'] or '无主题'}"
        received_at = format_email_time(row.get("received_at"))
        reply_received_at.text = f"接收时间：{received_at}" if received_at else ""
        body_viewer.value = row.get("body") or "无正文或附件内容"
        attachment_area.clear()
        attachments = list_email_attachments(row["id"])
        with attachment_area:
            if attachments:
                for attachment in attachments:
                    url = f"/api/emails/{row['id']}/attachments/{attachment['id']}"
                    with ui.row().classes("items-center justify-between w-full no-wrap"):
                        ui.label(attachment["filename"]).classes("text-sm truncate")
                        ui.button(icon="download",on_click=lambda u=url: ui.navigate.to(u)).props(f'flat dense round href="{url}"')
            else:
                ui.label("无附件").classes("text-xs text-gray-500")
        reply_editor.value = draft
        template_editor.value = raw_template

    def toggle_read(row):
        update_email_status(row["id"], is_read=0 if row.get("is_read") else 1)
        render_sidebar()
        render_email_list()

    def delete_mail(row):
        update_email_status(row["id"], is_deleted=1)
        render_email_list()
        render_meetings()

    async def analyze_mail(row):
        ui.notify("开始 AI 分析")
        try:
            analysis = await asyncio.to_thread(
                analyze_email,
                row["subject"] or "",
                row["body"] or "",
            )
            await asyncio.to_thread(update_email_analysis, row["id"], analysis)
        except Exception as exc:
            ui.notify(f"AI 分析失败：{exc}", type="negative")
            return

        selected_email["value"] = get_email(row["id"])
        ui.notify("AI 分析完成")
        render_email_list()
        render_meetings()

    def render_email_list():
        mail_area.clear()

        cat = selected_category["value"]
        scope = selected_scope["value"]
        filter_key = selected_filter["value"]
        if scope == "today" and filter_key:
            page_title.text = DASHBOARD_FILTERS.get(filter_key, "今日邮件")
        else:
            page_title.text = cat or "全部邮件"

        rows = list_filtered_emails(
            scope=scope,
            filter_key=filter_key,
            category=cat,
        )

        with mail_area:
            for row in rows:
                with ui.card().classes(mail_card_classes(row, clickable=True)).on(
                    "click",
                    lambda r=row: open_reply(r),
                    args=[],
                ):
                    with ui.row().classes("items-center justify-between w-full gap-2 no-wrap"):
                        ui.label(row["subject"] or "无主题").classes(
                            mail_subject_classes(row)
                        )
                        with ui.row().classes("items-center gap-1 no-wrap shrink-0"):
                            render_category_badge(row.get("category"))
                            render_priority_badge(row.get("priority"))
                            with stop_card_click(ui.button(icon="auto_awesome", on_click=lambda r=row: analyze_mail(r)).props("flat dense round").classes("ai-analysis-button")):
                                ui.tooltip("AI 分析")
                            with stop_card_click(ui.button(icon="reply", on_click=lambda r=row: open_reply(r)).props("flat dense round")):
                                ui.tooltip("回复")
                            read_icon = "mark_email_unread" if row.get("is_read") else "done"
                            read_tooltip = "标为未读" if row.get("is_read") else "已读"
                            with stop_card_click(ui.button(icon=read_icon, on_click=lambda r=row: toggle_read(r)).props("flat dense round")):
                                ui.tooltip(read_tooltip)
                            with stop_card_click(ui.button(icon="delete", color="negative", on_click=lambda r=row: delete_mail(r)).props("flat dense round")):
                                ui.tooltip("删除")

                    render_sender_summary(row)

                    if row["meeting_time"]:
                        ui.label(f"会议时间：{row['meeting_time']}").classes("text-sm text-amber-800")

                    if row["suggested_action"]:
                        ui.label(f"建议：{row['suggested_action']}").classes("text-sm text-amber-900")

    def render_meetings():
        meeting_area.clear()
        rows = list_meeting_emails()

        with meeting_area:
            for row in rows:
                if not row.get("meeting_time"):
                    continue

                with ui.card().classes("panel w-full p-3 mb-2"):
                    render_clickable_label(row["subject"] or "会议", "font-bold", row, open_reply)
                    render_clickable_label(f"时间：{row['meeting_time']}", "text-sm", row, open_reply)
                    if row.get("meeting_location"):
                        render_clickable_label(f"地点：{row['meeting_location']}", "text-sm", row, open_reply)
                    ui.button("生成回复", on_click=lambda r=row: open_reply(r)).classes("mt-2")

    render_email_list()
    render_meetings()


@ui.page("/templates")
def templates_page():
    apply_style()
    categories = get_categories()

    render_header("templates")

    with ui.column().classes("w-full h-[calc(100vh-4rem)] p-5 overflow-auto"):
        ui.label("回复模板管理").classes("text-2xl gold-title mb-4")

        ui.label("邮件分类").classes("text-lg gold-title")

        category_editor = ui.textarea(
            label="每行一个分类",
            value="\n".join(categories),
        ).classes("w-80").props("rows=8 outlined")

        def save_category_config():
            try:
                updated = save_categories(category_editor.value.splitlines())
                init_templates()
            except ValueError as exc:
                ui.notify(str(exc), type="negative")
                return

            selected.set_options(updated, value=updated[0])
            load()
            ui.notify("分类已保存，AI 分析会使用新的分类")

        ui.button("保存分类", on_click=save_category_config)

        ui.separator().classes("my-4")

        selected = ui.select(
            categories,
            value=categories[0],
            label="分类",
        ).classes("w-80")

        editor = ui.textarea(
            label="Markdown 模板",
        ).classes("w-full").props("rows=22 outlined")

        def load():
            editor.value = get_template(selected.value)

        def save():
            save_template(selected.value, editor.value or "")
            ui.notify("模板已保存")

        selected.on_value_change(lambda _: load())

        with ui.row():
            ui.button("保存模板", on_click=save)

        load()
