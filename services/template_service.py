from config import TEMPLATE_DIR, get_categories


DEFAULT_TEMPLATES = {
    "今日要务": """您好，

邮件已收到。

该事项我会优先处理，并尽快反馈进展。

谢谢。
""",
    "会议邀约": """您好，

感谢通知。

我已收到会议安排，会议时间为：{{meeting_time}}。
如有会议材料或议程，请提前同步，方便我提前准备。

谢谢。
""",
    "待我回复": """您好，

邮件已收到。

关于您提到的事项，我会尽快确认并反馈。
如有更紧急的时间要求，也请您同步告知。

谢谢。
""",
    "系统通知": """您好，

通知已收到。

我会根据邮件内容完成相关确认或处理。

谢谢。
""",
    "账单票据": """您好，

票据/账单信息已收到。

我会核对金额、日期和相关信息，如有问题会及时反馈。

谢谢。
""",
    "项目进展": """您好，

项目进展已收到。

我会关注相关变化，并根据需要同步后续反馈。

谢谢。
""",
    "低优先级": """您好，

邮件已收到，感谢同步。

如后续需要我进一步处理，请再告知。

谢谢。
""",
    "风险警示": """您好，

我已关注到该异常或风险信息。

请协助确认以下内容：

1. 影响范围
2. 当前状态
3. 是否需要我方立即处理
4. 后续建议动作

谢谢。
""",
}


def init_templates():
    for category in get_categories():
        path = TEMPLATE_DIR / f"{category}.md"
        if not path.exists():
            path.write_text(DEFAULT_TEMPLATES.get(category, ""), encoding="utf-8")


def get_template(category: str) -> str:
    path = TEMPLATE_DIR / f"{category}.md"
    if not path.exists():
        return DEFAULT_TEMPLATES.get(category, "")
    return path.read_text(encoding="utf-8")


def save_template(category: str, content: str):
    if category not in get_categories():
        raise ValueError("非法分类")

    path = TEMPLATE_DIR / f"{category}.md"
    path.write_text(content, encoding="utf-8")


def render_template(template: str, email_data: dict) -> str:
    return (
        template
        .replace("{{subject}}", email_data.get("subject", "") or "")
        .replace("{{sender}}", email_data.get("sender", "") or "")
        .replace("{{summary}}", email_data.get("summary", "") or "")
        .replace("{{meeting_time}}", email_data.get("meeting_time", "") or "")
        .replace("{{meeting_location}}", email_data.get("meeting_location", "") or "")
    )
