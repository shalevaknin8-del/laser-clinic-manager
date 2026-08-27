# ============================================================
# migrations/006_extend_appointments.py
# Release 2 - מוסיף ל-appointments את השדות שהתור צריך כדי לדעת
# מאיפה הוא הגיע (source) ואיך/מתי הוא בוטל.
#
# הרצה:  python3 migrations/006_extend_appointments.py
# בטוח להרצה חוזרת - כל שינוי נבדק לפני שהוא מתבצע.
# ============================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import get_connection
from migrations._helpers import add_column_if_missing


def run_migration():
    connection = get_connection()
    cursor = connection.cursor()

    try:
        # DEFAULT 'staff' חל גם על שורות קיימות ב-SQLite (לא רק על
        # שורות עתידיות) - כל תור שקיים היום נוצר בפועל ע"י הצוות
        add_column_if_missing(cursor, "appointments", "source",
                               "TEXT NOT NULL DEFAULT 'staff'")
        add_column_if_missing(cursor, "appointments", "created_by_user_id", "INTEGER")
        add_column_if_missing(cursor, "appointments", "cancelled_at", "TEXT")
        add_column_if_missing(cursor, "appointments", "cancelled_by", "TEXT")
        add_column_if_missing(cursor, "appointments", "reminder_sent_at", "TEXT")

        connection.commit()
    finally:
        connection.close()

    return True


if __name__ == "__main__":
    print("Running migration 006 (extend appointments)...")
    run_migration()
    print("Done.")
