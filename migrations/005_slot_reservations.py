# ============================================================
# migrations/005_slot_reservations.py
# Release 2 - שכבה 1 מתוך 3 של ההגנה מפני double-booking: שריון
# זמני של סלוט (10 דקות) בזמן שהלקוחה בוחרת ומאשרת.
#
# בנוסף: מנרמל טלפונים קיימים של לקוחות (05XXXXXXXX). עד עכשיו
# api/clients_api.py שמר את הטלפון כמו שהוקלד (רק strip), כי אף
# תכונה לא הסתמכה על חיפוש לפי טלפון. ה-identify endpoint החדש
# של הפורטל (identity/) כן מסתמך על זה - בלי נרמול, לקוחה קיימת
# עם טלפון שנשמר "050-123-4567" לא תיפגש בחיפוש "0501234567".
#
# הרצה:  python3 migrations/005_slot_reservations.py
# בטוח להרצה חוזרת.
# ============================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import engine
from models import Base, SlotReservation
from database import get_connection
from utils.validators import normalize_phone


def _backfill_normalized_phones():
    """
    עובד מול database.get_connection() הגולמי ולא מול ה-ORM בכוונה:
    שאילתת ORM על Client הייתה שולפת גם עמודות עתידיות (כמו
    token_version, migrations/012) שעוד לא קיימות בשלב הזה של
    ריצת המיגרציות בסדר - SELECT מפורש על client_id/phone בלבד
    לא תלוי בהן כלל.
    """
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("SELECT client_id, phone FROM clients WHERE phone IS NOT NULL")
        rows = cursor.fetchall()

        updated = 0
        for client_id, phone in rows:
            normalized = normalize_phone(phone)
            # טלפון שלא ניתן לנרמל (פורמט ישן/לא תקין) נשאר כמו
            # שהוא - לא מוחקים מידע, רק לא ניתן יהיה למצוא את
            # הלקוחה בפורטל דרך הטלפון הזה עד שיתוקן ידנית
            if normalized and normalized != phone:
                cursor.execute("UPDATE clients SET phone = ? WHERE client_id = ?",
                               (normalized, client_id))
                updated += 1

        connection.commit()
    finally:
        connection.close()

    print(f"  {updated} client phone numbers normalized")


def run_migration():
    Base.metadata.create_all(engine, tables=[SlotReservation.__table__])
    print("  slot_reservations ready")

    _backfill_normalized_phones()

    return True


if __name__ == "__main__":
    print("Running migration 005 (slot_reservations)...")
    run_migration()
    print("Done.")
