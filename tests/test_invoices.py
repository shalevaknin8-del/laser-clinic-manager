# ============================================================
# tests/test_invoices.py
# סקריפט בדיקה למנהל החשבוניות
# בודק CRUD + מראה את יצירת מספרי החשבונית האוטומטיים
# ============================================================

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database import initialize_database, get_connection
from entities.invoice import Invoice
from managers.invoice_manager import InvoiceManager


def print_separator(title):
    """מדפיס קו הפרדה עם כותרת"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def setup_test_data():
    """
    מוודא שיש לקוח בסיסי לבדיקה.
    החשבוניות דורשות client_id קיים (FK constraint).
    """
    connection = get_connection()
    cursor = connection.cursor()
    
    # מוסיף לקוח בדיקה אם לא קיים
    cursor.execute("""
        INSERT OR IGNORE INTO clients (client_id, full_name, phone)
        VALUES (1, 'Test Client', '0501234567')
    """)
    
    connection.commit()
    connection.close()
    print("Test data ready: client #1 exists")


def run_tests():
    """מריץ את כל בדיקות ה-CRUD של InvoiceManager"""
    
    initialize_database()
    setup_test_data()
    manager = InvoiceManager()
    
    
    # ============================================================
    # Test 1: INSERT first invoice - auto number 2026-0001
    # ============================================================
    print_separator("Test 1: INSERT - First invoice (auto-numbered)")
    
    invoice1 = Invoice(
        client_id=1,
        amount=250.0,
        invoice_date="2026-03-15",
        appointment_id=None
    )
    
    result = manager.insert_invoice(invoice1)
    print(f"Created: {result}")
    print(f"Auto-generated number: {result.invoice_number}")
    print(f"Internal ID: {result.invoice_id}")
    
    
    # ============================================================
    # Test 2: INSERT second invoice - should be 2026-0002
    # ============================================================
    print_separator("Test 2: INSERT - Second invoice (next number)")
    
    invoice2 = Invoice(
        client_id=1,
        amount=80.0,
        invoice_date="2026-03-16"
    )
    
    result = manager.insert_invoice(invoice2)
    print(f"Created: {result}")
    print(f"Auto-generated number: {result.invoice_number}")
    
    
    # ============================================================
    # Test 3: INSERT third invoice - should be 2026-0003
    # ============================================================
    print_separator("Test 3: INSERT - Third invoice")
    
    invoice3 = Invoice(
        client_id=1,
        amount=450.0,
        invoice_date="2026-03-17"
    )
    
    result = manager.insert_invoice(invoice3)
    print(f"Created: {result}")
    print(f"Auto-generated number: {result.invoice_number}")
    
    
    # ============================================================
    # Test 4: GET ALL - Show all invoices (sorted DESC)
    # ============================================================
    print_separator("Test 4: GET ALL - All invoices (newest first)")
    
    all_invoices = manager.get_all_invoices()
    print(f"Total invoices: {len(all_invoices)}\n")
    for invoice in all_invoices:
        print(f"  {invoice}")
    
    
    # ============================================================
    # Test 5: GET BY ID
    # ============================================================
    print_separator("Test 5: GET BY ID - Fetch specific invoice")
    
    found = manager.get_invoice_by_id(1)
    print(f"Found: {found}")
    
    
    # ============================================================
    # Test 6: UPDATE - Change amount (number stays same!)
    # ============================================================
    print_separator("Test 6: UPDATE - Change amount (number unchanged)")
    
    to_update = manager.get_invoice_by_id(1)
    original_number = to_update.invoice_number
    original_amount = to_update.amount
    
    to_update.amount = 275.0
    success = manager.update_invoice(to_update)
    print(f"Update succeeded? {success}")
    print(f"Original amount: {original_amount}, New amount: 275.0")
    
    # שולפים ומוודאים שהמספר לא השתנה
    verified = manager.get_invoice_by_id(1)
    print(f"After update: {verified}")
    print(f"Invoice number preserved? {verified.invoice_number == original_number}")
    
    
    # ============================================================
    # Test 7: DELETE
    # ============================================================
    print_separator("Test 7: DELETE - Delete third invoice")
    
    success = manager.delete_invoice(3)
    print(f"Delete succeeded? {success}")
    
    remaining = manager.get_all_invoices()
    print(f"Remaining invoices: {len(remaining)}")
    
    
    # ============================================================
    # Test 8: INSERT after delete - should skip deleted number
    # ============================================================
    print_separator("Test 8: INSERT after delete - Uses MAX, skips deleted")
    
    invoice4 = Invoice(
        client_id=1,
        amount=200.0,
        invoice_date="2026-03-18"
    )
    
    result = manager.insert_invoice(invoice4)
    print(f"Created: {result}")
    print(f"Number: {result.invoice_number}")
    print("(Note: uses MAX+1, so we get 2026-0004, not reuse deleted 0003)")
    
    
    print("\n" + "=" * 60)
    print("  All InvoiceManager tests completed!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    run_tests()