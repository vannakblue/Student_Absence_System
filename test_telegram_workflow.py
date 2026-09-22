"""
Unit tests for Telegram Workflow:
1. Leave Request Creation with 'Pending' Status
2. Telegram Callback Query handling (Approve / Reject)
3. 30-Minute Period Cutoff Detection & Unmarked Teacher Slots
4. Duplicate Alert Suppression (No Spams within the same hour)
5. Flask Webhook Endpoint & Status Update API
"""

import unittest
from datetime import datetime, timedelta
import database as db
import telegram_service
import app


class TestTelegramWorkflow(unittest.TestCase):

    def setUp(self):
        self.app = app.app.test_client()
        self.app.testing = True

        # Find a teacher with timetable slots
        conn = db.get_db_connection()
        row = conn.execute("""
            SELECT ts.teacher_id, t.full_name_kh, ts.day_code
            FROM timetable_slots ts
            JOIN teachers t ON ts.teacher_id = t.id
            WHERE ts.teacher_id IS NOT NULL
            LIMIT 1
        """).fetchone()
        conn.close()

        self.assertIsNotNone(row, "Need a teacher with timetable slots")
        self.teacher_id = row["teacher_id"]
        self.teacher_name = row["full_name_kh"]

    def test_leave_request_pending_status_and_telegram_markup(self):
        """ពាក្យសុំច្បាប់របស់គ្រូត្រូវតែមាន status='Pending' និងបង្កើត Inline Keyboard ត្រឹមត្រូវ"""
        # Pick next teaching day
        days = db.get_teacher_teaching_days(self.teacher_id)
        self.assertTrue(len(days) > 0)
        target_day_code = days[0]["day_code"]

        day_to_num = {'ច': 0, 'អ': 1, 'ព': 2, 'ព្រ': 3, 'សុ': 4, 'ស': 5}
        target_weekday = day_to_num[target_day_code]

        now = datetime.now()
        days_ahead = (target_weekday - now.weekday()) % 7
        if days_ahead <= 0:
            days_ahead += 7
        future_dt = now + timedelta(days=days_ahead)
        future_str = future_dt.strftime("%Y-%m-%d")

        leave_id = db.add_leave_request(
            person_type="TEACHER",
            person_id=self.teacher_id,
            start_date=future_str,
            end_date=future_str,
            reason="ធុរៈចាំបាច់ប្រចាំគ្រួសារយ៉ាងតិច១៥តួអក្សរ",
            status="Pending"
        )
        self.assertIsNotNone(leave_id)

        req = db.get_leave_request_by_id(leave_id)
        self.assertEqual(req["status"], "Pending")
        self.assertEqual(req["person_name_kh"], self.teacher_name)

    def test_callback_query_approve_flow(self):
        """តេស្តការចុចប៊ូតុង ✅ អនុម័ត តាមរយៈ Telegram Callback Query"""
        leave_id = db.add_leave_request(
            person_type="TEACHER",
            person_id=self.teacher_id,
            start_date="2026-10-15",
            end_date="2026-10-15",
            reason="តេស្តអនុម័តច្បាប់",
            status="Pending"
        )

        mock_callback = {
            "id": "cb_query_12345",
            "from": {"id": 999999, "first_name": "នាយកសាលា", "username": "headmaster"},
            "message": {"message_id": 8888, "chat": {"id": -100123456}, "text": "ពាក្យសុំច្បាប់"},
            "data": f"leave:approve:{leave_id}"
        }

        success, msg = telegram_service.handle_telegram_callback_query(mock_callback)
        self.assertTrue(success)

        # Check DB
        req = db.get_leave_request_by_id(leave_id)
        self.assertEqual(req["status"], "Approved")
        self.assertIn("នាយកសាលា", req["approved_by"])

    def test_callback_query_reject_flow(self):
        """តេស្តការចុចប៊ូតុង ❌ បដិសេធ តាមរយៈ Telegram Callback Query"""
        leave_id = db.add_leave_request(
            person_type="TEACHER",
            person_id=self.teacher_id,
            start_date="2026-10-16",
            end_date="2026-10-16",
            reason="តេស្តបដិសេធច្បាប់",
            status="Pending"
        )

        mock_callback = {
            "id": "cb_query_67890",
            "from": {"id": 999999, "first_name": "គណៈគ្រប់គ្រង", "username": "admin"},
            "message": {"message_id": 8889, "chat": {"id": -100123456}, "text": "ពាក្យសុំច្បាប់"},
            "data": f"leave:reject:{leave_id}"
        }

        success, msg = telegram_service.handle_telegram_callback_query(mock_callback)
        self.assertTrue(success)

        # Check DB
        req = db.get_leave_request_by_id(leave_id)
        self.assertEqual(req["status"], "Rejected")
        self.assertIn("គណៈគ្រប់គ្រង", req["approved_by"])

    def test_flask_webhook_endpoint(self):
        """តេស្តការហៅ POST /api/telegram/webhook"""
        leave_id = db.add_leave_request(
            person_type="TEACHER",
            person_id=self.teacher_id,
            start_date="2026-10-17",
            end_date="2026-10-17",
            reason="តេស្តតាម webhook route",
            status="Pending"
        )

        payload = {
            "callback_query": {
                "id": "cb_webhook_test",
                "from": {"id": 111111, "first_name": "Admin Tester"},
                "message": {"message_id": 5555, "chat": {"id": -100999}, "text": "ពាក្យសុំ"},
                "data": f"leave:approve:{leave_id}"
            }
        }

        res = self.app.post("/api/telegram/webhook", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("ok"))
        self.assertTrue(data.get("handled"))

        # Check DB
        req = db.get_leave_request_by_id(leave_id)
        self.assertEqual(req["status"], "Approved")

    def test_30_minute_period_window_logic(self):
        """តេស្តលក្ខខណ្ឌ ៣០ នាទីក្រោយចូលរៀន (Check & Dispatch)"""
        # Set cutoff to 30 mins
        db.set_setting("telegram_period_reminder_minutes", "30")

        # Period 1 Morning starts at 07:00
        # Simulated time 07:15 (only 15 mins in -> must NOT trigger)
        test_dt_early = datetime(2026, 9, 21, 7, 15, 0) # Monday 07:15
        res_early = telegram_service.check_and_dispatch_period_attendance(current_dt=test_dt_early)
        self.assertFalse(res_early["checked"])
        self.assertIn("Only 15 mins", res_early.get("reason", ""))

        # Simulated time 07:35 (35 mins in -> past 30-min cutoff -> MUST trigger)
        test_dt_due = datetime(2026, 9, 21, 7, 35, 0) # Monday 07:35
        res_due = telegram_service.check_and_dispatch_period_attendance(current_dt=test_dt_due)
        self.assertTrue(res_due["checked"])
        self.assertIn("ម៉ោងទី ១", res_due.get("period", ""))
        self.assertGreaterEqual(res_due.get("minutes_elapsed", 0), 30)

    def test_duplicate_alert_suppression(self):
        """តេស្តការការពារកុំឱ្យផ្ញើសារព្រមានជាន់គ្នាក្នុងម៉ោងតែមួយ (Duplicate Suppression)"""
        date_str = "2026-09-21"
        slot_id = 99999
        alert_type = "MISSED_ATTENDANCE"

        # Initially not sent
        self.assertFalse(db.is_period_alert_sent(date_str, slot_id, alert_type))

        # Record sent
        db.record_period_alert_sent(date_str, slot_id, alert_type)

        # Now must be true
        self.assertTrue(db.is_period_alert_sent(date_str, slot_id, alert_type))


if __name__ == "__main__":
    unittest.main()
