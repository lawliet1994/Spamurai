import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import database


def sample_email(uid, received_at, priority):
    return {
        "uid": uid,
        "sender": "sender@example.com",
        "subject": uid,
        "body": "body",
        "received_at": received_at,
        "category": "低优先级",
        "summary": "summary",
        "priority": priority,
    }


def failed_email(uid, received_at):
    data = sample_email(uid, received_at, "低")
    data["summary"] = "AI 分析失败，建议人工查看"
    return data


def meeting_email(uid, received_at, category="会议邀约"):
    data = sample_email(uid, received_at, "中")
    data["category"] = category
    data["meeting_time"] = "2026-04-26 15:00"
    data["meeting_location"] = "腾讯会议"
    return data


class DatabaseTests(unittest.TestCase):
    def test_list_emails_orders_by_received_time_descending(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "mail.db"

            with patch("database.DB_PATH", db_path):
                database.init_db()
                database.insert_email(sample_email(
                    "old-high",
                    "Fri, 24 Apr 2026 09:00:00 +0800",
                    "高",
                ))
                database.insert_email(sample_email(
                    "new-low",
                    "Sun, 26 Apr 2026 09:00:00 +0800",
                    "低",
                ))

                rows = database.list_emails()

        self.assertEqual([row["uid"] for row in rows], ["new-low", "old-high"])

    def test_list_emails_on_date_filters_by_local_received_date(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "mail.db"

            with patch("database.DB_PATH", db_path):
                database.init_db()
                database.insert_email(sample_email(
                    "today",
                    "Sun, 26 Apr 2026 09:00:00 +0800",
                    "低",
                ))
                database.insert_email(sample_email(
                    "yesterday",
                    "Sat, 25 Apr 2026 23:00:00 +0800",
                    "高",
                ))

                rows = database.list_emails_on_date(date(2026, 4, 26))

        self.assertEqual([row["uid"] for row in rows], ["today"])

    def test_list_emails_needing_analysis_on_date_returns_failed_today_messages(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "mail.db"

            with patch("database.DB_PATH", db_path):
                database.init_db()
                database.insert_email(failed_email(
                    "failed-today",
                    "Sun, 26 Apr 2026 09:00:00 +0800",
                ))
                database.insert_email(sample_email(
                    "ok-today",
                    "Sun, 26 Apr 2026 10:00:00 +0800",
                    "低",
                ))
                database.insert_email(failed_email(
                    "failed-yesterday",
                    "Sat, 25 Apr 2026 09:00:00 +0800",
                ))

                rows = database.list_emails_needing_analysis_on_date(date(2026, 4, 26))

        self.assertEqual([row["uid"] for row in rows], ["failed-today"])

    def test_list_meeting_emails_on_date_keeps_meetings_after_category_changes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "mail.db"

            with patch("database.DB_PATH", db_path):
                database.init_db()
                database.insert_email(meeting_email(
                    "moved-meeting",
                    "Sun, 26 Apr 2026 09:00:00 +0800",
                    category="项目进展",
                ))
                database.insert_email(sample_email(
                    "normal",
                    "Sun, 26 Apr 2026 10:00:00 +0800",
                    "低",
                ))

                rows = database.list_meeting_emails_on_date(date(2026, 4, 26))

        self.assertEqual([row["uid"] for row in rows], ["moved-meeting"])

    def test_list_filtered_emails_supports_today_dashboard_filters(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "mail.db"

            with patch("database.DB_PATH", db_path):
                database.init_db()
                database.insert_email(sample_email(
                    "today-high",
                    "Sun, 26 Apr 2026 09:00:00 +0800",
                    "高",
                ))
                database.insert_email(sample_email(
                    "yesterday-high",
                    "Sat, 25 Apr 2026 09:00:00 +0800",
                    "高",
                ))
                database.insert_email(meeting_email(
                    "today-meeting-moved",
                    "Sun, 26 Apr 2026 10:00:00 +0800",
                    category="项目进展",
                ))
                database.insert_email(sample_email(
                    "today-read",
                    "Sun, 26 Apr 2026 11:00:00 +0800",
                    "低",
                ))
                read_row = database.list_emails(category="低优先级")[0]
                database.update_email_status(read_row["id"], is_read=1)

                high_rows = database.list_filtered_emails(
                    scope="today",
                    filter_key="high",
                    target_date=date(2026, 4, 26),
                )
                meeting_rows = database.list_filtered_emails(
                    scope="today",
                    filter_key="meeting",
                    target_date=date(2026, 4, 26),
                )
                unread_rows = database.list_filtered_emails(
                    scope="today",
                    filter_key="unread",
                    target_date=date(2026, 4, 26),
                )

        self.assertEqual([row["uid"] for row in high_rows], ["today-high"])
        self.assertEqual([row["uid"] for row in meeting_rows], ["today-meeting-moved"])
        self.assertEqual(
            [row["uid"] for row in unread_rows],
            ["today-meeting-moved", "today-high"],
        )

    def test_update_email_status_can_mark_read_email_unread(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "mail.db"

            with patch("database.DB_PATH", db_path):
                database.init_db()
                database.insert_email(sample_email(
                    "read-toggle",
                    "Sun, 26 Apr 2026 09:00:00 +0800",
                    "低",
                ))
                row = database.list_emails()[0]

                database.update_email_status(row["id"], is_read=1)
                database.update_email_status(row["id"], is_read=0)

                updated = database.get_email(row["id"])

        self.assertEqual(updated["is_read"], 0)


if __name__ == "__main__":
    unittest.main()
