import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch

from services import ai_service


class AIServiceTests(unittest.TestCase):
    def test_email_analysis_prompt_includes_current_date_context(self):
        now = datetime(2026, 4, 26, 9, 30, tzinfo=ZoneInfo("Asia/Shanghai"))

        prompt = ai_service.build_email_analysis_prompt(
            subject="周五开会",
            body="我们周五下午三点开会。",
            now=now,
        )

        self.assertIn("当前日期：2026-04-26", prompt)
        self.assertIn("当前星期：星期日", prompt)
        self.assertIn("当前时区：Asia/Shanghai", prompt)
        self.assertIn("周五", prompt)
        self.assertIn("周五/星期五：2026-05-01", prompt)
        self.assertIn("基于当前日期解析", prompt)
        self.assertIn("不得输出早于当前日期的 meeting_time", prompt)

    def test_email_analysis_prompt_uses_configured_categories(self):
        with patch("services.ai_service.get_categories", return_value=["客户升级", "无需处理"]):
            prompt = ai_service.build_email_analysis_prompt(
                subject="客户反馈",
                body="客户需要尽快处理。",
            )

        self.assertIn("客户升级、无需处理", prompt)
        self.assertNotIn("今日要务、会议邀约", prompt)

    def test_email_analysis_prompt_asks_to_detect_phishing_risk(self):
        prompt = ai_service.build_email_analysis_prompt(
            subject="账号异常",
            body="请立即点击链接重新登录。",
        )

        self.assertIn("钓鱼邮件", prompt)
        self.assertIn("可疑链接", prompt)
        self.assertIn("风险警示", prompt)

    def test_analyze_email_falls_back_when_category_is_not_configured(self):
        with (
            patch("services.ai_service.get_categories", return_value=["客户升级", "无需处理"]),
            patch("services.ai_service.ask_ollama", return_value='{"category":"系统通知","priority":"中","summary":"摘要"}'),
        ):
            result = ai_service.analyze_email("主题", "正文")

        self.assertEqual(result["category"], "客户升级")
        self.assertEqual(result["priority"], "中")


if __name__ == "__main__":
    unittest.main()
