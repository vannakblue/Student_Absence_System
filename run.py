"""
ប្រព័ន្ធគ្រប់គ្រងអវត្តមានសិស្ស និងគ្រូបង្រៀន (Student & Teacher Absence Management System)
Application Runner with Auto Browser Launch & Network Support
"""

import os
import sys
import time
import socket
import webbrowser
import threading
import argparse

# Ensure UTF-8 output encoding for Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app import app
from database import init_db
from seed_data import seed_all


def get_local_ip():
    """ស្វែងរកអាសយដ្ឋាន IP ក្នុងបណ្តាញមូលដ្ឋាន (LAN / Wi-Fi IP)"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def open_browser(target_url, delay=1.2):
    """បើក Web Browser ដោយស្វ័យប្រវត្តិតាម URL ដែលបានកំណត់"""
    time.sleep(delay)
    try:
        print(f"\n🌐 កំពុងបើក Web Browser ទៅកាន់: {target_url}")
        webbrowser.open(target_url)
    except Exception as e:
        print(f"⚠️ មិនអាចបើក Browser ដោយស្វ័យប្រវត្តិបានទេ: {e}")


def main():
    parser = argparse.ArgumentParser(description="Student & Teacher Absence Management System Runner")
    parser.add_argument("--port", type=int, default=5000, help="Port to run the web server on (default: 5000)")
    parser.add_argument("--portal", action="store_true", help="Directly open the Teacher Mobile Portal in browser")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open web browser")
    args = parser.parse_args()

    # 1. Initialize Database & Seed Sample Data if needed
    init_db()
    seed_all()

    local_ip = get_local_ip()
    port = args.port

    local_url = f"http://127.0.0.1:{port}"
    portal_url = f"{local_url}/portal"
    lan_url = f"http://{local_ip}:{port}"
    apk_url = f"{lan_url}/download/apk"

    target_open_url = portal_url if args.portal else local_url

    print("========================================================================")
    print(" 🏫 Student & Teacher Absence Management System")
    print("    ប្រព័ន្ធគ្រប់គ្រងអវត្តមានសិស្ស និងគ្រូបង្រៀន (វិទ្យាល័យ)")
    print("========================================================================")
    print(f" 💻 Web Browser (កុំព្យូទ័រ):      {local_url}")
    print(f" 📱 Teacher Mobile Portal:        {portal_url}")
    print(f" 🌐 Wi-Fi / Mobile (ទូរសព្ទដៃ):   {lan_url}")
    print(f" 📥 Download APK (Android):       {apk_url}")
    print("------------------------------------------------------------------------")
    print(" 🔑 គណនីគំរូសម្រាប់សាកល្បង (Sample Accounts):")
    print("    - Admin:    Username: admin       | Password: 1627")
    print("    - គ្រូបង្រៀន: Username: 2890800096  | Password: 123456")
    print("------------------------------------------------------------------------")
    print(" ℹ️ ចុចបញ្ជា Ctrl + C ក្នុងផ្ទាំងនេះដើម្បីបញ្ឈប់ដំណើរការ Web Server")
    print("========================================================================")

    # 2. Launch browser in a background daemon thread
    if not args.no_browser:
        threading.Thread(target=open_browser, args=(target_open_url,), daemon=True).start()

    # 3. Start Flask Web Server
    try:
        app.run(host="0.0.0.0", port=port, debug=False)
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user.")
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
