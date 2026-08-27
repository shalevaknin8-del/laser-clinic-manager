# ============================================================
# migrations/013_portal_registration.py
# Release 2 - תוספת שהתגלתה תוך כדי בניית api/portal_api.py
# (לא הייתה בתכנון המקורי): כדי לממש את Part 4 Step 1-3 במפרט
# (זיהוי לפי טלפון+OTP, בלי חשיפת קיום/אי-קיום) צריך client_id
# קיים עוד *לפני* האימות - כי טבלת otp_codes דורשת client_id
# (FK NOT NULL, ראו migrations/002). לכן /identify יוצר "שלד"
# לקוחה (שם+טלפון בלבד) גם עבור טלפון חדש, עוד לפני אימות.
#
# profile_completed_at מבדיל שלד ממתין (NULL) מלקוחה אמיתית
# (NOT NULL) - כולל בין ניסיונות /identify חוזרים לאותו טלפון
# חדש, לפני שהיא בכלל אימתה קוד בפעם הראשונה.
#
# הרצה:  python3 migrations/013_portal_registration.py
# בטוח להרצה חוזרת.
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
        cursor.execute("PRAGMA table_info(clients)")
        column_already_existed = "profile_completed_at" in [row[1] for row in cursor.fetchall()]

        add_column_if_missing(cursor, "clients", "profile_completed_at", "TEXT")

        if not column_already_existed:
            # הבאקפיל חד-פעמי: רק בריצה שבה העמודה נוצרה זה עתה.
            # אסור להריץ את זה שוב בריצות הבאות - אחרת כל שלד פורטל
            # ממתין (profile_completed_at IS NULL, לקוחה חדשה שעוד
            # לא סיימה הרשמה) היה "מושלם" בטעות בכל הפעלה מחדש של השרת
            cursor.execute(
                "UPDATE clients SET profile_completed_at = COALESCE(created_at, CURRENT_TIMESTAMP) "
                "WHERE profile_completed_at IS NULL"
            )
            print(f"  {cursor.rowcount} existing clients marked as profile-complete")
        else:
            print("  backfill already ran previously - skipped")

        connection.commit()
    finally:
        connection.close()

    return True


if __name__ == "__main__":
    print("Running migration 013 (portal registration)...")
    run_migration()
    print("Done.")
