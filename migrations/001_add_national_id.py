# ============================================================
# migrations/001_add_national_id.py
# מוסיף עמודת תעודת זהות לטבלת הלקוחות.
#
# הרצה:  python3 migrations/001_add_national_id.py
#
# הסקריפט בטוח להרצה חוזרת. אם העמודה כבר קיימת,
# הוא מדווח על כך ויוצא בלי לשנות דבר.
#
# העמודה שומרת טביעת אצבע בלבד, לא את המספר עצמו.
# שם העמודה מסתיים ב-hash כדי שיהיה ברור לכל מי שקורא
# את הסכמה שאין כאן נתון קריא.
# ============================================================

import sys
from pathlib import Path

# מאפשר להריץ את הסקריפט ישירות מהטרמינל
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import get_connection


COLUMN_NAME = "national_id_hash"
TABLE_NAME = "clients"


def column_exists(cursor, table_name, column_name):
    """בודק אם עמודה כבר קיימת בטבלה."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    existing_columns = [row[1] for row in cursor.fetchall()]
    return column_name in existing_columns


def run_migration():
    """מוסיף את העמודה אם היא עדיין לא קיימת."""
    connection = get_connection()
    cursor = connection.cursor()

    try:
        if column_exists(cursor, TABLE_NAME, COLUMN_NAME):
            print(f"Column '{COLUMN_NAME}' already exists. Nothing to do.")
            return False

        # העמודה מוגדרת כמאפשרת ריק, כי ללקוחות הקיימים
        # עדיין אין תעודת זהות שמורה במערכת
        cursor.execute(
            f"ALTER TABLE {TABLE_NAME} ADD COLUMN {COLUMN_NAME} TEXT"
        )
        connection.commit()

        print(f"Column '{COLUMN_NAME}' added to '{TABLE_NAME}' successfully.")
        return True

    finally:
        connection.close()


if __name__ == "__main__":
    run_migration()