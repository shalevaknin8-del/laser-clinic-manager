# ============================================================
# migrations/run_all.py
# מריץ את כל המיגרציות לפי סדר.
#
# הרצה:  python3 migrations/run_all.py
#
# הסקריפט בטוח להרצה חוזרת, כי כל מיגרציה בודקת
# בעצמה אם השינוי כבר בוצע. לכן אפשר להריץ אותו
# בכל עדכון של השרת בלי לזכור מה כבר רץ.
# ============================================================

import sys
import importlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import initialize_database
from managers.appointment_treatment_manager import AppointmentTreatmentManager


# רשימת המיגרציות לפי סדר הרצה.
# מיגרציה חדשה בעתיד מתווספת כשורה בסוף הרשימה
MIGRATION_MODULES = [
    "migrations.001_add_national_id",
    "migrations.002_add_otp_table",
    "migrations.003_add_users_table",
]


def run_all():
    """מריץ את כל שלבי הכנת המסד לפי סדר התלויות."""
    print("Running database setup...")

    # יצירת הטבלאות הבסיסיות
    initialize_database()
    print("  base tables ready")

    # טבלת הקישור לטיפול מרוכב
    AppointmentTreatmentManager().ensure_table()
    print("  appointment_treatments ready")

    # הרצת המיגרציות אחת אחרי השנייה
    for module_name in MIGRATION_MODULES:
        print(f"  running {module_name}")
        module = importlib.import_module(module_name)
        module.run_migration()

    print("All migrations completed.")


if __name__ == "__main__":
    run_all()