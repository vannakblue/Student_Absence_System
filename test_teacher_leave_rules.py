"""
Unit tests for Teacher Leave Rules:
- Cutoff time validation for same-day requests
- Schedule / timetable slot validation
- Past date rejection
- Future date validation
"""

import unittest
from datetime import datetime, timedelta
import database as db


class TestTeacherLeaveRules(unittest.TestCase):

    def setUp(self):
        # Pick an active teacher with timetable slots
        conn = db.get_db_connection()
        row = conn.execute("""
            SELECT ts.teacher_id, t.full_name_kh, ts.day_code
            FROM timetable_slots ts
            JOIN teachers t ON ts.teacher_id = t.id
            WHERE ts.teacher_id IS NOT NULL
            LIMIT 1
        """).fetchone()
        conn.close()

        self.assertIsNotNone(row, "Must have at least one teacher with timetable slots")
        self.teacher_id = row["teacher_id"]
        self.day_code = row["day_code"]
        self.teacher_name = row["full_name_kh"]

        # Ensure default cutoff is 17:00
        db.set_setting("teacher_leave_cutoff_time", "17:00")

    def test_past_date_rejected(self):
        """សុំច្បាប់កាលបរិច្ឆេទអតីតកាល ត្រូវតែបដិសេធ"""
        past_dt = datetime.now() - timedelta(days=2)
        past_str = past_dt.strftime("%Y-%m-%d")
        is_valid, msg, slots = db.validate_teacher_leave_eligibility(
            self.teacher_id, past_str, past_str
        )
        self.assertFalse(is_valid)
        self.assertIn("កន្លងផុត", msg)

    def test_sunday_rejected(self):
        """សុំច្បាប់ថ្ងៃអាទិត្យ ត្រូវតែបដិសេធព្រោះគ្មានម៉ោងបង្រៀន"""
        # Find next Sunday and mock Saturday as today
        now = datetime.now()
        days_ahead = (6 - now.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        next_sunday = now + timedelta(days=days_ahead)
        mock_sat = next_sunday - timedelta(days=1)
        sun_str = next_sunday.strftime("%Y-%m-%d")

        is_valid, msg, slots = db.validate_teacher_leave_eligibility(
            self.teacher_id, sun_str, sun_str, current_dt=mock_sat
        )
        self.assertFalse(is_valid)
        self.assertIn("គ្មានម៉ោងបង្រៀន", msg)

    def test_same_day_after_cutoff_rejected(self):
        """សុំច្បាប់ថ្ងៃនេះ ក្រោយម៉ោង 17:00 ត្រូវតែបដិសេធ"""
        # Mock current_dt at 17:30
        now = datetime.now()
        mock_dt = now.replace(hour=17, minute=30, second=0)
        today_str = mock_dt.strftime("%Y-%m-%d")

        is_valid, msg, slots = db.validate_teacher_leave_eligibility(
            self.teacher_id, today_str, today_str, current_dt=mock_dt
        )
        self.assertFalse(is_valid)
        self.assertIn("ផុតម៉ោងកំណត់", msg)

    def test_same_day_before_cutoff_with_slots(self):
        """សុំច្បាប់ថ្ងៃនេះ មុនម៉ោង 17:00 ប្រសិនបើមានម៉ោងបង្រៀន គឺអនុញ្ញាត"""
        day_kh_map = {0: 'ច', 1: 'អ', 2: 'ព', 3: 'ព្រ', 4: 'សុ', 5: 'ស', 6: 'អា'}
        
        now = datetime.now()
        today_code = day_kh_map[now.weekday()]
        slots_today = [s for s in db.get_timetable_by_teacher(self.teacher_id) if s.get("day_code") == today_code]

        mock_dt = now.replace(hour=9, minute=0, second=0)
        today_str = mock_dt.strftime("%Y-%m-%d")

        is_valid, msg, slots = db.validate_teacher_leave_eligibility(
            self.teacher_id, today_str, today_str, current_dt=mock_dt
        )

        if slots_today:
            self.assertTrue(is_valid, f"Teacher has slots today so should be valid: {msg}")
            self.assertGreater(len(slots), 0)
        else:
            self.assertFalse(is_valid)
            self.assertIn("គ្មានម៉ោងបង្រៀន", msg)

    def test_next_day_teaching_day_accepted(self):
        """សុំច្បាប់ថ្ងៃបន្ទាប់ដែលមានម៉ោងបង្រៀន ត្រូវតែអនុញ្ញាត"""
        day_code_to_idx = {'ច': 0, 'អ': 1, 'ព': 2, 'ព្រ': 3, 'សុ': 4, 'ស': 5}
        target_w_idx = day_code_to_idx.get(self.day_code, 0)

        # Mock current_dt to be 1 day prior to teacher's teaching day (e.g. if target is Tuesday, mock Monday)
        now = datetime.now()
        # Find a date for target_w_idx
        days_to_target = (target_w_idx - now.weekday()) % 7
        target_dt = now + timedelta(days=days_to_target if days_to_target > 0 else 7)
        # Mock "today" as the day right before target_dt
        # If target_dt is Monday, mock Saturday (2 days before) or Sunday (1 day before)
        mock_now = target_dt - timedelta(days=1)
        if mock_now.weekday() == 6: # If Sunday, mock Saturday
            mock_now = target_dt - timedelta(days=2)

        target_str = target_dt.strftime("%Y-%m-%d")
        is_valid, msg, slots = db.validate_teacher_leave_eligibility(
            self.teacher_id, target_str, target_str, current_dt=mock_now
        )
        self.assertTrue(is_valid, f"Expected valid for next teaching day {target_str}: {msg}")
        self.assertGreater(len(slots), 0)

    def test_dates_beyond_next_day_rejected(self):
        """សុំច្បាប់លើសពីថ្ងៃបន្ទាប់ (ឧ. ២ ឬ ៥ ថ្ងៃទៅមុខ) ត្រូវតែបដិសេធដាច់ខាតសម្រាប់គ្រូ"""
        now = datetime.now()
        far_future = now + timedelta(days=5)
        far_str = far_future.strftime("%Y-%m-%d")

        is_valid, msg, slots = db.validate_teacher_leave_eligibility(
            self.teacher_id, far_str, far_str, current_dt=now, is_admin=False
        )
        self.assertFalse(is_valid)
        self.assertIn("ថ្ងៃបន្ទាប់", msg)

    def test_admin_can_override_future_dates(self):
        """Admin មានសិទ្ធិកត់ត្រាច្បាប់ថ្ងៃអនាគតបាន (is_admin=True)"""
        now = datetime.now()
        day_code_to_idx = {'ច': 0, 'អ': 1, 'ព': 2, 'ព្រ': 3, 'សុ': 4, 'ស': 5}
        target_w_idx = day_code_to_idx.get(self.day_code, 0)
        days_ahead = (target_w_idx - now.weekday()) % 7
        if days_ahead <= 1:
            days_ahead += 7
        future_dt = now + timedelta(days=days_ahead)
        future_str = future_dt.strftime("%Y-%m-%d")

        is_valid, msg, slots = db.validate_teacher_leave_eligibility(
            self.teacher_id, future_str, future_str, current_dt=now, is_admin=True
        )
        self.assertTrue(is_valid)

    def test_api_leave_eligibility_endpoint(self):
        """តេស្ត API GET /api/teacher/<id>/leave-eligibility"""
        from app import app
        client = app.test_client()
        now_str = datetime.now().strftime("%Y-%m-%d")
        res = client.get(f"/api/teacher/{self.teacher_id}/leave-eligibility?start_date={now_str}")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertIn("eligible", data)
        self.assertIn("cutoff_time", data)
        self.assertIn("min_date", data)
        self.assertIn("max_date", data)


if __name__ == "__main__":
    unittest.main()
