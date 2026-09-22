"""
ប្រព័ន្ធគ្រប់គ្រងអវត្តមានសិស្ស-គ្រូ (Student & Teacher Absence Management System)
Google Sheets Integration & Synchronization Module (using gspread)
Fully compatible with the SchoolSM 2026-2027 Production Google Spreadsheet
"""

import os
import json
import re
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from database import get_db_connection, get_setting, set_setting


# Scopes needed for Google Sheets & Google Drive
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]


def get_gspread_client(credentials_path=None):
    """
    បង្កើត gspread Client ដោយប្រើ Service Account JSON Key
    """
    # 1. First check environment variable for cloud hosting deployment
    env_creds = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if env_creds:
        try:
            creds_info = json.loads(env_creds)
            creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
            return gspread.authorize(creds)
        except Exception:
            pass

    if not credentials_path:
        credentials_path = get_setting("google_credentials_file", "google_service_account.json")

    # If relative path, join with current directory
    if not os.path.isabs(credentials_path):
        credentials_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), credentials_path)

    if not os.path.exists(credentials_path):
        # Fallback to default google_service_account.json
        alt_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "google_service_account.json")
        if os.path.exists(alt_path):
            credentials_path = alt_path
        else:
            raise FileNotFoundError(f"រកមិនឃើញឯកសារ Credentials: {credentials_path}")

    creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client


get_google_client = get_gspread_client


def test_google_sheet_connection(sheet_id=None, credentials_path=None):
    """
    ពិនិត្យការតភ្ជាប់ទៅកាន់ Google Sheet
    """
    try:
        if not sheet_id:
            sheet_id = get_setting("google_sheet_id", "1RnTas3BW3UfhwqMPhR7rU7b1FPEw35Xt-CL0aTJ2XkE")
        if not sheet_id:
            return {"success": False, "message": "មិនទាន់បានបញ្ចូល Google Sheet ID នៅឡើយទេ។"}

        client = get_gspread_client(credentials_path)
        sheet = client.open_by_key(sheet_id)
        return {
            "success": True,
            "message": f"តភ្ជាប់បានជោគជ័យទៅកាន់ Sheet: '{sheet.title}'",
            "title": sheet.title,
            "worksheet_count": len(sheet.worksheets())
        }
    except FileNotFoundError as fnf:
        return {"success": False, "message": str(fnf)}
    except Exception as e:
        return {"success": False, "message": f"បរាជ័យក្នុងការតភ្ជាប់៖ {str(e)}"}


def ensure_worksheet(spreadsheet, title, headers, rows=3000, cols=20):
    """
    ធានាថា Worksheet (Tab) មួយមានវត្តមានក្នុង Google Sheet
    ប្រសិនបើមានស្រាប់ យក Worksheet នោះ តែប្រសិនបើគ្មាន គឺបង្កើតថ្មី
    """
    try:
        ws = spreadsheet.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)
        ws.append_row(headers)
    return ws


