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

    def test_clean_email_body_removes_reply_headers_signature_and_unsupported_attachment_noise(self):
        body = """各位，请各部门认真学习，贯彻落实。


~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

丁晓斌

中国太平洋财产保险股份有限公司

营运中心上海分中心

电子邮箱：sodingxiaobin@cpic.com.cn

电话：021-33964125 18918503081



--------------------------------------------------------------------------------
----邮件原文----发件人："综合支持部" <sooffice@cpic.com.cn>收件人："丁晓斌" <sodingxiaobin@cpic.com.cn>发送时间：2026-04-09 13:23:25主题：集团总裁赵永刚在集团协同业务开门红总结会上的讲话各部门：

      附件为集团总裁赵永刚在集团协同业务开门红总结会上的讲话，请各部门认真学习，贯彻落实。

附件内容：

附件：情况通报.pdf
暂不支持读取此类型附件：application/pdf
"""

        cleaned = ai_service.clean_email_body_for_analysis(body)

        self.assertIn("各位，请各部门认真学习，贯彻落实。", cleaned)
        self.assertNotIn("电子邮箱", cleaned)
        self.assertNotIn("电话：", cleaned)
        self.assertNotIn("----邮件原文----", cleaned)
        self.assertNotIn("收件人：", cleaned)
        self.assertNotIn("暂不支持读取此类型附件", cleaned)

    def test_email_analysis_prompt_uses_cleaned_body(self):
        prompt = ai_service.build_email_analysis_prompt(
            subject="学习通知",
            body="请认真学习。\n\n~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n张三\n电话：123\n----邮件原文----发件人：a",
        )

        self.assertIn("请认真学习。", prompt)
        self.assertNotIn("电话：123", prompt)
        self.assertNotIn("----邮件原文----", prompt)


if __name__ == "__main__":
    unittest.main()
