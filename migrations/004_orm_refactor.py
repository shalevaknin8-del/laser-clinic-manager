# ============================================================
# migrations/004_orm_refactor.py
# מוסיף את העמודות והטבלאות החדשות שדורש המעבר ל-ORM/JWT/חבילות:
#   - clients: has_signed_health_declaration, health_declaration_file_path
#   - users:   token_version (לביטול refresh token בלי טבלת session)
#   - טבלאות חדשות: rooms, machines, staff_availability,
#     staff_time_off, packages, client_packages
#   - appointments: room_id, machine_id, staff_user_id, client_package_id
#
# הרצה:  python3 migrations/004_orm_refactor.py
# בטוח להרצה חוזרת - כל שינוי נבדק לפני שהוא מתבצע.
# ============================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import get_connection
from db import init_orm_tables


def _add_column_if_missing(cursor, table, column, column_def):
    cursor.execute(f"PRAGMA table_info({table})")
    existing = [row[1] for row in cursor.fetchall()]
    if column not in existing:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_def}")
        print(f"  {table}.{column} added")
    else:
        print(f"  {table}.{column} already exists - skipped")


def run_migration():
    connection = get_connection()
    cursor = connection.cursor()

    try:
        _add_column_if_missing(cursor, "clients", "has_signed_health_declaration",
                                "INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(cursor, "clients", "health_declaration_file_path", "TEXT")

        _add_column_if_missing(cursor, "users", "token_version", "INTEGER NOT NULL DEFAULT 0")

        _add_column_if_missing(cursor, "treatments", "requires_machine",
                                "INTEGER NOT NULL DEFAULT 1")
        _add_column_if_missing(cursor, "treatments", "default_machine_type", "TEXT")

        _add_column_if_missing(cursor, "appointments", "room_id", "INTEGER")
        _add_column_if_missing(cursor, "appointments", "machine_id", "INTEGER")
        _add_column_if_missing(cursor, "appointments", "staff_user_id", "INTEGER")
        _add_column_if_missing(cursor, "appointments", "client_package_id", "INTEGER")

        connection.commit()
    finally:
        connection.close()

    # הטבלאות החדשות לגמרי נוצרות דרך ה-ORM עצמו (Base.metadata.create_all),
    # כדי שהגדרתן תהיה במקום אחד (models.py) ולא כפולה כאן ב-SQL גולמי
    init_orm_tables()
    print("  rooms / machines / staff_availability / staff_time_off / "
          "packages / client_packages ready")

    return True


if __name__ == "__main__":
    print("Running migration 004 (ORM/JWT/packages refactor)...")
    run_migration()
    print("Done.")
