# ============================================================
# migrations/003_add_users_table.py
# יוצר את טבלת המשתמשים ואת טבלת יומן הפעולות.
#
# הרצה:  python3 migrations/003_add_users_table.py
#
# הערה על מחיקת משתמשים: אין כאן מחיקה. עובדת שעוזבת
# מסומנת כלא פעילה. מחיקה אמיתית הייתה מייתמת את כל
# רשומות היומן שלה ומאבדת את שרשרת האחריות.
#
# הסקריפט בטוח להרצה חוזרת.
# ============================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import get_connection


CREATE_USERS_SQL = """
CREATE TABLE IF NOT EXISTS users (
    user_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    phone               TEXT NOT NULL UNIQUE,
    password_hash       TEXT NOT NULL,
    full_name           TEXT NOT NULL,
    role                TEXT NOT NULL DEFAULT 'employee',
    is_active           INTEGER NOT NULL DEFAULT 1,
    failed_attempts     INTEGER NOT NULL DEFAULT 0,
    locked_until        TEXT,
    last_login_at       TEXT,
    password_changed_at TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_AUDIT_SQL = """
CREATE TABLE IF NOT EXISTS audit_log (
    audit_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER,
    username        TEXT,
    action          TEXT NOT NULL,
    entity_type     TEXT,
    entity_id       INTEGER,
    details         TEXT,
    ip_address      TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
"""

CREATE_AUDIT_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_audit_created
ON audit_log (created_at DESC);
"""


def run_migration():
    """יוצר את שתי הטבלאות אם הן עדיין לא קיימות."""
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(CREATE_USERS_SQL)
        cursor.execute(CREATE_AUDIT_SQL)
        cursor.execute(CREATE_AUDIT_INDEX_SQL)
        connection.commit()

        print("Tables 'users' and 'audit_log' are ready.")
        return True

    finally:
        connection.close()


if __name__ == "__main__":
    run_migration()