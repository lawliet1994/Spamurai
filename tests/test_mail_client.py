import poplib
import tempfile
import unittest
from email.message import EmailMessage
from pathlib import Path
from unittest.mock import patch

from services import mail_client


def analysis_result():
    return {
        "category": "低优先级",
        "summary": "摘要",
        "priority": "低",
        "meeting_time": "",
        "meeting_location": "",
        "suggested_action": "",
    }


class LoginFailsPOP3:
    quit_called = False

    def __init__(self, host):
        self.host = host

    def user(self, username):
        return b"+OK"

    def pass_(self, password):
        raise poplib.error_proto("-ERR authentication failed")

    def quit(self):
        self.__class__.quit_called = True
        return b"+OK"


class MailClientTests(unittest.TestCase):
    def test_safe_filename_replaces_windows_invalid_characters(self):
        value = mail_client._safe_filename('??????_1776059397910.png')

        self.assertEqual(value, "_______1776059397910.png")

    def test_sync_emails_stops_when_pop3_login_fails(self):
        LoginFailsPOP3.quit_called = False

        with patch("services.mail_client.poplib.POP3", LoginFailsPOP3):
            with self.assertRaisesRegex(RuntimeError, "POP3 login failed"):
                mail_client.sync_emails(limit=20)

        self.assertTrue(LoginFailsPOP3.quit_called)

    def test_sync_emails_logs_out_before_ai_analysis(self):
        calls = []
        raw_message = (
            b"From: sender@example.com\r\n"
            b"Subject: Test subject\r\n"
            b"Date: Sun, 26 Apr 2026 09:00:00 +0800\r\n"
            b"\r\n"
            b"Test body"
        )

        class OneMessagePOP3:
            def __init__(self, host):
                self.host = host

            def user(self, username):
                calls.append("user")
                return b"+OK"

            def pass_(self, password):
                calls.append("pass")
                return b"+OK"

            def uidl(self):
                calls.append("uidl")
                return b"+OK", [b"1 unique-id-1"], 12

            def retr(self, num):
                calls.append("retr")
                return b"+OK", raw_message.splitlines(), len(raw_message)

            def quit(self):
                calls.append("quit")
                return b"+OK"

        def analyze_email(subject, body):
            calls.append("analyze")
            return analysis_result()

        def insert_email(data):
            calls.append("insert")

        with (
            patch("services.mail_client.poplib.POP3", OneMessagePOP3),
            patch("services.mail_client.analyze_email", analyze_email),
            patch("services.mail_client.insert_email", insert_email),
        ):
            self.assertEqual(mail_client.sync_emails(limit=1), 1)

        self.assertLess(calls.index("quit"), calls.index("analyze"))

    def test_sync_emails_skips_existing_messages_before_ai_analysis(self):
        calls = []
        raw_message = (
            b"From: sender@example.com\r\n"
            b"Subject: Test subject\r\n"
            b"Date: Sun, 26 Apr 2026 09:00:00 +0800\r\n"
            b"\r\n"
            b"Test body"
        )

        class TwoMessagePOP3:
            def __init__(self, host):
                self.host = host

            def user(self, username):
                return b"+OK"

            def pass_(self, password):
                return b"+OK"

            def uidl(self):
                return b"+OK", [b"1 existing-id", b"2 new-id"], 24

            def retr(self, num):
                return b"+OK", raw_message.splitlines(), len(raw_message)

            def quit(self):
                return b"+OK"

        def email_exists(uid):
            calls.append(("exists", uid))
            return uid == "existing-id"

        def analyze_email(subject, body):
            calls.append("analyze")
            return analysis_result()

        def insert_email(data):
            calls.append(("insert", data["uid"]))

        with (
            patch("services.mail_client.poplib.POP3", TwoMessagePOP3),
            patch("services.mail_client.email_exists", email_exists),
            patch("services.mail_client.analyze_email", analyze_email),
            patch("services.mail_client.insert_email", insert_email),
        ):
            self.assertEqual(mail_client.sync_emails(limit=2), 1)

        self.assertEqual(calls.count("analyze"), 1)
        self.assertIn(("insert", "new-id"), calls)
        self.assertNotIn(("insert", "existing-id"), calls)

    def test_sync_emails_includes_readable_attachment_text_in_ai_analysis(self):
        calls = []
        message = EmailMessage()
        message["From"] = "sender@example.com"
        message["Subject"] = "Report"
        message["Date"] = "Sun, 26 Apr 2026 09:00:00 +0800"
        message.set_content("请查看附件。")
        message.add_attachment(
            "附件结论：预算超支，需要本周处理。",
            subtype="plain",
            filename="report.txt",
        )
        raw_message = message.as_bytes()

        class OneMessagePOP3:
            def __init__(self, host):
                self.host = host

            def user(self, username):
                return b"+OK"

            def pass_(self, password):
                return b"+OK"

            def uidl(self):
                return b"+OK", [b"1 unique-id-1"], 12

            def retr(self, num):
                return b"+OK", raw_message.splitlines(), len(raw_message)

            def quit(self):
                return b"+OK"

        def analyze_email(subject, body):
            calls.append(("analyze", subject, body))
            return analysis_result()

        with (
            patch("services.mail_client.poplib.POP3", OneMessagePOP3),
            patch("services.mail_client.email_exists", return_value=False),
            patch("services.mail_client.analyze_email", analyze_email),
            patch("services.mail_client.insert_email"),
            patch("services.mail_client.insert_email_attachments"),
        ):
            self.assertEqual(mail_client.sync_emails(limit=1), 1)

        analyzed_body = calls[0][2]
        self.assertIn("附件：report.txt", analyzed_body)
        self.assertIn("附件结论：预算超支，需要本周处理。", analyzed_body)

    def test_sync_emails_saves_original_attachments_for_download(self):
        saved = []
        message = EmailMessage()
        message["From"] = "sender@example.com"
        message["Subject"] = "Report"
        message["Date"] = "Sun, 26 Apr 2026 09:00:00 +0800"
        message.set_content("请查看附件。")
        message.add_attachment(
            b"binary report content",
            maintype="application",
            subtype="pdf",
            filename="report.pdf",
        )
        raw_message = message.as_bytes()

        class OneMessagePOP3:
            def __init__(self, host):
                self.host = host

            def user(self, username):
                return b"+OK"

            def pass_(self, password):
                return b"+OK"

            def uidl(self):
                return b"+OK", [b"1 unique-id-1"], 12

            def retr(self, num):
                return b"+OK", raw_message.splitlines(), len(raw_message)

            def quit(self):
                return b"+OK"

        def insert_email_attachments(email_uid, attachments):
            saved.append((email_uid, attachments))

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch("services.mail_client.poplib.POP3", OneMessagePOP3),
                patch("services.mail_client.email_exists", return_value=False),
                patch("services.mail_client.analyze_email", return_value=analysis_result()),
                patch("services.mail_client.insert_email"),
                patch("services.mail_client.insert_email_attachments", insert_email_attachments),
                patch("services.mail_client.ATTACHMENT_DIR", Path(tmpdir)),
            ):
                self.assertEqual(mail_client.sync_emails(limit=1), 1)

            stored = saved[0][1][0]
            stored_path = Path(stored["path"])

        self.assertEqual(saved[0][0], "unique-id-1")
        self.assertEqual(stored["filename"], "report.pdf")
        self.assertEqual(stored["content_type"], "application/pdf")
        self.assertEqual(stored_path.name, "report.pdf")
        self.assertEqual(stored["size"], len(b"binary report content"))


if __name__ == "__main__":
    unittest.main()
