"""
Unit Tests for Cloud Firestore Synchronization and API Endpoints
"""

import unittest
import json
from unittest.mock import patch, MagicMock
import database as db
import firestore_sync_service
from app import app


class TestFirestoreSync(unittest.TestCase):

    def setUp(self):
        self.app = app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        db.init_db()
        db.init_default_users()

    def test_01_api_access_control(self):
        """ផ្ទៀងផ្ទាត់ថា Firestore API endpoints ត្រូវបានការពារដោយ Admin login"""
        res1 = self.client.post("/api/sync/test-firestore")
        self.assertIn(res1.status_code, [401, 302])

        res2 = self.client.post("/api/sync/sheets-to-firestore")
        self.assertIn(res2.status_code, [401, 302])

        res3 = self.client.post("/api/sync/firestore-to-local")
        self.assertIn(res3.status_code, [401, 302])
        print("[OK] Access control verified for Firestore endpoints.")

    @patch("firestore_sync_service.get_firestore_client")
    def test_02_firestore_mocked_sync(self, mock_get_client):
        """សាកល្បងដំណើរការ Firestore Sync ជាមួយ Mocked Client"""
        mock_client = MagicMock()
        mock_client.project = "schoolsm"
        mock_get_client.return_value = mock_client
        mock_batch = MagicMock()
        mock_client.batch.return_value = mock_batch

        # Login as Admin
        self.client.post("/login", data={"username": "admin", "password": "admin123"})

        # Call test-firestore with mock
        res_test = self.client.post("/api/sync/test-firestore")
        self.assertEqual(res_test.status_code, 200)
        data_test = res_test.get_json()
        self.assertTrue(data_test["success"])
        print("[OK] Mocked test-firestore passed.")

        # Call sheets-to-firestore with mock
        res_sync = self.client.post("/api/sync/sheets-to-firestore")
        self.assertEqual(res_sync.status_code, 200)
        data_sync = res_sync.get_json()
        self.assertTrue(data_sync["success"])
        self.assertGreaterEqual(data_sync.get("synced_slots", 0), 1000)
        print(f"[OK] Mocked sheets-to-firestore passed with {data_sync['synced_slots']} slots synced.")

    def test_03_firestore_missing_db_graceful_handling(self):
        """ផ្ទៀងផ្ទាត់ថាប្រព័ន្ធផ្តល់សារណែនាំត្រឹមត្រូវពេល Firestore មិនទាន់ចុច Create Database លើ Console"""
        self.client.post("/login", data={"username": "admin", "password": "admin123"})
        res = self.client.post("/api/sync/test-firestore")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        if not data["success"] and data.get("needs_creation"):
            self.assertIn("Create database", data["message"])
            self.assertIn("console.firebase.google.com", data["message"])
            print("[OK] Graceful guidance message verified for uncreated Firestore database.")


if __name__ == "__main__":
    unittest.main()
