"""
Unit Tests for KKHS Cloud Timetable Synchronization (kkhs.web.app)
"""

import unittest
import json
import database as db
import kkhs_sync_service
from app import app


class TestKkhsSync(unittest.TestCase):

    def setUp(self):
        self.app = app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        db.init_db()
        db.init_default_users()

    def test_01_test_kkhs_connection(self):
        """សាកល្បងការតភ្ជាប់ទៅកាន់ Firebase RTDB របស់ kkhs.web.app"""
        res = kkhs_sync_service.test_kkhs_connection()
        self.assertTrue(res["success"], f"Connection failed: {res.get('message')}")
        self.assertIn("academic_year", res)
        print("[OK] Connection test to kkhs.web.app succeeded.")

    def test_02_sync_timetable_from_kkhs(self):
        """សាកល្បង Sync កាលវិភាគរួមទាំងមូលពី kkhs.web.app"""
        res = kkhs_sync_service.sync_kkhs_timetable(mode="merge")
        self.assertTrue(res["success"], f"Sync failed: {res.get('message')}")
        self.assertGreaterEqual(res["synced_slots"], 1000, "Should sync at least 1,000 slots")
        self.assertGreaterEqual(res["synced_teachers"], 100, "Should sync at least 100 teachers")
        self.assertGreaterEqual(res["synced_classes"], 40, "Should sync 40 classes")
        print(f"[OK] Successfully synced: {res['synced_slots']} slots, {res['synced_teachers']} teachers, {res['synced_classes']} classes.")

    def test_03_api_sync_endpoints(self):
        """សាកល្បង API Endpoints សម្រាប់ Admin"""
        # Login as Admin
        res_login = self.client.post("/login", data={"username": "admin", "password": "admin123"})
        self.assertEqual(res_login.status_code, 302)

        # Test connection endpoint
        res_conn = self.client.post("/api/sync/test-kkhs")
        self.assertEqual(res_conn.status_code, 200)
        data_conn = json.loads(res_conn.data)
        self.assertTrue(data_conn["success"])

        # Test sync endpoint
        res_sync = self.client.post("/api/sync/kkhs", json={"mode": "merge"})
        self.assertEqual(res_sync.status_code, 200)
        data_sync = json.loads(res_sync.data)
        self.assertTrue(data_sync["success"])
        print("[OK] API Endpoints /api/sync/test-kkhs and /api/sync/kkhs verified.")

    def test_04_teacher_portal_timetable_access(self):
        """ផ្ទៀងផ្ទាត់ថាគ្រូអាច Login និងមើលកាលវិភាគដើម្បីស្រង់វត្តមានបាន"""
        # Teacher 'កាន ដាវី' (Code: 2890800096)
        res_login = self.client.post("/login", data={"username": "2890800096", "password": "123456"})
        self.assertEqual(res_login.status_code, 302)
        self.assertIn("/portal", res_login.location)

        # Get portal page
        res_portal = self.client.get(res_login.location)
        self.assertEqual(res_portal.status_code, 200)
        html = res_portal.get_data(as_text=True)
        self.assertIn("កាន ដាវី", html)
        self.assertIn("ម៉ោងបង្រៀនថ្ងៃនេះ", html)
        print("[OK] Teacher can login and view timetable on portal for attendance taking.")


if __name__ == "__main__":
    unittest.main()