def push_to_google_sheets(sheet_id=None, credentials_path=None):
    """
    Push ទិន្នន័យពី Local SQLite Database ទៅកាន់ Google Sheet
    តាមរចនាសម្ព័ន្ធពិតប្រាកដនៃ SchoolSM 2026-2027
    """
    try:
        if not sheet_id:
            sheet_id = get_setting("google_sheet_id", "1RnTas3BW3UfhwqMPhR7rU7b1FPEw35Xt-CL0aTJ2XkE")
        if not sheet_id:
            return {"success": False, "message": "មិនទាន់បានបញ្ចូល Google Sheet ID នៅឡើយទេ។"}

        client = get_gspread_client(credentials_path)
        spreadsheet = client.open_by_key(sheet_id)
        conn = get_db_connection()

        # 1. Sync Student Attendance to '📅 វត្តមាន (Attendance)'
        student_headers = [
            "កាលបរិច្ឆេទ (Date)", "វេន (Session)", "ម៉ោងទី (Period)", "អត្តលេខ (Student ID)",
            "ឈ្មោះសិស្ស (Name)", "ថ្នាក់រៀន (Class)", "ស្ថានភាពវត្តមាន (Status)",
            "មូលហេតុ / កំណត់ចំណាំ (Reason/Notes)", "អ្នកកត់ត្រា (Recorded By)"
        ]
        
        # Check if production sheet already has "📅 វត្តមាន (Attendance)" or create it
        student_ws = ensure_worksheet(
            spreadsheet,
            title="📅 វត្តមាន (Attendance)",
            headers=student_headers,
            rows=5000,
            cols=15
        )

        student_rows = conn.execute("""
            SELECT sa.date, sa.shift, sa.period, s.student_code, s.full_name_kh, c.class_name,
                   CASE 
                       WHEN sa.status = 'PRESENT' THEN 'វត្តមាន'
                       WHEN sa.status = 'PERMISSION' THEN 'មានច្បាប់'
                       WHEN sa.status = 'ABSENT' THEN 'ឥតច្បាប់'
                       WHEN sa.status = 'LATE' THEN 'យឺត'
                       ELSE sa.status
                   END as status_kh,
                   COALESCE(sa.reason, '') as reason,
                   sa.recorded_by
            FROM student_attendance sa
            JOIN students s ON sa.student_id = s.id
            JOIN classes c ON sa.class_id = c.id
            ORDER BY sa.date DESC, c.class_name ASC, s.full_name_kh ASC
            LIMIT 3000
        """).fetchall()

        student_data = [student_headers]
        for r in student_rows:
            session_str = "ព្រឹក (Morning)" if r["shift"] == "Morning" else "រសៀល (Afternoon)"
            student_data.append([
                r["date"], session_str, r["period"] or "Daily", r["student_code"],
                r["full_name_kh"], r["class_name"], r["status_kh"], r["reason"],
                r["recorded_by"]
            ])

        student_ws.clear()
        student_ws.update(range_name="A1", values=student_data)

        # 2. Sync Teacher Attendance to '📅 វត្តមានគ្រូ (Teacher Attendance)'
        teacher_headers = [
            "កាលបរិច្ឆេទ (Date)", "វេន (Session)", "ម៉ោងទី (Period)", "កូដគ្រូ (Teacher Code)",
            "ឈ្មោះគ្រូ (Teacher Name)", "ភេទ", "មុខវិជ្ជា (Subject)", "ស្ថានភាព (Status)",
            "គ្រូជំនួស (Substitute)", "មូលហេតុ (Reason)", "កាលបរិច្ឆេទកត់ត្រា"
        ]
        teacher_ws = ensure_worksheet(
            spreadsheet,
            title="📅 វត្តមានគ្រូ (Teacher Attendance)",
            headers=teacher_headers,
            rows=2000,
            cols=15
        )

        teacher_rows = conn.execute("""
            SELECT ta.date, ta.shift, ta.period, t.teacher_code, t.full_name_kh, t.gender, t.subject,
                   CASE 
                       WHEN ta.status = 'PRESENT' THEN 'វត្តមាន'
                       WHEN ta.status = 'PERMISSION' THEN 'មានច្បាប់'
                       WHEN ta.status = 'ABSENT' THEN 'ឥតច្បាប់'
                       WHEN ta.status = 'LATE' THEN 'យឺត'
                       ELSE ta.status
                   END as status_kh,
                   COALESCE(sub.full_name_kh, '') as substitute_name,
                   COALESCE(ta.reason, '') as reason,
                   ta.created_at
            FROM teacher_attendance ta
            JOIN teachers t ON ta.teacher_id = t.id
            LEFT JOIN teachers sub ON ta.substitute_teacher_id = sub.id
            ORDER BY ta.date DESC, ta.shift ASC, t.full_name_kh ASC
            LIMIT 2000
        """).fetchall()

        teacher_data = [teacher_headers]
        for r in teacher_rows:
            session_str = "ព្រឹក (Morning)" if r["shift"] == "Morning" else "រសៀល (Afternoon)"
            teacher_data.append([
                r["date"], session_str, r["period"] or "Session", r["teacher_code"],
                r["full_name_kh"], r["gender"], r["subject"], r["status_kh"],
                r["substitute_name"], r["reason"], r["created_at"]
            ])

        teacher_ws.clear()
        teacher_ws.update(range_name="A1", values=teacher_data)

        # 3. Sync Leave Requests to '📝 ពាក្យសុំច្បាប់ (Leave Requests)'
        leave_headers = [
            "កាលបរិច្ឆេទសុំ", "ប្រភេទ", "ឈ្មោះសាមីខ្លួន", "ថ្ងៃចាប់ផ្តើម", "ថ្ងៃបញ្ចប់",
            "មូលហេតុ", "ស្ថានភាពអនុម័ត", "អនុម័តដោយ", "កាលបរិច្ឆេទបង្កើត"
        ]
        leave_ws = ensure_worksheet(
            spreadsheet,
            title="📝 ពាក្យសុំច្បាប់ (Leave Requests)",
            headers=leave_headers,
            rows=1000,
            cols=12
        )

        leave_rows = conn.execute("""
            SELECT lr.*,
                   CASE 
                       WHEN lr.person_type = 'TEACHER' THEN (SELECT full_name_kh FROM teachers WHERE id = lr.person_id)
                       WHEN lr.person_type = 'STUDENT' THEN (SELECT full_name_kh FROM students WHERE id = lr.person_id)
                       ELSE 'មិនស្គាល់'
                   END as applicant_name
            FROM leave_requests lr
            ORDER BY lr.created_at DESC
        """).fetchall()

        leave_data = [leave_headers]
        for lr in leave_rows:
            type_str = "គ្រូបង្រៀន" if lr["person_type"] == "TEACHER" else "សិស្ស"
            status_map = {"Pending": "រង់ចាំពិនិត្យ", "Approved": "បានអនុម័ត", "Rejected": "បដិសេធ"}
            leave_data.append([
                lr["start_date"], type_str, lr["applicant_name"] or "", lr["start_date"],
                lr["end_date"], lr["reason"] or "",
                status_map.get(lr["status"], lr["status"]), lr["approved_by"] or "",
                lr["created_at"]
            ])

        leave_ws.clear()
        leave_ws.update(range_name="A1", values=leave_data)

        # 4. Sync Master Teachers List to '👨‍🏫 បញ្ជីគ្រូបង្រៀន (Teachers)'
        t_master_headers = [
            "កូដគ្រូ", "ឈ្មោះគ្រូ (ខ្មែរ)", "ឈ្មោះឡាតាំង", "ភេទ", "មុខវិជ្ជា",
            "ទូរស័ព្ទ", "កម្រិតបង្រៀន", "តួនាទី", "ស្ថានភាព"
        ]
        t_master_ws = ensure_worksheet(
            spreadsheet,
            title="👨‍🏫 បញ្ជីគ្រូបង្រៀន (Teachers)",
            headers=t_master_headers,
            rows=500,
            cols=12
        )
        teachers_list = conn.execute("SELECT * FROM teachers ORDER BY full_name_kh ASC").fetchall()
        t_list_data = [t_master_headers]
        for t in teachers_list:
            t_list_data.append([
                t["teacher_code"], t["full_name_kh"], t["full_name_en"] or "",
                t["gender"], t["subject"], t["phone"] or "",
                t["training_level"] if "training_level" in t.keys() else "",
                t["current_duty"] if "current_duty" in t.keys() else "",
                t["status"]
            ])
        t_master_ws.clear()
        t_master_ws.update(range_name="A1", values=t_list_data)

        # Update last sync time
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        set_setting("last_sync_time", now_str)
        conn.close()

        return {
            "success": True,
            "message": f"បានបញ្ជូនទិន្នន័យទៅ Google Sheets ដោយជោគជ័យនៅម៉ោង {now_str}!",
            "sync_time": now_str,
            "students_synced": len(student_data) - 1,
            "teachers_synced": len(teacher_data) - 1,
            "leaves_synced": len(leave_data) - 1
        }

    except Exception as e:
        return {"success": False, "message": f"កំហុសក្នុងការ Sync ទៅ Google Sheets៖ {str(e)}"}


