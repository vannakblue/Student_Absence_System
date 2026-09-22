"""
សេវាធ្វើសមកាលកម្មកាលវិភាគពី kkhs.web.app (KKHS Cloud Timetable Sync Service)
ទាញយកទិន្នន័យពី Firebase Realtime Database របស់ kkhs.web.app មកធ្វើបច្ចុប្បន្នភាពក្នុង Database ក្នុងស្រុក
"""

import urllib.request
import json
import logging
import re
from datetime import datetime
import database as db

logger = logging.getLogger("kkhs_sync")

DEFAULT_KKHS_URL = "https://kkhs.web.app"
DEFAULT_FIREBASE_RTDB_URL = "https://school-timetable-67972-default-rtdb.asia-southeast1.firebasedatabase.app"

DAY_NAMES = {
    'ច': 'ចន្ទ',
    'អ': 'អង្គារ',
    'ព': 'ពុធ',
    'ព្រ': 'ព្រហស្បតិ៍',
    'សុ': 'សុក្រ',
    'ស': 'សៅរ៍'
}


def get_firebase_base_url():
    """ទាញយក URL មូលដ្ឋានរបស់ Firebase RTDB ពីការកំណត់ ឬតម្លៃ Default"""
    return db.get_setting("kkhs_firebase_url", DEFAULT_FIREBASE_RTDB_URL).rstrip("/")


def fetch_firebase_node(node_path, timeout=12):
    """
    ទាញយក JSON node ពី Firebase RTDB REST API
    ឧទាហរណ៍៖ node_path = 'timetable_data/schedule'
    """
    base_url = get_firebase_base_url()
    url = f"{base_url}/{node_path.lstrip('/')}.json"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Student-Absence-System/1.0 (KKHS-Sync)",
            "Accept": "application/json"
        }
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if resp.status != 200:
            raise Exception(f"HTTP Error {resp.status} ពេលទាញយកពី {node_path}")
        raw = resp.read().decode("utf-8")
        return json.loads(raw)


def test_kkhs_connection():
    """
    សាកល្បងការតភ្ជាប់ទៅកាន់ kkhs.web.app / Firebase RTDB
    """
    try:
        settings = fetch_firebase_node("timetable_data/settings", timeout=8)
        if not settings:
            return {
                "success": False,
                "message": "បានតភ្ជាប់ជោគជ័យ ប៉ុន្តែមិនទាន់មានទិន្នន័យកាលវិភាគនៅឡើយទេ"
            }
        academic_year = settings.get("academicYear", "N/A")
        school_location = settings.get("location", "")
        return {
            "success": True,
            "message": "ការតភ្ជាប់ទៅកាន់ kkhs.web.app ដំណើរការបានជោគជ័យ!",
            "academic_year": academic_year,
            "location": school_location,
            "source_url": DEFAULT_KKHS_URL
        }
    except Exception as e:
        logger.error(f"Error testing KKHS connection: {e}")
        return {
            "success": False,
            "message": f"មិនអាចតភ្ជាប់ទៅកាន់ kkhs.web.app បានឡើយ៖ {str(e)}"
        }


