"""
Unit Tests for Sparse Student Attendance Storage Model
(រក្សាទុកតែសិស្សអវត្តមាន និងសុំច្បាប់ប៉ុណ្ណោះក្នុង Database)
"""

import unittest
from datetime import datetime
import database as db
from app import app


class TestSparseStudentAttendance(unittest.TestCase):

    def setUp(self):
        self.app = app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        db.init_db()
        db.init_default_users()

    def test_01_save_only_absent_students(self):
        """ផ្ទៀងផ្ទាត់ថារក្សាទុកតែសិស្សអវត្តមាន និងសុំច្បាប់ប៉ុណ្ណោះក្នុង student_attendance"""
        classes = db.get_classes()
        self.assertGreater(len(classes), 0)
        c = classes[0]
        students = db.get_students(class_id=c["id"])
        self.assertGreaterEqual(len(students), 3)

        s1 = students[0]
        s2 = students[1]
        s3 = students[2]

        test_date = "2026-09-22"
        test_shift = "Morning"
        test_period = "Session 1"

        # Mark s1: PRESENT, s2: ABSENT, s3: PERMISSION
        records = [
            {"student_id": s1["id"], "status": "PRESENT", "reason": ""},
            {"student_id": s2["id"], "status": "ABSENT", "reason": "ឈឺក្បាល"},
            {"student_id": s3["id"], "status": "PERMISSION", "reason": "ធុរៈគ្រួសារ"},
        ]

        db.save_student_attendance(c["id"], test_date, test_shift, test_period, records, recorded_by="TestTeacher")

        # Verify database table rows
        conn = db.get_db_connection()
        rows = conn.execute("""
            SELECT student_id, status FROM student_attendance
            WHERE class_id = ? AND date = ? AND shift = ? AND period = ?
        """, (c["id"], test_date, test_shift, test_period)).fetchall()
        conn.close()

        stored_ids = {r["student_id"]: r["status"] for r in rows}

        # s1 (PRESENT) should NOT be stored!
        self.assertNotIn(s1["id"], stored_ids, "PRESENT student should NOT be in student_attendance")

        # s2 (ABSENT) and s3 (PERMISSION) MUST be stored
        self.assertIn(s2["id"], stored_ids)
        self.assertEqual(stored_ids[s2["id"]], "ABSENT")
        self.assertIn(s3["id"], stored_ids)
        self.assertEqual(stored_ids[s3["id"]], "PERMISSION")
        print(f"[OK] Sparse storage verified: only {len(rows)} absent/permission students saved.")

        # Verify get_student_attendance still returns ALL students with correct status
        att_list = db.get_student_attendance(c["id"], test_date, test_shift, test_period)
        att_map = {a["student_id"]: a["status"] for a in att_list}

        self.assertEqual(att_map[s1["id"]], "PRESENT", "Default should be PRESENT")
        self.assertEqual(att_map[s2["id"]], "ABSENT")
        self.assertEqual(att_map[s3["id"]], "PERMISSION")
        print("[OK] get_student_attendance correctly defaults missing records to PRESENT.")

    def test_02_all_present_100_percent(self):
        """ផ្ទៀងផ្ទាត់ករណីសិស្សមកគ្រប់ ១០០% (០ អវត្តមាន) គ្រូនៅតែត្រូវបានកត់ត្រាថាបានស្រង់វត្តមានរួចរាល់"""
        classes = db.get_classes()
        c = classes[0]
        students = db.get_students(class_id=c["id"])

        test_date = "2026-09-23"
        test_shift = "Morning"
        test_period = "Session 2"

        # All present
        records = [{"student_id": s["id"], "status": "PRESENT", "reason": ""} for s in students]

        db.save_student_attendance(c["id"], test_date, test_shift, test_period, records, recorded_by="TestTeacher")

        # student_attendance table should have 0 records for this slot
        conn = db.get_db_connection()
        count = conn.execute("""
            SELECT COUNT(*) FROM student_attendance
            WHERE class_id = ? AND date = ? AND shift = ? AND period = ?
        """, (c["id"], test_date, test_shift, test_period)).fetchone()[0]

        # attendance_audit_logs table MUST record the session
        audit_count = conn.execute("""
            SELECT COUNT(*) FROM attendance_audit_logs
            WHERE class_id = ? AND date = ? AND shift = ? AND period = ?
        """, (c["id"], test_date, test_shift, test_period)).fetchone()[0]
        conn.close()

        self.assertEqual(count, 0, "0 records in student_attendance when 100% present")
        self.assertGreaterEqual(audit_count, 1, "Session must be recorded in audit logs")
        print("[OK] 100% presence correctly stored with 0 student rows and 1 audit row.")

    def test_03_switch_absent_to_present(self):
        """ផ្ទៀងផ្ទាត់ពេលកែប្រែពីអវត្តមាន មកមានវត្តមានវិញ record ត្រូវបានលុបចេញពី Database"""
        classes = db.get_classes()
        c = classes[0]
        students = db.get_students(class_id=c["id"])
        s = students[0]

        test_date = "2026-09-24"
        test_shift = "Morning"
        test_period = "Session 3"

        # 1. Mark absent
        db.save_student_attendance(c["id"], test_date, test_shift, test_period, [
            {"student_id": s["id"], "status": "ABSENT", "reason": "យឺត"}
        ])

        conn = db.get_db_connection()
        count_before = conn.execute("""
            SELECT COUNT(*) FROM student_attendance
            WHERE class_id = ? AND date = ? AND student_id = ?
        """, (c["id"], test_date, s["id"])).fetchone()[0]
        self.assertEqual(count_before, 1)

        # 2. Update to PRESENT
        db.save_student_attendance(c["id"], test_date, test_shift, test_period, [
            {"student_id": s["id"], "status": "PRESENT", "reason": ""}
        ])

        count_after = conn.execute("""
            SELECT COUNT(*) FROM student_attendance
            WHERE class_id = ? AND date = ? AND student_id = ?
        """, (c["id"], test_date, s["id"])).fetchone()[0]
        conn.close()

        self.assertEqual(count_after, 0, "Absence record should be deleted when changed to PRESENT")
        print("[OK] Absence record deleted cleanly when student changes to PRESENT.")


if __name__ == "__main__":
    unittest.main()
