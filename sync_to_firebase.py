"""
Sync Local SQLite Database (attendance.db) to Firebase Realtime Database
Under /absence_system for the Cloud Web Client & Mobile PWA
"""

import os
import sys
import json
import sqlite3
import datetime
import urllib.request

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(PROJECT_DIR, "attendance.db")
FIREBASE_URL = "https://school-timetable-67972-default-rtdb.asia-southeast1.firebasedatabase.app/absence_system.json"

def sync_sqlite_to_firebase():
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] Database file not found at: {DB_PATH}")
        return False

    print("=" * 65)
    print("  [INFO] Starting Sync from SQLite to Firebase RTDB...")
    print(f"  [DB] {DB_PATH}")
    print(f"  [URL] {FIREBASE_URL}")
    print("=" * 65)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # 1. Fetch Classes
    c.execute("SELECT id, class_name, grade_level, shift, room_number, academic_year FROM classes ORDER BY grade_level, class_name")
    classes = [dict(row) for row in c.fetchall()]
    print(f"  [OK] Classes: {len(classes)}")

    # 2. Fetch Teachers
    c.execute("SELECT id, teacher_code, full_name_kh, full_name_en, gender, phone, email, subject, total_hours_weekly, status FROM teachers ORDER BY full_name_kh")
    teachers = [dict(row) for row in c.fetchall()]
    print(f"  [OK] Teachers: {len(teachers)}")

    # 3. Fetch Students (with class_name)
    c.execute("""
        SELECT s.id, s.student_code, s.full_name_kh, s.full_name_en, s.gender, s.dob,
               s.class_id, c.class_name, s.parent_name, s.parent_phone, s.status
        FROM students s
        LEFT JOIN classes c ON s.class_id = c.id
        WHERE LOWER(s.status) = 'active' OR s.status IS NULL
        ORDER BY c.class_name, s.full_name_kh
    """)
    all_students = [dict(row) for row in c.fetchall()]
    students_by_class = {}
    for s in all_students:
        cls = s["class_name"] or "Unknown"
        if cls not in students_by_class:
            students_by_class[cls] = []
        students_by_class[cls].append(s)
    print(f"  [OK] Students: {len(all_students)} (across {len(students_by_class)} classes)")

    # 4. Fetch Timetable Slots
    c.execute("""
        SELECT id, class_id, class_code, day_code, day_name, period_num, shift,
               subject_code, subject_name, teacher_id, teacher_code, teacher_name, room_number
        FROM timetable_slots
        ORDER BY class_code, day_code, period_num
    """)
    timetable_slots = [dict(row) for row in c.fetchall()]
    print(f"  [OK] Timetable slots: {len(timetable_slots)}")

    # 5. Fetch Users (for authentication in the client)
    c.execute("SELECT id, username, plain_password_hint, password_hash, role, full_name_kh, teacher_id, phone, is_active FROM users WHERE is_active = 1")
    users = [dict(row) for row in c.fetchall()]
    print(f"  [OK] Users: {len(users)}")

    # 6. Fetch Settings
    settings = {}
    try:
        c.execute("SELECT key, value FROM settings")
        for row in c.fetchall():
            settings[row["key"]] = row["value"]
    except Exception:
        pass

    conn.close()

    payload = {
        "classes": classes,
        "teachers": teachers,
        "students_by_class": students_by_class,
        "students_count": len(all_students),
        "timetable_slots": timetable_slots,
        "users": users,
        "settings": settings,
        "last_synced": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    print("\n  [INFO] Uploading payload to Firebase Cloud Database...")
    json_data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        FIREBASE_URL,
        data=json_data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="PUT"
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            if response.status == 200:
                print("\n" + "=" * 65)
                print("  [SUCCESS] SYNC TO FIREBASE REALTIME DATABASE COMPLETED!")
                print(f"  Students: {len(all_students)}")
                print(f"  Teachers: {len(teachers)}")
                print(f"  Classes: {len(classes)}")
                print(f"  Timetable slots: {len(timetable_slots)}")
                print(f"  Last synced: {payload['last_synced']}")
                print("=" * 65)
                return True
            else:
                print(f"  [ERROR] Firebase HTTP status: {response.status}")
                return False
    except Exception as e:
        print(f"  [ERROR] Connection error to Firebase: {e}")
        return False

if __name__ == "__main__":
    success = sync_sqlite_to_firebase()
    sys.exit(0 if success else 1)