def sync_kkhs_timetable(mode="merge"):
    """
    ធ្វើសមកាលកម្មទិន្នន័យកាលវិភាគ គ្រូបង្រៀន ថ្នាក់រៀន និងមុខវិជ្ជាពី kkhs.web.app
    mode: 'merge' (បន្ថែម/កែប្រែលើចាស់) ឬ 'replace' (ជំនួសថ្មីទាំងស្រុង)
    """
    results = {
        "success": False,
        "mode": mode,
        "synced_teachers": 0,
        "synced_classes": 0,
        "synced_subjects": 0,
        "synced_slots": 0,
        "errors": [],
        "sync_time": ""
    }

    try:
        # 1. Fetch live data from Firebase nodes
        logger.info("កំពុងទាញយកទិន្នន័យពី Firebase RTDB...")
        settings_data = fetch_firebase_node("timetable_data/settings") or {}
        subjects_data = fetch_firebase_node("timetable_data/subjects") or []
        classes_data = fetch_firebase_node("timetable_data/classes") or []
        teachers_data = fetch_firebase_node("timetable_data/teachers") or []
        schedule_data = fetch_firebase_node("timetable_data/schedule") or {}

        conn = db.get_db_connection()
        cur = conn.cursor()

        # 2. Sync Settings
        if settings_data.get("academicYear"):
            db.set_setting("academic_year", settings_data["academicYear"])

        # 3. Sync Subjects
        sub_name_map = {}
        for s in subjects_data:
            s_code = str(s.get("code") or "").strip()
            s_name = str(s.get("name") or "").strip()
            if not s_code:
                continue
            sub_name_map[s_code] = s_name
            cur.execute("""
                INSERT INTO subjects (code, name_kh)
                VALUES (?, ?)
                ON CONFLICT(code) DO UPDATE SET name_kh = excluded.name_kh
            """, (s_code, s_name))
            results["synced_subjects"] += 1

        # 4. Sync Classes
        class_code_to_id = {}
        # Pre-load existing classes
        for c in cur.execute("SELECT id, class_name, room_number FROM classes").fetchall():
            raw_c_name = c["class_name"].replace("ថ្នាក់ទី ", "").strip()
            class_code_to_id[raw_c_name] = c["id"]

        for c in classes_data:
            c_code = str(c.get("id") or "").strip()
            if not c_code:
                continue
            grade_str = str(c.get("grade") or "7")
            try:
                grade_num = int(grade_str)
            except ValueError:
                grade_num = 7
            shift = "Morning" if grade_num in [7, 8, 9, 10] else "Afternoon"

            if c_code not in class_code_to_id:
                cur.execute("""
                    INSERT INTO classes (class_name, grade_level, shift)
                    VALUES (?, ?, ?)
                """, (f"ថ្នាក់ទី {c_code}", grade_num, shift))
                new_cid = cur.lastrowid
                class_code_to_id[c_code] = new_cid
            results["synced_classes"] += 1

        # 5. Sync Teachers and build tCode lookup
        tcode_to_teacher = {}
        # Pre-load existing teachers by teacher_code and name
        db_teachers_by_code = {}
        db_teachers_by_name = {}
        for t in cur.execute("SELECT id, teacher_code, full_name_kh, subject FROM teachers").fetchall():
            if t["teacher_code"]:
                db_teachers_by_code[str(t["teacher_code"]).strip()] = dict(t)
            if t["full_name_kh"]:
                db_teachers_by_name[str(t["full_name_kh"]).strip()] = dict(t)

        for t in teachers_data:
            t_moeys_id = str(t.get("id") or "").strip()
            t_name = str(t.get("name") or "").strip()
            if not t_name:
                continue

            raw_gender = t.get("gender") or "M"
            gender = "F" if raw_gender in ["ស្រី", "F", "Female"] else "M"
            phone = str(t.get("phone") or "").strip()
            duty = str(t.get("duty") or "បង្រៀន").strip()
            qualification = str(t.get("type") or "").strip()

            # Determine primary subject name from subjects list
            t_subjects = t.get("subjects") or []
            primary_sub_name = ""
            if t_subjects:
                primary_sub_code = t_subjects[0].get("code")
                primary_sub_name = sub_name_map.get(primary_sub_code, "")

            # Match or insert into teachers
            existing_t = db_teachers_by_code.get(t_moeys_id) or db_teachers_by_name.get(t_name)
            if existing_t:
                teacher_id = existing_t["id"]
                cur.execute("""
                    UPDATE teachers
                    SET full_name_kh = ?, gender = ?, phone = COALESCE(NULLIF(?, ''), phone),
                        current_duty = ?, qualification = ?, subject = COALESCE(NULLIF(?, ''), subject)
                    WHERE id = ?
                """, (t_name, gender, phone, duty, qualification, primary_sub_name, teacher_id))
            else:
                cur.execute("""
                    INSERT INTO teachers (teacher_code, full_name_kh, gender, phone, subject, current_duty, qualification, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'Active')
                """, (t_moeys_id, t_name, gender, phone, primary_sub_name, duty, qualification))
                teacher_id = cur.lastrowid
                db_teachers_by_code[t_moeys_id] = {"id": teacher_id, "teacher_code": t_moeys_id, "full_name_kh": t_name}
                db_teachers_by_name[t_name] = {"id": teacher_id, "teacher_code": t_moeys_id, "full_name_kh": t_name}

            results["synced_teachers"] += 1

            # Map all tCodes assigned to this teacher (e.g., M1, P4, etc.)
            for sub_entry in t_subjects:
                t_code = sub_entry.get("tCode")
                if t_code:
                    s_code = sub_entry.get("code")
                    s_name = sub_name_map.get(s_code, "")
                    tcode_to_teacher[t_code] = {
                        "teacher_id": teacher_id,
                        "teacher_code": t_moeys_id,
                        "t_code": t_code,
                        "teacher_name": t_name,
                        "subject_code": s_code,
                        "subject_name": s_name
                    }

        conn.commit()

        # Ensure teacher accounts exist in users table
        db.init_default_users()

        # 6. Sync Schedule Matrix
        if mode == "replace":
            cur.execute("DELETE FROM timetable_slots")
            conn.commit()

        # Process each class in schedule
        for c_code, day_slots in schedule_data.items():
            if not isinstance(day_slots, dict):
                continue

            class_id = class_code_to_id.get(c_code)
            for slot_key, tcode_val in day_slots.items():
                if not tcode_val:
                    continue
                # Parse slot_key: e.g. "ច1", "អ3", "ព្រ7"
                m = re.match(r'^([^\d]+)(\d+)$', slot_key)
                if not m:
                    continue

                d_code, p_num_str = m.groups()
                period_num = int(p_num_str)
                d_name = DAY_NAMES.get(d_code, d_code)
                shift = "Morning" if period_num <= 4 else "Afternoon"

                info = tcode_to_teacher.get(tcode_val)
                if not info:
                    info = tcode_to_teacher.get(tcode_val.upper())

                teacher_id = info["teacher_id"] if info else None
                teacher_code = info["teacher_code"] if info else ""
                teacher_name = info["teacher_name"] if info else ""
                subject_code = info["subject_code"] if info else ""
                subject_name = info["subject_name"] if info else ""

                cur.execute("""
                    INSERT INTO timetable_slots (
                        class_id, class_code, day_code, day_name, period_num,
                        shift, subject_code, subject_name, teacher_id, teacher_code, teacher_name
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(class_code, day_code, period_num) DO UPDATE SET
                        class_id = excluded.class_id,
                        day_name = excluded.day_name,
                        shift = excluded.shift,
                        subject_code = excluded.subject_code,
                        subject_name = excluded.subject_name,
                        teacher_id = excluded.teacher_id,
                        teacher_code = excluded.teacher_code,
                        teacher_name = excluded.teacher_name
                """, (
                    class_id, c_code, d_code, d_name, period_num,
                    shift, subject_code, subject_name, teacher_id, teacher_code, teacher_name
                ))
                results["synced_slots"] += 1

        conn.commit()
        conn.close()

        sync_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.set_setting("kkhs_last_sync_time", sync_time_str)
        db.set_setting("kkhs_last_sync_stats", json.dumps(results))

        results["success"] = True
        results["sync_time"] = sync_time_str
        results["message"] = (
            f"បានធ្វើសមកាលកម្មកាលវិភាគពី kkhs.web.app ដោយជោគជ័យ! "
            f"បញ្ចូល/ធ្វើបច្ចុប្បន្នភាពកាលវិភាគ {results['synced_slots']} ម៉ោង, "
            f"គ្រូបង្រៀន {results['synced_teachers']} នាក់ និងថ្នាក់រៀន {results['synced_classes']} ថ្នាក់។"
        )
        return results

    except Exception as e:
        logger.error(f"Error during KKHS sync: {e}", exc_info=True)
        results["success"] = False
        results["message"] = f"កំហុសក្នុងការ Sync ពី kkhs.web.app៖ {str(e)}"
        results["errors"].append(str(e))
        return results
