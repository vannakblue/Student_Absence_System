"""
Unit & Integration Tests for PWA, Service Worker, and Android APK Download
"""

import unittest
import os
from app import app

class TestPwaAndApk(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()

    def test_service_worker_route(self):
        """ផ្ទៀងផ្ទាត់ថា /sw.js បម្រើ JavaScript និងមាន Service-Worker-Allowed header"""
        response = self.client.get("/sw.js")
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/javascript", response.content_type)
        self.assertEqual(response.headers.get("Service-Worker-Allowed"), "/")
        self.assertIn(b"kkhs-portal", response.data)

    def test_manifest_route(self):
        """ផ្ទៀងផ្ទាត់ថា /manifest.json បម្រើ JSON Manifest ត្រឹមត្រូវ"""
        response = self.client.get("/manifest.json")
        self.assertIn(b"/portal", response.data)
        self.assertIn(b"standalone", response.data)

    def test_apk_download_route(self):
        """ផ្ទៀងផ្ទាត់ការទាញយក APK តាមរយៈ /download/apk និង /portal/apk"""
        for url in ["/download/apk", "/portal/apk"]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content_type, "application/vnd.android.package-archive")
            self.assertIn("StudentAbsenceSystem.apk", response.headers.get("Content-Disposition", ""))
            self.assertGreater(len(response.data), 1000)

    def test_qr_routes(self):
        """ផ្ទៀងផ្ទាត់ការបង្កើតរូបភាព QR Code សម្រាប់ APK និង Portal"""
        for url in ["/api/qr/apk", "/api/qr/portal"]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertIn("image/png", response.content_type)
            self.assertTrue(response.data.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_pwa_icons_exist(self):
        """ផ្ទៀងផ្ទាត់វត្តមានរូបភាព Icons គុណភាពខ្ពស់សម្រាប់ PWA និង Android"""
        base_dir = app.root_path
        icons = [
            "static/icons/icon-192.png",
            "static/icons/icon-512.png",
            "static/icons/icon-maskable.png",
            "static/icons/apple-touch-icon.png",
            "static/icons/favicon.png"
        ]
        for icon in icons:
            full_path = os.path.join(base_dir, icon)
            self.assertTrue(os.path.exists(full_path), f"Missing icon: {icon}")
            self.assertGreater(os.path.getsize(full_path), 500)

if __name__ == "__main__":
    unittest.main()
