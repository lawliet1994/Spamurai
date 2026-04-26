import imaplib
import unittest
from email.message import EmailMessage
from unittest.mock import patch

from services import mail_client


class SelectFailsIMAP:
    searched = False
    logged_out = False

    def __init__(self, host):
        self.host = host

    def login(self, user, password):
        return "OK", [b"LOGIN completed"]

    def _simple_command(self, command, payload):
        return "OK", [b"ID completed"]

    def select(self, mailbox):
        return "NO", [b"Mailbox does not exist"]

    def search(self, charset, criterion):
        self.__class__.searched = True
        raise imaplib.IMAP4.error(
            "command SEARCH illegal in state AUTH, only allowed in states SELECTED"
        )

    def logout(self):
        self.__class__.logged_out = True
        return "BYE", [b"LOGOUT completed"]


class MailClientTests(unittest.TestCase):
    def test_sync_emails_stops_when_mailbox_select_fails(self):
        SelectFailsIMAP.searched = False
        SelectFailsIMAP.logged_out = False

        with patch("services.mail_client.imaplib.IMAP4_SSL", SelectFailsIMAP):
            with self.assertRaisesRegex(RuntimeError, "IMAP select failed"):
                mail_client.sync_emails(limit=20)

        self.assertFalse(SelectFailsIMAP.searched)
        self.assertTrue(SelectFailsIMAP.logged_out)

    def test_sync_emails_sends_imap_id_before_select(self):
        calls = []

        class RecordsIMAP(SelectFailsIMAP):
            def login(self, user, password):
                calls.append("login")
                return "OK", [b"LOGIN completed"]

            def _simple_command(self, command, payload):
                calls.append((command, payload))
                return "OK", [b"ID completed"]

            def select(self, mailbox):
                calls.append("select")
                return "NO", [b"Mailbox does not exist"]

        with patch("services.mail_client.imaplib.IMAP4_SSL", RecordsIMAP):
            with self.assertRaisesRegex(RuntimeError, "IMAP select failed"):
                mail_client.sync_emails(limit=20)

        self.assertEqual(calls[0], "login")
        self.assertEqual(calls[1][0], "ID")
        self.assertIn('"MailAssistant"', calls[1][1])
        self.assertEqual(calls[2], "select")

    def test_sync_emails_continues_when_imap_id_is_unsupported(self):
        calls = []

        class UnsupportedIDIMAP(SelectFailsIMAP):
            def _simple_command(self, command, payload):
                calls.append((command, payload))
                raise imaplib.IMAP4.error("ID unsupported")

            def select(self, mailbox):
                calls.append("select")
                return "NO", [b"Mailbox does not exist"]

        with patch("services.mail_client.imaplib.IMAP4_SSL", UnsupportedIDIMAP):
            with self.assertRaisesRegex(RuntimeError, "IMAP select failed"):
                mail_client.sync_emails(limit=20)

        self.assertEqual(calls[0][0], "ID")
        self.assertEqual(calls[1], "select")

    def test_sync_emails_logs_out_before_ai_analysis(self):
        calls = []
        raw_message = (
            b"From: sender@example.com\r\n"
            b"Subject: Test subject\r\n"
            b"Date: Sun, 26 Apr 2026 09:00:00 +0800\r\n"
            b"\r\n"
            b"Test body"
        )

        class OneMessageIMAP:
            def __init__(self, host):
                self.host = host

            def login(self, user, password):
                calls.append("login")
                return "OK", [b"LOGIN completed"]

            def _simple_command(self, command, payload):
                calls.append("id")
                return "OK", [b"ID completed"]

            def select(self, mailbox):
                calls.append("select")
                return "OK", [b"1"]

            def search(self, charset, criterion):
                calls.append("search")
                return "OK", [b"1"]

            def fetch(self, num, query):
                calls.append("fetch")
                return "OK", [(b"1 (RFC822 {1}", raw_message)]

            def logout(self):
                calls.append("logout")
                return "BYE", [b"LOGOUT completed"]

        def analyze_email(subject, body):
            calls.append("analyze")
            return {
                "category": "低优先级",
                "summary": "摘要",
                "priority": "低",
                "meeting_time": "",
                "meeting_location": "",
                "suggested_action": "",
            }

        def insert_email(data):
            calls.append("insert")

        with (
            patch("services.mail_client.imaplib.IMAP4_SSL", OneMessageIMAP),
            patch("services.mail_client.analyze_email", analyze_email),
            patch("services.mail_client.insert_email", insert_email),
        ):
            self.assertEqual(mail_client.sync_emails(limit=1), 1)

        self.assertLess(calls.index("logout"), calls.index("analyze"))

    def test_sync_emails_skips_existing_messages_before_ai_analysis(self):
        calls = []
        raw_message = (
            b"From: sender@example.com\r\n"
            b"Subject: Test subject\r\n"
            b"Date: Sun, 26 Apr 2026 09:00:00 +0800\r\n"
            b"\r\n"
            b"Test body"
        )

        class TwoMessageIMAP:
            def __init__(self, host):
                self.host = host

            def login(self, user, password):
                return "OK", [b"LOGIN completed"]

            def _simple_command(self, command, payload):
                return "OK", [b"ID completed"]

            def select(self, mailbox):
                return "OK", [b"2"]

            def search(self, charset, criterion):
                return "OK", [b"1 2"]

            def fetch(self, num, query):
                return "OK", [(b"1 (RFC822 {1}", raw_message)]

            def logout(self):
                return "BYE", [b"LOGOUT completed"]

        def email_exists(uid):
            calls.append(("exists", uid))
            return uid == "1"

        def analyze_email(subject, body):
            calls.append("analyze")
            return {
                "category": "低优先级",
                "summary": "摘要",
                "priority": "低",
                "meeting_time": "",
                "meeting_location": "",
                "suggested_action": "",
            }

        def insert_email(data):
            calls.append(("insert", data["uid"]))

        with (
            patch("services.mail_client.imaplib.IMAP4_SSL", TwoMessageIMAP),
            patch("services.mail_client.email_exists", email_exists),
            patch("services.mail_client.analyze_email", analyze_email),
            patch("services.mail_client.insert_email", insert_email),
        ):
            self.assertEqual(mail_client.sync_emails(limit=2), 1)

        self.assertEqual(calls.count("analyze"), 1)
        self.assertIn(("insert", "2"), calls)
        self.assertNotIn(("insert", "1"), calls)

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

        class OneMessageIMAP:
            def __init__(self, host):
                self.host = host

            def login(self, user, password):
                return "OK", [b"LOGIN completed"]

            def _simple_command(self, command, payload):
                return "OK", [b"ID completed"]

            def select(self, mailbox):
                return "OK", [b"1"]

            def search(self, charset, criterion):
                return "OK", [b"1"]

            def fetch(self, num, query):
                return "OK", [(b"1 (RFC822 {1}", raw_message)]

            def logout(self):
                return "BYE", [b"LOGOUT completed"]

        def analyze_email(subject, body):
            calls.append(("analyze", subject, body))
            return {
                "category": "低优先级",
                "summary": "摘要",
                "priority": "低",
                "meeting_time": "",
                "meeting_location": "",
                "suggested_action": "",
            }

        with (
            patch("services.mail_client.imaplib.IMAP4_SSL", OneMessageIMAP),
            patch("services.mail_client.email_exists", return_value=False),
            patch("services.mail_client.analyze_email", analyze_email),
            patch("services.mail_client.insert_email"),
        ):
            self.assertEqual(mail_client.sync_emails(limit=1), 1)

        analyzed_body = calls[0][2]
        self.assertIn("附件：report.txt", analyzed_body)
        self.assertIn("附件结论：预算超支，需要本周处理。", analyzed_body)


if __name__ == "__main__":
    unittest.main()
