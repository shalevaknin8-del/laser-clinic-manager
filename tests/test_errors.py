# ============================================================
# tests/test_errors.py
# בדיקת מנגנון תרגום השגיאות
# ============================================================

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import sqlite3
from utils.db_errors import translate_db_error


def print_separator(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def run_tests():
    """בודק שכל סוג שגיאה מתורגם נכון"""

    # ============================================================
    # Test 1: Foreign key error
    # ============================================================
    print_separator("Test 1: FOREIGN KEY error")

    error = sqlite3.IntegrityError("FOREIGN KEY constraint failed")
    print(translate_db_error(error))


    # ============================================================
    # Test 2: UNIQUE on invoice number
    # ============================================================
    print_separator("Test 2: UNIQUE constraint on invoice_number")

    error = sqlite3.IntegrityError(
        "UNIQUE constraint failed: invoices.invoice_number"
    )
    print(translate_db_error(error))


    # ============================================================
    # Test 3: NOT NULL - field name extracted
    # ============================================================
    print_separator("Test 3: NOT NULL - should name the field")

    error = sqlite3.IntegrityError(
        "NOT NULL constraint failed: clients.full_name"
    )
    print(translate_db_error(error))


    # ============================================================
    # Test 4: Missing table
    # ============================================================
    print_separator("Test 4: Missing table")

    error = sqlite3.OperationalError("no such table: clients")
    print(translate_db_error(error))


    # ============================================================
    # Test 5: Database locked
    # ============================================================
    print_separator("Test 5: Database locked")

    error = sqlite3.OperationalError("database is locked")
    print(translate_db_error(error))


    # ============================================================
    # Test 6: Unknown error with context
    # ============================================================
    print_separator("Test 6: Unknown error with context")

    error = ValueError("something weird")
    print(translate_db_error(error, context="הוספת תור"))


    print("\n" + "=" * 60)
    print("  All error-translation tests completed!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    run_tests()