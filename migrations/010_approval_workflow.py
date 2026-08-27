# ============================================================
# migrations/010_approval_workflow.py
# Release 2 - זרימת האישור (Part 16 במפרט) + שכבה 3 מתוך 3 של
# ההגנה מפני double-booking: אינדקסים ייחודיים חלקיים.
#
# למה per-resource ולא (appointment_date, appointment_time) גלובלי:
# הקליניקה הזו כבר תומכת בכמה תורים באותה שעה בדיוק (חדרים/מכשירים/
# עובדות שונות - ראו managers/appointment_treatment_manager.py,
# האילוץ התלת-כיווני). אינדקס גלובלי על תאריך+שעה בלבד היה שובר
# את זה. במקום זה - שלושה אינדקסים, אחד לכל משאב, כדי לתפוס בדיוק
# את התרחיש שהמפרט חושש ממנו: שני קליקים בו-זמנית ש"זוכים" לאותה
# עובדת/חדר/מכשיר באותה שעה. NULL לא מתנגש עם NULL ב-SQLite
# (סמנטיקה סטנדרטית של unique index), אז תור בלי משאב משויך לא נחסם.
#
# backfill: כל תור קיים (source='staff', מלפני הפיצ'ר הזה) מסומן
# approval_status='confirmed' - הוא כבר "אושר" בכך שצוות קבע אותו
# ישירות. רק תורי פורטל/צ'אטבוט חדשים נכנסים עם pending_approval.
#
# הרצה:  python3 migrations/010_approval_workflow.py
# בטוח להרצה חוזרת.
# ============================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import get_connection
from migrations._helpers import add_column_if_missing


def _warn_if_conflicts_exist(cursor, resource_column):
    """
    בודק מראש אם כבר קיימים תורים כפולים על אותו משאב/תאריך/שעה -
    אם כן, יצירת ה-unique index למטה תיכשל עם שגיאת SQLite גולמית.
    בדיקה מפורשת כאן נותנת הודעה ברורה במקום debugging בעיוורון.
    לא מוחקים כלום אוטומטית - זה החלטה שדורשת בן אדם.
    """
    cursor.execute(f"""
        SELECT {resource_column}, appointment_date, appointment_time, COUNT(*)
        FROM appointments
        WHERE status != 'cancelled' AND {resource_column} IS NOT NULL
        GROUP BY {resource_column}, appointment_date, appointment_time
        HAVING COUNT(*) > 1
    """)
    conflicts = cursor.fetchall()
    if conflicts:
        print(f"  WARNING: {len(conflicts)} existing double-booking(s) found on {resource_column} - "
              f"index creation below will fail until these are resolved manually: {conflicts}")


def run_migration():
    connection = get_connection()
    cursor = connection.cursor()

    try:
        add_column_if_missing(cursor, "appointments", "approval_status",
                               "TEXT NOT NULL DEFAULT 'pending_approval'")
        add_column_if_missing(cursor, "appointments", "approved_by_user_id", "INTEGER")
        add_column_if_missing(cursor, "appointments", "approved_at", "TEXT")
        add_column_if_missing(cursor, "appointments", "rejection_reason", "TEXT")
        add_column_if_missing(cursor, "appointments", "approval_expires_at", "TEXT")

        # תורים ישנים/של צוות לא צריכים לעבור אישור בדיעבד
        cursor.execute(
            "UPDATE appointments SET approval_status = 'confirmed' "
            "WHERE source = 'staff' AND approval_status = 'pending_approval'"
        )
        print(f"  {cursor.rowcount} existing staff appointments marked confirmed")

        cursor.execute(
            "CREATE INDEX IF NOT EXISTS ix_appointments_approval "
            "ON appointments(approval_status, approval_expires_at)"
        )

        _warn_if_conflicts_exist(cursor, "staff_user_id")
        _warn_if_conflicts_exist(cursor, "room_id")
        _warn_if_conflicts_exist(cursor, "machine_id")

        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_appt_staff_slot "
            "ON appointments(staff_user_id, appointment_date, appointment_time) "
            "WHERE status != 'cancelled'"
        )
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_appt_room_slot "
            "ON appointments(room_id, appointment_date, appointment_time) "
            "WHERE status != 'cancelled'"
        )
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_appt_machine_slot "
            "ON appointments(machine_id, appointment_date, appointment_time) "
            "WHERE status != 'cancelled'"
        )
        print("  approval + per-resource unique indexes ready")

        connection.commit()
    finally:
        connection.close()

    return True


if __name__ == "__main__":
    print("Running migration 010 (approval workflow)...")
    run_migration()
    print("Done.")
