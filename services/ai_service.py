import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from config import DEFAULT_CATEGORY, OLLAMA_URL, OLLAMA_MODEL, get_categories


LOCAL_TIMEZONE = ZoneInfo("Asia/Shanghai")
WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
SHORT_WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def ask_ollama(prompt: str, json_mode=False) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "think": False,
    }

    if json_mode:
        payload["format"] = "json"

    resp = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()
    result = resp.json()
    response = result.get("response", "")
    print("OLLAMA response:")
    print(response)
    return response


def _future_weekday_mapping(now: datetime) -> str:
    lines = []
    today = now.date()

    for index, weekday in enumerate(WEEKDAYS):
        days_ahead = (index - now.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        date = today + timedelta(days=days_ahead)
        lines.append(f"{SHORT_WEEKDAYS[index]}/{weekday}：{date.isoformat()}")

    next_monday = today + timedelta(days=((0 - now.weekday()) % 7 or 7) + 7)
    lines.append(f"下周一/下星期一：{next_monday.isoformat()}")
    return "\n".join(lines)


def build_email_analysis_prompt(subject: str, body: str, now: datetime | None = None) -> str:
    now = now or datetime.now(LOCAL_TIMEZONE)
    if now.tzinfo is None:
        now = now.replace(tzinfo=LOCAL_TIMEZONE)

    timezone_name = getattr(now.tzinfo, "key", str(now.tzinfo))
    current_date = now.date().isoformat()
    current_weekday = WEEKDAYS[now.weekday()]
    weekday_mapping = _future_weekday_mapping(now)
    categories = get_categories()
    category_options = "、".join(categories)

    return f"""
你是一个企业邮箱秘书。请分析下面邮件，输出严格 JSON，不要解释。

当前日期：{current_date}
当前星期：{current_weekday}
当前时区：{timezone_name}

如果邮件中出现“今天、明天、后天、本周五、周五、下周一”等相对日期或星期表达，必须基于当前日期解析。
例如当前星期日时，“周五”通常指接下来最近的星期五，而不是过去的星期五。
如果邮件没有明确写“昨天、上周、已结束、过去”等过去语义，不得输出早于当前日期的 meeting_time。

未来最近星期映射：
{weekday_mapping}

分类只能从以下选择：
{category_options}

风险识别要求：
如果邮件疑似钓鱼邮件、诈骗或账号安全风险，必须提高优先级，并尽量归类为“风险警示”（如果该分类在可选分类中）。
重点识别：可疑链接或短链接、诱导重新登录、索要密码/验证码/银行卡信息、冒充领导/同事/供应商、异常付款或转账要求、制造紧急威胁或限时压力、可疑附件或宏文件、发件人与显示身份不一致。
这类邮件的 summary 要明确说明可疑点，suggested_action 要建议不要点击链接或附件，并通过官方渠道核验。

输出格式：
{{
  "category": "...",
  "priority": "高/中/低",
  "summary": "不超过80字的摘要",
  "need_reply": true,
  "meeting_time": "如果有会议时间，输出 ISO 格式或原文时间，否则为空",
  "meeting_location": "如果有地点、会议室、腾讯会议、Zoom、Teams链接则填写，否则为空",
  "suggested_action": "建议用户下一步做什么"
}}

邮件主题：
{subject}

邮件正文：
{body[:4000]}
"""


def analyze_email(subject: str, body: str) -> dict:
    prompt = build_email_analysis_prompt(subject, body)
    categories = get_categories()
    default_category = DEFAULT_CATEGORY if DEFAULT_CATEGORY in categories else categories[0]

    try:
        text = ask_ollama(prompt, json_mode=True)
        data = json.loads(text)
        category = data.get("category") or default_category
        if category not in categories:
            category = default_category

        return {
            "category": category,
            "priority": data.get("priority", "低"),
            "summary": data.get("summary", "无摘要"),
            "meeting_time": data.get("meeting_time", ""),
            "meeting_location": data.get("meeting_location", ""),
            "suggested_action": data.get("suggested_action", ""),
        }

    except Exception:
        return {
            "category": default_category,
            "priority": "低",
            "summary": "AI 分析失败，建议人工查看",
            "meeting_time": "",
            "meeting_location": "",
            "suggested_action": "打开原邮件确认内容",
        }


def suggest_template(category: str, current_template: str, sample_summary: str = "") -> str:
    prompt = f"""
你是企业邮箱助手，请优化下面这个邮件回复模板。

要求：
1. 正式、简洁、礼貌
2. 不过度承诺
3. 保留 Markdown 格式
4. 可以使用变量：
   - {{{{subject}}}}
   - {{{{sender}}}}
   - {{{{summary}}}}
   - {{{{meeting_time}}}}
   - {{{{meeting_location}}}}
5. 只输出优化后的模板，不要解释

邮件分类：
{category}

当前模板：
{current_template}

样例邮件摘要：
{sample_summary}
"""
    return ask_ollama(prompt).strip()