# =============================================================
# KKHS.WEB.APP <--> GOOGLE SHEETS CLOUD BRIDGE
# =============================================================
def backup_kkhs_to_google_sheets(sheet_id=None, credentials_path=None):
    """
    ទាញយកទិន្នន័យពី kkhs.web.app (Firebase RTDB) ហើយ Backup ទៅក្នុង Google Sheets
    (SchoolSM 2026-2027) ក្នុង Tab '🗓️ កាលវិភាគរួម (KKHS Backup)' និង '👨‍🏫 គ្រូបង្រៀន KKHS (Teachers Backup)'
    """
    import kkhs_sync_service

    try:
        if not sheet_id:
            sheet_id = get_setting("google_sheet_id", "1RnTas3BW3UfhwqMPhR7rU7b1FPEw35Xt-CL0aTJ2XkE")
        if not sheet_id:
            return {"success": False, "message": "មិនទាន់បានបញ្ចូល Google Sheet ID នៅឡើយទេ។"}

        client = get_gspread_client(credentials_path)
        spreadsheet = client.open_by_key(sheet_id)

        # 1. Fetch live data from Firebase RTDB
        subjects_data = kkhs_sync_service.fetch_firebase_node("timetable_data/subjects") or []
        teachers_data = kkhs_sync_service.fetch_firebase_node("timetable_data/teachers") or []
        schedule_data = kkhs_sync_service.fetch_firebase_node("timetable_data/schedule") or {}

        sub_name_map = {s.get("code"): s.get("name") for s in subjects_data if s.get("code")}

        # 2. Backup Teachers to '👨‍🏫 គ្រូបង្រៀន KKHS (Teachers Backup)'
        teacher_headers = [
            "ល.រ", "កូដគ្រូ MOEYS (ID)", "ឈ្មោះគ្រូបង្រៀន (Name)", "ភេទ (Gender)",
            "លេខទូរស័ព្ទ (Phone)", "មុខវិជ្ជាឯកទេស (Subject)", "កូដបង្រៀន (tCodes)",
            "តួនាទី (Duty)", "កម្រិតបណ្តុះបណ្តាល (Type)"
        ]
        t_backup_ws = ensure_worksheet(
            spreadsheet,
            title="👨‍🏫 គ្រូបង្រៀន KKHS (Teachers Backup)",
            headers=teacher_headers,
            rows=300,
            cols=12
        )

        tcode_to_teacher = {}
        teacher_rows_data = [teacher_headers]

        for idx, t in enumerate(teachers_data, start=1):
            t_id = str(t.get("id") or "").strip()
            t_name = str(t.get("name") or "").strip()
            gender = t.get("gender") or "M"
            phone = str(t.get("phone") or "").strip()
            duty = str(t.get("duty") or "បង្រៀន").strip()
            q_type = str(t.get("type") or "").strip()

            t_subjects = t.get("subjects") or []
            tcodes_list = [s.get("tCode") for s in t_subjects if s.get("tCode")]
            tcodes_str = ", ".join(tcodes_list)
            primary_sub = sub_name_map.get(t_subjects[0].get("code"), "") if t_subjects else ""

            teacher_rows_data.append([
                idx, t_id, t_name, gender, phone, primary_sub, tcodes_str, duty, q_type
            ])

            for sub_entry in t_subjects:
                tc = sub_entry.get("tCode")
                if tc:
                    tcode_to_teacher[tc] = {
                        "teacher_code": t_id,
                        "teacher_name": t_name,
                        "subject_code": sub_entry.get("code"),
                        "subject_name": sub_name_map.get(sub_entry.get("code"), "")
                    }

        t_backup_ws.clear()
        t_backup_ws.update(range_name="A1", values=teacher_rows_data)

        # 3. Backup Timetable to '🗓️ កាលវិភាគរួម (KKHS Backup)'
        tt_headers = [
            "ល.រ", "ថ្នាក់រៀន (Class)", "ថ្ងៃបង្រៀន (Day Code)", "ឈ្មោះថ្ងៃ (Day Name)",
            "ម៉ោងទី (Period 1-8)", "វេនសិក្សា (Shift)", "មុខវិជ្ជា (Subject)",
            "កូដគ្រូ (Teacher Code)", "ឈ្មោះគ្រូបង្រៀន (Teacher Name)", "កូដបង្រៀន (tCode)",
            "បន្ទប់ (Room)", "កាលបរិច្ឆេទ Backup"
        ]
        tt_backup_ws = ensure_worksheet(
            spreadsheet,
            title="🗓️ កាលវិភាគរួម (KKHS Backup)",
            headers=tt_headers,
            rows=3000,
            cols=15
        )

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        day_names = {'ច': 'ចន្ទ', 'អ': 'អង្គារ', 'ព': 'ពុធ', 'ព្រ': 'ព្រហស្បតិ៍', 'សុ': 'សុក្រ', 'ស': 'សៅរ៍'}

        timetable_rows_data = [tt_headers]
        slot_idx = 1

        for c_code, day_slots in schedule_data.items():
            if not isinstance(day_slots, dict):
                continue
            for slot_key, tcode_val in day_slots.items():
                if not tcode_val:
                    continue
                m = re.match(r'^([^\d]+)(\d+)$', slot_key)
                if not m:
                    continue
                d_code, p_num_str = m.groups()
                period_num = int(p_num_str)
                d_name = day_names.get(d_code, d_code)
                shift = "Morning" if period_num <= 4 else "Afternoon"

                t_info = tcode_to_teacher.get(tcode_val) or tcode_to_teacher.get(tcode_val.upper())
                t_code = t_info["teacher_code"] if t_info else ""
                t_name = t_info["teacher_name"] if t_info else tcode_val
                s_name = t_info["subject_name"] if t_info else ""

                timetable_rows_data.append([
                    slot_idx, c_code, d_code, d_name, period_num, shift, s_name,
                    t_code, t_name, tcode_val, "", now_str
                ])
                slot_idx += 1

        tt_backup_ws.clear()
        tt_backup_ws.update(range_name="A1", values=timetable_rows_data)

        set_setting("kkhs_sheets_last_backup_time", now_str)

        return {
            "success": True,
            "message": f"បាន Backup កាលវិភាគ {slot_idx - 1} ម៉ោង និងគ្រូបង្រៀន {len(teacher_rows_data) - 1} នាក់ ពី kkhs.web.app ទៅ Google Sheets ដោយជោគជ័យ!",
            "backup_time": now_str,
            "slots_backed_up": slot_idx - 1,
            "teachers_backed_up": len(teacher_rows_data) - 1,
            "sheet_title": spreadsheet.title
        }

    except Exception as e:
        return {"success": False, "message": f"កំហុសក្នុងការ Backup ទៅ Google Sheets៖ {str(e)}"}


