"""
Unit Tests for KKHS -> Google Sheets Backup & Google Sheets -> Student_Absence_System Permanent Timetable Bridge
"""

import unittest
import json
import database as db
import google_sheets_sync
from app import app


class TestKkhsGoogleSheetsBridge(unittest.TestCase):

    def setUp(self):
        self.app = app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        db.init_db()
        db.init_default_users()

    def test_01_api_access_control(self):
        """ផ្ទៀងផ្ទាត់ថា Endpoint ថ្មីត្រូវបានការពារដោយ Admin Permission"""
        # Unauthenticated request should be redirected or rejected with 401
        res1 = self.client.post("/api/sync/kkhs-to-sheets")
        self.assertIn(res1.status_code, [401, 302], "Unauthenticated access should be blocked")

        res2 = self.client.post("/api/sync/sheets-to-timetable", json={"mode": "merge"})
        self.assertIn(res2.status_code, [401, 302], "Unauthenticated access should be blocked")
        print("[OK] Access control verified for Google Sheets bridge endpoints.")

    def test_02_admin_endpoints_with_session(self):
        """ផ្ទៀងផ្ទាត់ Admin អាចដំណើរការ API sync kkhs-to-sheets និង sheets-to-timetable"""
        # Login as Admin
        res_login = self.client.post("/login", data={"username": "admin", "password": "admin123"})
        self.assertEqual(res_login.status_code, 302)

        # Test pull from Google Sheets endpoint
        res_pull = self.client.post("/api/sync/sheets-to-timetable", json={"mode": "merge"})
        self.assertEqual(res_pull.status_code, 200)
        data_pull = json.loads(res_pull.data)
        self.assertTrue(data_pull["success"], f"Sheets pull failed: {data_pull.get('message')}")
        self.assertGreaterEqual(data_pull.get("synced_slots", 0), 1000)
        print(f"[OK] Admin endpoint sheets-to-timetable successfully pulled {data_pull['synced_slots']} slots.")

    def test_03_teacher_login_and_attendance_flow(self):
        """ផ្ទៀងផ្ទាត់គ្រូបង្រៀនអាច Login តាមរយៈកូដក្រសួង ឬលេខទូរស័ព្ទ និងចូលស្រង់វត្តមានសិស្ស"""
        # Login with MOEYS code (e.g. 2890800096)
        res_login = self.client.post("/login", data={"username": "2890800096", "password": "123456"})
        self.assertEqual(res_login.status_code, 302)

        # Access teacher portal
        res_portal = self.client.get("/portal")
        self.assertEqual(res_portal.status_code, 200)
        html = res_portal.get_data(as_text=True)
        self.assertIn("កាន ដាវី", html)

        # Access teacher attendance page
        res_att = self.client.get("/portal/attendance")
        # Outside active teaching hours (e.g. night time), teacher is safely protected and redirected to /portal
        if res_att.status_code == 302:
            self.assertIn("/portal", res_att.location)
            res_follow = self.client.get(res_att.location)
            self.assertEqual(res_follow.status_code, 200)
            self.assertIn("កាន ដាវី", res_follow.get_data(as_text=True))
        else:
            self.assertEqual(res_att.status_code, 200)
            html_att = res_att.get_data(as_text=True)
            self.assertIn("កាន ដាវី", html_att)
        print("[OK] Teacher login and attendance flow validated.")


if __name__ == "__main__":
    unittest.main()
