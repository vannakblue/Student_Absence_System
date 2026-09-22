"""
Automated Verification & Test Script for Student & Teacher Absence Management System
Including Authentication, Teacher Accounts, Password Management, and Excel Export
"""

import os
import sys
import unittest
from datetime import datetime

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import database as db
import export_service
from app import app


class TestStudentAbsenceSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init_db()
        db.init_default_users()
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        cls.client = app.test_client()

    def test_01_database_classes_and_teachers(self):
        classes = db.get_classes()
        self.assertEqual(len(classes), 40, "Should have exactly 40 classes from old database")
        
        teachers = db.get_teachers()
        self.assertEqual(len(teachers), 119, "Should have exactly 119 teachers from old database")

        students = db.get_students()
        self.assertEqual(len(students), 1998, "Should have exactly 1,998 students from old database")
        print(f"[OK] Database verified: {len(classes)} classes, {len(teachers)} teachers, {len(students)} students.")

    def test_02_user_accounts_generation(self):
        users = db.get_all_users()
        self.assertGreaterEqual(len(users), 120, "Should have at least 1 admin + 119 teachers = 120 accounts")

        admin = db.get_user_by_username("admin")
        self.assertIsNotNone(admin)
        self.assertEqual(admin["role"], "admin")

        teacher_user = db.get_user_by_username("2890800096")
        self.assertIsNotNone(teacher_user)
        self.assertEqual(teacher_user["role"], "teacher")
        self.assertEqual(teacher_user["plain_password_hint"], "123456")
        print(f"[OK] Verified user accounts: {len(users)} users total (Admin + Teachers).")

    def test_03_authentication_logic(self):
        # 1. Admin login valid
        auth_admin = db.authenticate_user("admin", "admin123")
        self.assertIsNotNone(auth_admin)
        self.assertEqual(auth_admin["username"], "admin")

        # 2. Teacher login valid
        auth_teacher = db.authenticate_user("2890800096", "123456")
        self.assertIsNotNone(auth_teacher)
        self.assertEqual(auth_teacher["role"], "teacher")

        # 3. Invalid login
        bad_auth = db.authenticate_user("admin", "wrongpassword")
        self.assertIsNone(bad_auth)

        bad_user = db.authenticate_user("nonexistent_user", "123456")
        self.assertIsNone(bad_user)
        print("[OK] Authentication verification passed (Admin, Teacher, and invalid cases).")

    def test_04_teacher_attendance_operations(self):
        today = datetime.now().strftime("%Y-%m-%d")
        teachers = db.get_teachers()
        first_t = teachers[0]
        
        # Save attendance
        records = [{
            "teacher_id": first_t["id"],
            "status": "PERMISSION",
            "reason": "មានធុរៈគ្រួសារ",
            "substitute_teacher_id": teachers[1]["id"] if len(teachers) > 1 else None,
            "notes": "Test"
        }]
        success = db.save_teacher_attendance(today, "Morning", "Session 1", records)
        self.assertTrue(success)

        # Retrieve and verify
        att_list = db.get_teacher_attendance(today, "Morning", "Session 1")
        matched = [a for a in att_list if a["teacher_id"] == first_t["id"]]
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["status"], "PERMISSION")
        print("[OK] Teacher attendance save and read verified.")

    def test_05_student_attendance_operations(self):
        today = datetime.now().strftime("%Y-%m-%d")
        classes = db.get_classes()
        first_c = classes[0]
        students = db.get_students(class_id=first_c["id"])
        self.assertGreater(len(students), 0)

        records = [
            {"student_id": students[0]["id"], "status": "ABSENT", "reason": "ឈឺផ្ដាសាយ"}
        ]
        success = db.save_student_attendance(first_c["id"], today, "Morning", "Daily", records)
        self.assertTrue(success)

        att_list = db.get_student_attendance(first_c["id"], today, "Morning", "Daily")
        matched = [a for a in att_list if a["student_id"] == students[0]["id"]]
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["status"], "ABSENT")
        print("[OK] Student attendance save and read verified.")

    def test_06_timetable_operations(self):
        slots_7a = db.get_timetable_by_class("7A")
        self.assertGreater(len(slots_7a), 0, "7A should have timetable slots")
        first_slot = slots_7a[0]
        self.assertIn("day_name", first_slot)
        self.assertIn("period_num", first_slot)

        tt_classes = db.get_all_timetable_classes()
        self.assertGreater(len(tt_classes), 0)
        print(f"[OK] Timetable verified: {len(tt_classes)} classes in timetable, {len(slots_7a)} slots for 7A.")

    def test_07_excel_exports(self):
        # Student Excel
        student_excel = export_service.export_student_attendance_excel()
        self.assertTrue(os.path.exists(student_excel))
        self.assertGreater(os.path.getsize(student_excel), 1000)

        # Teacher Excel
        teacher_excel = export_service.export_teacher_attendance_excel()
        self.assertTrue(os.path.exists(teacher_excel))
        self.assertGreater(os.path.getsize(teacher_excel), 1000)

        # Users Credential Excel
        users_excel = export_service.export_users_excel()
        self.assertTrue(os.path.exists(users_excel))
        self.assertGreater(os.path.getsize(users_excel), 1000)
        print("[OK] All Excel exports verified (Students, Teachers, and User Credentials).")

    def test_08_login_flow_and_session(self):
        # 1. Unauthenticated request to / should redirect to /login
        res_unauth = self.client.get("/", follow_redirects=False)
        self.assertEqual(res_unauth.status_code, 302)
        self.assertIn("/login", res_unauth.location)

        # 2. Login GET returns 200
        res_login_page = self.client.get("/login")
        self.assertEqual(res_login_page.status_code, 200)

        # 3. Post invalid credentials
        res_bad_login = self.client.post("/login", data={"username": "admin", "password": "wrong"}, follow_redirects=True)
        self.assertIn("ឈ្មោះគណនី ឬលេខសម្ងាត់មិនត្រឹមត្រូវទេ".encode("utf-8"), res_bad_login.data)

        # 4. Login as Admin
        with self.client.session_transaction() as sess:
            sess.clear()
        res_admin_login = self.client.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=False)
        self.assertEqual(res_admin_login.status_code, 302)
        self.assertEqual(res_admin_login.location, "/")

        # 5. Access protected admin pages as Admin
        admin_pages = [
            "/",
            "/users",
            "/teacher-attendance",
            "/teachers",
            "/reports",
            "/settings"
        ]
        for page in admin_pages:
            res = self.client.get(page)
            self.assertEqual(res.status_code, 200, f"Admin failed to access {page}")

        # 6. Admin can download users excel
        res_excel = self.client.get("/export/users/excel")
        self.assertEqual(res_excel.status_code, 200)

        # 7. Admin reset user password
        teacher = db.get_user_by_username("2890800096")
        res_reset = self.client.post(f"/users/reset-password/{teacher['id']}")
        self.assertEqual(res_reset.status_code, 200)
        self.assertTrue(res_reset.get_json()["success"])

        print("[OK] Admin login flow and admin page access verified.")

    def test_09_teacher_login_and_access(self):
        with self.client.session_transaction() as sess:
            sess.clear()

        # Login as teacher
        res_teacher_login = self.client.post(
            "/login", 
            data={"username": "2890800096", "password": "123456"}, 
            follow_redirects=False
        )
        self.assertEqual(res_teacher_login.status_code, 302)
        self.assertIn("/portal", res_teacher_login.location)

        # Teacher accesses /portal
        res_portal = self.client.get("/portal")
        self.assertEqual(res_portal.status_code, 200)

        # Teacher accesses attendance (redirected to locked portal attendance) & timetable
        res_student_att = self.client.get("/student-attendance", follow_redirects=True)
        self.assertEqual(res_student_att.status_code, 200)

        res_timetable = self.client.get("/timetable")
        self.assertEqual(res_timetable.status_code, 200)

        # Teacher tries to access admin-only /users -> should be redirected to portal
        res_forbidden = self.client.get("/users", follow_redirects=False)
        self.assertEqual(res_forbidden.status_code, 302)
        self.assertIn("/portal", res_forbidden.location)

        # Teacher changes password
        res_pwd = self.client.post("/change-password", json={
            "old_password": "123456",
            "new_password": "teacher_new_pass",
            "confirm_password": "teacher_new_pass"
        })
        self.assertEqual(res_pwd.status_code, 200)
        self.assertTrue(res_pwd.get_json()["success"])

        # Reset teacher's password back to 123456 for test cleanliness
        teacher = db.get_user_by_username("2890800096")
        db.reset_user_password(teacher["id"], "123456")

        print("[OK] Teacher login flow, permissions, and password change verified.")

    def test_10_timetable_slot_crud(self):
        teachers = db.get_teachers()
        t_id = teachers[0]["id"]

        # 1. Admin saves a new timetable slot
        slot_id = db.save_timetable_slot(
            slot_id=None,
            class_code="7A",
            teacher_id=t_id,
            day_code="ច",
            period_num=8,
            shift="Afternoon",
            subject_name="គណិតវិទ្យា",
            room_number="បន្ទប់ ១០១"
        )
        self.assertIsNotNone(slot_id)

        # 2. Retrieve slot
        slot = db.get_timetable_slot_by_id(slot_id)
        self.assertIsNotNone(slot)
        self.assertEqual(slot["class_code"], "7A")
        self.assertEqual(slot["subject_name"], "គណិតវិទ្យា")
        self.assertEqual(slot["room_number"], "បន្ទប់ ១០១")

        # 3. Update slot
        db.save_timetable_slot(
            slot_id=slot_id,
            class_code="7A",
            teacher_id=t_id,
            day_code="ច",
            period_num=8,
            shift="Afternoon",
            subject_name="រូបវិទ្យា",
            room_number="បន្ទប់ ១០២"
        )
        updated_slot = db.get_timetable_slot_by_id(slot_id)
        self.assertEqual(updated_slot["subject_name"], "រូបវិទ្យា")
        self.assertEqual(updated_slot["room_number"], "បន្ទប់ ១០២")

        # 4. Delete slot
        deleted = db.delete_timetable_slot(slot_id)
        self.assertTrue(deleted)
        self.assertIsNone(db.get_timetable_slot_by_id(slot_id))
        print("[OK] Timetable slot CRUD operations verified.")

    def test_11_automatic_teacher_absence_from_unmarked_slots(self):
        test_date = "2026-09-21"  # Monday (ចន្ទ)

        # Reconcile from master timetable slots
        result = db.calculate_teacher_attendance_from_slots(test_date)
        self.assertGreater(result["total_slots"], 0, "Should evaluate slots for Monday")
        self.assertIn("present", result)
        self.assertIn("absent", result)
        self.assertIn("unmarked_slots", result)

        # Check accountability list
        accountability = db.get_timetable_accountability(test_date)
        self.assertEqual(len(accountability), result["total_slots"])
        for item in accountability[:5]:
            self.assertIn(item["teacher_status"], ["PRESENT", "ABSENT", "PERMISSION"])
            if not item["is_marked"] and item["teacher_status"] == "ABSENT":
                self.assertIn("ខកខានមិនបានស្រង់វត្តមានសិស្ស", item["status_reason"])

        # Check dashboard stats include accountability info
        stats = db.get_dashboard_stats(test_date)
        self.assertIn("timetable_reconcile", stats)
        self.assertIn("unmarked_slots", stats)
        print(f"[OK] Automatic teacher absence rule verified: {result['present']} present, {result['absent']} absent from {result['total_slots']} slots.")

    def test_12_timetable_and_reconcile_api_endpoints(self):
        # Admin session
        with self.client.session_transaction() as sess:
            sess["user"] = {"id": 1, "username": "admin", "role": "admin", "full_name_kh": "Admin"}

        teachers = db.get_teachers()
        t_id = teachers[0]["id"]

        # 1. Test /api/subjects
        res_subs = self.client.get("/api/subjects")
        self.assertEqual(res_subs.status_code, 200)
        self.assertGreaterEqual(len(res_subs.get_json()["data"]), 17)

        # 2. Test /api/timetable/slot/save
        res_save = self.client.post("/api/timetable/slot/save", json={
            "class_code": "8A",
            "teacher_id": t_id,
            "day_code": "ព",
            "period_num": 1,
            "shift": "Morning",
            "subject_name": "គីមីវិទ្យា",
            "room_number": "Lab 1"
        })
        self.assertEqual(res_save.status_code, 200)
        saved_slot_id = res_save.get_json()["slot_id"]

        # 3. Test /api/teacher-attendance/reconcile
        res_reconcile = self.client.post("/api/teacher-attendance/reconcile", json={"date": "2026-09-21"})
        self.assertEqual(res_reconcile.status_code, 200)
        self.assertTrue(res_reconcile.get_json()["success"])

        # 4. Clean up test slot
        if saved_slot_id:
            res_del = self.client.post(f"/api/timetable/slot/delete/{saved_slot_id}")
            self.assertEqual(res_del.status_code, 200)

        print("[OK] Timetable and reconcile API endpoints verified.")


if __name__ == "__main__":
    unittest.main()
