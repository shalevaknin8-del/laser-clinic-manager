# ============================================================
# tests/test_error_handling.py
# בדיקת מנגנון הטיפול בשגיאות במנהלים
# ============================================================

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database import initialize_database
from entities.client import Client
from entities.appointment import Appointment
from managers.client_manager import ClientManager
from managers.appointment_manager import AppointmentManager


def print_separator(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def run_tests():
    initialize_database()
    client_manager = ClientManager()


    # ============================================================
    # Test 1: Valid insert - no error
    # ============================================================
    print_separator("Test 1: Valid insert - last_error should stay None")

    client = Client(full_name="Sara Cohen", phone="0501234567")
    result = client_manager.insert_client(client)

    print(f"Result: {result}")
    print(f"last_error: {client_manager.last_error}")
    print("(Expected: None)")


    # ============================================================
    # Test 2: Missing required field
    # ============================================================
    print_separator("Test 2: Missing full_name - NOT NULL violation")

    bad_client = Client(full_name=None, phone="0501234567")
    result = client_manager.insert_client(bad_client)

    print(f"Result: {result}   (Expected: None)")
    print(f"Error message: {client_manager.last_error}")


    # ============================================================
    # Test 3: Delete non-existent
    # ============================================================
    print_separator("Test 3: Delete non-existent client")

    success = client_manager.delete_client(999999)

    print(f"Success: {success}   (Expected: False)")
    print(f"Error message: {client_manager.last_error}")


    # ============================================================
    # Test 4: Delete client that has appointments
    # ============================================================
    print_separator("Test 4: Delete client with linked records")

    # יוצרים תור ללקוח שיצרנו ב-Test 1
    appointment_manager = AppointmentManager()
    appointment = Appointment(
        client_id=result if result else 1,
        treatment_id=1,
        appointment_date="2026-05-01",
        appointment_time="10:00"
    )

    # מנסים למחוק לקוח 1 (יש לו תורים מבדיקות קודמות)
    success = client_manager.delete_client(1)

    print(f"Success: {success}")
    print(f"Error message: {client_manager.last_error}")


    print("\n" + "=" * 60)
    print("  Error handling tests completed!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    run_tests()