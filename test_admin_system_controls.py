"""
Test Suite for Admin System Controls:
1. Maintenance Mode On/Off (API 503, Portal maintenance page, Admin access)
2. Class & Grade Suspension (Grade 7-12, specific classes, attendance blocked, excluded from unmarked slots)
3. School Vacations (Date ranges, attendance blocked, periodic check skipped)
4. Holidays (Cambodian holidays, custom holidays, attendance blocked, periodic check skipped)
5. 8-Period Deadline Matrix (Individual period deadlines 1-8, e.g. 25m vs 30m)
6. Telegram Missed Attendance Recipients (Multi-chat parsing)
7. Telegram Leave Request Approvers (Multi-chat parsing & button delivery)
8. Separate Daily Report Telegram Destinations (Student vs Teacher)
9. Separate Hourly Absence Telegram Destinations (Student vs Teacher)
10. Day-of-Week Scheduled Report Dispatch
"""

import os
import sys
import json
from datetime import datetime, timedelta

# Ensure workspace root is in path
WORKSPACE = os.path.dirname(os.path.abspath(__file__))
if WORKSPACE not in sys.path:
    sys.path.insert(0, WORKSPACE)

import database as db
import telegram_service as ts
from app import app


def run_tests():
    print("================================================================")
    print("STARTING ADMIN SYSTEM CONTROLS VERIFICATION TEST SUITE")
    print("================================================================")

    db.init_db()

    # -------------------------------------------------------------
    # 1. Maintenance Mode Tests
    # -------------------------------------------------------------
    print("\n--- TEST 1: Maintenance Mode ---")
    orig_maint = db.get_setting("maintenance_mode", "0")
    try:
        # Set Maintenance ON
        db.set_setting("maintenance_mode", "1")
        in_maint, _ = db.is_system_in_maintenance()
        assert in_maint is True, "Maintenance should be True"

        # Check API response under maintenance
        with app.test_client() as client:
            # API endpoint should return 503 JSON
            resp = client.get("/api/classes")
            assert resp.status_code == 503, f"Expected 503, got {resp.status_code}"
            data = resp.get_json()
            assert data.get("maintenance") is True
            assert "ថែទាំ" in data.get("message", "")
            print("  [PASS] API returned 503 JSON with Khmer maintenance message")

            # Portal HTML page should return 503 with maintenance template
            resp_html = client.get("/portal")
            assert resp_html.status_code == 503, f"Expected 503 HTML, got {resp_html.status_code}"
            assert "ប្រព័ន្ធកំពុងស្ថិតក្រោមការថែទាំ" in resp_html.get_data(as_text=True)
            print("  [PASS] Non-admin HTML request returned 503 Maintenance Page")

            # Admin session should still be allowed
            with client.session_transaction() as sess:
                sess["user"] = {"id": 1, "username": "admin", "role": "admin", "full_name_kh": "Admin"}
            resp_admin = client.get("/settings")
            assert resp_admin.status_code == 200, f"Admin should access settings, got {resp_admin.status_code}"
            assert "Maintenance Mode (ON)" in resp_admin.get_data(as_text=True)
            print("  [PASS] Admin can access system with warning banner displayed")

        # Turn Maintenance OFF
        db.set_setting("maintenance_mode", "0")
        in_maint_off, _ = db.is_system_in_maintenance()
        assert in_maint_off is False
        with app.test_client() as client:
            resp = client.get("/api/classes")
            assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
            print("  [PASS] Normal access restored when Maintenance Mode is OFF")
    finally:
        db.set_setting("maintenance_mode", orig_maint)

    # -------------------------------------------------------------
    # 2. Grade & Class Suspension Tests
    # -------------------------------------------------------------
    print("\n--- TEST 2: Class & Grade Level Suspensions ---")
    classes = db.get_classes()
    assert len(classes) > 0, "Need at least one class in DB for testing"
    test_class = classes[0]
    test_class_id = test_class["id"]
    test_grade = str(test_class["grade_level"])

    # Reset any existing suspensions
    db.unsuspend_class(test_class_id)
    db.unsuspend_grade(test_grade)

    is_susp, _, _ = db.is_class_suspended(test_class_id)
    assert not is_susp, "Class should initially be unsuspended"

    # Test Grade Suspension
    db.suspend_grade(test_grade, f"ជួសជុលអគារសិក្សាកម្រិត {test_grade}")
    is_susp, reason, _ = db.is_class_suspended(test_class_id)
    assert is_susp is True, f"Class in grade {test_grade} should be suspended"
    assert "ជួសជុលអគារសិក្សា" in reason
    print(f"  [PASS] Grade {test_grade} suspension cascaded to class {test_class['class_name']}: {reason}")

    # Check that check_submission_window_rule blocks attendance for suspended grade
    can_sub, code, msg, phase, _ = db.check_submission_window_rule(
        class_id=test_class_id,
        date_str=datetime.now().strftime("%Y-%m-%d"),
        shift="Morning",
        period_str="Session 1",
        is_admin=False
    )
    assert can_sub is False, "Suspended grade should not submit attendance"
    assert code == 403
    assert "ជួសជុលអគារសិក្សា" in msg
    print("  [PASS] check_submission_window_rule blocked attendance for suspended grade")

    # Unsuspend grade
    db.unsuspend_grade(test_grade)
    is_susp, _, _ = db.is_class_suspended(test_class_id)
    assert not is_susp, "Class should be unsuspended after grade unsuspended"

    # Test Specific Class Suspension
    db.suspend_class(test_class_id, "សកម្មភាពក្រៅកម្មវិធីសិក្សា")
    is_susp, reason, _ = db.is_class_suspended(test_class_id)
    assert is_susp is True
    assert "សកម្មភាពក្រៅកម្មវិធីសិក្សា" in reason
    print(f"  [PASS] Specific class {test_class['class_name']} suspended directly: {reason}")

    can_sub, code, msg, _, _ = db.check_submission_window_rule(
        class_id=test_class_id,
        date_str=datetime.now().strftime("%Y-%m-%d"),
        shift="Morning",
        period_str="Session 1",
        is_admin=False
    )
    assert can_sub is False
    assert code == 403
    assert "សកម្មភាពក្រៅកម្មវិធីសិក្សា" in msg
    print("  [PASS] check_submission_window_rule blocked attendance for suspended class")

    # Verify unmarked slots excludes suspended class
    today_str = datetime.now().strftime("%Y-%m-%d")
    slots_res = db.get_unmarked_slots_for_period(today_str, 1, "Morning")
    unmarked_class_ids = [u.get("resolved_class_id") or u.get("class_id") for u in slots_res.get("unmarked", [])]
    assert test_class_id not in unmarked_class_ids, "Suspended class must be excluded from unmarked list"
    print("  [PASS] Suspended class successfully excluded from unmarked period slots")

    # Clean up suspension
    db.unsuspend_class(test_class_id)
    is_susp, _, _ = db.is_class_suspended(test_class_id)
    assert not is_susp

    # -------------------------------------------------------------
    # 3. Vacation Periods Tests
    # -------------------------------------------------------------
    print("\n--- TEST 3: School Vacations ---")
    for v in db.get_vacations():
        if "តេស្ត" in v["title"]:
            db.delete_vacation(v["id"])

    vac_id = db.add_vacation(
        title="វិស្សមកាលតូច តេស្ត",
        start_date="2026-11-01",
        end_date="2026-11-15",
        academic_year="2026-2027",
        notes="សម្រាប់ធ្វើតេស្តប្រព័ន្ធ"
    )
    assert vac_id > 0

    # Inside vacation range
    is_vac, vac_dict = db.is_vacation_date("2026-11-05")
    assert is_vac is True
    assert "វិស្សមកាលតូច តេស្ត" in vac_dict["title"]
    print(f"  [PASS] 2026-11-05 correctly detected inside vacation '{vac_dict['title']}'")

    # Outside vacation range
    is_vac_out, _ = db.is_vacation_date("2026-11-20")
    assert is_vac_out is False
    print("  [PASS] 2026-11-20 correctly detected outside vacation")

    # check_submission_window_rule blocks attendance on vacation date
    dt_vac = datetime(2026, 11, 5, 7, 15, 0)
    can_sub, code, msg, _, _ = db.check_submission_window_rule(
        class_id=test_class_id,
        date_str="2026-11-05",
        shift="Morning",
        period_str="Session 1",
        is_admin=False,
        current_dt=dt_vac
    )
    assert can_sub is False
    assert code == 403
    assert "វិស្សមកាល" in msg
    print("  [PASS] check_submission_window_rule blocked submission during vacation")

    # Admin override check
    can_sub_admin, _, _, _, _ = db.check_submission_window_rule(
        class_id=test_class_id,
        date_str="2026-11-05",
        shift="Morning",
        period_str="Session 1",
        is_admin=True,
        current_dt=dt_vac
    )
    assert can_sub_admin is True, "Admin should be able to override vacation restriction"
    print("  [PASS] Admin can override vacation rule if needed")

    # Cleanup vacation
    db.delete_vacation(vac_id)
    is_vac_deleted, _ = db.is_vacation_date("2026-11-05")
    assert is_vac_deleted is False
    print("  [PASS] Vacation deleted cleanly")

    # -------------------------------------------------------------
    # 4. Holidays Tests
    # -------------------------------------------------------------
    print("\n--- TEST 4: School Holidays ---")
    holidays = db.get_holidays()
    print(f"  Currently seeded holidays count: {len(holidays)}")
    assert len(holidays) >= 20, "Should have Cambodian holidays seeded"

    # Check Khmer New Year date (2026-04-14)
    is_hol, hol_dict = db.is_holiday_date("2026-04-14")
    assert is_hol is True
    assert "ចូលឆ្នាំថ្មី" in hol_dict["holiday_name"]
    print(f"  [PASS] 2026-04-14 correctly identified as holiday: {hol_dict['holiday_name']}")

    # check_submission_window_rule blocks attendance on holiday
    dt_hol = datetime(2026, 4, 14, 7, 15, 0)
    can_sub, code, msg, _, _ = db.check_submission_window_rule(
        class_id=test_class_id,
        date_str="2026-04-14",
        shift="Morning",
        period_str="Session 1",
        is_admin=False,
        current_dt=dt_hol
    )
    assert can_sub is False
    assert code == 403
    assert "ឈប់សម្រាក" in msg
    print("  [PASS] check_submission_window_rule blocked submission on holiday")

    # Custom holiday addition and deletion
    cust_id = db.add_holiday("ទិវាពិសេសសាលា", "2026-08-20", notes="Custom")
    assert cust_id > 0
    is_cust, cust_dict = db.is_holiday_date("2026-08-20")
    assert is_cust is True and cust_dict["holiday_name"] == "ទិវាពិសេសសាលា"
    db.delete_holiday(cust_id)
    is_cust_del, _ = db.is_holiday_date("2026-08-20")
    assert is_cust_del is False
    print("  [PASS] Custom holiday CRUD works as expected")

    # -------------------------------------------------------------
    # 5. 8-Period Deadline Matrix Tests
    # -------------------------------------------------------------
    print("\n--- TEST 5: 8-Period Deadline Matrix ---")
    orig_p1 = db.get_period_deadline_minutes(1)
    orig_p2 = db.get_period_deadline_minutes(2)

    try:
        # Configure Period 1 to 25 mins and Period 2 to 35 mins
        db.set_setting("period_1_deadline_minutes", "25")
        db.set_setting("period_2_deadline_minutes", "35")

        assert db.get_period_deadline_minutes(1) == 25
        assert db.get_period_deadline_minutes(2) == 35
        print("  [PASS] get_period_deadline_minutes(1) = 25, get_period_deadline_minutes(2) = 35")

        # Test Period 1 window logic at 07:20 (20 mins in) vs 07:26 (26 mins in)
        # Period 1 is 07:00 - 07:50.
        # At 07:20: elapsed is 20 mins <= 25 mins -> phase should be 'first_30'
        dt_within_p1 = datetime(2026, 9, 22, 7, 20, 0)
        p_info_p1 = db.get_current_period_info(dt_within_p1)
        assert p_info_p1["has_active_period"] is True
        assert p_info_p1["period"]["db_period_num"] == 1
        assert p_info_p1["phase"] == "first_30", f"Expected first_30 at min 20 for 25m deadline, got {p_info_p1['phase']}"
        assert p_info_p1["period"]["deadline_minutes"] == 25
        # Remaining seconds should be (25 - 20) * 60 = 300
        assert p_info_p1["period"]["sec_remaining_first_30"] == 300
        print("  [PASS] Period 1 at 07:20 (minute 20/25): phase=first_30, sec_remaining=300")

        # At 07:26: elapsed is 26 mins > 25 mins -> phase should transition to phase2_window
        dt_past_p1 = datetime(2026, 9, 22, 7, 26, 0)
        p_info_past_p1 = db.get_current_period_info(dt_past_p1)
        assert p_info_past_p1["phase"] == "second_30", f"Expected second_30 at min 26 for 25m deadline, got {p_info_past_p1['phase']}"
        print("  [PASS] Period 1 at 07:26 (minute 26/25): successfully transitioned to second_30")

        # Period 2 is 08:00 - 09:00. At 08:26 (26 mins in):
        # Since Period 2 deadline is 35 mins, 26 mins <= 35 mins -> phase should STILL be first_30!
        dt_p2_within = datetime(2026, 9, 22, 8, 26, 0)
        p_info_p2 = db.get_current_period_info(dt_p2_within)
        assert p_info_p2["period"]["db_period_num"] == 2
        assert p_info_p2["phase"] == "first_30", f"Period 2 with 35m deadline should be first_30 at 26m, got {p_info_p2['phase']}"
        assert p_info_p2["period"]["sec_remaining_first_30"] == (35 - 26) * 60
        print("  [PASS] Period 2 at 08:26 (minute 26/35): still in first_30 as configured!")
    finally:
        db.set_setting("period_1_deadline_minutes", str(orig_p1))
        db.set_setting("period_2_deadline_minutes", str(orig_p2))

    # -------------------------------------------------------------
    # 6. Telegram Recipient Parsing Tests
    # -------------------------------------------------------------
    print("\n--- TEST 6: Telegram Routing & Multi-recipient Helpers ---")
    orig_unrecorded = db.get_setting("telegram_unrecorded_alert_chat_ids", "")
    orig_approvers = db.get_setting("telegram_leave_approver_chat_ids", "")
    orig_daily_stu = db.get_setting("telegram_daily_student_report_chat_id", "")
    orig_daily_tch = db.get_setting("telegram_daily_teacher_report_chat_id", "")
    orig_hr_stu = db.get_setting("telegram_hourly_student_absence_chat_id", "")
    orig_hr_tch = db.get_setting("telegram_hourly_teacher_absence_chat_id", "")

    try:
        # Test Unrecorded recipients parsing (comma and newline mixed)
        db.set_setting("telegram_unrecorded_alert_chat_ids", "-100123456789,  -100987654321 \n -100555444333 , ")
        unrec_ids = ts.get_unrecorded_alert_chat_ids()
        assert unrec_ids == ["-100123456789", "-100987654321", "-100555444333"], f"Parsed: {unrec_ids}"
        print(f"  [PASS] Unrecorded alert recipients parsed correctly: {unrec_ids}")

        # Test Leave approvers parsing
        db.set_setting("telegram_leave_approver_chat_ids", "11223344, 55667788")
        approver_ids = ts.get_leave_approver_chat_ids()
        assert approver_ids == ["11223344", "55667788"]
        print(f"  [PASS] Leave approver IDs parsed correctly: {approver_ids}")

        # Test Separate Daily & Hourly Chat IDs
        db.set_setting("telegram_daily_student_report_chat_id", "-100STUDENT_DAILY")
        db.set_setting("telegram_daily_teacher_report_chat_id", "-100TEACHER_DAILY")
        db.set_setting("telegram_hourly_student_absence_chat_id", "-100STUDENT_HOURLY")
        db.set_setting("telegram_hourly_teacher_absence_chat_id", "-100TEACHER_HOURLY")

        assert ts.get_daily_student_report_chat_id() == "-100STUDENT_DAILY"
        assert ts.get_daily_teacher_report_chat_id() == "-100TEACHER_DAILY"
        assert ts.get_hourly_student_absence_chat_id() == "-100STUDENT_HOURLY"
        assert ts.get_hourly_teacher_absence_chat_id() == "-100TEACHER_HOURLY"
        print("  [PASS] Separate chat IDs for student vs teacher (daily & hourly) verified")

        # Fallback check: if specific ID is empty, it falls back to telegram_admin_chat_id
        db.set_setting("telegram_daily_student_report_chat_id", "")
        db.set_setting("telegram_admin_chat_id", "-100FALLBACK_DEFAULT")
        assert ts.get_daily_student_report_chat_id() == "-100FALLBACK_DEFAULT"
        print("  [PASS] Chat ID fallback to general telegram_admin_chat_id verified")
    finally:
        db.set_setting("telegram_unrecorded_alert_chat_ids", orig_unrecorded)
        db.set_setting("telegram_leave_approver_chat_ids", orig_approvers)
        db.set_setting("telegram_daily_student_report_chat_id", orig_daily_stu)
        db.set_setting("telegram_daily_teacher_report_chat_id", orig_daily_tch)
        db.set_setting("telegram_hourly_student_absence_chat_id", orig_hr_stu)
        db.set_setting("telegram_hourly_teacher_absence_chat_id", orig_hr_tch)

    # -------------------------------------------------------------
    # 7. Day-of-Week Scheduled Report Dispatch Tests
    # -------------------------------------------------------------
    print("\n--- TEST 7: Day-of-Week Scheduled Daily Report Dispatch ---")
    now = datetime.now()
    day_key = ts.DAY_NAME_KEY_MAP.get(now.weekday(), "mon")
    cur_hm = now.strftime("%H:%M")
    orig_sched = db.get_setting(f"daily_report_time_{day_key}", "")

    try:
        # Configure schedule for today as 'off'
        db.set_setting(f"daily_report_time_{day_key}", "off")

        # Trigger checker: should not dispatch because time is 'off'
        res = ts.check_and_dispatch_scheduled_daily_reports(now)
        assert res.get("dispatched") is False, "Should not dispatch when schedule is 'off'"
        print(f"  [PASS] Scheduler ignores off/disabled days for {day_key}")

        # Configure schedule with mismatched time (23:59)
        db.set_setting(f"daily_report_time_{day_key}", "23:59")
        res_mismatch = ts.check_and_dispatch_scheduled_daily_reports(now)
        assert res_mismatch.get("dispatched") is False
        print("  [PASS] Scheduler ignores mismatched dispatch time")

        # Mock send_daily_absence_report to avoid Telegram network call
        orig_send_fn = ts.send_daily_absence_report
        ts.send_daily_absence_report = lambda dt: (True, "Mock sent successfully")

        conn = db.get_db_connection()
        conn.execute("DELETE FROM telegram_alert_logs WHERE alert_type = 'DAILY_DISPATCH_SCHEDULE'")
        conn.commit()
        conn.close()

        try:
            # Configure schedule for current minute
            db.set_setting(f"daily_report_time_{day_key}", cur_hm)
            res_matched = ts.check_and_dispatch_scheduled_daily_reports(now)
            assert res_matched.get("dispatched") is True, f"Expected dispatch True, got {res_matched}"
            print(f"  [PASS] Scheduler successfully triggered on {day_key} at {cur_hm}")

            # Immediately check again in same day/minute: should skip due to dedup
            res_again = ts.check_and_dispatch_scheduled_daily_reports(now)
            assert res_again.get("dispatched") is False, "Should not duplicate dispatch on same date"
            assert "Already dispatched today" in res_again.get("reason", "")
            print("  [PASS] Scheduler dedup prevented duplicate dispatch")
        finally:
            ts.send_daily_absence_report = orig_send_fn
            conn = db.get_db_connection()
            conn.execute("DELETE FROM telegram_alert_logs WHERE alert_type = 'DAILY_DISPATCH_SCHEDULE'")
            conn.commit()
            conn.close()
    finally:
        db.set_setting(f"daily_report_time_{day_key}", orig_sched)

    print("\n================================================================")
    print("ALL 7 SYSTEM CONTROL TEST SUITES PASSED SUCCESSFULLY! (100% OK)")
    print("================================================================\n")


if __name__ == "__main__":
    run_tests()
