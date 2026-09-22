"""
ប្រព័ន្ធគ្រប់គ្រងអវត្តមានសិស្ស និងគ្រូបង្រៀន (Student & Teacher Absence Management System)
Flask Web Application & REST APIs
"""

import os
import sys
import json
import socket
import io
import qrcode
from datetime import datetime

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import functools
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash, session
import database as db
import export_service
import google_sheets_sync
import telegram_service
import kkhs_sync_service
import firestore_sync_service

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "student_absence_system_secret_key_cambodia")

# Ensure database and default users are initialized
db.init_db()
db.init_default_users()


@app.context_processor
def inject_school_info():
    return {
        "global_school_name_kh": db.get_setting("school_name_kh", "វិទ្យាល័យ ហ៊ុន សែន កំពង់កន្ទួត"),
        "global_school_name_en": db.get_setting("school_name_en", "Hun Sen Kampong Kantuot High School"),
        "current_user": session.get("user")
    }


def login_required(role=None):
    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            if "user" not in session:
                if request.path.startswith("/api/"):
                    return jsonify({"success": False, "error": "Unauthorized", "message": "សូមចូលគណនីជាមុនសិន"}), 401
                return redirect(url_for("login", next=request.url))

            user = session["user"]
            if role and user.get("role") != role:
                if request.path.startswith("/api/"):
                    return jsonify({"success": False, "error": "Forbidden", "message": "អ្នកមិនមានសិទ្ធិអនុវត្តប្រតិបត្តិការនេះទេ"}), 403
                flash("អ្នកមិនមានសិទ្ធិចូលទំព័រនេះទេ (ទាមទារសិទ្ធិជា Administrator)!", "warning")
                return redirect(url_for("portal_page", teacher_id=user.get("teacher_id")))

            return f(*args, **kwargs)
        return decorated_function
    return decorator


# -------------------------------------------------------------
# Authentication & User Management Routes
# -------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()
        remember = bool(request.form.get("remember"))

        user = db.authenticate_user(username, password)
        if user:
            session["user"] = {
                "id": user["id"],
                "username": user["username"],
                "role": user["role"],
                "full_name_kh": user["full_name_kh"],
                "teacher_id": user["teacher_id"],
                "phone": user["phone"]
            }
            session.permanent = remember

            next_url = request.args.get("next")
            if user["role"] == "admin":
                if next_url and not next_url.startswith("/login"):
                    return redirect(next_url)
                return redirect(url_for("index"))
            else:
                return redirect(url_for("portal_page", teacher_id=user["teacher_id"]))
        else:
            return render_template("login.html", username=username, error="ឈ្មោះគណនី ឬលេខសម្ងាត់មិនត្រឹមត្រូវទេ! សូមព្យាយាមម្តងទៀត។")

    if "user" in session:
        user = session["user"]
        if user.get("role") == "admin":
            return redirect(url_for("index"))
        else:
            return redirect(url_for("portal_page", teacher_id=user.get("teacher_id")))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("លោកអ្នកបានចាកចេញពីប្រព័ន្ធដោយជោគជ័យ!", "info")
    return redirect(url_for("login"))


@app.route("/change-password", methods=["POST"])
@login_required()
def change_password():
    data = request.get_json() if request.is_json else request.form
    old_password = (data.get("old_password") or "").strip()
    new_password = (data.get("new_password") or "").strip()
    confirm_password = (data.get("confirm_password") or "").strip()

    user_info = session.get("user")
    user = db.authenticate_user(user_info["username"], old_password)
    if not user:
        if request.is_json:
            return jsonify({"success": False, "message": "លេខសម្ងាត់បច្ចុប្បន្ន (Old Password) មិនត្រឹមត្រូវទេ!"}), 400
        flash("លេខសម្ងាត់បច្ចុប្បន្នមិនត្រឹមត្រូវទេ!", "danger")
        return redirect(request.referrer or url_for("index"))

    if len(new_password) < 6:
        if request.is_json:
            return jsonify({"success": False, "message": "លេខសម្ងាត់ថ្មីត្រូវមានយ៉ាងតិច ៦ តួអក្សរ!"}), 400
        flash("លេខសម្ងាត់ថ្មីត្រូវមានយ៉ាងតិច ៦ តួអក្សរ!", "danger")
        return redirect(request.referrer or url_for("index"))

    if new_password != confirm_password:
        if request.is_json:
            return jsonify({"success": False, "message": "ការបញ្ជាក់លេខសម្ងាត់ថ្មីមិនត្រូវគ្នាទេ!"}), 400
        flash("ការបញ្ជាក់លេខសម្ងាត់ថ្មីមិនត្រូវគ្នាទេ!", "danger")
        return redirect(request.referrer or url_for("index"))

    db.change_user_password(user_info["id"], new_password)

    if request.is_json:
        return jsonify({"success": True, "message": "បានផ្លាស់ប្តូរលេខសម្ងាត់ដោយជោគជ័យ!"})
    flash("បានផ្លាស់ប្តូរលេខសម្ងាត់ដោយជោគជ័យ!", "success")
    return redirect(request.referrer or url_for("index"))


@app.route("/users")
@login_required(role="admin")
def users_page():
    users = db.get_all_users()
    return render_template("users.html", users=users)


