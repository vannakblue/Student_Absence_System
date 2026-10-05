"""
Unit tests for Admin Proxy Attendance Functionality
(Admin ចុះវត្តមានសិស្សជំនួសគ្រូដែលមានបញ្ហា ដូចជាទូរសព្ទខូច ឬដាច់សេវា)
"""

import unittest
from datetime import datetime
import database as db
from app import app


class TestAdminProxyAttendance(unittest.TestCase):

    def setUp(self):
        self.app = app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        db.init_db()
        db.init_default_users()

    def test_01_get_scheduled_teacher_for_slot(self):
        """ផ្ទៀងផ្ទាត់ការស្វែងរកគ្រូបង្រៀនតាមកាលវិភាគសម្រាប់ថ្នាក់ និងម៉ោងសិក្សា"""
        classes = db.get_classes()
        self.assertGreater(len(classes), 0)
        c = classes[0]

        # Get any timetable slot for this class
        conn = db.get_db_connection()
        slot = conn.execute("""
            SELECT ts.*, t.id as teacher_id, t.full_name_kh
            FROM timetable_slots ts
            JOIN teachers t ON ts.teacher_id = t.id
            WHERE ts.class_code LIKE '%' || ? || '%' OR ts.class_id = ?
            LIMIT 1
        """, (c["class_name"].replace("ថ្នាក់ទី", "").strip(), c["id"])).fetchone()
        conn.close()

        if slot:
            # Map day_code to a test date
            day_to_weekday = {'ច': 0, 'អ': 1, 'ព': 2, 'ព្រ': 3, 'សុ': 4, 'ស': 5}
            w_idx = day_to_weekday.get(slot["day_code"], 0)
            # Find a 2026 date that matches this weekday
            test_date = f"2026-09-2{1 + w_idx}" # 2026-09-21 is Monday (0)

            found = db.get_scheduled_teacher_for_slot(
                class_id=c["id"],
                date_str=test_date,
                period_str=f"Session {slot['period_num']}",
                shift=slot["shift"]
            )
            self.assertIsNotNone(found)
            self.assertEqual(found["teacher_id"], slot["teacher_id"])
            print(f"[OK] Found scheduled teacher: {found['full_name_kh']} for {c['class_name']} Session {slot['period_num']}.")

    def test_02_admin_records_attendance_on_behalf_of_teacher(self):
        """Admin ចុះវត្តមានសិស្សជំនួសគ្រូករណីទូរសព្ទខូច"""
        # Login as Admin
        with self.client.session_transaction() as sess:
            sess["user"] = {
                "id": 1,
                "username": "admin",
                "role": "admin",
                "full_name_kh": "Admin System"
            }

        classes = db.get_classes()
        c = classes[0]
        students = db.get_students(class_id=c["id"])
        self.assertGreaterEqual(len(students), 2)
        s1 = students[0]

        teachers = db.get_teachers(active_only=True)
        self.assertGreater(len(teachers), 0)
        t = teachers[0]

        test_date = "2026-09-28" # Monday
        test_shift = "Morning"
        test_period = "Session 1"
        proxy_reason = "ទូរសព្ទខូច / មានបញ្ហា"

        # Admin submits attendance on behalf of teacher t
        res = self.client.post("/api/student-attendance", json={
            "class_id": c["id"],
            "date": test_date,
            "shift": test_shift,
            "period": test_period,
            "records": [
                {"student_id": s1["id"], "status": "ABSENT", "reason": "ឈឺ"}
            ],
            "on_behalf_of_teacher_id": t["id"],
            "proxy_reason": proxy_reason
        })

        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["proxy_teacher_id"], t["id"])
        self.assertEqual(data["phase"], "admin_proxy")
        self.assertIn(t["full_name_kh"], data["message"])
        print(f"[OK] Admin recorded attendance on behalf of {t['full_name_kh']}.")

        # Verify Database: student_attendance recorded_by
        conn = db.get_db_connection()
        sa_row = conn.execute("""
            SELECT * FROM student_attendance
            WHERE class_id = ? AND date = ? AND shift = ? AND period = ? AND student_id = ?
        """, (c["id"], test_date, test_shift, test_period, s1["id"])).fetchone()

        self.assertIsNotNone(sa_row)
        self.assertIn("Admin (ជំនួស៖", sa_row["recorded_by"])
        self.assertIn(t["full_name_kh"], sa_row["recorded_by"])
        self.assertIn(proxy_reason, sa_row["recorded_by"])

        # Verify Database: attendance_audit_logs has teacher_id and phase 'admin_proxy'
        audit_row = conn.execute("""
            SELECT * FROM attendance_audit_logs
            WHERE class_id = ? AND date = ? AND period = ?
            ORDER BY id DESC LIMIT 1
        """, (c["id"], test_date, test_period)).fetchone()

        self.assertIsNotNone(audit_row)
        self.assertEqual(audit_row["teacher_id"], t["id"])
        self.assertEqual(audit_row["phase"], "admin_proxy")
        self.assertIn("on behalf of", audit_row["notes"])
        self.assertIn(proxy_reason, audit_row["notes"])
        conn.close()
        print("[OK] Audit log and attendance table correctly attributed to teacher via admin proxy.")

    def test_03_teacher_cannot_spoof_proxy_attendance(self):
        """គ្រូធម្មតាមិនអាចប្រើប្រាស់មុខងារចុះជំនួសដើម្បីក្លែងបន្លំ teacher_id ឡើយ"""
        teachers = db.get_teachers(active_only=True)
        self.assertGreaterEqual(len(teachers), 2)
        t1 = teachers[0]
        t2 = teachers[1]

        # Login as teacher 1
        with self.client.session_transaction() as sess:
            sess["user"] = {
                "id": 2,
                "username": "teacher1",
                "role": "teacher",
                "teacher_id": t1["id"],
                "full_name_kh": t1["full_name_kh"]
            }

        classes = db.get_classes()
        c = classes[0]

        # Try to submit attendance claiming to be on behalf of teacher 2
        res = self.client.post("/api/student-attendance", json={
            "class_id": c["id"],
            "date": "2026-09-22",
            "shift": "Morning",
            "period": "Session 1",
            "records": [],
            "on_behalf_of_teacher_id": t2["id"],
            "proxy_reason": "ព្យាយាមបន្លំ"
        })

        data = res.get_json()
        self.assertIsNone(data.get("proxy_teacher_id"), "Teacher cannot use proxy_teacher_id")
        print("[OK] Non-admin cannot spoof proxy attendance for other teachers.")

    def test_04_admin_proxy_clears_teacher_unmarked_status(self):
        """ពេល Admin ចុះវត្តមានសិស្សជំនួសគ្រូ គ្រូនោះលែងត្រូវបានកត់ត្រាថាខកខាន/អវត្តមានទៀតហើយ"""
        # Find a timetable slot on Monday without existing leave
        conn = db.get_db_connection()
        slot = conn.execute("""
            SELECT ts.*, COALESCE(c.id, ts.class_id) as resolved_class_id, t.id as t_id, t.full_name_kh
            FROM timetable_slots ts
            JOIN teachers t ON ts.teacher_id = t.id
            LEFT JOIN classes c ON ts.class_id = c.id OR c.class_name LIKE '%' || ts.class_code || '%'
            WHERE ts.day_code = 'ច' AND t.status = 'Active'
              AND t.id NOT IN (SELECT person_id FROM leave_requests WHERE person_type = 'TEACHER' AND status = 'Approved')
            LIMIT 1
        """).fetchone()

        if not slot:
            # If all had leaves, just pick first slot and clear leave for test
            slot = conn.execute("""
                SELECT ts.*, COALESCE(c.id, ts.class_id) as resolved_class_id, t.id as t_id, t.full_name_kh
                FROM timetable_slots ts
                JOIN teachers t ON ts.teacher_id = t.id
                LEFT JOIN classes c ON ts.class_id = c.id OR c.class_name LIKE '%' || ts.class_code || '%'
                WHERE ts.day_code = 'ច' AND t.status = 'Active'
                LIMIT 1
            """).fetchone()
        conn.close()

        if slot:
            test_date = "2026-09-28" # Monday
            p_label = f"Session {slot['period_num']}"
            t_id = slot["t_id"]
            c_id = slot["resolved_class_id"]

            with self.client.session_transaction() as sess:
                sess["user"] = {
                    "id": 1,
                    "username": "admin",
                    "role": "admin",
                    "full_name_kh": "Admin System"
                }

            # Admin submits 100% present on behalf of this teacher
            res = self.client.post("/api/student-attendance", json={
                "class_id": c_id,
                "date": test_date,
                "shift": slot["shift"] or "Morning",
                "period": p_label,
                "records": [],
                "on_behalf_of_teacher_id": t_id,
                "proxy_reason": "ទូរសព្ទខូច"
            })
            self.assertEqual(res.status_code, 200)

            # Check timetable accountability
            result = db.calculate_teacher_attendance_from_slots(test_date)
            # Check teacher attendance table
            conn = db.get_db_connection()
            ta_row = conn.execute("""
                SELECT * FROM teacher_attendance
                WHERE date = ? AND teacher_id = ? AND period LIKE '%' || ? || '%'
            """, (test_date, t_id, slot["period_num"])).fetchone()
            conn.close()

            if ta_row:
                self.assertEqual(ta_row["status"], "PRESENT", "Teacher should be PRESENT because admin marked on their behalf")
                print(f"[OK] Teacher {slot['full_name_kh']} credited as PRESENT after admin proxy submission.")


if __name__ == "__main__":
    unittest.main()
