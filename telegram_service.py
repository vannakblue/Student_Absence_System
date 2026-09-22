"""
ប្រព័ន្ធគ្រប់គ្រងការផ្ញើសារ Telegram (Telegram Notification Service)
Student & Teacher Absence Management System
"""

import os
import sys
import logging
from datetime import datetime
import requests
import database as db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telegram_service")


def to_khmer_numerals(num_str):
    """បំប្លែងលេខអារ៉ាប់ (0-9) ទៅជាលេខខ្មែរ (០-៩)"""
    khmer_digits = {'0': '០', '1': '១', '2': '២', '3': '៣', '4': '៤',
                    '5': '៥', '6': '៦', '7': '៧', '8': '៨', '9': '៩'}
    return "".join(khmer_digits.get(c, c) for c in str(num_str))


def format_khmer_date(date_str):
    """បំប្លែងកាលបរិច្ឆេទ YYYY-MM-DD ទៅជា dd/mm/yyyy ជាលេខខ្មែរ"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        d = dt.strftime("%d/%m/%Y")
        return to_khmer_numerals(d)
    except Exception:
        return to_khmer_numerals(date_str)


def send_telegram_message(chat_id, text, parse_mode="HTML", reply_markup=None, bot_token=None):
    """
    ផ្ញើសារទៅកាន់ Telegram Chat ID តាមរយៈ Telegram Bot API (គាំទ្រ reply_markup សម្រាប់ Inline Keyboard)
    """
    if not bot_token:
        bot_token = db.get_setting("telegram_bot_token", "").strip()

    if not bot_token or not chat_id:
        return False, "Telegram Bot Token ឬ Chat ID មិនទាន់ត្រូវបានកំណត់ទេ"

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": str(chat_id).strip(),
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    try:
        res = requests.post(url, json=payload, timeout=10)
        data = res.json()
        if res.status_code == 200 and data.get("ok"):
            logger.info(f"Telegram message sent to {chat_id} successfully.")
            return True, "ផ្ញើសារបានជោគជ័យ!"
        else:
            err = data.get("description", f"HTTP Error {res.status_code}")
            logger.warning(f"Telegram API Error ({chat_id}): {err}")
            return False, err
    except Exception as e:
        logger.error(f"Failed to send Telegram message to {chat_id}: {e}")
        return False, str(e)


def edit_telegram_message(chat_id, message_id, text, reply_markup=None, parse_mode="HTML", bot_token=None):
    """
    កែសម្រួលអត្ថបទសារ Telegram ដែលបានផ្ញើរួច (ឧទាហរណ៍៖ ប្តូរប៊ូតុង Inline ទៅជាសេចក្តីបញ្ជាក់ការអនុម័ត)
    """
    if not bot_token:
        bot_token = db.get_setting("telegram_bot_token", "").strip()
    if not bot_token or not chat_id or not message_id:
        return False, "ព័ត៌មានមិនគ្រប់គ្រាន់សម្រាប់កែសម្រួលសារ Telegram"

    url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
    payload = {
        "chat_id": str(chat_id).strip(),
        "message_id": int(message_id),
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    try:
        res = requests.post(url, json=payload, timeout=10)
        data = res.json()
        if res.status_code == 200 and data.get("ok"):
            return True, "កែសម្រួលសារបានជោគជ័យ"
        return False, data.get("description", f"HTTP {res.status_code}")
    except Exception as e:
        logger.error(f"Failed to edit Telegram message: {e}")
        return False, str(e)


def answer_telegram_callback_query(callback_query_id, text=None, show_alert=False, bot_token=None):
    """
    ឆ្លើយតប Callback Query ទៅកាន់ Telegram App ពេល Admin ចុចប៊ូតុង Inline
    """
    if not bot_token:
        bot_token = db.get_setting("telegram_bot_token", "").strip()
    if not bot_token or not callback_query_id:
        return False

    url = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
    payload = {"callback_query_id": str(callback_query_id)}
    if text:
        payload["text"] = text
        payload["show_alert"] = show_alert

    try:
        requests.post(url, json=payload, timeout=8)
        return True
    except Exception as e:
        logger.warning(f"Error answering callback query: {e}")
        return False


def test_telegram_connection(bot_token=None, chat_id=None):
    """
    តេស្តផ្ញើសារសាកល្បងទៅកាន់ Admin Telegram
    """
    if not bot_token:
        bot_token = db.get_setting("telegram_bot_token", "").strip()
    if not chat_id:
        chat_id = db.get_setting("telegram_admin_chat_id", "").strip()

    if not bot_token:
        return False, "សូមបញ្ចូល Telegram Bot Token ជាមុនសិន!"
    if not chat_id:
        return False, "សូមបញ្ចូល Telegram Admin Chat ID ជាមុនសិន!"

    school_name = db.get_setting("school_name_kh", "វិទ្យាល័យ ហ៊ុន សែន កំពង់កន្ទួត")
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    msg = (
        f"🤖 <b>តេស្តប្រព័ន្ធ Telegram Bot ជោគជ័យ!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏫 <b>{school_name}</b>\n"
        f"🕒 ពេលវេលា៖ {to_khmer_numerals(now_str)}\n"
        f"✅ ប្រព័ន្ធគ្រប់គ្រងអវត្តមានសិស្ស និងគ្រូបង្រៀន បានភ្ជាប់ទំនាក់ទំនងជាមួយ Telegram Bot រួចរាល់ដោយរលូន!"
    )
    return send_telegram_message(chat_id, msg, bot_token=bot_token)


def send_daily_absence_report(target_date=None):
    """
    ផ្ញើរបាយការណ៍សិស្ស និងគ្រូអវត្តមានប្រចាំថ្ងៃទៅកាន់ Admin Telegram
    """
    if not target_date:
        target_date = datetime.now().strftime("%Y-%m-%d")

    admin_chat_id = db.get_setting("telegram_admin_chat_id", "").strip()
    bot_token = db.get_setting("telegram_bot_token", "").strip()
    notify_enabled = db.get_setting("telegram_notify_absence", "1") == "1"

    if not notify_enabled or not bot_token or not admin_chat_id:
        return False, "Telegram Bot មិនទាន់បានបើក ឬមិនទាន់កំណត់ Chat ID សម្រាប់ Admin ទេ"

    school_name = db.get_setting("school_name_kh", "វិទ្យាល័យ ហ៊ុន សែន កំពង់កន្ទួត")
    formatted_date = format_khmer_date(target_date)

    conn = db.get_db_connection()

    # 1. ស្ថិតិអវត្តមានសិស្ស
    student_rows = conn.execute("""
        SELECT sa.status, sa.reason, sa.period, sa.shift,
               s.student_code, s.full_name_kh, s.gender,
               c.class_name
        FROM student_attendance sa
        JOIN students s ON sa.student_id = s.id
        JOIN classes c ON sa.class_id = c.id
        WHERE sa.date = ? AND sa.status IN ('ABSENT', 'PERMISSION')
        ORDER BY c.grade_level ASC, c.class_name ASC, s.full_name_kh ASC
    """, (target_date,)).fetchall()

    # 2. ស្ថិតិអវត្តមានគ្រូបង្រៀន
    teacher_rows = conn.execute("""
        SELECT ta.status, ta.reason, ta.shift, ta.period,
               t.teacher_code, t.full_name_kh, t.gender, t.subject
        FROM teacher_attendance ta
        JOIN teachers t ON ta.teacher_id = t.id
        WHERE ta.date = ? AND ta.status IN ('ABSENT', 'PERMISSION')
        ORDER BY t.full_name_kh ASC
    """, (target_date,)).fetchall()

    # Leave requests for teachers today
    leave_rows = conn.execute("""
        SELECT lr.reason, t.full_name_kh, t.subject
        FROM leave_requests lr
        JOIN teachers t ON lr.person_id = t.id
        WHERE lr.person_type = 'TEACHER'
          AND lr.status = 'Approved'
          AND ? BETWEEN lr.start_date AND lr.end_date
    """, (target_date,)).fetchall()

    conn.close()

    total_stud_absent = sum(1 for r in student_rows if r["status"] == "ABSENT")
    total_stud_permission = sum(1 for r in student_rows if r["status"] == "PERMISSION")

    # Group students by class
    class_absences = {}
    for r in student_rows:
        cname = r["class_name"]
        if cname not in class_absences:
            class_absences[cname] = []
        class_absences[cname].append(r)

    # Build Message
    msg_lines = [
        f"📊 <b>របាយការណ៍អវត្តមានប្រចាំថ្ងៃ (Daily Absence Report)</b>",
        f"🏫 <b>{school_name}</b>",
        f"📅 កាលបរិច្ឆេទ៖ <b>{formatted_date}</b>",
        f"━━━━━━━━━━━━━━━━━━━━\n",
        f"👥 <b>អវត្តមានសិស្សានុសិស្សសរុប៖ {to_khmer_numerals(len(student_rows))} នាក់</b>",
        f"   ❌ ឥតច្បាប់ (ABSENT)៖ {to_khmer_numerals(total_stud_absent)} នាក់",
        f"   ⚠️ មានច្បាប់ (PERMISSION)៖ {to_khmer_numerals(total_stud_permission)} នាក់\n"
    ]

    if class_absences:
        msg_lines.append("📋 <b>ព័ត៌មានលម្អិតតាមថ្នាក់រៀន៖</b>")
        for cname, slist in class_absences.items():
            stud_strs = []
            for s in slist[:6]: # Limit display to avoid hitting Telegram length
                st_icon = "❌" if s["status"] == "ABSENT" else "⚠️"
                stud_strs.append(f"{st_icon} {s['full_name_kh']}")
            extra = f" (+{to_khmer_numerals(len(slist)-6)} នាក់ទៀត)" if len(slist) > 6 else ""
            msg_lines.append(f"• <b>ថ្នាក់ {cname}</b> ({to_khmer_numerals(len(slist))} នាក់)៖ {', '.join(stud_strs)}{extra}")
    else:
        msg_lines.append("✅ <i>គ្មានសិស្សអវត្តមាននៅថ្ងៃនេះទេ (វត្តមាន ១០០%)!</i>")

    msg_lines.append("\n━━━━━━━━━━━━━━━━━━━━")
    teacher_absent_count = len(teacher_rows) + len(leave_rows)
    msg_lines.append(f"👨‍🏫 <b>អវត្តមានគ្រូបង្រៀនសរុប៖ {to_khmer_numerals(teacher_absent_count)} នាក់</b>")

    if teacher_rows or leave_rows:
        seen_teachers = set()
        for tr in teacher_rows:
            tname = tr["full_name_kh"]
            if tname not in seen_teachers:
                seen_teachers.add(tname)
                st_icon = "❌" if tr["status"] == "ABSENT" else "⚠️"
                msg_lines.append(f"• {st_icon} <b>{tname}</b> (ឯកទេស {tr['subject']}) - {tr['status']} ({tr['reason'] or 'គ្មានមូលហេតុ'})")
        for lr in leave_rows:
            tname = lr["full_name_kh"]
            if tname not in seen_teachers:
                seen_teachers.add(tname)
                msg_lines.append(f"• 📝 <b>{tname}</b> (ឯកទេស {lr['subject']}) - សុំច្បាប់ឈប់សម្រាក ({lr['reason']})")
    else:
        msg_lines.append("✅ <i>គ្រូបង្រៀនទាំងអស់បានចូលបង្រៀនពេញលេញគ្រប់ម៉ោង!</i>")

    msg_lines.append(f"\n🕒 បញ្ជូនរបាយការណ៍នៅម៉ោង៖ {to_khmer_numerals(datetime.now().strftime('%H:%M'))}")

    final_text = "\n".join(msg_lines)
    return send_telegram_message(admin_chat_id, final_text, bot_token=bot_token)


def send_hourly_student_and_homeroom_alerts(class_id, date_str, shift, period_label, teacher_name="", subject_name="", absent_records=None):
    """
    ផ្ញើរបាយការណ៍អវត្តមានតាមម៉ោង៖
    1. ផ្ញើទៅកាន់ Telegram របស់អាណាព្យាបាលសិស្សម្នាក់ៗ (ប្រសិនបើមាន Telegram)
    2. ផ្ញើទៅកាន់ Telegram Group របស់គ្រូបន្ទុកថ្នាក់
    """
    if not absent_records:
        return True, "គ្មានសិស្សអវត្តមានក្នុងម៉ោងនេះទេ"

    bot_token = db.get_setting("telegram_bot_token", "").strip()
    if not bot_token:
        return False, "មិនទាន់កំណត់ Telegram Bot Token"

    school_name = db.get_setting("school_name_kh", "វិទ្យាល័យ ហ៊ុន សែន កំពង់កន្ទួត")
    school_phone = db.get_setting("school_phone", "023 888 999")
    formatted_date = format_khmer_date(date_str)
    shift_kh = "ពេលព្រឹក" if shift == "Morning" else "ពេលរសៀល"

    conn = db.get_db_connection()
    class_row = conn.execute("SELECT * FROM classes WHERE id = ?", (class_id,)).fetchone()
    class_name = class_row["class_name"] if class_row else f"ថ្នាក់ #{class_id}"
    homeroom_chat_id = class_row["telegram_chat_id"] if class_row and "telegram_chat_id" in class_row.keys() else None

    # Filter only absent or permission records
    flagged_students = [r for r in absent_records if r.get("status") in ("ABSENT", "PERMISSION", "LATE")]
    if not flagged_students:
        conn.close()
        return True, "គ្មានសិស្សអវត្តមាន"

    notify_parents_enabled = db.get_setting("telegram_notify_parent", "1") == "1"
    notify_homeroom_enabled = db.get_setting("telegram_notify_homeroom", "1") == "1"

    # 1. ផ្ញើទៅអាណាព្យាបាលសិស្សម្នាក់ៗ
    if notify_parents_enabled:
        for rec in flagged_students:
            student_id = rec.get("student_id")
            s_row = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
            if not s_row:
                continue

            parent_tg = s_row["parent_telegram"] if "parent_telegram" in s_row.keys() and s_row["parent_telegram"] else None
            # Only send if parent Telegram chat ID / username is specified
            if parent_tg and parent_tg.strip():
                status_text = "អវត្តមានឥតច្បាប់ (ABSENT)" if rec.get("status") == "ABSENT" else ("សុំច្បាប់ (PERMISSION)" if rec.get("status") == "PERMISSION" else "មកយឺត (LATE)")
                status_icon = "❌" if rec.get("status") == "ABSENT" else "⚠️"
                reason_text = rec.get("reason", "").strip() or "មិនបានបញ្ជាក់មូលហេតុ"

                parent_msg = (
                    f"📢 <b>ដំណឹងអវត្តមានសិស្ស - {school_name}</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"ជូនចំពោះអាណាព្យាបាលសិស្សឈ្មោះ៖ <b>{s_row['full_name_kh']}</b>\n"
                    f"• អត្តលេខ៖ <code>{s_row['student_code']}</code>\n"
                    f"• ថ្នាក់រៀន៖ <b>{class_name}</b>\n"
                    f"• កាលបរិច្ឆេទ៖ {formatted_date} ({shift_kh})\n"
                    f"• ម៉ោងសិក្សា៖ <b>{period_label}</b>\n"
                    f"• ស្ថានភាព៖ {status_icon} <b>{status_text}</b>\n"
                    f"• មូលហេតុ៖ {reason_text}\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"ℹ️ <i>សូមអាណាព្យាបាលមេត្តាជ្រាបជាព័ត៌មាន។ ប្រសិនបើមានចម្ងល់ សូមទាក់ទងមកកាន់សាលារៀនតាមលេខ៖ {school_phone}</i>"
                )
                try:
                    send_telegram_message(parent_tg, parent_msg, bot_token=bot_token)
                except Exception as ex:
                    logger.warning(f"Could not send to parent {parent_tg}: {ex}")

    # 2. ផ្ញើទៅ Telegram Group របស់គ្រូបន្ទុកថ្នាក់
    if notify_homeroom_enabled and homeroom_chat_id and homeroom_chat_id.strip():
        absent_list = [r for r in flagged_students if r.get("status") == "ABSENT"]
        perm_list = [r for r in flagged_students if r.get("status") == "PERMISSION"]
        late_list = [r for r in flagged_students if r.get("status") == "LATE"]

        group_msg_lines = [
            f"📋 <b>របាយការណ៍អវត្តមានសិស្សតាមម៉ោង</b>",
            f"🏫 <b>{school_name}</b>",
            f"• ថ្នាក់រៀន៖ <b>{class_name}</b>",
            f"• កាលបរិច្ឆេទ៖ {formatted_date} ({shift_kh})",
            f"• ម៉ោងបង្រៀន៖ <b>{period_label}</b>",
        ]
        if teacher_name:
            t_info = f"• គ្រូបង្រៀន៖ <b>{teacher_name}</b>"
            if subject_name:
                t_info += f" ({subject_name})"
            group_msg_lines.append(t_info)

        group_msg_lines.append("━━━━━━━━━━━━━━━━━━━━")

        if absent_list:
            group_msg_lines.append(f"❌ <b>អវត្តមានឥតច្បាប់ ({to_khmer_numerals(len(absent_list))} នាក់)៖</b>")
            for idx, item in enumerate(absent_list, 1):
                s_name = item.get("full_name_kh") or f"សិស្ស #{item.get('student_id')}"
                r_text = f" ({item.get('reason')})" if item.get("reason") else ""
                group_msg_lines.append(f"  {to_khmer_numerals(idx)}. {s_name}{r_text}")

        if perm_list:
            group_msg_lines.append(f"\n⚠️ <b>មានច្បាប់ ({to_khmer_numerals(len(perm_list))} នាក់)៖</b>")
            for idx, item in enumerate(perm_list, 1):
                s_name = item.get("full_name_kh") or f"សិស្ស #{item.get('student_id')}"
                r_text = f" ({item.get('reason')})" if item.get("reason") else ""
                group_msg_lines.append(f"  {to_khmer_numerals(idx)}. {s_name}{r_text}")

        if late_list:
            group_msg_lines.append(f"\n⏰ <b>មកយឺត ({to_khmer_numerals(len(late_list))} នាក់)៖</b>")
            for idx, item in enumerate(late_list, 1):
                s_name = item.get("full_name_kh") or f"សិស្ស #{item.get('student_id')}"
                group_msg_lines.append(f"  {to_khmer_numerals(idx)}. {s_name}")

        group_msg_lines.append(f"\n🕒 កត់ត្រាដោយស្វ័យប្រវត្តិនាវេលាម៉ោង {to_khmer_numerals(datetime.now().strftime('%H:%M'))}")

        final_group_msg = "\n".join(group_msg_lines)
        send_telegram_message(homeroom_chat_id, final_group_msg, bot_token=bot_token)

    conn.close()
    return True, "បានផ្ញើដំណឹង Telegram រួចរាល់"


def send_leave_request_to_admin_with_buttons(leave_id):
    """
    ផ្ញើដំណឹងពាក្យសុំច្បាប់ថ្មីទៅ Telegram Admin ជាមួយប៊ូតុង Inline Keyboard (✅ អនុម័ត / ❌ បដិសេធ)
    """
    req = db.get_leave_request_by_id(leave_id)
    if not req:
        return False, "រកមិនឃើញពាក្យសុំច្បាប់"

    admin_chat_id = db.get_setting("telegram_leave_admin_chat_id", "").strip() or db.get_setting("telegram_admin_chat_id", "").strip()
    bot_token = db.get_setting("telegram_bot_token", "").strip()
    if not bot_token or not admin_chat_id:
        return False, "មិនទាន់កំណត់ Telegram Bot Token ឬ Admin Chat ID"

    school_name = db.get_setting("school_name_kh", "វិទ្យាល័យ ហ៊ុន សែន កំពង់កន្ទួត")
    start_fmt = format_khmer_date(req["start_date"])
    end_fmt = format_khmer_date(req["end_date"])
    date_display = start_fmt if req["start_date"] == req["end_date"] else f"{start_fmt} ដល់ {end_fmt}"

    person_type_kh = "លោកគ្រូ-អ្នកគ្រូ" if req["person_type"] == "TEACHER" else "សិស្សានុសិស្ស"
    person_icon = "👨‍🏫" if req["person_type"] == "TEACHER" else "🎓"

    # Fetch slots affected if teacher
    slots_info = ""
    if req["person_type"] == "TEACHER":
        try:
            _, _, affected_slots = db.validate_teacher_leave_eligibility(req["person_id"], req["start_date"], req["end_date"])
            if affected_slots:
                slot_names = [f"• ថ្នាក់ {s['class_code']} {s['period_label']}" for s in affected_slots[:6]]
                slots_info = "\n⏰ <b>ម៉ោងបង្រៀនដែលត្រូវសម្រាក៖</b>\n" + "\n".join(slot_names)
                if len(affected_slots) > 6:
                    slots_info += f"\n<i>(+{to_khmer_numerals(len(affected_slots)-6)} ម៉ោងទៀត)</i>"
        except Exception as ex:
            logger.warning(f"Error checking leave affected slots: {ex}")

    msg = (
        f"📝 <b>ពាក្យសុំច្បាប់ឈប់សម្រាកថ្មី ({person_type_kh})</b>\n"
        f"🏫 <b>{school_name}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{person_icon} <b>{req['person_name_kh']}</b> (អត្តលេខ៖ <code>{req['person_code'] or '-'}</code>)\n"
    )
    if req.get("subject"):
        msg += f"📚 ឯកទេស៖ <b>{req['subject']}</b>\n"
    msg += (
        f"📅 កាលបរិច្ឆេទ៖ <b>{date_display}</b>\n"
        f"💬 មូលហេតុ៖ <i>{req['reason']}</i>\n"
    )
    if slots_info:
        msg += slots_info + "\n"
    msg += (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👇 <i>សូមជ្រើសរើសសកម្មភាពដើម្បីអនុម័ត ឬបដិសេធ៖</i>"
    )

    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "✅ អនុម័ត (Approve)", "callback_data": f"leave:approve:{leave_id}"},
                {"text": "❌ បដិសេធ (Reject)", "callback_data": f"leave:reject:{leave_id}"}
            ]
        ]
    }

    return send_telegram_message(admin_chat_id, msg, reply_markup=reply_markup, bot_token=bot_token)


def handle_telegram_callback_query(callback_data_dict):
    """
    ដំណើរការ Callback Query ពី Telegram Webhook នៅពេល Admin ចុចប៊ូតុង Inline
    """
    cb_id = callback_data_dict.get("id")
    from_user = callback_data_dict.get("from", {})
    user_name = from_user.get("first_name", "")
    if from_user.get("last_name"):
        user_name += f" {from_user.get('last_name')}"
    user_name = user_name.strip() or from_user.get("username") or "Admin Telegram"

    message = callback_data_dict.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    message_id = message.get("message_id")
    data_str = callback_data_dict.get("data", "")

    if not data_str:
        answer_telegram_callback_query(cb_id, text="ទិន្នន័យមិនត្រឹមត្រូវ")
        return False, "ទិន្នន័យមិនត្រឹមត្រូវ"

    parts = data_str.split(":")
    if len(parts) >= 3 and parts[0] == "leave":
        action = parts[1] # approve or reject
        try:
            leave_id = int(parts[2])
        except ValueError:
            return False, "Invalid leave ID"

        req = db.get_leave_request_by_id(leave_id)
        if not req:
            answer_telegram_callback_query(cb_id, text="⚠️ រកមិនឃើញពាក្យសុំច្បាប់នេះទេ")
            return False, "Leave not found"

        now_str = to_khmer_numerals(datetime.now().strftime("%H:%M - %d/%m/%Y"))
        orig_text = message.get("text", "")

        if action == "approve":
            db.update_leave_request_status(leave_id, "Approved", approved_by=f"{user_name}")
            answer_telegram_callback_query(cb_id, text="✅ បានអនុម័តពាក្យសុំច្បាប់ជោគជ័យ!")
            updated_text = (
                f"{orig_text}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ <b>បានអនុម័តដោយ៖ {user_name}</b>\n"
                f"🕒 វេលាម៉ោង៖ {now_str}"
            )
            edit_telegram_message(chat_id, message_id, updated_text, reply_markup={"inline_keyboard": []})
            return True, f"Approved leave #{leave_id}"

        elif action == "reject":
            db.update_leave_request_status(leave_id, "Rejected", approved_by=f"{user_name}")
            answer_telegram_callback_query(cb_id, text="❌ បានបដិសេធពាក្យសុំច្បាប់!")
            updated_text = (
                f"{orig_text}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"❌ <b>ត្រូវបានបដិសេធដោយ៖ {user_name}</b>\n"
                f"🕒 វេលាម៉ោង៖ {now_str}"
            )
            edit_telegram_message(chat_id, message_id, updated_text, reply_markup={"inline_keyboard": []})
            return True, f"Rejected leave #{leave_id}"

    answer_telegram_callback_query(cb_id, text="ការបញ្ជាមិនស្គាល់")
    return False, "Unknown action"


def check_and_dispatch_period_attendance(current_dt=None):
    """
    រៀងរាល់ម៉ោងសិក្សា៖ ពិនិត្យមើលនៅក្រោយពេលចូលថ្នាក់ ៣០ នាទី (ឬចំនួននាទីកំណត់ដោយ Admin)៖
    1. បើគ្រូមិនទាន់ស្រង់វត្តមាន ➡️ ផ្ញើសារព្រមានរំលឹកបន្ទាន់ទៅកាន់ Telegram Admin
    2. បើគ្រូបានស្រង់វត្តមានរួច ➡️ ផ្ញើដំណឹងអវត្តមានសិស្សទៅ Telegram Class Group
    """
    if current_dt is None:
        current_dt = datetime.now()

    # Skip Sundays
    if current_dt.weekday() == 6:
        return {"checked": False, "reason": "Sunday - No classes"}

    bot_token = db.get_setting("telegram_bot_token", "").strip()
    admin_chat_id = db.get_setting("telegram_admin_chat_id", "").strip()
    if not bot_token:
        return {"checked": False, "reason": "No bot token configured"}

    period_info = db.get_current_period_info(current_dt)
    if not period_info.get("has_active_period"):
        return {"checked": False, "reason": "Outside teaching hours"}

    active_p = period_info.get("period")
    if not active_p:
        return {"checked": False, "reason": "No period details"}

    start_min = active_p["start_hour"] * 60 + active_p["start_min"]
    cur_min = current_dt.hour * 60 + current_dt.minute
    minutes_elapsed = cur_min - start_min

    # Threshold minutes (default 30 mins)
    try:
        reminder_threshold = int(db.get_setting("telegram_period_reminder_minutes", "30"))
    except Exception:
        reminder_threshold = 30

    if minutes_elapsed < reminder_threshold:
        return {
            "checked": False,
            "reason": f"Only {minutes_elapsed} mins into period (threshold is {reminder_threshold} mins)"
        }

    date_str = current_dt.strftime("%Y-%m-%d")
    period_num = active_p["db_period_num"]
    shift = active_p["shift"]
    school_name = db.get_setting("school_name_kh", "វិទ្យាល័យ ហ៊ុន សែន កំពង់កន្ទួត")

    slots_data = db.get_unmarked_slots_for_period(date_str, period_num, shift)
    unmarked_slots = slots_data.get("unmarked", [])
    marked_slots = slots_data.get("marked", [])

    alerts_sent = 0
    # 1. សម្រាប់គ្រូដែលខកខានមិនទាន់ស្រង់វត្តមាន ផ្ញើទៅ Admin
    if admin_chat_id and unmarked_slots:
        for slot in unmarked_slots:
            slot_id = slot["id"]
            if not db.is_period_alert_sent(date_str, slot_id, "MISSED_ATTENDANCE"):
                teacher_name = slot.get("teacher_full_name") or "លោកគ្រូ-អ្នកគ្រូ"
                subject_name = slot.get("teacher_subject") or "មុខវិជ្ជាទូទៅ"
                class_name = slot.get("class_name") or slot.get("class_code")
                room = slot.get("room_number") or "-"

                warning_msg = (
                    f"⚠️ <b>ការរំលឹក៖ គ្រូខកខានមិនទាន់ស្រង់វត្តមានសិស្ស!</b>\n"
                    f"🏫 <b>{school_name}</b>\n"
                    f"🕒 ម៉ោងសិក្សា៖ <b>{active_p['label']}</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"👨‍🏫 <b>{teacher_name}</b> (ឯកទេស {subject_name})\n"
                    f"🏫 ថ្នាក់រៀន៖ <b>{class_name}</b> | បន្ទប់៖ <b>{room}</b>\n"
                    f"👉 <i>បានចូលរៀនលើស {to_khmer_numerals(reminder_threshold)} នាទីហើយ តែមិនទាន់កត់ត្រាវត្តមានសិស្សនៅឡើយ!</i>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"🕒 វេលាព្រមាន៖ {to_khmer_numerals(current_dt.strftime('%H:%M'))}"
                )
                ok, _ = send_telegram_message(admin_chat_id, warning_msg, bot_token=bot_token)
                if ok:
                    db.record_period_alert_sent(date_str, slot_id, "MISSED_ATTENDANCE")
                    alerts_sent += 1

    return {
        "checked": True,
        "period": active_p["label"],
        "minutes_elapsed": minutes_elapsed,
        "unmarked_count": len(unmarked_slots),
        "marked_count": len(marked_slots),
        "alerts_sent": alerts_sent
    }


def setup_telegram_webhook(webhook_url, bot_token=None):
    """
    ចុះឈ្មោះ Webhook URL ជាមួយ Telegram Bot API
    """
    if not bot_token:
        bot_token = db.get_setting("telegram_bot_token", "").strip()
    if not bot_token:
        return False, "សូមបញ្ចូល Telegram Bot Token ជាមុនសិន!"
    if not webhook_url:
        return False, "សូមបញ្ចូល Webhook URL!"

    url = f"https://api.telegram.org/bot{bot_token}/setWebhook"
    try:
        res = requests.post(url, json={"url": webhook_url.strip()}, timeout=10)
        data = res.json()
        if res.status_code == 200 and data.get("ok"):
            db.set_setting("telegram_webhook_url", webhook_url.strip())
            return True, "បានភ្ជាប់ Webhook ជាមួយ Telegram ដោយជោគជ័យ!"
        return False, data.get("description", "Error setting webhook")
    except Exception as e:
        return False, str(e)


def get_telegram_webhook_info(bot_token=None):
    """
    ត្រួតពិនិត្យព័ត៌មានស្ថានភាព Webhook ពី Telegram
    """
    if not bot_token:
        bot_token = db.get_setting("telegram_bot_token", "").strip()
    if not bot_token:
        return False, "មិនទាន់កំណត់ Telegram Bot Token ទេ"

    url = f"https://api.telegram.org/bot{bot_token}/getWebhookInfo"
    try:
        res = requests.get(url, timeout=10)
        data = res.json()
        if res.status_code == 200 and data.get("ok"):
            return True, data.get("result", {})
        return False, data.get("description", "Error getting webhook info")
    except Exception as e:
        return False, str(e)