@app.route("/users/reset-password/<int:user_id>", methods=["POST"])
@login_required(role="admin")
def users_reset_password(user_id):
    success = db.reset_user_password(user_id, "123456")
    if success:
        return jsonify({"success": True, "message": "បានកំណត់លេខសម្ងាត់ឡើងវិញទៅជា 123456 រួចរាល់!"})
    return jsonify({"success": False, "message": "មិនអាចកំណត់លេខសម្ងាត់ឡើងវិញបានទេ"}), 400


@app.route("/export/users/excel")
@login_required(role="admin")
def export_users_excel_route():
    file_path = export_service.export_users_excel()
    return send_file(file_path, as_attachment=True, download_name=os.path.basename(file_path))


# -------------------------------------------------------------
# Web Page Routes
# -------------------------------------------------------------
@app.route("/")
@login_required(role="admin")
def index():
    today = datetime.now().strftime("%Y-%m-%d")
    stats = db.get_dashboard_stats(today)
    classes = db.get_classes()
    school_name = db.get_setting("school_name_kh", "វិទ្យាល័យ ហ៊ុន សែន កំពង់កន្ទួត")
    return render_template("dashboard.html", stats=stats, today=today, classes=classes, school_name=school_name)


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_today_khmer_day():
    day_idx = datetime.now().weekday()
    mapping = {
        0: {"code": "ច", "name": "ចន្ទ", "en": "Monday"},
        1: {"code": "អ", "name": "អង្គារ", "en": "Tuesday"},
        2: {"code": "ព", "name": "ពុធ", "en": "Wednesday"},
        3: {"code": "ព្រ", "name": "ព្រហស្បតិ៍", "en": "Thursday"},
        4: {"code": "សុ", "name": "សុក្រ", "en": "Friday"},
        5: {"code": "ស", "name": "សៅរ៍", "en": "Saturday"},
        6: {"code": "អា", "name": "អាទិត្យ", "en": "Sunday"}
    }
    return mapping.get(day_idx, {"code": "ច", "name": "ចន្ទ", "en": "Monday"})


@app.route("/portal")
@login_required()
def portal_page():
    all_teachers = db.get_teachers(active_only=True)
    all_classes = db.get_classes()
    user = session.get("user")
    is_teacher = bool(user and user.get("role") == "teacher")

    teacher_id = request.args.get("teacher_id", type=int)
    # If logged in user is a teacher, STRICTLY lock to their own teacher_id
    if is_teacher and user.get("teacher_id"):
        teacher_id = user["teacher_id"]
    elif not teacher_id:
        if all_teachers:
            teacher_id = all_teachers[0]["id"]

    current_teacher = db.get_teacher_by_id(teacher_id) if teacher_id else (all_teachers[0] if all_teachers else None)
    today_info = get_today_khmer_day()

    today_slots = []
    active_slot_info = None
    if current_teacher:
        today_slots = db.get_teacher_today_slots(current_teacher["id"], today_info["code"])
        active_slot_info = db.get_current_teaching_slot(current_teacher["id"])

    return render_template(
        "portal.html",
        current_teacher=current_teacher,
        all_teachers=all_teachers,
        all_classes=all_classes,
        today_info=today_info,
        today_slots=today_slots,
        active_slot_info=active_slot_info,
        is_teacher=is_teacher
    )


