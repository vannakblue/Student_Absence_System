# ប្រព័ន្ធគ្រប់គ្រងអវត្តមានសិស្ស និងគ្រូបង្រៀន (Student & Teacher Absence Management System)

ប្រព័ន្ធគ្រប់គ្រងអវត្តមានសិស្ស និងគ្រូបង្រៀនពេញលេញ បង្កើតឡើងដោយប្រើប្រាស់ **Python (Flask)**, មូលដ្ឋានទិន្នន័យក្នុងម៉ាស៊ីន **SQLite Database (`attendance.db`)**, ព្រមទាំងមុខងារតភ្ជាប់ **Google Sheets Synchronization (`gspread`)** និងការផលិតរបាយការណ៍ជា **Excel (`.xlsx`)** តាមស្តង់ដារក្រសួងអប់រំ យុវជន និងកីឡា។

---

## 🌟 លក្ខណៈពិសេសចម្បង (Key Features)

1. **មូលដ្ឋានទិន្នន័យ (Database for Python)៖**
   - ប្រើប្រាស់ **SQLite (`attendance.db`)** ដែលជា Database ប្រកបដោយសុវត្ថិភាព ល្បឿនលឿនបំផុត និងដំណើរការ Offline ១០០%។
   - មិនបាច់ដំឡើង Server Database ស្មុគស្មាញ (ដូចជា MySQL/Postgres)។
2. **ស្រង់វត្តមានគ្រូបង្រៀន (Teacher Attendance)៖**
   - ស្រង់វត្តមានតាមកាលបរិច្ឆេទ វេន (ព្រឹក/រសៀល) និងម៉ោងបង្រៀន (Session 1-3 ឬ Daily)។
   - កត់ត្រាស្ថានភាព៖ **វត្តមាន (Present)**, **មានច្បាប់ (Permission)**, **ឥតច្បាប់ (Absent)**, **មកយឺត (Late)**។
   - ជ្រើសរើស **គ្រូបង្រៀនជំនួស (Substitute Teacher)** និងមូលហេតុច្បាស់លាស់។
   - ប៊ូតុងរហ័ស៖ «វត្តមានទាំងអស់» ដោយគ្រាន់តែចុច ១ លើក។
3. **ស្រង់វត្តមានសិស្សានុសិស្ស (Student Attendance)៖**
   - ស្រង់វត្តមានតាមថ្នាក់រៀន (ឧ. ថ្នាក់ ៧ក, ៨ខ, ១០A, ១២វិទ្យាសាស្ត្រ...)។
   - បង្ហាញព័ត៌មានលម្អិតសិស្ស ភេទ ថ្ងៃខែឆ្នាំកំណើត និងលេខទូរស័ព្ទអាណាព្យាបាល។
   - ប៊ូតុង «វត្តមានទាំងអស់» ជួយសន្សំសំចៃពេលវេលារបស់គ្រូ ឬអ្នកស្រង់វត្តមាន។
4. **ពាក្យសុំច្បាប់ (Leave Requests)៖**
   - កត់ត្រាច្បាប់ឈប់សម្រាកសម្រាប់ទាំងគ្រូ និងសិស្ស (កាលបរិច្ឆេទចាប់ផ្តើម-បញ្ចប់ មូលហេតុ និងអ្នកអនុម័ត)។
5. **របាយការណ៍ និង Excel Export (Reports & Export)៖**
   - ទាញយករបាយការណ៍វត្តមានគ្រូ និងសិស្សជាឯកសារ Excel (`.xlsx`) ស្រស់ស្អាត មានទម្រង់ត្រឹមត្រូវ។
6. **Google Sheets Database Synchronization៖**
   - ភ្ជាប់ជាមួយ Google Sheets តាម `gspread` API។
   - Push ទិន្នន័យវត្តមានសិស្ស-គ្រូ និងបញ្ជីឈ្មោះ Master ទៅកាន់ Google Sheet ដោយផ្ទាល់។

---

## 🚀 របៀបដំណើរការកម្មវិធី (How to Run)

### វិធីទី ១៖ ចុចលើ File Batch (ងាយស្រួលបំផុត)
- គ្រាន់តែ Double-click លើឯកសារ **`run.bat`** នោះប្រព័ន្ធនឹងដំណើរការ និងបើក Web Browser ទៅកាន់ `http://localhost:5000` ដោយស្វ័យប្រវត្តិ។

### វិធីទី ២៖ ដំណើរការតាម Command Line
```bash
python run.py
```
ឬ
```bash
python app.py
```
បើក Browser រួចចូលទៅកាន់៖ `http://localhost:5000`

---

## 📑 របៀបភ្ជាប់ Google Sheets ជា Database (Google Sheets Setup)

1. បង្កើត Google Spreadsheet ថ្មីមួយនៅលើ Google Drive របស់អ្នក។
2. ចម្លង **Google Sheet ID** ពីលើ Address bar (អក្សរកូដចន្លោះពី `/d/` ដល់ `/edit`)។
3. ចូលទៅទំព័រ **Google Sheets & Settings** ក្នុងកម្មវិធី រួច Paste Google Sheet ID នោះចូល។
4. ដាក់ឯកសារ Google Cloud Service Account Key ឈ្មោះ `credentials.json` ចូលក្នុង Folder នេះ។
5. Share Google Sheet នោះទៅកាន់ email របស់ Service Account ជាមួយសិទ្ធិជា **Editor**។
6. ចុចប៊ូតុង **Sync ទៅ Google Sheets ឥឡូវនេះ** ជាការស្រេច!

---

## 📁 រចនាសម្ព័ន្ធឯកសារ (Project Structure)

```
Student_Absence_System/
│
├── app.py                      # Flask Server & REST APIs
├── database.py                 # SQLite Schema, Models & CRUD Operations
├── seed_data.py                # Initial Cambodian Schools Sample Data
├── export_service.py           # Excel (.xlsx) Report Generator (openpyxl)
├── google_sheets_sync.py       # Google Sheets API / gspread Synchronization
├── requirements.txt            # Python Dependencies
├── run.py                      # Python App Launcher
├── run.bat                     # 1-Click Windows Launcher
├── README.md                   # Complete Documentation
│
├── templates/                  # Modern HTML5 Templates
│   ├── base.html
│   ├── dashboard.html
│   ├── teacher_attendance.html
│   ├── student_attendance.html
│   ├── teachers.html
│   ├── students.html
│   ├── leave_requests.html
│   ├── reports.html
│   └── settings.html
│
└── static/
    ├── css/
    │   └── style.css           # Premium Vanilla CSS Design System
    └── js/
        └── app.js              # Client-side Interactions, Toasts, Sync
```
