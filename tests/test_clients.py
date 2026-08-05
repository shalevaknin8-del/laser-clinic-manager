# ============================================================
# tests/test_clients.py
# סקריפט בדיקה - מפעיל את כל 5 המתודות של ClientManager
# ומדפיס תוצאות לוודא שהמערכת עובדת תקין
# ============================================================

import sys
from pathlib import Path

# מוסיף את התיקייה הראשית של הפרויקט לנתיב החיפוש של פייתון
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database import initialize_database
from entities.client import Client
from managers.client_manager import ClientManager


def print_separator(title):
    """מדפיס קו הפרדה עם כותרת - עוזר לקריאת פלט הבדיקות"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def run_tests():
    """מריץ את כל בדיקות ה-CRUD של ClientManager"""
    
    # מוודא שה-DB מאותחל
    initialize_database()
    
    # יוצר מופע של המנהל
    manager = ClientManager()
    
    
    # ============================================================
    # Test 1: INSERT first client (with all fields)
    # ============================================================
    print_separator("Test 1: INSERT - First client (full details)")
    
    client1 = Client(
        full_name="Ronit Levi",
        phone="0501234567",
        email="ronit@example.com",
        address="Tel Aviv"
    )
    
    result = manager.insert_client(client1)
    print(f"Created: {result}")
    print(f"Assigned ID: {result.client_id}")
    
    
    # ============================================================
    # Test 2: INSERT second client (minimal - no email/address)
    # ============================================================
    print_separator("Test 2: INSERT - Second client (minimal)")
    
    client2 = Client(
        full_name="Michal Avraham",
        phone="0521234567"
    )
    
    result = manager.insert_client(client2)
    print(f"Created: {result}")
    print(f"Assigned ID: {result.client_id}")
    
    
    # ============================================================
    # Test 3: GET BY ID
    # ============================================================
    print_separator("Test 3: GET BY ID - Fetch first client")
    
    found = manager.get_client_by_id(client1.client_id)
    print(f"Found: {found}")
    
    
    # ============================================================
    # Test 4: GET ALL
    # ============================================================
    print_separator("Test 4: GET ALL - All clients (sorted by name)")
    
    all_clients = manager.get_all_clients()
    print(f"Total clients in system: {len(all_clients)}")
    for c in all_clients:
        print(f"  {c}")
    
    
    # ============================================================
    # Test 5: UPDATE
    # ============================================================
    print_separator("Test 5: UPDATE - Change first client's email")
    
    to_update = manager.get_client_by_id(client1.client_id)
    to_update.email = "ronit.new@example.com"
    to_update.address = "Ramat Gan"
    
    success = manager.update_client(to_update)
    print(f"Update succeeded? {success}")
    
    # שולפים שוב לוודא שהערכים באמת השתנו
    verified = manager.get_client_by_id(client1.client_id)
    print(f"After update: {verified}")
    
    
    # ============================================================
    # Test 6: DELETE
    # ============================================================
    print_separator("Test 6: DELETE - Delete second client")
    
    success = manager.delete_client(client2.client_id)
    print(f"Delete succeeded? {success}")
    
    
    # ============================================================
    # Test 7: GET BY ID for deleted (should return None)
    # ============================================================
    print_separator("Test 7: GET BY ID - Fetch deleted client (should be None)")
    
    deleted = manager.get_client_by_id(client2.client_id)
    print(f"Deleted client result: {deleted}")
    print(f"Is None? {deleted is None}")
    
    
    # ============================================================
    # Test 8: DELETE non-existent client
    # ============================================================
    print_separator("Test 8: DELETE - Non-existent client (should return False)")
    
    success = manager.delete_client(999999)
    print(f"Delete succeeded? {success}")
    print("(Expected: False)")
    
    
    print("\n" + "=" * 60)
    print("  All ClientManager tests completed!")
    print("=" * 60 + "\n")


# הרצה - רק אם קוראים לקובץ ישירות
if __name__ == "__main__":
    run_tests()