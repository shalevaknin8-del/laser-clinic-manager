# ============================================================
# migrations/012_client_token_version.py
# Release 2 - תוספת קטנה שהתגלתה תוך כדי בניית identity/tokens.py
# (לא הייתה בתכנון המקורי שהוצג ואושר): כדי ש-POST /logout של
# הפורטל יבטל בפועל refresh tokens קיימים (ולא רק ימחק את הטוקן
# בצד הלקוח), צריך אותו מנגנון בדיוק כמו users.token_version.
#
# הרצה:  python3 migrations/012_client_token_version.py
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
        add_column_if_missing(cursor, "clients", "token_version",
                               "INTEGER NOT NULL DEFAULT 0")
        connection.commit()
    finally:
        connection.close()

    return True


if __name__ == "__main__":
    print("Running migration 012 (client token_version)...")
    run_migration()
    print("Done.")
