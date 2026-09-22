"""
ប្រព័ន្ធគ្រប់គ្រងអវត្តមានសិស្ស និងគ្រូបង្រៀន (Student & Teacher Absence Management System)
Application Runner with Auto Browser Launch
"""

import os
import sys
import time
import webbrowser
import threading

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


def open_browser():
    time.sleep(1.2)
    webbrowser.open("http://127.0.0.1:5000")


if __name__ == "__main__":
    print("------------------------------------------------------------------")
    print(" Student & Teacher Absence Management System")
    print(" ប្រព័ន្ធគ្រប់គ្រងអវត្តមានសិស្ស និងគ្រូបង្រៀន (SchoolSM)")
    print(" Running on: http://localhost:5000")
    print("------------------------------------------------------------------")

    # 1. Initialize DB & Seed if empty
    init_db()
    seed_all()

    # 2. Open browser in background thread
    threading.Thread(target=open_browser, daemon=True).start()

    # 3. Start Flask web server
    app.run(host="0.0.0.0", port=5000, debug=False)
