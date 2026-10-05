# -*- coding: utf-8 -*-
"""
Deploy Script for KKHS Student Absence System to Firebase Hosting
"""
import os
import sys
import subprocess
import webbrowser

# Ensure UTF-8 output on Windows terminal
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_DIR)

print("=" * 65, flush=True)
print("  🚀 កំពុងដំណើរការ Deploy Student Absence System to Firebase...", flush=True)
print("=" * 65, flush=True)
print(flush=True)

print("[1/2] ធ្វើបច្ចុប្បន្នភាពទិន្នន័យ (Sync Data to Firebase)...", flush=True)
try:
    ret = subprocess.run([sys.executable, "sync_to_firebase.py"], check=False)
    if ret.returncode != 0:
        print("\n[WARNING] Sync ទិន្នន័យមិនទាន់ជោគជ័យ (អាចមកពីមិនទាន់បង្កើត RTDB) ប៉ុន្តែនឹងបន្ត Deploy Frontend...", flush=True)
except Exception as e:
    print(f"\n[WARNING] មិនអាចដំណើរការ sync_to_firebase.py: {e}", flush=True)

print(flush=True)
print("[2/2] កំពុងបញ្ជូន Frontend ទៅកាន់ Firebase Hosting (https://kkhs-absence.web.app)...", flush=True)
try:
    ret2 = subprocess.run("firebase deploy --only hosting --project kkhs-absence", shell=True, check=False)
    if ret2.returncode != 0:
        print("\n[ERROR] ការ Deploy ទៅកាន់ Firebase Hosting បរាជ័យ!", flush=True)
        sys.exit(ret2.returncode)
except Exception as e:
    print(f"\n[ERROR] កំហុសពេលហៅ firebase deploy: {e}", flush=True)
    sys.exit(1)

print(flush=True)
print("=" * 65, flush=True)
print("  🎉 DEPLOY TO FIREBASE HOSTING COMPLETED SUCCESSFULLY!", flush=True)
print("  🌐 Live URL: https://kkhs-absence.web.app", flush=True)
print("=" * 65, flush=True)
print(flush=True)

try:
    webbrowser.open("https://kkhs-absence.web.app")
except Exception:
    pass