@app.route("/portal/attendance")
@login_required()
def portal_attendance_page():
    user = session.get("user")
    is_teacher = bool(user and user.get("role") == "teacher")
    period_info = db.get_current_period_info()

    if is_teacher:
        teacher_id = user.get("teacher_id")
        active_slot_info = db.get_current_teaching_slot(teacher_id)
        if not active_slot_info.get("has_slot"):
            flash(f"លោកគ្រូ-អ្នកគ្រូ មិនមានម៉ោងបង្រៀននៅក្នុងម៉ោងនេះទេ ({active_slot_info.get('reason', '')})!", "warning")
            return redirect(url_for("portal_page"))

        slot = active_slot_info["slot"]
        current_class = db.get_class_by_id(slot["class_db_id"])
        date_str = active_slot_info["period_info"]["current_date_str"]
        shift = active_slot_info["period_info"]["period"]["shift"]
        period = f"Session {slot['period_num']}"
        period_label = active_slot_info["period_info"]["period"]["label"]
        period_short = active_slot_info["period_info"]["period"]["short_label"]
        window_phase = active_slot_info["period_info"]["phase"]
        window_phase_kh = active_slot_info["period_info"]["phase_kh"]
        submission_audit = active_slot_info.get("audit", {})
        is_locked = True
        sec_remaining_first_30 = active_slot_info["period_info"]["period"].get("sec_remaining_first_30", 0)
        sec_remaining_period = active_slot_info["period_info"]["period"].get("sec_remaining_period", 0)

        # Check if submission is allowed right now
        sub_count = submission_audit.get("submission_count", 0)
        if window_phase == "first_30":
            can_submit = True
            submit_help_text = "លោកគ្រូ-អ្នកគ្រូ អាចបញ្ចូល ឬកែប្រែបានច្រើនដងក្នុង ៣០ នាទីដំបូងនេះ"
        else:
            if sub_count == 0:
                can_submit = True
                submit_help_text = "ចន្លោះពេលបន្ថែម៖ អនុញ្ញាតបញ្ចូលបានតែ ១ ដងគត់ មុនផុតកំណត់"
            else:
                can_submit = False
                submit_help_text = "បានផុតម៉ោងអនុញ្ញាតកែប្រែ (បានបញ្ចូលរួចហើយ)"

        attendance_list = db.get_student_attendance(current_class["id"], date_str, shift, period) if current_class else []

        return render_template(
            "portal_attendance.html",
            current_class=current_class,
            date=date_str,
            date_display=active_slot_info["period_info"]["current_date_display"],
            shift=shift,
            period=period,
            period_label=period_label,
            period_short=period_short,
            window_phase=window_phase,
            window_phase_kh=window_phase_kh,
            submission_audit=submission_audit,
            can_submit=can_submit,
            submit_help_text=submit_help_text,
            is_locked=is_locked,
            sec_remaining_first_30=sec_remaining_first_30,
            sec_remaining_period=sec_remaining_period,
            attendance_list=attendance_list
        )

    # If Admin
    class_code = request.args.get("class_code", "").strip()
    class_id = request.args.get("class_id", type=int)
    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    shift = request.args.get("shift", period_info["period"]["shift"] if period_info.get("period") else "Morning")
    period = request.args.get("period", f"Session {period_info['period']['db_period_num']}" if period_info.get("period") else "Daily")

    current_class = None
    if class_id:
        current_class = db.get_class_by_id(class_id)
    elif class_code:
        current_class = db.get_class_by_code(class_code)
        if current_class:
            class_id = current_class["id"]

    if not current_class:
        classes = db.get_classes()
        if classes:
            current_class = classes[0]
            class_id = current_class["id"]

    attendance_list = db.get_student_attendance(class_id, date_str, shift, period) if class_id else []

    return render_template(
        "portal_attendance.html",
        current_class=current_class,
        date=date_str,
        date_display=datetime.strptime(date_str, "%Y-%m-%d").strftime("%d/%m/%Y"),
        shift=shift,
        period=period,
        period_label=f"វេន {shift} - {period}",
        period_short=period,
        window_phase="admin",
        window_phase_kh="សិទ្ធិ Administrator (គ្មានដែនកំណត់)",
        submission_audit={"submission_count": 0},
        can_submit=True,
        submit_help_text="សិទ្ធិគ្រប់គ្រងជា Administrator",
        is_locked=False,
        sec_remaining_first_30=0,
        sec_remaining_period=period_info.get("sec_until_next_hour", 3600),
        attendance_list=attendance_list
    )


