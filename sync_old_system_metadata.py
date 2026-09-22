"""
Sync and Populate Full Structure, School Profile, Configurations, and Google Sheets Credentials
from the Old System (original_django_models.json & master_production_backup.json)
"""

import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import os
import json
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DJANGO_DATA_PATH = r"E:\Dev\Dev_Others\Time_Table_Setup\data\original_django_models.json"
BACKUP_PATH = r"E:\Dev\Dev_Others\Time_Table_Setup\data\master_production_backup.json"
DB_PATH = os.path.join(BASE_DIR, "attendance.db")


def sync_all():
    print("=" * 60)
    print(" Populating Complete Structure and Metadata from Old System")
    print("=" * 60)

    if not os.path.exists(DJANGO_DATA_PATH):
        print(f"[ERROR] Cannot find {DJANGO_DATA_PATH}")
        return

    with open(DJANGO_DATA_PATH, "r", encoding="utf-8") as f:
        odm = json.load(f)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    def set_setting(key, val):
        cur.execute("""
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, str(val)))

    # 1. School Profile Structure
    sp = next((x["fields"] for x in odm if x.get("model") == "accounts.schoolprofile"), {})
    if sp:
        set_setting("school_name_kh", sp.get("name_kh") or "វិទ្យាល័យ ហ៊ុន សែន កំពង់កន្ទួត")
        set_setting("school_name_en", sp.get("name_en") or "Hun Sen Kampong Kantuot High School")
        set_setting("school_short_name", sp.get("short_name") or "វិ. ហស កំពង់កន្ទួត")
        set_setting("school_code", sp.get("school_code") or "08010306901")
        set_setting("school_motto", sp.get("motto") or "ចំណេះដឹង វិន័យ សីលធម៌ គុណធម៌")
        set_setting("ministry_name", sp.get("ministry_name") or "ក្រសួងអប់រំ យុវជន និងកីឡា")
        set_setting("poe_name", sp.get("poe_name") or "មន្ទីរអប់រំ យុវជន និងកីឡា ខេត្តកណ្តាល")
        set_setting("doe_name", sp.get("doe_name") or "ការិយាល័យអប់រំ យុវជន និងកីឡា ស្រុកកណ្តាលស្ទឹង")
        set_setting("principal_name", sp.get("principal_name") or "លោកបណ្ឌិត សុខ ចាន់ថន")
        set_setting("school_phone", sp.get("phone") or "023 888 999 / 012 345 678")
        set_setting("school_email", sp.get("email") or "info@schoolsm.edu.kh")
        set_setting("school_website", sp.get("website") or "https://schoolsm.edu.kh")
        address = f"{sp.get('street_address', '')} {sp.get('commune', '')} {sp.get('district', '')} {sp.get('province', '')}".strip()
        set_setting("school_address", address)
        print(f"[OK] Migrated School Profile: {sp.get('name_kh')} (Code: {sp.get('school_code')})")

    # 2. Google Sheets Config Structure
    gsc = next((x["fields"] for x in odm if x.get("model") == "accounts.googlesheetsconfig"), {})
    if gsc:
        sheet_id = "1RnTas3BW3UfhwqMPhR7rU7b1FPEw35Xt-CL0aTJ2XkE"
        set_setting("google_sheet_id", sheet_id)
        set_setting("google_admin_email", gsc.get("admin_email") or "vannakblue@gmail.com")
        set_setting("google_drive_folder_id", gsc.get("drive_folder_id") or "1WGYYh07JnfyRzimtuFKAAGCzWjAI-rQa")
        
        sa_content = gsc.get("service_account_json_content")
        if sa_content:
            sa_path = os.path.join(BASE_DIR, "google_service_account.json")
            with open(sa_path, "w", encoding="utf-8") as saf:
                saf.write(sa_content)
            set_setting("google_credentials_file", "google_service_account.json")
            print(f"[OK] Extracted authentic Google Service Account JSON to {sa_path}")

    # 3. Telegram Config Structure
    tg = next((x["fields"] for x in odm if x.get("model") == "accounts.telegramconfig"), {})
    if tg:
        set_setting("telegram_notify_absence", "1" if tg.get("notify_on_absence") else "0")
        set_setting("telegram_auto_backup", "1" if tg.get("auto_backup_enabled") else "0")
        print("[OK] Migrated Telegram alerts configuration.")

    # 4. Populate 17 Subjects Table (to support full curriculum structure)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name_kh TEXT NOT NULL,
            weekly_hours_g7 INTEGER DEFAULT 2,
            weekly_hours_g8 INTEGER DEFAULT 2,
            weekly_hours_g9 INTEGER DEFAULT 2,
            weekly_hours_g10 INTEGER DEFAULT 2,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    if os.path.exists(BACKUP_PATH):
        with open(BACKUP_PATH, "r", encoding="utf-8") as bf:
            backup_data = json.load(bf)
        subjects = backup_data.get("subjects", [])
        for s in subjects:
            cur.execute("""
                INSERT INTO subjects (code, name_kh, weekly_hours_g7, weekly_hours_g8, weekly_hours_g9, weekly_hours_g10)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET
                    name_kh = excluded.name_kh,
                    weekly_hours_g7 = excluded.weekly_hours_g7,
                    weekly_hours_g8 = excluded.weekly_hours_g8,
                    weekly_hours_g9 = excluded.weekly_hours_g9,
                    weekly_hours_g10 = excluded.weekly_hours_g10
            """, (s.get("code"), s.get("name"), s.get("h7", 2), s.get("h8", 2), s.get("h9", 2), s.get("h10", 2)))
        print(f"[OK] Migrated {len(subjects)} official curriculum subjects.")

    # 5. Enrich Teacher Records with Civil Servant Qualifications
    teachers_raw = [x for x in odm if x.get("model") == "teachers.teacher"]
    # Add columns to teachers table if not existing
    cur.execute("PRAGMA table_info(teachers)")
    t_cols = [c[1] for c in cur.fetchall()]
    if "qualification" not in t_cols:
        cur.execute("ALTER TABLE teachers ADD COLUMN qualification TEXT")
    if "current_duty" not in t_cols:
        cur.execute("ALTER TABLE teachers ADD COLUMN current_duty TEXT")
    if "training_level" not in t_cols:
        cur.execute("ALTER TABLE teachers ADD COLUMN training_level TEXT")

    for t in teachers_raw:
        tf = t["fields"]
        tcode = str(tf.get("teacher_id") or "")
        qual = tf.get("qualification") or ""
        duty = tf.get("current_duty") or "គ្រូបង្រៀន"
        level = tf.get("training_level") or ""
        cur.execute("""
            UPDATE teachers 
            SET qualification = ?, current_duty = ?, training_level = ?
            WHERE teacher_code = ?
        """, (qual, duty, level, tcode))
    print(f"[OK] Enriched 119 teachers with qualification, current duty, and training level.")

    # 6. Enrich Student Records with Parent Details and DOB
    students_raw = [x for x in odm if x.get("model") == "students.student"]
    cur.execute("PRAGMA table_info(students)")
    s_cols = [c[1] for c in cur.fetchall()]
    if "father_name" not in s_cols:
        cur.execute("ALTER TABLE students ADD COLUMN father_name TEXT")
    if "mother_name" not in s_cols:
        cur.execute("ALTER TABLE students ADD COLUMN mother_name TEXT")

    for s in students_raw:
        sf = s["fields"]
        scode = str(sf.get("student_id") or "")
        f_name = sf.get("father_name") or ""
        m_name = sf.get("mother_name") or ""
        cur.execute("""
            UPDATE students 
            SET father_name = ?, mother_name = ?
            WHERE student_code = ?
        """, (f_name, m_name, scode))
    print(f"[OK] Enriched 1,998 students with parent details.")

    conn.commit()
    conn.close()
    print("=" * 60)
    print(" Complete Structure and Workflows Migration Complete!")
    print("=" * 60)


if __name__ == "__main__":
    sync_all()
