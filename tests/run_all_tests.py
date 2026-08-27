# ============================================================
# tests/run_all_tests.py
# מריץ את כל חבילת הבדיקות (תרחישי חובה + אבטחה + מקרי קצה)
# ומדפיס סיכום קריא בסוף - הפלט של הקובץ הזה הוא הוכחת ההרצה.
#
# הרצה:  python3 tests/run_all_tests.py
#
# משתמש ב-pytest תחת הקאפה, עם -s כדי שהתמלולים המודפסים
# בתוך test_scenarios.py יופיעו במסך ולא ייבלעו ע"י הלכידה
# הרגילה של פלט הבדיקות.
# ============================================================

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = Path(__file__).resolve().parent


TEST_SUITES = [
    ("תרחישי החובה (5 תרחישים)", "test_scenarios.py"),
    ("בדיקות אבטחה", "test_security.py"),
    ("מקרי קצה", "test_edge_cases.py"),
]


def main():
    print("=" * 70)
    print("  מריץ את כל חבילת הבדיקות - laser_clinic_manager")
    print("=" * 70)

    overall_exit_code = 0
    results = []

    for title, filename in TEST_SUITES:
        print("\n" + "-" * 70)
        print(f"  {title}  ({filename})")
        print("-" * 70)

        exit_code = pytest.main([
            "-v", "-s", "--tb=short",
            str(TESTS_DIR / filename),
        ])

        results.append((title, exit_code))
        if exit_code != 0:
            overall_exit_code = exit_code

    print("\n" + "=" * 70)
    print("  סיכום")
    print("=" * 70)
    for title, exit_code in results:
        status = "PASS" if exit_code == 0 else f"FAIL (exit code {exit_code})"
        print(f"  {status:20s} {title}")

    print("=" * 70)
    if overall_exit_code == 0:
        print("  כל הבדיקות עברו בהצלחה")
    else:
        print("  יש בדיקות שנכשלו - ראו פירוט למעלה")
    print("=" * 70)

    return overall_exit_code


if __name__ == "__main__":
    sys.exit(main())
