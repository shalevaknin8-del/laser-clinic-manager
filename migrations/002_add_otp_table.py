# ============================================================
# migrations/002_add_otp_table.py
# יוצר את הטבלה ששומרת קודי אימות חד-פעמיים.
#
# הרצה:  python3 migrations/002_add_otp_table.py
#
# הטבלה שומרת טביעת אצבע של הקוד ולא את הקוד עצמו,
# מאותה סיבה שבה תעודת הזהות נשמרת כטביעת אצבע:
# הקוד משמש להשוואה בלבד ואין סיבה שיהיה קריא.
#
# הסקריפט בטוח להרצה חוזרת.
# ============================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import get_connection


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS otp_codes (
    otp_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id       INTEGER NOT NULL,
    code_hash       TEXT NOT NULL,
    channel         TEXT NOT NULL,
    purpose         TEXT NOT NULL DEFAULT 'identity_verification',
    attempts_used   INTEGER NOT NULL DEFAULT 0,
    is_used         INTEGER NOT NULL DEFAULT 0,
    expires_at      TEXT NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (client_id) REFERENCES clients(client_id)
);
"""

# אינדקס שמאיץ את איתור הקוד הפעיל האחרון של לקוחה
CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_otp_client_active
ON otp_codes (client_id, is_used, expires_at);
"""


def run_migration():
    """יוצר את הטבלה ואת האינדקס אם הם עדיין לא קיימים."""
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(CREATE_TABLE_SQL)
        cursor.execute(CREATE_INDEX_SQL)
        connection.commit()

        print("Table 'otp_codes' is ready.")
        return True

    finally:
        connection.close()


if __name__ == "__main__":
    run_migration()