"""
Cloud Firestore Synchronization Service for Student_Absence_System
តភ្ជាប់ និងធ្វើសមកាលកម្មទិន្នន័យរវាង Google Sheets, Cloud Firestore និង Local SQLite Database
"""

import os
import json
import logging
from datetime import datetime
import google.auth
from google.oauth2 import service_account
from google.cloud import firestore
import database as db
import google_sheets_sync

logger = logging.getLogger("firestore_sync")

# Cached firestore client
_firestore_client = None


def get_firestore_client(force_refresh=False):
    """
    បង្កើត ឬទាញយក Google Cloud Firestore Client
    គាំទ្រទាំង file 'google_service_account.json' និង environment variable 'GOOGLE_SERVICE_ACCOUNT_JSON'
    """
    global _firestore_client
    if _firestore_client is not None and not force_refresh:
        return _firestore_client

    env_creds = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if env_creds:
        try:
            creds_dict = json.loads(env_creds)
            credentials = service_account.Credentials.from_service_account_info(creds_dict)
            project_id = creds_dict.get("project_id", "schoolsm")
            _firestore_client = firestore.Client(project=project_id, credentials=credentials)
            return _firestore_client
        except Exception as e:
            logger.warning(f"Failed to load Firestore credentials from env: {e}")

    creds_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "google_service_account.json")
    if os.path.exists(creds_path):
        with open(creds_path, "r", encoding="utf-8") as f:
            creds_dict = json.load(f)
        credentials = service_account.Credentials.from_service_account_info(creds_dict)
        project_id = creds_dict.get("project_id", "schoolsm")
        _firestore_client = firestore.Client(project=project_id, credentials=credentials)
        return _firestore_client

    # Fallback to default credentials
    _firestore_client = firestore.Client()
    return _firestore_client


def test_firestore_connection():
    """
    ពិនិត្យការតភ្ជាប់ទៅកាន់ Cloud Firestore Database
    """
    try:
        client = get_firestore_client(force_refresh=True)
        # Ping collection metadata
        meta_ref = client.collection("_system_health").document("ping")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        meta_ref.set({"status": "online", "last_ping": now_str})
        return {
            "success": True,
            "message": f"ការតភ្ជាប់ទៅកាន់ Cloud Firestore (Project: {client.project}) ជោគជ័យ!",
            "project_id": client.project,
            "ping_time": now_str
        }
    except Exception as e:
        err_msg = str(e)
        logger.error(f"Firestore connection error: {err_msg}")
        proj_id = getattr(client, "project", "schoolsm") if 'client' in locals() and client else "schoolsm"
        if "404" in err_msg and "does not exist" in err_msg:
            return {
                "success": False,
                "needs_creation": True,
                "project_id": proj_id,
                "message": (
                    f"Cloud Firestore មិនទាន់ត្រូវបានបើកដំណើរការ (Enable) នៅលើ Firebase Console នៃគម្រោង {proj_id} ទេ។ "
                    f"សូមចូលទៅកាន់ https://console.firebase.google.com/project/{proj_id}/firestore "
                    "រួចចុច «Create database» ដើម្បីបើកដំណើរការ។"
                ),
                "error": err_msg
            }
        return {
            "success": False,
            "message": f"កំហុសតភ្ជាប់ទៅកាន់ Firestore: {err_msg}",
            "error": err_msg
        }