def pull_timetable_from_google_sheets(sheet_id=None, credentials_path=None, mode="merge"):
    """
    ទាញយកទិន្នន័យកាលវិភាគពី Google Sheets (Tab '🗓️ កាលវិភាគរួម (KKHS Backup)')
    មកធ្វើបច្ចុប្បន្នភាពចូល SQLite Local Database សម្រាប់ប្រើប្រាស់ជាអចិន្ត្រៃយ៍ក្នុងការស្រង់វត្តមាន
    """
    import database as db

    try:
        if not sheet_id:
            sheet_id = get_setting("google_sheet_id", "1RnTas3BW3UfhwqMPhR7rU7b1FPEw35Xt-CL0aTJ2XkE")
        if not sheet_id:
            return {"success": False, "message": "មិនទាន់បានបញ្ចូល Google Sheet ID នៅឡើយទេ។"}

        client = get_gspread_client(credentials_path)
        spreadsheet = client.open_by_key(sheet_id)

        try:
            ws = spreadsheet.worksheet("🗓️ កាលវិភាគរួម (KKHS Backup)")
        except gspread.exceptions.WorksheetNotFound:
            return {
                "success": False,
                "message": "រកមិនឃើញសន្លឹកកិច្ចការ '🗓️ កាលវិភាគរួម (KKHS Backup)' ក្នុង Google Sheets ឡើយ។ សូមធ្វើការ Backup ជាមុនសិន។"
            }

        all_values = ws.get_all_values()
        if not all_values or len(all_values) < 2:
            return {"success": False, "message": "មិនមានទិន្នន័យកាលវិភាគក្នុងសន្លឹកកិច្ចការ Google Sheets ឡើយ។"}

        headers = [h.strip().lower() for h in all_values[0]]
        # Find column indices
        col_map = {}
        for idx, h in enumerate(headers):
            if "ថ្នាក់" in h or "class" in h:
                col_map["class"] = idx
            elif "កូដថ្ងៃ" in h or "day code" in h or "ថ្ងៃបង្រៀន" in h:
                col_map["day"] = idx
            elif "ម៉ោង" in h or "period" in h:
                col_map["period"] = idx
            elif "មុខវិជ្ជា" in h or "subject" in h:
                col_map["subject"] = idx
            elif "កូដគ្រូ" in h or "teacher code" in h:
                col_map["teacher_code"] = idx
            elif "ឈ្មោះគ្រូ" in h or "teacher name" in h:
                col_map["teacher_name"] = idx
            elif "បន្ទប់" in h or "room" in h:
                col_map["room"] = idx

        conn = get_db_connection()
        cur = conn.cursor()

        # Pre-load teachers lookup
        teachers_by_code = {}
        teachers_by_name = {}
        for t in cur.execute("SELECT id, teacher_code, full_name_kh, subject FROM teachers").fetchall():
            if t["teacher_code"]:
                teachers_by_code[str(t["teacher_code"]).strip().lower()] = dict(t)
            if t["full_name_kh"]:
                teachers_by_name[str(t["full_name_kh"]).strip()] = dict(t)

        # Pre-load classes
        class_code_to_id = {}
        for c in cur.execute("SELECT id, class_name FROM classes").fetchall():
            c_code = c["class_name"].replace("ថ្នាក់ទី ", "").strip()
            class_code_to_id[c_code] = c["id"]

        day_names = {'ច': 'ចន្ទ', 'អ': 'អង្គារ', 'ព': 'ពុធ', 'ព្រ': 'ព្រហស្បតិ៍', 'សុ': 'សុក្រ', 'ស': 'សៅរ៍'}

        if mode == "replace":
            cur.execute("DELETE FROM timetable_slots")
            conn.commit()

        synced_count = 0

        for row_idx, r in enumerate(all_values[1:], start=2):
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

            # Parse period
            p_digits = ''.join(filter(str.isdigit, raw_p))
            if not p_digits:
                continue
            period_num = int(p_digits)
            if period_num < 1 or period_num > 8:
                continue

            shift = "Morning" if period_num <= 4 else "Afternoon"
            d_name = day_names.get(d_code, d_code)

            # Ensure class exists
            if c_code not in class_code_to_id:
                m_g = re.match(r'(\d+)', c_code)
                grade_val = int(m_g.group(1)) if m_g else 7
                cur.execute("INSERT INTO classes (class_name, grade_level, shift) VALUES (?, ?, ?)",
                            (f"ថ្នាក់ទី {c_code}", grade_val, shift))
                class_code_to_id[c_code] = cur.lastrowid

            class_id = class_code_to_id.get(c_code)

            # Resolve teacher
            matched_t = teachers_by_code.get(t_code.lower()) or teachers_by_name.get(t_name)
            if not matched_t and t_name:
                for db_tname, db_t in teachers_by_name.items():
                    if t_name in db_tname or db_tname in t_name:
                        matched_t = db_t
                        break

            teacher_id = matched_t["id"] if matched_t else None
            final_tcode = matched_t["teacher_code"] if matched_t else t_code
            final_tname = matched_t["full_name_kh"] if matched_t else t_name

            cur.execute("""
                INSERT INTO timetable_slots (
                    class_id, class_code, day_code, day_name, period_num,
                    shift, subject_code, subject_name, teacher_id, teacher_code, teacher_name, room_number
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(class_code, day_code, period_num) DO UPDATE SET
                    class_id = excluded.class_id,
                    day_name = excluded.day_name,
                    shift = excluded.shift,
                    subject_code = excluded.subject_code,
                    subject_name = excluded.subject_name,
                    teacher_id = excluded.teacher_id,
                    teacher_code = excluded.teacher_code,
                    teacher_name = excluded.teacher_name,
                    room_number = excluded.room_number
            """, (
                class_id, c_code, d_code, d_name, period_num,
                shift, "", s_name, teacher_id, final_tcode, final_tname, room
            ))
            synced_count += 1

        conn.commit()
        conn.close()

        # Ensure teacher accounts in users table
        db.init_default_users()

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        set_setting("kkhs_sheets_last_pull_time", now_str)

        return {
            "success": True,
            "message": f"បានទាញយកកាលវិភាគចំនួន {synced_count} ម៉ោងបង្រៀនពី Google Sheets មកកាន់ Local Database ដោយជោគជ័យ!",
            "pull_time": now_str,
            "slots_imported": synced_count,
            "synced_slots": synced_count
        }

    except Exception as e:
        return {"success": False, "message": f"កំហុសក្នុងការទាញយកពី Google Sheets៖ {str(e)}"}
