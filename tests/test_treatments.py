# ============================================================
# tests/test_treatments.py
# סקריפט בדיקה למנהל הטיפולים
# בודק CRUD + מפעיל את seed_catalog לאתחול ראשוני
# ============================================================

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database import initialize_database
from entities.treatment import Treatment
from managers.treatment_manager import TreatmentManager


def print_separator(title):
    """מדפיס קו הפרדה עם כותרת"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def run_tests():
    """מריץ את כל בדיקות ה-CRUD של TreatmentManager"""
    
    initialize_database()
    manager = TreatmentManager()
    
    
    # ============================================================
    # Test 1: SEED CATALOG - Initial catalog setup
    # ============================================================
    print_separator("Test 1: SEED - Initialize catalog with 13 treatments")
    
    added = manager.seed_catalog()
    print(f"Treatments added: {added}")
    
    
    # ============================================================
    # Test 2: GET ALL - Show entire catalog
    # ============================================================
    print_separator("Test 2: GET ALL - Full catalog (sorted by price)")
    
    all_treatments = manager.get_all_treatments()
    print(f"Total treatments in catalog: {len(all_treatments)}\n")
    for treatment in all_treatments:
        print(f"  {treatment}")
    
    
    # ============================================================
    # Test 3: INSERT - Add new package treatment
    # ============================================================
    print_separator("Test 3: INSERT - Add custom package treatment")
    
    winter_package = Treatment(
        treatment_name="חבילת חורף",
        body_area="פנים, שפם, סנטר, צוואר",
        price=450,
        duration_minutes=45
    )
    
    result = manager.insert_treatment(winter_package)
    print(f"Created: {result}")
    print(f"Areas count: {result.get_areas_count()} (this is a package!)")
    
    
    # ============================================================
    # Test 4: GET BY ID - Fetch specific treatment
    # ============================================================
    print_separator("Test 4: GET BY ID - Fetch treatment")
    
    found = manager.get_treatment_by_id(1)
    print(f"Found: {found}")
    print(f"Areas as list: {found.get_areas_list()}")
    
    
    # ============================================================
    # Test 5: UPDATE - Modify a treatment
    # ============================================================
    print_separator("Test 5: UPDATE - Change treatment price")
    
    to_update = manager.get_treatment_by_id(1)
    original_price = to_update.price
    to_update.price = 280
    
    success = manager.update_treatment(to_update)
    print(f"Update succeeded? {success}")
    print(f"Original price: {original_price}, New price: 280")
    
    verified = manager.get_treatment_by_id(1)
    print(f"After update: {verified}")
    
    
    # ============================================================
    # Test 6: SEED again (should skip - idempotent)
    # ============================================================
    print_separator("Test 6: SEED again - Should skip (idempotent)")
    
    added = manager.seed_catalog()
    print(f"Treatments added this time: {added}")
    print("(Expected: 0 - because catalog is not empty)")
    
    
    # ============================================================
    # Test 7: DELETE non-existent
    # ============================================================
    print_separator("Test 7: DELETE - Non-existent treatment")
    
    success = manager.delete_treatment(999999)
    print(f"Delete succeeded? {success}")
    print("(Expected: False)")
    
    
    print("\n" + "=" * 60)
    print("  All TreatmentManager tests completed!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    run_tests()