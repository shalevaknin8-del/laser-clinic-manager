# ============================================================
# tests/test_conflicts.py
# בדיקת מנגנון מניעת ההתנגשויות בתורים
# מוודא שהמערכת תופסת חפיפות זמן ומאפשרת תורים צמודים
# ============================================================

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database import initialize_database, get_connection
from entities.appointment import Appointment
from managers.appointment_manager import AppointmentManager
from managers.treatment_manager import TreatmentManager


def print_separator(title):
    """מדפיס קו הפרדה עם כותרת"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def setup_test_data():
    """
    מכין את הנתונים לבדיקה:
    - לקוח אחד
    - קטלוג טיפולים (דרך seed_catalog)
    """
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO clients (client_id, full_name, phone)
        VALUES (1, 'Test Client', '0501234567')
    """)

    connection.commit()
    connection.close()

    # ממלא את קטלוג הטיפולים אם ריק
    treatment_manager = TreatmentManager()
    treatment_manager.seed_catalog()


def run_tests():
    """בודק את כל מנגנון מניעת ההתנגשויות"""

    initialize_database()
    setup_test_data()
    manager = AppointmentManager()

    TEST_DATE = "2026-04-10"


    # ============================================================
    # Test 1: Book first appointment - 30 min treatment
    # ============================================================
    print_separator("Test 1: Book Brazilian (30 min) at 10:00")

    # טיפול 6 = ברזילאי, 30 דקות
    first = Appointment(
        client_id=1,
        treatment_id=6,
        appointment_date=TEST_DATE,
        appointment_time="10:00"
    )

    has_conflict, message = manager.check_conflict(
        TEST_DATE, "10:00", treatment_id=6
    )
    print(f"Conflict before booking? {has_conflict}")

    result = manager.insert_appointment(first)
    print(f"Booked: appointment #{result.appointment_id} at 10:00-10:30")


    # ============================================================
    # Test 2: Exact same time - MUST conflict
    # ============================================================
    print_separator("Test 2: Same exact time 10:00 - should CONFLICT")

    has_conflict, message = manager.check_conflict(
        TEST_DATE, "10:00", treatment_id=2
    )
    print(f"Conflict? {has_conflict}   (Expected: True)")
    print(f"Message: {message}")


    # ============================================================
    # Test 3: Overlap in the middle - the tricky case
    # ============================================================
    print_separator("Test 3: 10:15 - overlaps middle - should CONFLICT")

    has_conflict, message = manager.check_conflict(
        TEST_DATE, "10:15", treatment_id=2
    )
    print(f"Conflict? {has_conflict}   (Expected: True)")
    print(f"Message: {message}")
    print("(This is the case a naive 'same time' check would MISS)")


    # ============================================================
    # Test 4: Starts before, ends inside - should conflict
    # ============================================================
    print_separator("Test 4: 09:45 (20 min) - ends 10:05 - should CONFLICT")

    # טיפול 1 = פנים מלא, 20 דקות
    has_conflict, message = manager.check_conflict(
        TEST_DATE, "09:45", treatment_id=1
    )
    print(f"Conflict? {has_conflict}   (Expected: True)")
    print(f"Message: {message}")


    # ============================================================
    # Test 5: Exactly adjacent - should NOT conflict
    # ============================================================
    print_separator("Test 5: 10:30 - exactly when first ends - NO conflict")

    has_conflict, message = manager.check_conflict(
        TEST_DATE, "10:30", treatment_id=2
    )
    print(f"Conflict? {has_conflict}   (Expected: False)")
    print("(Back-to-back appointments are legal)")


    # ============================================================
    # Test 6: Well before - no conflict
    # ============================================================
    print_separator("Test 6: 09:00 - well before - NO conflict")

    has_conflict, message = manager.check_conflict(
        TEST_DATE, "09:00", treatment_id=2
    )
    print(f"Conflict? {has_conflict}   (Expected: False)")


    # ============================================================
    # Test 7: Different day - no conflict
    # ============================================================
    print_separator("Test 7: Same time, different day - NO conflict")

    has_conflict, message = manager.check_conflict(
        "2026-04-11", "10:00", treatment_id=6
    )
    print(f"Conflict? {has_conflict}   (Expected: False)")


    # ============================================================
    # Test 8: exclude_appointment_id - updating existing
    # ============================================================
    print_separator("Test 8: Update same appointment - should NOT self-conflict")

    has_conflict, message = manager.check_conflict(
        TEST_DATE, "10:00", treatment_id=6,
        exclude_appointment_id=result.appointment_id
    )
    print(f"Conflict? {has_conflict}   (Expected: False)")
    print("(An appointment must not conflict with itself when edited)")


    # ============================================================
    # Test 9: Available slots
    # ============================================================
    print_separator("Test 9: Show available slots for a 10-min treatment")

    slots = manager.get_available_slots(TEST_DATE, treatment_id=2)
    print(f"Total free slots: {len(slots)}")
    print(f"First 8:  {slots[:8]}")
    print(f"Around the booked time: {[s for s in slots if '09:4' in s or '10:' in s]}")
    print("(10:00 through 10:15 should be missing - they are taken)")


    print("\n" + "=" * 60)
    print("  All conflict-detection tests completed!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    run_tests()