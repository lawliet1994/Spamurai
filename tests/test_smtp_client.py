import unittest
from unittest.mock import patch

from services import smtp_client


class FakeSMTP:
    instances = []

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.login_args = None
        self.messages = []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def login(self, user, password):
        self.login_args = (user, password)

    def send_message(self, message):
        self.messages.append(message)


class SMTPClientTests(unittest.TestCase):
    def test_build_reply_message_uses_sender_address_and_reply_subject(self):
        with patch("services.smtp_client.SMTP_FROM", "me@example.com"):
            message = smtp_client.build_reply_message(
                {
                    "sender": "Alice <alice@example.com>",
                    "subject": "项目进展",
                },
                "收到，谢谢。",
            )

        self.assertEqual(message["From"], "me@example.com")
        self.assertEqual(message["To"], "alice@example.com")
        self.assertEqual(message["Subject"], "Re: 项目进展")
        self.assertEqual(message.get_content().strip(), "收到，谢谢。")

    def test_send_reply_uses_configured_smtp_server(self):
        FakeSMTP.instances = []
        with (
            patch("services.smtp_client.SMTP_HOST", "smtp.test.local"),
            patch("services.smtp_client.SMTP_PORT", 465),
            patch("services.smtp_client.SMTP_USER", "me@example.com"),
            patch("services.smtp_client.SMTP_PASS", "secret"),
            patch("services.smtp_client.SMTP_FROM", "me@example.com"),
            patch("services.smtp_client.smtplib.SMTP_SSL", FakeSMTP),
        ):
            result = smtp_client.send_reply(
                {
                    "sender": "sender@example.com",
                    "subject": "Re: 已有回复前缀",
                },
                "正文",
            )

        smtp = FakeSMTP.instances[0]
        self.assertEqual((smtp.host, smtp.port), ("smtp.test.local", 465))
        self.assertEqual(smtp.login_args, ("me@example.com", "secret"))
        self.assertEqual(smtp.messages[0]["Subject"], "Re: 已有回复前缀")
        self.assertEqual(result, {"to": "sender@example.com", "subject": "Re: 已有回复前缀"})

    def test_send_reply_requires_smtp_config(self):
        with patch("services.smtp_client.SMTP_HOST", ""):
            with self.assertRaisesRegex(RuntimeError, "SMTP_HOST"):
                smtp_client.send_reply({"sender": "sender@example.com"}, "正文")


if __name__ == "__main__":
    unittest.main()