def sync_sheets_to_firestore(sheet_id=None):
    """
    ទាញយកទិន្នន័យកាលវិភាគពី Google Sheets ('🗓️ កាលវិភាគរួម (KKHS Backup)')
    រួច Sync បញ្ចូលទៅក្នុង Cloud Firestore សម្រាប់ប្រើប្រាស់ជាអចិន្ត្រៃយ៍លើ Cloud
    ព្រមទាំង Update Local SQLite Database ក្នុងពេលតែមួយ។
    """
    try:
        client = get_firestore_client(force_refresh=True)
    except Exception as e:
        return {"success": False, "message": f"មិនអាចបង្កើត Firestore Client: {e}"}

    # 1. First pull from Google Sheets to verify and parse data
    try:
        client_sheets = google_sheets_sync.get_gspread_client()
        if not sheet_id:
            sheet_id = db.get_setting("google_sheet_id", "1RnTas3BW3UfhwqMPhR7rU7b1FPEw35Xt-CL0aTJ2XkE")

        spreadsheet = client_sheets.open_by_key(sheet_id)

        # Get Timetable sheet
        try:
            ws_tt = spreadsheet.worksheet("🗓️ កាលវិភាគរួម (KKHS Backup)")
            all_tt_rows = ws_tt.get_all_values()
        except Exception:
            return {
                "success": False,
                "message": "រកមិនឃើញសន្លឹកកិច្ចការ '🗓️ កាលវិភាគរួម (KKHS Backup)' ក្នុង Google Sheets ទេ! សូមដំណើរការ Backup ពី kkhs ជាមុនសិន។"
            }

        # Get Teachers sheet
        all_t_rows = []
        try:
            ws_t = spreadsheet.worksheet("👨‍🏫 គ្រូបង្រៀន KKHS (Teachers Backup)")
            all_t_rows = ws_t.get_all_values()
        except Exception:
            pass

    except Exception as e:
        return {"success": False, "message": f"កំហុសក្នុងការអាន Google Sheets: {e}"}

    if len(all_tt_rows) < 2:
        return {"success": False, "message": "គ្មានទិន្នន័យកាលវិភាគក្នុង Google Sheets ទេ។"}

    # 2. Prepare Timetable slots
    # Header: ["ល.រ", "ថ្នាក់រៀន (Class)", "ថ្ងៃបង្រៀន (Day Code)", "ឈ្មោះថ្ងៃ (Day Name)",
    #          "ម៉ោងទី (Period 1-8)", "វេនសិក្សា (Shift)", "មុខវិជ្ជា (Subject)",
    #          "កូដគ្រូ (Teacher Code)", "ឈ្មោះគ្រូបង្រៀន (Teacher Name)", "កូដបង្រៀន (tCode)", "បន្ទប់ (Room)", ...]
    header = all_tt_rows[0]
    col_map = {}
    for idx, h in enumerate(header):
        h_clean = h.lower()
        if "ថ្នាក់" in h_clean or "class" in h_clean:
            col_map["class"] = idx
        elif "ថ្ងៃបង្រៀន" in h_clean or "day code" in h_clean:
            col_map["day"] = idx
        elif "ឈ្មោះថ្ងៃ" in h_clean or "day name" in h_clean:
            col_map["day_name"] = idx
        elif "ម៉ោង" in h_clean or "period" in h_clean:
            col_map["period"] = idx
        elif "វេន" in h_clean or "shift" in h_clean:
            col_map["shift"] = idx
        elif "មុខវិជ្ជា" in h_clean or "subject" in h_clean:
            col_map["subject"] = idx
        elif "កូដគ្រូ" in h_clean or "teacher code" in h_clean:
            col_map["teacher_code"] = idx
        elif "ឈ្មោះគ្រូ" in h_clean or "teacher name" in h_clean:
            col_map["teacher_name"] = idx
        elif "បន្ទប់" in h_clean or "room" in h_clean:
            col_map["room"] = idx

    day_names = {'ច': 'ចន្ទ', 'អ': 'អង្គារ', 'ព': 'ពុធ', 'ព្រ': 'ព្រហស្បតិ៍', 'សុ': 'សុក្រ', 'ស': 'សៅរ៍'}
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    slots_to_write = []
    classes_set = set()

    for r in all_tt_rows[1:]:
        if not any(r):
            continue
        c_code = r[col_map.get("class", 1)].strip() if len(r) > col_map.get("class", 1) else ""
        d_code = r[col_map.get("day", 2)].strip() if len(r) > col_map.get("day", 2) else ""
        raw_p = r[col_map.get("period", 4)].strip() if len(r) > col_map.get("period", 4) else ""
        s_name = r[col_map.get("subject", 6)].strip() if len(r) > col_map.get("subject", 6) else ""
        t_code = r[col_map.get("teacher_code", 7)].strip() if len(r) > col_map.get("teacher_code", 7) else ""
        t_name = r[col_map.get("teacher_name", 8)].strip() if len(r) > col_map.get("teacher_name", 8) else ""
        room = r[col_map.get("room", 10)].strip() if len(r) > col_map.get("room", 10) else ""

        if not c_code or not d_code or not raw_p:
            continue

        try:
            period_num = int("".join(filter(str.isdigit, raw_p)))
        except ValueError:
            continue

        shift = "Morning" if period_num <= 4 else "Afternoon"
        d_name = day_names.get(d_code, d_code)
        doc_id = f"{c_code}_{d_code}_{period_num}"

        classes_set.add(c_code)
        slots_to_write.append({
            "doc_id": doc_id,
            "data": {
                "class_code": c_code,
                "day_code": d_code,
                "day_name": d_name,
                "period_num": period_num,
                "shift": shift,
                "subject_name": s_name,
                "teacher_code": t_code,
                "teacher_name": t_name,
                "room_number": room,
                "updated_at": now_str,
                "source": "google_sheets_kkhs_backup"
            }
        })

    # 3. Prepare Teachers to write
    teachers_to_write = []
    if len(all_t_rows) > 1:
        for r in all_t_rows[1:]:
            if len(r) < 3 or not r[1]:
                continue
            t_code = str(r[1]).strip()
            t_name = str(r[2]).strip()
            gender = str(r[3]).strip() if len(r) > 3 else "M"
            phone = str(r[4]).strip() if len(r) > 4 else ""
            subject = str(r[5]).strip() if len(r) > 5 else ""
            tcodes = str(r[6]).strip() if len(r) > 6 else ""
            duty = str(r[7]).strip() if len(r) > 7 else ""
            t_type = str(r[8]).strip() if len(r) > 8 else ""

            teachers_to_write.append({
                "doc_id": t_code,
                "data": {
                    "teacher_code": t_code,
                    "full_name_kh": t_name,
                    "gender": gender,
                    "phone": phone,
                    "subject": subject,
                    "tcodes": tcodes,
                    "duty": duty,
                    "type": t_type,
                    "updated_at": now_str
                }
            })

    # 4. Batch Write to Cloud Firestore
    # Firestore allows up to 500 writes per batch. We use batches of 400.
    BATCH_SIZE = 400
    try:
        # Write Slots
        for i in range(0, len(slots_to_write), BATCH_SIZE):
            chunk = slots_to_write[i:i + BATCH_SIZE]
            batch = client.batch()
            for item in chunk:
                ref = client.collection("timetable_slots").document(item["doc_id"])
                batch.set(ref, item["data"])
            batch.commit()

        # Write Teachers
        for i in range(0, len(teachers_to_write), BATCH_SIZE):
            chunk = teachers_to_write[i:i + BATCH_SIZE]
            batch = client.batch()
            for item in chunk:
                ref = client.collection("teachers").document(item["doc_id"])
                batch.set(ref, item["data"])
            batch.commit()

        # Write Metadata
        meta_ref = client.collection("sync_metadata").document("kkhs_sheets_backup")
        meta_ref.set({
            "last_sync_time": now_str,
            "synced_slots": len(slots_to_write),
            "synced_teachers": len(teachers_to_write),
            "synced_classes": len(classes_set),
            "source_sheet_id": sheet_id
        })

    except Exception as e:
        err_str = str(e)
        proj_id = getattr(client, "project", "schoolsm") if 'client' in locals() and client else "schoolsm"
        if "404" in err_str and "does not exist" in err_str:
            return {
                "success": False,
                "needs_creation": True,
                "project_id": proj_id,
                "message": (
                    f"Cloud Firestore មិនទាន់ត្រូវបានបើកដំណើរការ (Enable) នៅលើ Firebase Console នៃគម្រោង {proj_id} ទេ។ "
                    f"សូមចូលទៅកាន់ https://console.firebase.google.com/project/{proj_id}/firestore "
                    "រួចចុច «Create database» ដើម្បីបើកដំណើរការ។"
                )
            }
        return {"success": False, "message": f"កំហុសក្នុងការសរសេរចូល Firestore: {e}"}

    # 5. Also sync to local SQLite database so local app is 100% updated
    google_sheets_sync.pull_timetable_from_google_sheets(sheet_id=sheet_id, mode="merge")
    db.set_setting("firestore_last_sync_time", now_str)

    return {
        "success": True,
        "message": f"បាន Sync ពី Google Sheets ទៅ Cloud Firestore ចំនួន {len(slots_to_write)} ម៉ោងបង្រៀន និងគ្រូ {len(teachers_to_write)} នាក់ដោយជោគជ័យ!",
        "synced_slots": len(slots_to_write),
        "synced_teachers": len(teachers_to_write),
        "synced_classes": len(classes_set),
        "sync_time": now_str
    }


