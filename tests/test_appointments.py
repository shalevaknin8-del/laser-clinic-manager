# ============================================================
# tests/test_appointments.py
# סקריפט בדיקה - מפעיל את כל 5 המתודות של AppointmentManager
# ומדפיס תוצאות לוודא שהמערכת עובדת תקין
# ============================================================

import sys
from pathlib import Path

# מוסיף את התיקייה הראשית של הפרויקט לנתיב החיפוש של פייתון
# כך שנוכל לייבא מ-managers ו-entities
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database import initialize_database
from entities.appointment import Appointment
from managers.appointment_manager import AppointmentManager


def print_separator(title):
    """מדפיס קו הפרדה עם כותרת - עוזר לקריאת פלט הבדיקות"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def setup_test_data():
    """
    מוסיף לקוח וטיפול בסיסיים לצורך הבדיקה בלבד.
    בעתיד (יום 3-4) - נבנה ClientManager ו-TreatmentManager מסודרים.
    """
    from database import get_connection
    
    connection = get_connection()
    cursor = connection.cursor()
    
    # מוסיף לקוחה לדוגמה - INSERT OR IGNORE = לא נוסיף פעמיים בהרצות חוזרות
    cursor.execute("""
        INSERT OR IGNORE INTO clients (client_id, full_name, phone)
        VALUES (1, 'רונית לוי', '0501234567')
    """)
    
    # מוסיף טיפול לדוגמה
    cursor.execute("""
        INSERT OR IGNORE INTO treatments (treatment_id, treatment_name, body_area, price, duration_minutes)
        VALUES (1, 'Full Face', 'פנים מלא', 250.0, 20)
    """)
    
    cursor.execute("""
        INSERT OR IGNORE INTO treatments (treatment_id, treatment_name, body_area, price, duration_minutes)
        VALUES (2, 'Upper Lip', 'שפם', 80.0, 10)
    """)
    
    connection.commit()
    connection.close()
    print("נתוני בדיקה הוכנסו: לקוח 1, טיפולים 1 ו-2")


def run_tests():
    """מריץ את כל בדיקות ה-CRUD של AppointmentManager"""
    
    # מוודא שה-DB מאותחל (יוצר טבלאות אם חסרות)
    initialize_database()
    
    # מכניס נתוני עזר לבדיקה (לקוח, טיפולים)
    setup_test_data()
    
    # יוצר מופע של המנהל - נשתמש בו לכל הבדיקות
    manager = AppointmentManager()
    
    
    # ============================================================
    # בדיקה 1: הוספת תור ראשון
    # ============================================================
    print_separator("Test 1: INSERT - First appointment")
    
    appointment1 = Appointment(
        client_id=1,
        treatment_id=1,
        appointment_date="2025-03-15",
        appointment_time="10:00",
        notes="לקוחה חדשה"
    )
    
    result = manager.insert_appointment(appointment1)
    print(f"תור שנוצר: {result}")
    print(f"ID שהוקצה אוטומטית: {result.appointment_id}")
    
    
    # ============================================================
    # בדיקה 2: הוספת תור שני
    # ============================================================
    print_separator("Test 2: INSERT - Second appointment")
    
    appointment2 = Appointment(
        client_id=1,
        treatment_id=2,
        appointment_date="2025-03-20",
        appointment_time="14:30"
    )
    
    result = manager.insert_appointment(appointment2)
    print(f"תור שנוצר: {result}")
    
    
    # ============================================================
    # בדיקה 3: שליפת תור לפי ID
    # ============================================================
    print_separator("Test 3: GET BY ID - Fetch first appointment")
    
    found = manager.get_appointment_by_id(1)
    print(f"תור שנמצא: {found}")
    
    
    # ============================================================
    # בדיקה 4: שליפת כל התורים
    # ============================================================
    print_separator("Test 4: GET ALL - All appointments")
    
    all_appointments = manager.get_all_appointments()
    print(f"סה\"כ תורים במערכת: {len(all_appointments)}")
    for appointment in all_appointments:
        print(f"  {appointment}")
    
    
    # ============================================================
    # בדיקה 5: עדכון תור
    # ============================================================
    print_separator("Test 5: UPDATE - Update first appointment status")
    
    # שולפים את התור, משנים את הסטטוס, ומעדכנים
    to_update = manager.get_appointment_by_id(1)
    to_update.status = "completed"
    to_update.notes = "הטיפול בוצע בהצלחה"
    
    success = manager.update_appointment(to_update)
    print(f"האם העדכון הצליח? {success}")
    
    # שולפים שוב לוודא שהערך אכן השתנה
    verified = manager.get_appointment_by_id(1)
    print(f"אחרי העדכון: {verified}")
    
    
    # ============================================================
    # בדיקה 6: מחיקת תור
    # ============================================================
    print_separator("Test 6: DELETE - Delete second appointment")
    
    success = manager.delete_appointment(2)
    print(f"האם המחיקה הצליחה? {success}")
    
    remaining = manager.get_all_appointments()
    print(f"תורים שנשארו: {len(remaining)}")
    
    
    # ============================================================
    # בדיקה 7: שליפת תור שנמחק - צריך להחזיר None
    # ============================================================
    print_separator("Test 7: GET BY ID - Fetch deleted (should be None)")
    
    deleted = manager.get_appointment_by_id(2)
    print(f"תור עם ID=2 (שנמחק): {deleted}")
    print(f"האם התוצאה היא None? {deleted is None}")
    
    
    # ============================================================
    # בדיקה 8: ניסיון למחוק תור לא קיים
    # ============================================================
    print_separator("Test 8: DELETE - Non-existent (should return False)")
    
    success = manager.delete_appointment(999)
    print(f"האם המחיקה הצליחה? {success}")
    print("(צפוי: False - כי אין תור עם ID=999)")

    # ============================================================
    # Test 9: JOIN - Appointments with client and treatment names
    # ============================================================
    print_separator("Test 9: JOIN - Show appointments with details")
    
    # שולפים את התורים דרך JOIN - מקבלים tuples עם שמות אמיתיים
    detailed_rows = manager.get_all_appointments_with_details()
    
    print(f"Total appointments with details: {len(detailed_rows)}\n")
    
    # כל שורה היא tuple: (id, client_name, treatment_name, date, time, status)
    for row in detailed_rows:
        appointment_id = row[0]
        client_name = row[1]
        treatment_name = row[2]
        date = row[3]
        time = row[4]
        status = row[5]
        
        print(f"  Appointment #{appointment_id}")
        print(f"    Client: {client_name}")
        print(f"    Treatment: {treatment_name}")
        print(f"    When: {date} at {time}")
        print(f"    Status: {status}\n")
    
    print("\n" + "=" * 60)
    print("  All AppointmentManager tests completed!")
    print("=" * 60 + "\n")


# הרצה - רק אם קוראים לקובץ ישירות
if __name__ == "__main__":
    run_tests()