@app.route("/portal/qr")
def portal_qr():
    local_ip = get_local_ip()
    port = request.host.split(":")[-1] if ":" in request.host else "5000"
    portal_url = f"http://{local_ip}:{port}/portal"

    img = qrcode.make(portal_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@app.route("/api/portal/local-url")
def api_portal_local_url():
    local_ip = get_local_ip()
    port = request.host.split(":")[-1] if ":" in request.host else "5000"
    portal_url = f"http://{local_ip}:{port}/portal"
    return jsonify({"local_ip": local_ip, "port": port, "portal_url": portal_url})


@app.route("/timetable")
@login_required()
def timetable_page():
    classes = db.get_classes()
    timetable_classes = db.get_all_timetable_classes()
    teachers = db.get_teachers(active_only=True)
    subjects = db.get_all_subjects()

    user = session.get("user")
    is_teacher = bool(user and user.get("role") == "teacher")

    view_type = request.args.get("view", "class")
    selected_class_code = request.args.get("class_code", timetable_classes[0] if timetable_classes else "7A")
    selected_teacher_id = request.args.get("teacher_id", teachers[0]["id"] if teachers else 1, type=int)

    # Strict isolation: A teacher can ONLY see their own timetable
    if is_teacher:
        view_type = "teacher"
        selected_teacher_id = user.get("teacher_id") or (teachers[0]["id"] if teachers else 1)

    class_obj = None
    if view_type == "teacher":
        slots = db.get_timetable_by_teacher(selected_teacher_id)
        current_entity = db.get_teacher_by_id(selected_teacher_id)
    else:
        slots = db.get_timetable_by_class(selected_class_code)
        class_obj = db.get_class_by_code(selected_class_code)
        current_entity = {"full_name_kh": f"ថ្នាក់ទី {selected_class_code}", "code": selected_class_code}

    grid = {}
    for s in slots:
        grid[(s["day_code"], s["period_num"])] = s

    days = [
        {"code": "ច", "name": "ចន្ទ"},
        {"code": "អ", "name": "អង្គារ"},
        {"code": "ព", "name": "ពុធ"},
        {"code": "ព្រ", "name": "ព្រហស្បតិ៍"},
        {"code": "សុ", "name": "សុក្រ"},
        {"code": "ស", "name": "សៅរ៍"},
    ]
    periods = [1, 2, 3, 4, 5, 6, 7, 8]

    return render_template(
        "timetable.html",
        view_type=view_type,
        classes=classes,
        timetable_classes=timetable_classes,
        teachers=teachers,
        subjects=subjects,
        selected_class_code=selected_class_code,
        selected_teacher_id=selected_teacher_id,
        current_entity=current_entity,
        class_obj=class_obj,
        grid=grid,
        days=days,
        periods=periods,
        is_teacher=is_teacher
    )


@app.route("/teacher-attendance")
@login_required(role="admin")
def teacher_attendance_page():
    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    shift = request.args.get("shift", "Morning")
    period = request.args.get("period", "Session 1")

    # Run auto-reconciliation from master timetable slots first
    db.calculate_teacher_attendance_from_slots(date_str)

    teachers_att = db.get_teacher_attendance(date_str, shift, period)
    all_teachers = db.get_teachers(active_only=True)
    accountability_slots = db.get_timetable_accountability(date_str, shift)
    unmarked_slots = [s for s in accountability_slots if not s.get("is_marked")]

    return render_template(
        "teacher_attendance.html",
        date=date_str,
        shift=shift,
        period=period,
        attendance_list=teachers_att,
        all_teachers=all_teachers,
        accountability_slots=accountability_slots,
        unmarked_count=len(unmarked_slots)
    )


@app.route("/student-attendance")
@login_required()
def student_attendance_page():
    user = session.get("user")
    if user and user.get("role") == "teacher":
        return redirect(url_for("portal_attendance_page"))

    classes = db.get_classes()
    class_id = request.args.get("class_id", classes[0]["id"] if classes else 1, type=int)
    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    shift = request.args.get("shift", "Morning")
    period = request.args.get("period", "Daily")

    current_class = db.get_class_by_id(class_id)
    students_att = db.get_student_attendance(class_id, date_str, shift, period)

    return render_template(
        "student_attendance.html",
        classes=classes,
        current_class=current_class,
        class_id=class_id,
        date=date_str,
        shift=shift,
        period=period,
        attendance_list=students_att
    )


@app.route("/teachers")
@login_required(role="admin")
def teachers_page():
    teachers = db.get_teachers(active_only=False)
    return render_template("teachers.html", teachers=teachers)


@app.route("/students")
@login_required()
def students_page():
    classes = db.get_classes()
    class_id = request.args.get("class_id", type=int)
    students = db.get_students(class_id=class_id, active_only=False)
    return render_template("students.html", students=students, classes=classes, selected_class_id=class_id)


@app.route("/leave-requests")
@login_required()
def leave_requests_page():
    requests = db.get_leave_requests()
    teachers = db.get_teachers(active_only=True)
    students = db.get_students(active_only=True)
    return render_template("leave_requests.html", requests=requests, teachers=teachers, students=students)


@app.route("/reports")
@login_required(role="admin")
def reports_page():
    classes = db.get_classes()
    class_id = request.args.get("class_id", type=int)
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    report_type = request.args.get("type", "students")

    if report_type == "teachers":
        report_data = db.get_teacher_report_data(start_date=start_date, end_date=end_date)
    else:
        report_data = db.get_student_report_data(class_id=class_id, start_date=start_date, end_date=end_date)

    return render_template(
        "reports.html",
        classes=classes,
        selected_class_id=class_id,
        start_date=start_date,
        end_date=end_date,
        report_type=report_type,
        report_data=report_data
    )


@app.route("/settings")
@login_required(role="admin")
def settings_page():
    settings = db.get_all_settings()
    return render_template("settings.html", settings=settings)


# -------------------------------------------------------------
# REST API Endpoints
# -------------------------------------------------------------
@app.route("/api/dashboard-stats")
def api_dashboard_stats():
    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    stats = db.get_dashboard_stats(date_str)
    return jsonify(stats)


@app.route("/api/teacher-attendance", methods=["GET", "POST"])
def api_teacher_attendance():
    if request.method == "POST":
        data = request.get_json() or {}
        date_str = data.get("date")
        shift = data.get("shift", "Morning")
        period = data.get("period", "Session 1")
        records = data.get("records", [])

        if not date_str or not records:
            return jsonify({"success": False, "message": "ទិន្នន័យមិនគ្រប់គ្រាន់"}), 400

        db.save_teacher_attendance(date_str, shift, period, records)
        return jsonify({"success": True, "message": "បានរក្សាទុកវត្តមានគ្រូដោយជោគជ័យ!"})

    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    shift = request.args.get("shift", "Morning")
    period = request.args.get("period", "Session 1")
    records = db.get_teacher_attendance(date_str, shift, period)
    return jsonify({"success": True, "data": records})


@app.route("/api/student-attendance", methods=["GET", "POST"])
def api_student_attendance():
    if request.method == "POST":
        data = request.get_json() or {}
        class_id = data.get("class_id")
        date_str = data.get("date")
        shift = data.get("shift", "Morning")
        period = data.get("period", "Daily")
        records = data.get("records", [])

        if not class_id or not date_str or not records:
            return jsonify({"success": False, "message": "ទិន្នន័យមិនគ្រប់គ្រាន់"}), 400

        user = session.get("user")
        is_admin = bool(user and user.get("role") == "admin")
        teacher_id = user.get("teacher_id") if user else None

        # Verify time-window rule if user is a teacher
        can_submit, status_code, msg, phase, sub_count = db.check_submission_window_rule(
            class_id=int(class_id),
            date_str=date_str,
            shift=shift,
            period_str=period,
            teacher_id=teacher_id,
            is_admin=is_admin
        )
        if not can_submit:
            return jsonify({
                "success": False,
                "message": msg,
                "phase": phase,
                "submission_count": sub_count
            }), status_code

        # Extract period_num
        period_num = 1
        if "Session " in str(period):
            try:
                period_num = int(str(period).replace("Session ", "").strip())
            except Exception:
                pass
        elif str(period).isdigit():
            period_num = int(period)

        recorded_by = user.get("full_name_kh", "Teacher") if user else "Teacher"

        # Save student attendance
        db.save_student_attendance(class_id, date_str, shift, period, records, recorded_by=recorded_by)

        # Record audit log
        audit_count = db.record_attendance_audit(
            class_id=int(class_id),
            date_str=date_str,
            shift=shift,
            period_str=period,
            period_num=period_num,
            teacher_id=teacher_id,
            phase=phase,
            ip_address=request.remote_addr,
            notes=f"Recorded by {recorded_by}"
        )

        # Trigger Telegram Alerts in background / try-except
        try:
            teacher_name = user.get("full_name_kh", "") if user else ""
            subject_name = ""
            if teacher_id:
                t_obj = db.get_teacher_by_id(teacher_id)
                if t_obj:
                    subject_name = t_obj.get("subject", "")

            p_info = db.get_current_period_info()
            period_label = p_info["period"]["label"] if p_info.get("period") else period

            telegram_service.send_hourly_student_and_homeroom_alerts(
                class_id=int(class_id),
                date_str=date_str,
                shift=shift,
                period_label=period_label,
                teacher_name=teacher_name,
                subject_name=subject_name,
                absent_records=records
            )
        except Exception as tg_err:
            app.logger.warning(f"Telegram alert error: {tg_err}")

        return jsonify({
            "success": True,
            "message": "បានរក្សាទុកវត្តមានសិស្សដោយជោគជ័យ!",
            "phase": phase,
            "submission_count": audit_count
        })

    class_id = request.args.get("class_id", type=int)
    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    shift = request.args.get("shift", "Morning")
    period = request.args.get("period", "Daily")
    records = db.get_student_attendance(class_id, date_str, shift, period)
    return jsonify({"success": True, "data": records})


@app.route("/api/timetable/class/<class_code>")
@login_required()
def api_timetable_class(class_code):
    user = session.get("user")
    slots = db.get_timetable_by_class(class_code)
    if user and user.get("role") == "teacher":
        t_id = user.get("teacher_id")
        slots = [s for s in slots if s.get("teacher_id") == t_id]
    return jsonify({"success": True, "data": slots})


@app.route("/api/timetable/teacher/<int:teacher_id>")
@login_required()
def api_timetable_teacher(teacher_id):
    user = session.get("user")
    if user and user.get("role") == "teacher" and user.get("teacher_id") != teacher_id:
        return jsonify({"success": False, "message": "លោកគ្រូ-អ្នកគ្រូមានសិទ្ធិមើលឃើញតែកាលវិភាគផ្ទាល់ខ្លួនប៉ុណ្ណោះ!"}), 403
    slots = db.get_timetable_by_teacher(teacher_id)
    return jsonify({"success": True, "data": slots})


@app.route("/api/timetable/slot/save", methods=["POST"])
@login_required(role="admin")
def api_save_timetable_slot():
    data = request.get_json() or {}
    slot_id = data.get("slot_id")
    class_code = data.get("class_code", "").strip()
    teacher_id = data.get("teacher_id")
    day_code = data.get("day_code", "").strip()
    period_num = data.get("period_num")
    shift = data.get("shift")
    subject_name = data.get("subject_name", "").strip()
    room_number = data.get("room_number", "").strip()

    if not class_code or not day_code or not period_num or not teacher_id or not subject_name:
        return jsonify({"success": False, "message": "សូមបំពេញព័ត៌មានកាលវិភាគឱ្យបានគ្រប់ជ្រុងជ្រោយ (ថ្នាក់, ថ្ងៃ, ម៉ោង, គ្រូ, មុខវិជ្ជា)!"}), 400

    saved_id = db.save_timetable_slot(
        slot_id=int(slot_id) if slot_id else None,
        class_code=class_code,
        teacher_id=int(teacher_id),
        day_code=day_code,
        period_num=int(period_num),
        shift=shift,
        subject_name=subject_name,
        room_number=room_number
    )
    return jsonify({"success": True, "slot_id": saved_id, "message": "បានរក្សាទុកម៉ោងបង្រៀនក្នុងកាលវិភាគដោយជោគជ័យ!"})


@app.route("/api/timetable/slot/delete/<int:slot_id>", methods=["POST", "DELETE"])
@login_required(role="admin")
def api_delete_timetable_slot(slot_id):
    db.delete_timetable_slot(slot_id)
    return jsonify({"success": True, "message": "បានលុបម៉ោងបង្រៀនចេញពីកាលវិភាគរួចរាល់!"})


@app.route("/api/teacher-attendance/reconcile", methods=["POST", "GET"])
@login_required(role="admin")
def api_reconcile_teacher_attendance():
    data = request.get_json() if request.is_json else request.args
    date_str = (data.get("date") if data else None) or datetime.now().strftime("%Y-%m-%d")
    result = db.calculate_teacher_attendance_from_slots(date_str)
    return jsonify({
        "success": True,
        "data": result,
        "message": f"បានផ្ទៀងផ្ទាត់វត្តមានគ្រូតាមកាលវិភាគជោគជ័យ! (វត្តមាន: {result['present']}, អវត្តមាន: {result['absent']}, ច្បាប់: {result['permission']})"
    })


@app.route("/api/timetable/accountability")
@login_required()
def api_timetable_accountability():
    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    shift = request.args.get("shift", "All")
    slots = db.get_timetable_accountability(date_str, shift)
    return jsonify({"success": True, "data": slots})


@app.route("/api/subjects")
@login_required()
def api_subjects():
    subjects = db.get_all_subjects()
    return jsonify({"success": True, "data": subjects})


@app.route("/api/teachers", methods=["GET", "POST"])
def api_teachers():
    if request.method == "POST":
        data = request.get_json() or {}
        code = data.get("teacher_code", "").strip()
        name_kh = data.get("full_name_kh", "").strip()
        gender = data.get("gender", "M")
        phone = data.get("phone", "").strip()
        email = data.get("email", "").strip()
        subject = data.get("subject", "").strip()
        name_en = data.get("full_name_en", "").strip()
        hours = int(data.get("total_hours_weekly", 18))

        if not code or not name_kh:
            return jsonify({"success": False, "message": "សូមបញ្ចូលកូដគ្រូ និងឈ្មោះគ្រូ"}), 400

        new_id = db.add_teacher(code, name_kh, gender, phone, email, subject, name_en, hours)
        return jsonify({"success": True, "id": new_id, "message": "បានបន្ថែមគ្រូបង្រៀនថ្មីជោគជ័យ!"})

    teachers = db.get_teachers(active_only=False)
    return jsonify({"success": True, "data": teachers})


@app.route("/api/teachers/<int:teacher_id>", methods=["PUT", "DELETE"])
def api_teacher_detail(teacher_id):
    if request.method == "DELETE":
        db.delete_teacher(teacher_id)
        return jsonify({"success": True, "message": "បានលុបគ្រូបង្រៀនជោគជ័យ!"})

    data = request.get_json() or {}
    db.update_teacher(
        teacher_id=teacher_id,
        code=data.get("teacher_code"),
        full_name_kh=data.get("full_name_kh"),
        gender=data.get("gender"),
        phone=data.get("phone", ""),
        email=data.get("email", ""),
        subject=data.get("subject", ""),
        full_name_en=data.get("full_name_en", ""),
        status=data.get("status", "Active"),
        total_hours=int(data.get("total_hours_weekly", 18))
    )
    return jsonify({"success": True, "message": "បានកែប្រែព័ត៌មានគ្រូបង្រៀនជោគជ័យ!"})


@app.route("/api/students", methods=["GET", "POST"])
def api_students():
    if request.method == "POST":
        data = request.get_json() or {}
        code = data.get("student_code", "").strip()
        name_kh = data.get("full_name_kh", "").strip()
        gender = data.get("gender", "M")
        class_id = data.get("class_id")
        dob = data.get("dob", "")
        name_en = data.get("full_name_en", "").strip()
        parent_name = data.get("parent_name", "").strip()
        parent_phone = data.get("parent_phone", "").strip()
        parent_telegram = data.get("parent_telegram", "").strip()

        if not code or not name_kh or not class_id:
            return jsonify({"success": False, "message": "សូមបញ្ចូលអត្តលេខ ឈ្មោះ និងថ្នាក់"}), 400

        new_id = db.add_student(code, name_kh, gender, class_id, dob, name_en, parent_name, parent_phone, parent_telegram)
        return jsonify({"success": True, "id": new_id, "message": "បានបន្ថែមសិស្សថ្មីជោគជ័យ!"})

    class_id = request.args.get("class_id", type=int)
    students = db.get_students(class_id=class_id, active_only=False)
    return jsonify({"success": True, "data": students})


@app.route("/api/students/<int:student_id>", methods=["PUT", "DELETE"])
def api_student_detail(student_id):
    if request.method == "DELETE":
        db.delete_student(student_id)
        return jsonify({"success": True, "message": "បានលុបសិស្សជោគជ័យ!"})

    data = request.get_json() or {}
    db.update_student(
        student_id=student_id,
        code=data.get("student_code"),
        full_name_kh=data.get("full_name_kh"),
        gender=data.get("gender"),
        class_id=data.get("class_id"),
        dob=data.get("dob", ""),
        full_name_en=data.get("full_name_en", ""),
        parent_name=data.get("parent_name", ""),
        parent_phone=data.get("parent_phone", ""),
        status=data.get("status", "Active"),
        parent_telegram=data.get("parent_telegram", "")
    )
    return jsonify({"success": True, "message": "បានកែប្រែព័ត៌មានសិស្សជោគជ័យ!"})


@app.route("/api/classes", methods=["GET", "POST"])
def api_classes():
    if request.method == "POST":
        data = request.get_json() or {}
        name = data.get("class_name", "").strip()
        grade = int(data.get("grade_level", 7))
        shift = data.get("shift", "Morning")
        room = data.get("room_number", "").strip()
        academic_year = data.get("academic_year", "2026-2027")

        if not name:
            return jsonify({"success": False, "message": "សូមបញ្ចូលឈ្មោះថ្នាក់"}), 400

        new_id = db.add_class(name, grade, shift, room, academic_year)
        return jsonify({"success": True, "id": new_id, "message": "បានបង្កើតថ្នាក់រៀនថ្មីជោគជ័យ!"})

    classes = db.get_classes()
    return jsonify({"success": True, "data": classes})


@app.route("/api/leave-requests", methods=["GET", "POST"])
def api_leave_requests():
    if request.method == "POST":
        data = request.get_json() or {}
        person_type = data.get("person_type", "TEACHER")
        person_id = data.get("person_id")
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        reason = data.get("reason", "").strip()
        approved_by = data.get("approved_by", "Headmaster")
        notes = data.get("notes", "")

        if not person_id or not start_date or not end_date or not reason:
            return jsonify({"success": False, "message": "សូមបំពេញព័ត៌មានច្បាប់ឱ្យបានពេញលេញ"}), 400

        new_id = db.add_leave_request(person_type, person_id, start_date, end_date, reason, approved_by, notes)
        return jsonify({"success": True, "id": new_id, "message": "បានកត់ត្រាពាក្យសុំច្បាប់ជោគជ័យ!"})

    person_type = request.args.get("person_type")
    rows = db.get_leave_requests(person_type)
    return jsonify({"success": True, "data": rows})


# -------------------------------------------------------------
# Excel Export Endpoints
# -------------------------------------------------------------
@app.route("/export/excel/students")
def export_excel_students():
    class_id = request.args.get("class_id", type=int)
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    file_path = export_service.export_student_attendance_excel(
        class_id=class_id, start_date=start_date, end_date=end_date
    )
    return send_file(file_path, as_attachment=True, download_name=os.path.basename(file_path))


@app.route("/export/excel/teachers")
def export_excel_teachers():
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    file_path = export_service.export_teacher_attendance_excel(
        start_date=start_date, end_date=end_date
    )
    return send_file(file_path, as_attachment=True, download_name=os.path.basename(file_path))


@app.route("/timetable/template/excel")
@login_required(role="admin")
def timetable_template_excel():
    """ទាញយកឯកសារ Excel Template គំរូកាលវិភាគរួមសម្រាប់ Admin បំពេញ"""
    file_path = export_service.export_timetable_template_excel()
    return send_file(file_path, as_attachment=True, download_name=os.path.basename(file_path))


@app.route("/export/excel/timetable")
@login_required(role="admin")
def export_timetable_excel():
    """Export កាលវិភាគរួមសាលាទាំងមូលចេញជា Excel"""
    file_path = export_service.export_master_timetable_excel()
    return send_file(file_path, as_attachment=True, download_name=os.path.basename(file_path))


@app.route("/api/timetable/import-excel", methods=["POST"])
@login_required(role="admin")
def api_import_timetable_excel():
    """ទទួលឯកសារ Excel កាលវិភាគរួម និងធ្វើការ Import ចូល Database"""
    if "file" not in request.files:
        return jsonify({"success": False, "message": "សូមជ្រើសរើសឯកសារ Excel (.xlsx) ដើម្បីបញ្ចូល"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"success": False, "message": "ឈ្មោះឯកសារមិនត្រឹមត្រូវទេ"}), 400

    mode = request.form.get("mode", "merge") # 'merge' or 'replace'

    scratch_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scratch")
    os.makedirs(scratch_dir, exist_ok=True)
    save_path = os.path.join(scratch_dir, f"upload_tt_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
    file.save(save_path)

    try:
        res = db.import_timetable_from_excel(save_path, mode=mode)
        return jsonify({
            "success": True,
            "message": f"បានបញ្ចូលកាលវិភាគរួមចំនួន {res['imported_count']} ម៉ោងបង្រៀនដោយជោគជ័យ!",
            "data": res
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"កំហុសក្នុងការអានឯកសារ Excel៖ {str(e)}"}), 500


# -------------------------------------------------------------
# Google Sheets Configuration & Sync Endpoints
# -------------------------------------------------------------
@app.route("/api/settings/save", methods=["POST"])
def api_settings_save():
    data = request.form if request.form else (request.get_json() or {})
    for key, val in data.items():
        db.set_setting(key, val)
    return jsonify({"success": True, "message": "បានរក្សាទុកការកំណត់ជោគជ័យ!"})


@app.route("/api/sync/test-sheets", methods=["POST"])
def api_sync_test():
    data = request.get_json() or {}
    sheet_id = data.get("sheet_id") or db.get_setting("google_sheet_id", "")
    res = google_sheets_sync.test_google_sheet_connection(sheet_id=sheet_id)
    return jsonify(res)


@app.route("/api/sync/push-sheets", methods=["POST"])
def api_sync_push():
    data = request.get_json() or {}
    sheet_id = data.get("sheet_id") or db.get_setting("google_sheet_id", "")
    res = google_sheets_sync.push_to_google_sheets(sheet_id=sheet_id)
    return jsonify(res)


# -------------------------------------------------------------
# KKHS Timetable (kkhs.web.app) Cloud Sync Endpoints
# -------------------------------------------------------------
@app.route("/api/sync/test-kkhs", methods=["POST"])
@login_required(role="admin")
def api_sync_test_kkhs():
    """សាកល្បងការតភ្ជាប់ទៅកាន់ kkhs.web.app"""
    res = kkhs_sync_service.test_kkhs_connection()
    return jsonify(res)


@app.route("/api/sync/kkhs", methods=["POST"])
@login_required(role="admin")
def api_sync_kkhs():
    """ធ្វើសមកាលកម្មកាលវិភាគរួម គ្រូបង្រៀន និងថ្នាក់រៀនពី kkhs.web.app"""
    data = request.get_json() or (request.form.to_dict() if request.form else {})
    mode = data.get("mode", "merge")
    res = kkhs_sync_service.sync_kkhs_timetable(mode=mode)
    return jsonify(res)


@app.route("/api/sync/kkhs-to-sheets", methods=["POST"])
@login_required(role="admin")
def api_sync_kkhs_to_sheets():
    """Backup ទិន្នន័យកាលវិភាគពី kkhs.web.app ទៅ Google Sheets"""
    data = request.get_json(silent=True) or (request.form.to_dict() if request.form else {})
    sheet_id = data.get("sheet_id") or db.get_setting("google_sheet_id", "")
    res = google_sheets_sync.backup_kkhs_to_google_sheets(sheet_id=sheet_id)
    return jsonify(res)


@app.route("/api/sync/sheets-to-timetable", methods=["POST"])
@login_required(role="admin")
def api_sync_sheets_to_timetable():
    """ទាញយកកាលវិភាគពី Google Sheets Backup មកកាន់ Local Database សម្រាប់ប្រើប្រាស់ជាអចិន្ត្រៃយ៍"""
    data = request.get_json(silent=True) or (request.form.to_dict() if request.form else {})
    sheet_id = data.get("sheet_id") or db.get_setting("google_sheet_id", "")
    mode = data.get("mode", "merge")
    res = google_sheets_sync.pull_timetable_from_google_sheets(sheet_id=sheet_id, mode=mode)
    return jsonify(res)


@app.route("/api/sync/test-firestore", methods=["POST"])
@login_required(role="admin")
def api_test_firestore():
    """តេស្តការតភ្ជាប់ទៅកាន់ Cloud Firestore"""
    res = firestore_sync_service.test_firestore_connection()
    return jsonify(res)


@app.route("/api/sync/sheets-to-firestore", methods=["POST"])
@login_required(role="admin")
def api_sync_sheets_to_firestore():
    """Sync កាលវិភាគពី Google Sheets ទៅកាន់ Cloud Firestore ជាអចិន្ត្រៃយ៍ និង update local DB"""
    data = request.get_json(silent=True) or (request.form.to_dict() if request.form else {})
    sheet_id = data.get("sheet_id") or db.get_setting("google_sheet_id", "")
    res = firestore_sync_service.sync_sheets_to_firestore(sheet_id=sheet_id)
    return jsonify(res)


@app.route("/api/sync/firestore-to-local", methods=["POST"])
@login_required(role="admin")
def api_sync_firestore_to_local():
    """ទាញយកពី Cloud Firestore មកកាន់ Local Database ពេល Container restart"""
    res = firestore_sync_service.pull_firestore_to_local()
    return jsonify(res)


# -------------------------------------------------------------
# Time Window & Telegram Endpoints
# -------------------------------------------------------------
@app.route("/api/portal/current-slot")
def api_portal_current_slot():
    """ផ្តល់ព័ត៌មានស្ថានភាពម៉ោងបច្ចុប្បន្ន ម៉ោងបង្រៀន និងរយៈពេលនៅសល់"""
    user = session.get("user")
    period_info = db.get_current_period_info()
    teacher_id = user.get("teacher_id") if user else None

    slot_info = None
    if teacher_id:
        slot_info = db.get_current_teaching_slot(teacher_id)

    return jsonify({
        "success": True,
        "period_info": period_info,
        "teacher_slot": slot_info,
        "is_teacher": bool(user and user.get("role") == "teacher")
    })


@app.route("/api/telegram/test", methods=["POST"])
@login_required(role="admin")
def api_telegram_test():
    """តេស្តផ្ញើសារ Telegram Bot"""
    data = request.get_json() or {}
    bot_token = data.get("bot_token") or db.get_setting("telegram_bot_token", "")
    chat_id = data.get("chat_id") or db.get_setting("telegram_admin_chat_id", "")

    success, msg = telegram_service.test_telegram_connection(bot_token=bot_token, chat_id=chat_id)
    return jsonify({"success": success, "message": msg})


@app.route("/api/telegram/send-daily-report", methods=["POST"])
@login_required(role="admin")
def api_telegram_send_daily():
    """បញ្ជាឱ្យផ្ញើរបាយការណ៍សិស្ស-គ្រូអវត្តមានប្រចាំថ្ងៃទៅ Telegram Admin"""
    data = request.get_json() or {}
    target_date = data.get("date") or datetime.now().strftime("%Y-%m-%d")

    success, msg = telegram_service.send_daily_absence_report(target_date=target_date)
    return jsonify({"success": success, "message": msg})


@app.route("/api/classes/homeroom", methods=["POST"])
@login_required(role="admin")
def api_class_homeroom():
    """កំណត់គ្រូបន្ទុកថ្នាក់ និង Telegram Group របស់ថ្នាក់"""
    data = request.get_json() or {}
    class_id = data.get("class_id")
    teacher_id = data.get("homeroom_teacher_id")
    telegram_chat_id = data.get("telegram_chat_id", "").strip()

    if not class_id:
        return jsonify({"success": False, "message": "សូមជ្រើសរើសថ្នាក់រៀន"}), 400

    db.update_class_homeroom_and_telegram(
        class_id=int(class_id),
        homeroom_teacher_id=int(teacher_id) if teacher_id else None,
        telegram_chat_id=telegram_chat_id
    )
    return jsonify({"success": True, "message": "បានកំណត់គ្រូបន្ទុកថ្នាក់ និង Telegram Group ដោយជោគជ័យ!"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"==================================================")
    print(f" Student & Teacher Absence Management System")
    print(f" ប្រព័ន្ធគ្រប់គ្រងអវត្តមានសិស្ស និងគ្រូបង្រៀន")
    print(f" Server running at: http://localhost:{port}")
    print(f"==================================================")
    app.run(host="0.0.0.0", port=port, debug=True)
