# ============================================================
# tests/test_soft_delete.py
# בדיקת מנגנון ה-Soft Delete של חשבוניות
# מוודא שמספרי חשבוניות לא חוזרים אחרי ביטול
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
    """מוודא שיש לקוח בסיסי לבדיקה - חשבונית דורשת client_id קיים"""
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO clients (client_id, full_name, phone)
        VALUES (1, 'Test Client', '0501234567')
    """)

    connection.commit()
    connection.close()


def run_tests():
    """בודק את כל מנגנון ה-Soft Delete"""

    initialize_database()
    setup_test_data()
    manager = InvoiceManager()


    # ============================================================
    # Test 1: Create three invoices
    # ============================================================
    print_separator("Test 1: INSERT - Create three invoices")

    for amount in [250.0, 80.0, 450.0]:
        invoice = Invoice(
            client_id=1,
            amount=amount,
            invoice_date="2026-03-15"
        )
        result = manager.insert_invoice(invoice)
        print(f"  Created: {result.invoice_number} - {result.amount} NIS")


    # ============================================================
    # Test 2: DELETE should be blocked
    # ============================================================
    print_separator("Test 2: DELETE - Should be blocked by law")

    success = manager.delete_invoice(3)
    print(f"Delete returned: {success}")
    print("(Expected: False - deletion is illegal)")


    # ============================================================
    # Test 3: CANCEL instead
    # ============================================================
    print_separator("Test 3: CANCEL - Soft delete the third invoice")

    success = manager.cancel_invoice(3)
    print(f"Cancel returned: {success}")


    # ============================================================
    # Test 4: Active invoices only
    # ============================================================
    print_separator("Test 4: GET ALL - Active only (default)")

    active = manager.get_all_invoices()
    print(f"Active invoices: {len(active)}")
    for inv in active:
        print(f"  {inv}")


    # ============================================================
    # Test 5: Including cancelled - for tax audit
    # ============================================================
    print_separator("Test 5: GET ALL - Including cancelled (audit view)")

    everything = manager.get_all_invoices(include_cancelled=True)
    print(f"All invoices: {len(everything)}")
    for inv in everything:
        print(f"  {inv}")


    # ============================================================
    # Test 6: THE BIG ONE - number must not be reused
    # ============================================================
    print_separator("Test 6: INSERT after cancel - Number must NOT repeat")

    new_invoice = Invoice(
        client_id=1,
        amount=100.0,
        invoice_date="2026-03-16"
    )
    result = manager.insert_invoice(new_invoice)

    print(f"New invoice number: {result.invoice_number}")
    print("Expected: 2026-0004")
    print(f"Correct? {result.invoice_number == '2026-0004'}")


    # ============================================================
    # Test 7: Cancel twice - should fail
    # ============================================================
    print_separator("Test 7: CANCEL again - Should fail")

    success = manager.cancel_invoice(3)
    print(f"Cancel returned: {success}")
    print("(Expected: False - already cancelled)")


    # ============================================================
    # Test 8: Restore a cancelled invoice
    # ============================================================
    print_separator("Test 8: RESTORE - Bring back cancelled invoice")

    success = manager.restore_invoice(3)
    print(f"Restore returned: {success}")

    active = manager.get_all_invoices()
    print(f"Active invoices now: {len(active)}")
    print("(Expected: 4 - the restored one is back)")


    print("\n" + "=" * 60)
    print("  All Soft Delete tests completed!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    run_tests()