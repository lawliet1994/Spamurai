import unittest
from unittest.mock import patch

import ui_pages


class FakeLabel:
    def __init__(self):
        self.text = ""
        self.class_names = []

    def classes(self, value):
        self.class_names.append(value)


class HomeBackgroundSyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_home_background_sync_updates_status_without_refresh(self):
        status = FakeLabel()
        timers = []

        async def fake_to_thread(func, **kwargs):
            return func(**kwargs)

        def fake_sync(limit):
            self.assertEqual(limit, 20)
            return 2, 1

        with (
            patch("ui_pages.asyncio.to_thread", fake_to_thread),
            patch("ui_pages.sync_and_analyze_today", fake_sync),
            patch("ui_pages.ui.timer", lambda *args, **kwargs: timers.append((args, kwargs))),
        ):
            await ui_pages.run_home_background_sync(status)

        self.assertEqual(status.text, "后台同步完成：新增 2 封，补分析 1 封")
        self.assertEqual(timers, [])


class MailStyleTests(unittest.TestCase):
    def test_mail_classes_reflect_read_state(self):
        unread = {"is_read": 0}
        read = {"is_read": 1}

        self.assertIn("mail-card-unread", ui_pages.mail_card_classes(unread))
        self.assertIn("font-bold", ui_pages.mail_subject_classes(unread))
        self.assertIn("mail-card-read", ui_pages.mail_card_classes(read))
        self.assertIn("font-medium text-gray-600", ui_pages.mail_subject_classes(read))

    def test_unread_counts_by_category_ignores_read_and_deleted_rows(self):
        rows = [
            {"category": "今日要务", "is_read": 0, "is_deleted": 0},
            {"category": "今日要务", "is_read": 1, "is_deleted": 0},
            {"category": "会议邀约", "is_read": 0, "is_deleted": 0},
            {"category": "会议邀约", "is_read": 0, "is_deleted": 1},
        ]

        total, counts = ui_pages.unread_counts_by_category(rows)

        self.assertEqual(total, 2)
        self.assertEqual(counts, {"今日要务": 1, "会议邀约": 1})

    def test_format_email_time_uses_local_datetime(self):
        value = ui_pages.format_email_time("Sun, 26 Apr 2026 09:30:00 +0800")

        self.assertEqual(value, "2026-04-26 09:30")

    def test_format_email_time_falls_back_to_original_value(self):
        value = ui_pages.format_email_time("invalid date")

        self.assertEqual(value, "invalid date")

    def test_email_meta_text_excludes_summary(self):
        row = {
            "sender": "sender@example.com",
            "summary": "摘要内容",
            "received_at": "Sun, 26 Apr 2026 09:30:00 +0800",
        }

        value = ui_pages.email_meta_text(row)

        self.assertEqual(value, "sender@example.com · 2026-04-26 09:30")
        self.assertNotIn("摘要内容", value)


if __name__ == "__main__":
    unittest.main()
