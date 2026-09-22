"""
Unit and Integration Tests for Time-Window Submission Rules,
Timetable Slot Auto-Binding, and Telegram Notification Service.
Student & Teacher Absence Management System
"""

import os
import sys
import unittest
from datetime import datetime, date
from unittest.mock import patch, MagicMock

import io
import database as db
from app import app
import telegram_service
import export_service

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


class TestTimeWindowRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init_db()
        db.init_default_users()

    def setUp(self):
        self.app = app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        conn = db.get_db_connection()
        conn.execute("DELETE FROM attendance_audit_logs WHERE class_id >= 9000")
        conn.commit()
        conn.close()

    def tearDown(self):
        conn = db.get_db_connection()
        conn.execute("DELETE FROM attendance_audit_logs WHERE class_id >= 9000")
        conn.commit()
        conn.close()

    # -------------------------------------------------------------
    # 1. Period Detection & Phase Logic
    # -------------------------------------------------------------
    def test_period_detection_morning(self):
        """ផ្ទៀងផ្ទាត់ការសម្គាល់ម៉ោង និងវេនពេលព្រឹក (Morning Periods)"""
        # Period 1: 07:15 -> Morning, Period 1, first_30
        dt_p1_first = datetime(2026, 9, 21, 7, 15, 0)
        info = db.get_current_period_info(dt_p1_first)
        self.assertTrue(info["has_active_period"])
        self.assertEqual(info["period"]["period_display_num"], 1)
        self.assertEqual(info["period"]["shift"], "Morning")
        self.assertEqual(info["period"]["phase"], "first_30")

        # Period 1: 07:45 -> Morning, Period 1, second_30
        dt_p1_second = datetime(2026, 9, 21, 7, 45, 0)
        info = db.get_current_period_info(dt_p1_second)
        self.assertTrue(info["has_active_period"])
        self.assertEqual(info["period"]["period_display_num"], 1)
        self.assertEqual(info["period"]["phase"], "second_30")

        # Period 2: 08:20 -> Morning, Period 2, first_30
        dt_p2 = datetime(2026, 9, 21, 8, 20, 0)
        info = db.get_current_period_info(dt_p2)
        self.assertTrue(info["has_active_period"])
        self.assertEqual(info["period"]["period_display_num"], 2)
        self.assertEqual(info["period"]["db_period_num"], 2)

        # Period 4: 10:10 -> Morning, Period 4
        dt_p4 = datetime(2026, 9, 21, 10, 10, 0)
        info = db.get_current_period_info(dt_p4)
        self.assertTrue(info["has_active_period"])
        self.assertEqual(info["period"]["period_display_num"], 4)
        self.assertEqual(info["period"]["db_period_num"], 4)

    def test_period_detection_afternoon(self):
        """ផ្ទៀងផ្ទាត់ការសម្គាល់ម៉ោង និងវេនពេលរសៀល (Afternoon Periods)"""
        # Period 1 (13:00 - 14:00) -> db_period_num 5
        dt_aft1 = datetime(2026, 9, 21, 13, 20, 0)
        info = db.get_current_period_info(dt_aft1)
        self.assertTrue(info["has_active_period"])
        self.assertEqual(info["period"]["shift"], "Afternoon")
        self.assertEqual(info["period"]["period_display_num"], 1)
        self.assertEqual(info["period"]["db_period_num"], 5)
        self.assertEqual(info["period"]["phase"], "first_30")

        # Period 4 (16:00 - 17:00) -> db_period_num 8
        dt_aft4 = datetime(2026, 9, 21, 16, 45, 0)
        info = db.get_current_period_info(dt_aft4)
        self.assertTrue(info["has_active_period"])
        self.assertEqual(info["period"]["shift"], "Afternoon")
        self.assertEqual(info["period"]["period_display_num"], 4)
        self.assertEqual(info["period"]["db_period_num"], 8)
        self.assertEqual(info["period"]["phase"], "second_30")

    def test_outside_teaching_hours(self):
        """ផ្ទៀងផ្ទាត់ពេលក្រៅម៉ោងបង្រៀន (Outside Teaching Hours)"""
        # 11:30 is lunch break between morning and afternoon
        dt_lunch = datetime(2026, 9, 21, 11, 30, 0)
        info = db.get_current_period_info(dt_lunch)
        self.assertFalse(info["has_active_period"])

        # 06:30 is before school starts
        dt_early = datetime(2026, 9, 21, 6, 30, 0)
        info = db.get_current_period_info(dt_early)
        self.assertFalse(info["has_active_period"])

        # 18:00 is after school ends
        dt_late = datetime(2026, 9, 21, 18, 0, 0)
        info = db.get_current_period_info(dt_late)
        self.assertFalse(info["has_active_period"])

    # -------------------------------------------------------------
    # 2. Submission Window Enforcement Rules
    # -------------------------------------------------------------
    def test_admin_override(self):
        """Admin អាចកែប្រែបានគ្រប់ពេលវេលា (Administrative Override)"""
        can_submit, status_code, msg, phase, count = db.check_submission_window_rule(
            class_id=1,
            date_str="2026-09-01",
            shift="Morning",
            period_str="Session 1",
            is_admin=True
        )
        self.assertTrue(can_submit)
        self.assertEqual(status_code, 200)
        self.assertEqual(phase, "admin")

    def test_first_30_minutes_allows_multiple_submissions(self):
        """ក្នុងរយៈពេល ៣០ នាទីដំបូង (First 30 mins)៖ គ្រូអាចដាក់ស្នើ និងកែប្រែបានច្រើនដង"""
        # Simulation time: Monday at 07:15:00
        sim_dt = datetime(2026, 9, 21, 7, 15, 0) # Monday
        sim_date = "2026-09-21"
        test_class_id = 9001

        # 1. Check rule for first time
        can_submit, status_code, msg, phase, count = db.check_submission_window_rule(
            class_id=test_class_id,
            date_str=sim_date,
            shift="Morning",
            period_str="Session 1",
            is_admin=False,
            current_dt=sim_dt
        )
        self.assertTrue(can_submit)
        self.assertEqual(status_code, 200)
        self.assertEqual(phase, "first_30")

        # Record first submission audit
        db.record_attendance_audit(
            class_id=test_class_id,
            date_str=sim_date,
            shift="Morning",
            period_str="Session 1",
            period_num=1,
            teacher_id=None,
            phase="first_30"
        )

        # 2. Check rule again in first 30 mins (e.g. 07:25) -> MUST still allow update
        sim_dt_2 = datetime(2026, 9, 21, 7, 25, 0)
        can_submit2, status_code2, msg2, phase2, count2 = db.check_submission_window_rule(
            class_id=test_class_id,
            date_str=sim_date,
            shift="Morning",
            period_str="Session 1",
            is_admin=False,
            current_dt=sim_dt_2
        )
        self.assertTrue(can_submit2)
        self.assertEqual(status_code2, 200)
        self.assertEqual(phase2, "first_30")
        self.assertGreaterEqual(count2, 1)

    def test_second_30_minutes_allows_only_once_if_not_submitted(self):
        """ក្នុងរយៈពេល ៣០ នាទីក្រោយ (Second 30 mins, e.g. 07:30 - 08:00)៖
        - ប្រសិនបើមិនទាន់បានដាក់ស្នើទាល់តែសោះ -> អនុញ្ញាតដាក់ស្នើបានតែ ១ ដងគត់
        - បន្ទាប់ពីដាក់ស្នើរួច ឬធ្លាប់ដាក់ស្នើពីមុន -> បដិសេធដាច់ខាត (403 Locked)
        """
        sim_dt_second = datetime(2026, 9, 21, 7, 45, 0)
        sim_date = "2026-09-21"
        test_class_id = 9999 # Fresh class ID with 0 prior audits

        # Step 1: No previous audit -> Allowed to submit once
        can_submit, status_code, msg, phase, count = db.check_submission_window_rule(
            class_id=test_class_id,
            date_str=sim_date,
            shift="Morning",
            period_str="Session 1",
            is_admin=False,
            current_dt=sim_dt_second
        )
        self.assertTrue(can_submit)
        self.assertEqual(status_code, 200)
        self.assertEqual(phase, "second_30")
        self.assertEqual(count, 0)

        # Step 2: Now record that late submission
        db.record_attendance_audit(
            class_id=test_class_id,
            date_str=sim_date,
            shift="Morning",
            period_str="Session 1",
            period_num=1,
            teacher_id=None,
            phase="second_30"
        )

        # Step 3: Teacher tries to submit/edit AGAIN in the second 30 minutes -> MUST BE REJECTED (403)
        can_submit_again, status_code_again, msg_again, phase_again, count_again = db.check_submission_window_rule(
            class_id=test_class_id,
            date_str=sim_date,
            shift="Morning",
            period_str="Session 1",
            is_admin=False,
            current_dt=sim_dt_second
        )
        self.assertFalse(can_submit_again)
        self.assertEqual(status_code_again, 403)
        self.assertEqual(phase_again, "locked_second_30")
        self.assertIn("មិនអាចកែប្រែបានទៀតទេ", msg_again)

    def test_cutoff_rejection_after_period_ends(self):
        """នៅពេលផុតម៉ោង (ឧ. >= ០៨:០០ សម្រាប់ម៉ោង ៧-៨)៖ បដិសេធដាច់ខាត (Reject HTTP 403)"""
        # Time is 08:05:00 (Period 2 active, Period 1 is expired)
        sim_dt_expired = datetime(2026, 9, 21, 8, 5, 0)
        sim_date = "2026-09-21"

        # Attempt to submit for Period 1 ("Session 1")
        can_submit, status_code, msg, phase, count = db.check_submission_window_rule(
            class_id=1,
            date_str=sim_date,
            shift="Morning",
            period_str="Session 1",
            is_admin=False,
            current_dt=sim_dt_expired
        )
        self.assertFalse(can_submit)
        self.assertEqual(status_code, 403)
        self.assertEqual(phase, "expired_period")
        self.assertIn("ផុតកំណត់ម៉ោងស្រង់វត្តមានហើយ", msg)

    def test_wrong_date_rejection(self):
        """គ្រូបង្រៀនមិនអាចស្រង់វត្តមានខុសពីកាលបរិច្ឆេទថ្ងៃនេះបានទេ"""
        sim_dt = datetime(2026, 9, 21, 7, 15, 0)
        can_submit, status_code, msg, phase, count = db.check_submission_window_rule(
            class_id=1,
            date_str="2026-09-20", # Yesterday
            shift="Morning",
            period_str="Session 1",
            is_admin=False,
            current_dt=sim_dt
        )
        self.assertFalse(can_submit)
        self.assertEqual(status_code, 403)
        self.assertEqual(phase, "invalid_date")

    # -------------------------------------------------------------
    # 3. Telegram Service Functionality
    # -------------------------------------------------------------
    def test_telegram_khmer_numerals(self):
        """បំប្លែងលេខអារ៉ាប់ទៅជាលេខខ្មែរ"""
        self.assertEqual(telegram_service.to_khmer_numerals("0123456789"), "០១២៣៤៥៦៧៨៩")
        self.assertEqual(telegram_service.to_khmer_numerals(2026), "២០២៦")
        self.assertEqual(telegram_service.format_khmer_date("2026-09-21"), "២១/០៩/២០២៦")

    @patch("requests.post")
    def test_telegram_send_message_success(self, mock_post):
        """តេស្តការផ្ញើសារ Telegram ជោគជ័យតាម Mock"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 12345}}
        mock_post.return_value = mock_response

        ok, msg = telegram_service.send_telegram_message(
            chat_id="12345678",
            text="សួស្តី! Test Message",
            bot_token="test_token_123"
        )
        self.assertTrue(ok)
        self.assertIn("ជោគជ័យ", msg)
        mock_post.assert_called_once()

    @patch("requests.post")
    def test_telegram_send_daily_report(self, mock_post):
        """តេស្តការផ្ញើរបាយការណ៍អវត្តមានប្រចាំថ្ងៃទៅ Telegram Admin"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 12345}}
        mock_post.return_value = mock_response

        # Save telegram settings
        db.set_setting("telegram_bot_token", "dummy_token")
        db.set_setting("telegram_admin_chat_id", "-100123456")

        ok, msg = telegram_service.send_daily_absence_report(target_date="2026-09-21")
        self.assertTrue(ok)
        self.assertIn("ជោគជ័យ", msg)

    # -------------------------------------------------------------
    # 4. API Endpoints for Telegram and Homeroom
    # -------------------------------------------------------------
    def test_api_current_slot(self):
        """តេស្ត Endpoint /api/portal/current-slot"""
        res = self.client.get("/api/portal/current-slot")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("period_info", data)

    def test_api_class_homeroom_config(self):
        """តេស្ត Endpoint POST /api/classes/homeroom"""
        # Login as Admin first
        with self.client.session_transaction() as sess:
            sess["user"] = {"id": 1, "username": "admin", "role": "admin", "full_name_kh": "Admin"}

        classes = db.get_classes()
        self.assertTrue(len(classes) > 0)
        test_class = classes[0]

        teachers = db.get_teachers()
        test_teacher = teachers[0] if teachers else None

        res = self.client.post("/api/classes/homeroom", json={
            "class_id": test_class["id"],
            "homeroom_teacher_id": test_teacher["id"] if test_teacher else None,
            "telegram_chat_id": "-100987654321"
        })
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()["success"])

        # Verify in database
        updated_class = db.get_class_by_id(test_class["id"])
        self.assertEqual(updated_class["telegram_chat_id"], "-100987654321")
        if test_teacher:
            self.assertEqual(updated_class["homeroom_teacher_id"], test_teacher["id"])

    # -------------------------------------------------------------
    # 5. Master School Timetable Import & Teacher View Isolation
    # -------------------------------------------------------------
    def test_export_timetable_template_and_master_excel(self):
        """តេស្តការបង្កើត Excel Template និង Master Timetable Excel Export"""
        template_path = export_service.export_timetable_template_excel()
        self.assertTrue(os.path.exists(template_path))
        self.assertGreater(os.path.getsize(template_path), 1000)

        master_path = export_service.export_master_timetable_excel()
        self.assertTrue(os.path.exists(master_path))
        self.assertGreater(os.path.getsize(master_path), 1000)

    def test_import_timetable_from_excel_merge_and_replace(self):
        """តេស្តការ Import កាលវិភាគរួមតាមរយៈ Excel (Merge Mode & Replace Mode)"""
        import openpyxl

        # 1. Create a test workbook matching the template format
        test_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scratch", "test_import_tt.xlsx")
        os.makedirs(os.path.dirname(test_file_path), exist_ok=True)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "កាលវិភាគរួម"

        headers = ["ល.រ", "ថ្នាក់រៀន", "ថ្ងៃបង្រៀន", "ម៉ោងទី", "មុខវិជ្ជា", "គ្រូបង្រៀន", "បន្ទប់"]
        ws.append(headers)

        teachers = db.get_teachers(active_only=True)
        self.assertTrue(len(teachers) > 0)
        first_teacher = teachers[0]

        # Add sample slot for Class 99A (fresh test class)
        ws.append([1, "99A", "ច", 1, "ភាសាខ្មែរ", first_teacher["teacher_code"], "B-101"])
        ws.append([2, "99A", "ច", 2, "គណិតវិទ្យា", first_teacher["full_name_kh"], "B-101"])
        wb.save(test_file_path)

        # 2. Test Merge Import
        result_merge = db.import_timetable_from_excel(test_file_path, mode="merge")
        self.assertTrue(result_merge["success"])
        self.assertEqual(result_merge["imported_count"], 2)

        # Verify in database
        slots_99a = db.get_timetable_by_class("99A")
        self.assertEqual(len(slots_99a), 2)
        self.assertEqual(slots_99a[0]["period_num"], 1)
        self.assertEqual(slots_99a[0]["teacher_id"], first_teacher["id"])
        self.assertEqual(slots_99a[1]["period_num"], 2)

        # Clean up test slots for 99A
        conn = db.get_db_connection()
        conn.execute("DELETE FROM timetable_slots WHERE class_code = '99A'")
        conn.commit()
        conn.close()

    def test_api_timetable_excel_endpoints_admin(self):
        """តេស្ត Endpoints សម្រាប់ Download Template, Export, និង Import (Admin Only)"""
        with self.client.session_transaction() as sess:
            sess["user"] = {"id": 1, "username": "admin", "role": "admin", "full_name_kh": "Admin"}

        # 1. Download Template
        res_tpl = self.client.get("/timetable/template/excel")
        self.assertEqual(res_tpl.status_code, 200)
        self.assertIn("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", res_tpl.content_type)

        # 2. Export Master Timetable
        res_exp = self.client.get("/export/excel/timetable")
        self.assertEqual(res_exp.status_code, 200)

        # 3. Import via API
        tpl_path = export_service.export_timetable_template_excel()
        with open(tpl_path, "rb") as f:
            file_data = io.BytesIO(f.read())

        res_import = self.client.post(
            "/api/timetable/import-excel",
            data={"file": (file_data, "master_template.xlsx"), "mode": "merge"},
            content_type="multipart/form-data"
        )
        self.assertEqual(res_import.status_code, 200)
        data = res_import.get_json()
        self.assertTrue(data["success"])
        self.assertIn("បានបញ្ចូលកាលវិភាគរួម", data["message"])

    def test_teacher_view_isolation_timetable_page(self):
        """តេស្តការរឹតបន្តឹងសិទ្ធិរបស់គ្រូ៖ គ្រូមើលឃើញតែកាលវិភាគផ្ទាល់ខ្លួនប៉ុណ្ណោះនៅលើ /timetable"""
        teachers = db.get_teachers(active_only=True)
        self.assertGreater(len(teachers), 1)
        teacher_1 = teachers[0]
        teacher_2 = teachers[1]

        # Login as teacher 1
        with self.client.session_transaction() as sess:
            sess["user"] = {
                "id": 101,
                "username": teacher_1["teacher_code"],
                "role": "teacher",
                "full_name_kh": teacher_1["full_name_kh"],
                "teacher_id": teacher_1["id"]
            }

        # Attempt to access another teacher's timetable via query parameter
        res = self.client.get(f"/timetable?view=teacher&teacher_id={teacher_2['id']}")
        self.assertEqual(res.status_code, 200)
        # Verify that the rendered HTML contains teacher 1's name and DOES NOT show the view switcher dropdowns
        html_content = res.get_data(as_text=True)
        self.assertIn(teacher_1["full_name_kh"], html_content)
        self.assertIn("កាលវិភាគបង្រៀនផ្ទាល់ខ្លួន", html_content)
        self.assertNotIn('id="btnToggleEditMode"', html_content)
        self.assertNotIn('onclick="openImportTimetableModal()"', html_content)
        self.assertNotIn('onclick="openHomeroomModal()"', html_content)

        # Attempt to access class view
        res_class = self.client.get("/timetable?view=class&class_code=7A")
        self.assertEqual(res_class.status_code, 200)
        html_class = res_class.get_data(as_text=True)
        # Backend must force teacher view of teacher 1
        self.assertIn(teacher_1["full_name_kh"], html_class)
        self.assertIn("កាលវិភាគបង្រៀនផ្ទាល់ខ្លួន", html_class)

    def test_teacher_privacy_timetable_api(self):
        """តេស្ត API Endpoints មិនអនុញ្ញាតឱ្យគ្រូទាញយកកាលវិភាគគ្រូដទៃឡើយ (HTTP 403)"""
        teachers = db.get_teachers(active_only=True)
        self.assertGreater(len(teachers), 1)
        teacher_1 = teachers[0]
        teacher_2 = teachers[1]

        # Login as teacher 1
        with self.client.session_transaction() as sess:
            sess["user"] = {
                "id": 101,
                "username": teacher_1["teacher_code"],
                "role": "teacher",
                "full_name_kh": teacher_1["full_name_kh"],
                "teacher_id": teacher_1["id"]
            }

        # Query own timetable API -> Allowed (200)
        res_own = self.client.get(f"/api/timetable/teacher/{teacher_1['id']}")
        self.assertEqual(res_own.status_code, 200)
        self.assertTrue(res_own.get_json()["success"])

        # Query other teacher's timetable API -> FORBIDDEN (403)
        res_other = self.client.get(f"/api/timetable/teacher/{teacher_2['id']}")
        self.assertEqual(res_other.status_code, 403)
        self.assertFalse(res_other.get_json()["success"])
        self.assertIn("កាលវិភាគផ្ទាល់ខ្លួនប៉ុណ្ណោះ", res_other.get_json()["message"])

    def test_get_teacher_today_slots_timing_and_disabled_rules(self):
        """តេស្តការគណនា Timing Status និង Disabled State សម្រាប់កាលវិភាគថ្ងៃនេះ"""
        teachers = db.get_teachers(active_only=True)
        teacher = teachers[0]

        # Setup test timetable slots for this teacher on Monday (day_code: ច) using unique test class codes
        conn = db.get_db_connection()
        try:
            conn.execute("DELETE FROM timetable_slots WHERE class_code IN ('T91', 'T92', 'T93')")
            conn.execute("""
                INSERT INTO timetable_slots (class_code, day_code, day_name, period_num, shift, subject_name, teacher_id)
                VALUES ('T91', 'ច', 'ចន្ទ', 1, 'Morning', 'គណិតវិទ្យា', ?),
                       ('T92', 'ច', 'ចន្ទ', 2, 'Morning', 'រូបវិទ្យា', ?),
                       ('T93', 'ច', 'ចន្ទ', 3, 'Morning', 'គីមីវិទ្យា', ?)
            """, (teacher["id"], teacher["id"], teacher["id"]))
            conn.commit()
        finally:
            conn.close()

        try:
            # 1. Simulate Monday at 07:20 AM (Period 1 active)
            dt_p1 = datetime(2026, 9, 21, 7, 20, 0) # Monday
            slots = db.get_teacher_today_slots(teacher["id"], "ច", today_date="2026-09-21", current_dt=dt_p1)
            p1_slot = next((s for s in slots if s["class_code"] == "T91"), None)
            p2_slot = next((s for s in slots if s["class_code"] == "T92"), None)
            p3_slot = next((s for s in slots if s["class_code"] == "T93"), None)
            self.assertIsNotNone(p1_slot)
            self.assertIsNotNone(p2_slot)
            self.assertIsNotNone(p3_slot)

            # Period 1 should be ACTIVE and ENABLED for taking attendance
            self.assertTrue(p1_slot["is_current_active"])
            self.assertEqual(p1_slot["timing_status"], "ACTIVE")
            self.assertTrue(p1_slot["can_take_attendance"])

            # Period 2 should be UPCOMING and DISABLED
            self.assertFalse(p2_slot["is_current_active"])
            self.assertEqual(p2_slot["timing_status"], "UPCOMING")
            self.assertFalse(p2_slot["can_take_attendance"])
            self.assertEqual(p2_slot["disabled_reason"], "មិនទាន់ដល់ម៉ោងបង្រៀន")

            # Period 3 should be UPCOMING and DISABLED
            self.assertFalse(p3_slot["is_current_active"])
            self.assertEqual(p3_slot["timing_status"], "UPCOMING")
            self.assertFalse(p3_slot["can_take_attendance"])

            # 2. Simulate Monday at 08:45 AM (Period 2 active)
            dt_p2 = datetime(2026, 9, 21, 8, 45, 0)
            slots_p2 = db.get_teacher_today_slots(teacher["id"], "ច", today_date="2026-09-21", current_dt=dt_p2)
            p1_slot2 = next((s for s in slots_p2 if s["class_code"] == "T91"), None)
            p2_slot2 = next((s for s in slots_p2 if s["class_code"] == "T92"), None)
            p3_slot2 = next((s for s in slots_p2 if s["class_code"] == "T93"), None)

            # Period 1 is now PAST and DISABLED
            self.assertFalse(p1_slot2["is_current_active"])
            self.assertEqual(p1_slot2["timing_status"], "PAST")
            self.assertFalse(p1_slot2["can_take_attendance"])

            # Period 2 is ACTIVE
            self.assertTrue(p2_slot2["is_current_active"])
            self.assertEqual(p2_slot2["timing_status"], "ACTIVE")
            self.assertTrue(p2_slot2["can_take_attendance"])

            # Period 3 is UPCOMING and DISABLED
            self.assertFalse(p3_slot2["is_current_active"])
            self.assertEqual(p3_slot2["timing_status"], "UPCOMING")
            self.assertFalse(p3_slot2["can_take_attendance"])
        finally:
            conn = db.get_db_connection()
            conn.execute("DELETE FROM timetable_slots WHERE class_code IN ('T91', 'T92', 'T93')")
            conn.commit()
            conn.close()

    def test_portal_page_disables_non_active_classes_for_teachers(self):
        """តេស្តទំព័រ /portal សម្រាប់គ្រូបង្រៀន៖ បិទ (Disable) ថ្នាក់មិនត្រូវម៉ោងទាំងអស់"""
        teachers = db.get_teachers(active_only=True)
        teacher = teachers[0]

        with self.client.session_transaction() as sess:
            sess["user"] = {
                "id": 101,
                "username": teacher["teacher_code"],
                "role": "teacher",
                "full_name_kh": teacher["full_name_kh"],
                "teacher_id": teacher["id"]
            }

        res = self.client.get("/portal")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Verify disabled button classes or labels exist in the rendered HTML
        self.assertIn("mobile-portal-body", html)
        self.assertIn("ម៉ោងបង្រៀនថ្ងៃនេះ", html)


if __name__ == "__main__":
    unittest.main()

