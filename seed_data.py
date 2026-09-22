"""
ទិន្នន័យគំរូសម្រាប់ប្រព័ន្ធគ្រប់គ្រងអវត្តមានសិស្ស-គ្រូ (Seed Data)
"""

import os
import random
from datetime import datetime, timedelta
from database import (
    init_db, get_db_connection,
    add_class, add_teacher, add_student,
    save_teacher_attendance, save_student_attendance
)


def seed_all():
    init_db()
    conn = get_db_connection()

    # Check if already seeded
    teacher_count = conn.execute("SELECT COUNT(*) FROM teachers").fetchone()[0]
    if teacher_count > 0:
        print(f"Database already contains {teacher_count} teachers. Skipping seed.")
        conn.close()
        return

    print("Seeding initial classes, teachers, and students...")

    # 1. Seed Classes (ថ្នាក់រៀនគំរូ)
    classes_data = [
        ("ថ្នាក់ ៧ក", 7, "Morning", "B-101", "2026-2027"),
        ("ថ្នាក់ ៨ខ", 8, "Morning", "B-102", "2026-2027"),
        ("ថ្នាក់ ១០A", 10, "Afternoon", "C-201", "2026-2027"),
        ("ថ្នាក់ ១២វិទ្យាសាស្ត្រ", 12, "Afternoon", "A-301", "2026-2027"),
    ]
    class_ids = []
    for cname, grade, shift, room, yr in classes_data:
        cid = add_class(cname, grade, shift, room, yr)
        class_ids.append(cid)

    # 2. Seed Teachers (គ្រូបង្រៀនគំរូ)
    teachers_data = [
        ("T001", "ស៊ុន វណ្ណា", "M", "012 889 901", "vanna@school.edu.kh", "គណិតវិទ្យា", "Sun Vanna", 18),
        ("T002", "កែវ ចិន្តា", "F", "098 776 543", "chinda@school.edu.kh", "រូបវិទ្យា", "Keo Chinda", 16),
        ("T003", "ចាន់ វិបុល", "M", "077 334 221", "vibol@school.edu.kh", "ភាសាខ្មែរ", "Chan Vibol", 20),
        ("T004", "អ៊ុំ សុធា", "F", "089 654 321", "sothea@school.edu.kh", "គីមីវិទ្យា", "Oum Sothea", 16),
        ("T005", "ម៉ៅ សុខា", "M", "016 445 566", "sokha@school.edu.kh", "ភាសាអង់គ្លេស", "Mao Sokha", 18),
        ("T006", "ហេង រស្មី", "F", "092 112 233", "reaksmey@school.edu.kh", "ជីវវិទ្យា", "Heng Reaksmey", 16),
        ("T007", "លី សុវណ្ណារ៉ា", "M", "011 998 877", "sovannara@school.edu.kh", "ប្រវត្តិវិទ្យា", "Ly Sovannara", 16),
        ("T008", "ស៊ឹម ស្រីមុំ", "F", "088 554 433", "sreymom@school.edu.kh", "ភូមិវិទ្យា", "Sim Sreymom", 16),
        ("T009", "ប៉ែន ពិសិដ្ឋ", "M", "097 223 344", "piseth@school.edu.kh", "ព័ត៌មានវិទ្យា", "Pen Piseth", 14),
        ("T010", "តាំង សុផាត", "F", "085 667 788", "sophat@school.edu.kh", "សីលធម៌-ពលរដ្ឋ", "Tang Sophat", 14),
    ]
    teacher_ids = []
    for code, name, gender, phone, email, subj, en, hrs in teachers_data:
        tid = add_teacher(code, name, gender, phone, email, subj, en, hrs)
        teacher_ids.append(tid)

    # 3. Seed Students (សិស្សានុសិស្សគំរូ តាមថ្នាក់នីមួយៗ)
    student_templates = [
        ("ស៊ូ វិច្ឆិកា", "Sou Vicheka", "F", "2010-03-12", "ស៊ូ សំណាង", "012 345 678"),
        ("សុខ ពិសិដ្ឋ", "Sok Piseth", "M", "2010-07-21", "សុខ សារឿន", "015 678 910"),
        ("ជា សុគន្ធា", "Chea Sokunthea", "F", "2010-01-15", "ជា គឹមស៊្រុន", "089 123 456"),
        ("ខៀវ វឌ្ឍនៈ", "Khiev Vattana", "M", "2010-11-05", "ខៀវ សារ៉ាត់", "098 765 432"),
        ("នូ ចាន់ថន", "Nou Chanthon", "M", "2010-09-18", "នូ សុផល", "077 554 433"),
        ("ម៉េង ស្រីពៅ", "Meng Sreypov", "F", "2010-05-25", "ម៉េង ចាន់ធី", "088 998 877"),
        ("លឹម រតនៈ", "Lim Rothana", "M", "2010-12-30", "លឹម គឹមសាន", "011 223 344"),
        ("ទៀង កល្យាណ", "Tieng Kallyan", "F", "2010-08-14", "ទៀង វិចិត្រ", "092 334 455"),
        ("អ៊ុច បូទី", "Uch Boty", "M", "2010-04-02", "អ៊ុច វ៉ាន់នី", "016 778 899"),
        ("សោម ធីតា", "Som Thida", "F", "2010-06-19", "សោម សុជាតិ", "095 889 900"),
    ]

    all_students = []
    student_counter = 1
    for cid_idx, cid in enumerate(class_ids):
        grade_prefix = [7, 8, 10, 12][cid_idx]
        for idx, (kh_name, en_name, gender, dob, parent, parent_phone) in enumerate(student_templates):
            scode = f"STU{grade_prefix:02d}-{student_counter:03d}"
            sid = add_student(
                code=scode,
                full_name_kh=f"{kh_name} ({idx+1})",
                gender=gender,
                class_id=cid,
                dob=dob,
                full_name_en=en_name,
                parent_name=parent,
                parent_phone=parent_phone
            )
            all_students.append((sid, cid))
            student_counter += 1

    print(f"Seeded {len(teachers_data)} teachers, {len(classes_data)} classes, and {len(all_students)} students.")

    # 4. Seed Attendance History for the past 5 days
    today = datetime.now().date()
    statuses = ["PRESENT", "PRESENT", "PRESENT", "PRESENT", "PERMISSION", "ABSENT", "LATE"]
    reasons_perm = ["មានធុរៈគ្រួសារចាំបាច់", "ឈឺ ផ្ដាសាយធំ", "ទៅពិនិត្យសុខភាពនៅមន្ទីរពេទ្យ"]
    reasons_absent = ["មិនបានដំណឹង", "មិនមានច្បាប់"]

    for d in range(5, -1, -1):
        day_date = (today - timedelta(days=d)).strftime("%Y-%m-%d")

        # Teacher Attendance for day_date
        t_records = []
        for tid in teacher_ids:
            st = random.choices(["PRESENT", "PERMISSION", "ABSENT", "LATE"], weights=[80, 10, 5, 5])[0]
            reason = ""
            sub_id = None
            if st == "PERMISSION":
                reason = random.choice(reasons_perm)
                sub_id = random.choice([t for t in teacher_ids if t != tid])
            elif st == "ABSENT":
                reason = random.choice(reasons_absent)
            t_records.append({
                "teacher_id": tid,
                "status": st,
                "reason": reason,
                "substitute_teacher_id": sub_id,
                "notes": "ទិន្នន័យស្រង់ប្រចាំថ្ងៃ"
            })
        save_teacher_attendance(day_date, "Morning", "Session 1", t_records, "Admin")

        # Student Attendance for day_date (for all classes)
        for cid in class_ids:
            c_students = [s for s in all_students if s[1] == cid]
            s_records = []
            for sid, _ in c_students:
                st = random.choices(["PRESENT", "PERMISSION", "ABSENT", "LATE"], weights=[85, 8, 4, 3])[0]
                reason = ""
                if st == "PERMISSION":
                    reason = random.choice(reasons_perm)
                elif st == "ABSENT":
                    reason = random.choice(reasons_absent)
                s_records.append({
                    "student_id": sid,
                    "status": st,
                    "reason": reason
                })
            save_student_attendance(cid, day_date, "Morning", "Daily", s_records, "Teacher")

    conn.close()
    print("Seeded sample attendance records for the past 5 days.")


if __name__ == "__main__":
    seed_all()