def pull_firestore_to_local():
    """
    ទាញយកទិន្នន័យពី Cloud Firestore មកកាន់ Local SQLite Database
    (ប្រើនៅពេល Container លើ Firebase / Cloud Run restart ឬចាប់ផ្តើមថ្មី)
    """
    try:
        client = get_firestore_client()
        slots_ref = client.collection("timetable_slots").stream()

        conn = db.get_db_connection()
        cur = conn.cursor()

        pulled_count = 0
        for doc in slots_ref:
            d = doc.to_dict()
            c_code = d.get("class_code", "")
            d_code = d.get("day_code", "")
            p_num = d.get("period_num", 1)
            shift = d.get("shift", "Morning")
            s_name = d.get("subject_name", "")
            t_code = d.get("teacher_code", "")
            t_name = d.get("teacher_name", "")
            room = d.get("room_number", "")
            d_name = d.get("day_name", "")

            # Get or create class_id
            class_row = cur.execute("SELECT id FROM classes WHERE class_name = ? OR class_name = ?", (c_code, f"ថ្នាក់ទី {c_code}")).fetchone()
            class_id = class_row["id"] if class_row else None

            # Get teacher_id
            teacher_row = cur.execute("SELECT id FROM teachers WHERE teacher_code = ?", (t_code,)).fetchone()
            teacher_id = teacher_row["id"] if teacher_row else None

            cur.execute("""
                INSERT INTO timetable_slots (
                    class_id, class_code, day_code, day_name, period_num,
                    shift, subject_code, subject_name, teacher_id, teacher_code, teacher_name, room_number
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(class_code, day_code, period_num) DO UPDATE SET
                    shift = excluded.shift,
                    subject_name = excluded.subject_name,
                    teacher_id = excluded.teacher_id,
                    teacher_code = excluded.teacher_code,
                    teacher_name = excluded.teacher_name,
                    room_number = excluded.room_number
            """, (
                class_id, c_code, d_code, d_name, p_num,
                shift, "", s_name, teacher_id, t_code, t_name, room
            ))
            pulled_count += 1

        conn.commit()
        conn.close()

        db.init_default_users()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return {
            "success": True,
            "message": f"បានទាញយកកាលវិភាគចំនួន {pulled_count} ម៉ោងពី Cloud Firestore មកកាន់ Local Database ដោយជោគជ័យ!",
            "pulled_slots": pulled_count,
            "pull_time": now_str
        }
    except Exception as e:
        return {"success": False, "message": f"កំហុសក្នុងការទាញយកពី Firestore: {e}"}
