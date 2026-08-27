# ============================================================
# migrations/008_clinic_settings.py
# Release 2 - מדיניות הקליניקה שניתנת לשינוי בלי לגעת בקוד.
#
# הערה על working_days: המוסכמה הקיימת במערכת (StaffAvailability.day_of_week,
# utils/datetime_utils.day_of_week) היא 0=שני ... 6=ראשון (עקבי עם
# date.weekday() של פייתון). שבוע עבודה בישראל הוא ראשון-חמישי,
# ולכן ברירת המחדל כאן היא "6,0,1,2,3" (ראשון,שני,שלישי,רביעי,חמישי)
# ולא "0,1,2,3,4" כמו שכתוב במפרט המקורי (שמניח שבוע עבודה שני-שישי) -
# ניתן לשינוי בכל עת דרך מסך ההגדרות (Release 2, שלב P1).
#
# הרצה:  python3 migrations/008_clinic_settings.py
# בטוח להרצה חוזרת - זריעה רק לערכים שעוד לא קיימים.
# ============================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import engine, get_session
from models import Base, ClinicSetting


DEFAULT_SETTINGS = {
    "booking_window_days": "60",
    "min_hours_before_booking": "4",
    "cancellation_deadline_hours": "24",
    "reminder_hours_before": "24",
    "max_open_appointments_per_client": "3",
    "working_hours_start": "09:00",
    "working_hours_end": "20:00",
    "working_days": "6,0,1,2,3",
}


def _seed_defaults():
    session = get_session()
    existing_keys = {row.key for row in session.query(ClinicSetting.key).all()}

    added = 0
    for key, value in DEFAULT_SETTINGS.items():
        if key not in existing_keys:
            session.add(ClinicSetting(key=key, value=value))
            added += 1

    if added:
        session.commit()
    print(f"  {added} default settings seeded ({len(DEFAULT_SETTINGS) - added} already existed)")


def run_migration():
    Base.metadata.create_all(engine, tables=[ClinicSetting.__table__])
    print("  clinic_settings ready")

    _seed_defaults()

    return True


if __name__ == "__main__":
    print("Running migration 008 (clinic_settings)...")
    run_migration()
    print("Done.")
