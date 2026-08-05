# ============================================================
# tests/test_leads.py
# סקריפט בדיקה למנהל הלידים
# בודק CRUD + המרת ליד ללקוח (הפעולה המרכזית של בונוס 2)
# ============================================================

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database import initialize_database
from entities.lead import Lead
from managers.lead_manager import LeadManager


def print_separator(title):
    """מדפיס קו הפרדה עם כותרת"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def run_tests():
    """מריץ את כל בדיקות ה-CRUD של LeadManager"""

    initialize_database()
    manager = LeadManager()


    # ============================================================
    # Test 1: INSERT - First lead
    # ============================================================
    print_separator("Test 1: INSERT - First lead (Instagram)")

    lead1 = Lead(
        full_name="שרה כהן",
        phone="0501112233",
        source="instagram",
        notes="שאלה על חבילת פנים"
    )

    result = manager.insert_lead(lead1)
    print(f"Created: {result}")
    print(f"Assigned ID: {result.lead_id}")


    # ============================================================
    # Test 2: INSERT - Second lead
    # ============================================================
    print_separator("Test 2: INSERT - Second lead (Facebook)")

    lead2 = Lead(
        full_name="מיכל אברהם",
        phone="0522223344",
        source="facebook"
    )

    result = manager.insert_lead(lead2)
    print(f"Created: {result}")


    # ============================================================
    # Test 3: GET BY ID + Entity helper methods
    # ============================================================
    print_separator("Test 3: GET BY ID + Entity methods")

    found = manager.get_lead_by_id(lead1.lead_id)
    print(f"Found: {found}")
    print(f"Is active?    {found.is_active()}     (Expected: True)")
    print(f"Is converted? {found.is_converted()}  (Expected: False)")


    # ============================================================
    # Test 4: GET ALL
    # ============================================================
    print_separator("Test 4: GET ALL - Newest first")

    all_leads = manager.get_all_leads()
    print(f"Total leads: {len(all_leads)}\n")
    for lead in all_leads:
        print(f"  {lead}")


    # ============================================================
    # Test 5: UPDATE - Move to 'in_progress'
    # ============================================================
    print_separator("Test 5: UPDATE - Status to 'in_progress'")

    to_update = manager.get_lead_by_id(lead1.lead_id)
    to_update.status = "in_progress"
    to_update.notes = "התקשרתי - מעוניינת מאוד"

    success = manager.update_lead(to_update)
    print(f"Update succeeded? {success}")

    verified = manager.get_lead_by_id(lead1.lead_id)
    print(f"After update: {verified}")


    # ============================================================
    # Test 6: CONVERT - The main event (Transaction!)
    # ============================================================
    print_separator("Test 6: CONVERT - Lead becomes Client")

    new_client = manager.convert_lead_to_client(
        lead_id=lead1.lead_id,
        email="sarah@example.com",
        address="תל אביב"
    )

    if new_client is not None:
        print(f"New client: {new_client}")
    else:
        print("Conversion FAILED")


    # ============================================================
    # Test 7: VERIFY - Lead status changed in DB
    # ============================================================
    print_separator("Test 7: VERIFY - Status after conversion")

    converted = manager.get_lead_by_id(lead1.lead_id)
    print(f"Lead now: {converted}")
    print(f"Is converted? {converted.is_converted()}  (Expected: True)")
    print(f"Is active?    {converted.is_active()}     (Expected: False)")


    # ============================================================
    # Test 8: CONVERT again - Should be blocked
    # ============================================================
    print_separator("Test 8: CONVERT again - Should fail")

    duplicate = manager.convert_lead_to_client(
        lead_id=lead1.lead_id,
        email="duplicate@example.com"
    )

    print(f"Result: {duplicate}")
    print(f"Is None? {duplicate is None}  (Expected: True)")


    # ============================================================
    # Test 9: CONVERT non-existent lead
    # ============================================================
    print_separator("Test 9: CONVERT - Non-existent lead")

    fake = manager.convert_lead_to_client(lead_id=999999)

    print(f"Result: {fake}")
    print(f"Is None? {fake is None}  (Expected: True)")


    # ============================================================
    # Test 10: DELETE
    # ============================================================
    print_separator("Test 10: DELETE - Remove unconverted lead")

    success = manager.delete_lead(lead2.lead_id)
    print(f"Delete succeeded? {success}")

    remaining = manager.get_all_leads()
    print(f"Remaining leads: {len(remaining)}")


    print("\n" + "=" * 60)
    print("  All LeadManager tests completed!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    run_tests()