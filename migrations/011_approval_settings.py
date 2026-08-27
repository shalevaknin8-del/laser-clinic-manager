# ============================================================
# migrations/011_approval_settings.py
# Release 2 - הגדרות מדיניות זרימת האישור. שורות נוספות ל-
# clinic_settings (לא טבלה חדשה - נוצרה כבר ב-008).
#
# הרצה:  python3 migrations/011_approval_settings.py
# בטוח להרצה חוזרת - זריעה רק לערכים שעוד לא קיימים.
# ============================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import get_session
from models import ClinicSetting


DEFAULT_SETTINGS = {
    "approval_window_hours": "12",
    "post_approval_cancel_hours": "2",
    "notify_admin_on_new_request": "true",
    "admin_notification_batch_minutes": "30",
}


def run_migration():
    session = get_session()
    existing_keys = {row.key for row in session.query(ClinicSetting.key).all()}

    added = 0
    for key, value in DEFAULT_SETTINGS.items():
        if key not in existing_keys:
            session.add(ClinicSetting(key=key, value=value))
            added += 1

    if added:
        session.commit()
    print(f"  {added} approval settings seeded ({len(DEFAULT_SETTINGS) - added} already existed)")

    return True


if __name__ == "__main__":
    print("Running migration 011 (approval settings)...")
    run_migration()
    print("Done.")
