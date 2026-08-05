# ============================================================
# main.py
# מערכת ניהול קליניקת לייזר - נקודת הכניסה הראשית
# מפעיל את התפריט האינטראקטיבי לניהול תורים, לקוחות,
# טיפולים, חשבוניות ולידים.
#
# הרצה:  python3 main.py
# ============================================================

from database import initialize_database

from entities.appointment import Appointment
from entities.client import Client
from entities.treatment import Treatment
from entities.invoice import Invoice
from entities.lead import Lead

from managers.appointment_manager import AppointmentManager
from managers.client_manager import ClientManager
from managers.treatment_manager import TreatmentManager
from managers.invoice_manager import InvoiceManager
from managers.lead_manager import LeadManager

from utils.display import (
    print_header, print_success, print_error, print_info, pause,
    ask_text, ask_number, ask_int, ask_choice, confirm,
    ask_name, ask_phone, ask_email, ask_date, ask_time,
)


# יוצרים מופע אחד מכל מנהל - משמשים בכל המערכת
appointment_manager = AppointmentManager()
client_manager = ClientManager()
treatment_manager = TreatmentManager()
invoice_manager = InvoiceManager()
lead_manager = LeadManager()


# ============================================================
# תפריט תורים
# ============================================================

def add_appointment():
    """מסך הוספת תור חדש - כולל בחירת לקוח, טיפול ובדיקת התנגשות"""
    print_header("הוספת תור חדש")

    # שלב 1: בחירת לקוח מתוך רשימה
    clients = client_manager.get_all_clients()

    if len(clients) == 0:
        print_error("אין לקוחות במערכת - יש להוסיף לקוח קודם")
        pause()
        return

    print("\nלקוחות במערכת:")
    for client in clients:
        print(f"  {client.client_id}. {client.full_name} - {client.phone}")

    client_id = ask_int("\nמזהה הלקוח")
    if client_id is None:
        return

    # מוודאים שהלקוח קיים
    selected_client = client_manager.get_client_by_id(client_id)
    if selected_client is None:
        print_error("הלקוח לא נמצא")
        pause()
        return

    # שלב 2: בחירת טיפול מהקטלוג
    treatments = treatment_manager.get_all_treatments()

    if len(treatments) == 0:
        print_error("הקטלוג ריק - יש לאתחל את קטלוג הטיפולים")
        pause()
        return

    print("\nקטלוג טיפולים:")
    for treatment in treatments:
        print(f"  {treatment.treatment_id}. {treatment.treatment_name} - "
              f"{treatment.price} שח - {treatment.duration_minutes} דקות")

    treatment_id = ask_int("\nמזהה הטיפול")
    if treatment_id is None:
        return

    selected_treatment = treatment_manager.get_treatment_by_id(treatment_id)
    if selected_treatment is None:
        print_error("הטיפול לא נמצא")
        pause()
        return

    # שלב 3: תאריך
    appointment_date = ask_date()
    if appointment_date is None:
        return

    # שלב 4: מציגים שעות פנויות לפני שמבקשים שעה
    available = appointment_manager.get_available_slots(
        appointment_date, treatment_id
    )

    if len(available) == 0:
        print_error("אין שעות פנויות בתאריך זה")
        pause()
        return

    print_info(f"שעות פנויות: {', '.join(available[:12])}")
    if len(available) > 12:
        print(f"    ועוד {len(available) - 12} שעות...")

    appointment_time = ask_time()
    if appointment_time is None:
        return

    # שלב 5: בדיקת התנגשות
    has_conflict, conflict_message = appointment_manager.check_conflict(
        appointment_date, appointment_time, treatment_id
    )

    if has_conflict:
        print_error(conflict_message)
        pause()
        return

    # שלב 6: הערות (רשות)
    notes = ask_text("הערות (רשות)", allow_empty=True)

    # שלב 7: יצירה ושמירה
    new_appointment = Appointment(
        client_id=client_id,
        treatment_id=treatment_id,
        appointment_date=appointment_date,
        appointment_time=appointment_time,
        notes=notes
    )

    result = appointment_manager.insert_appointment(new_appointment)

    if result is None:
        print_error(appointment_manager.last_error)
    else:
        print_success(
            f"נקבע תור #{result.appointment_id} עבור {selected_client.full_name} "
            f"בתאריך {appointment_date} בשעה {appointment_time}"
        )

    pause()


def show_appointments():
    """מציג את כל התורים עם שמות לקוחות וטיפולים"""
    print_header("רשימת תורים")

    rows = appointment_manager.get_all_appointments_with_details()

    if len(rows) == 0:
        print_info("אין תורים במערכת")
        pause()
        return

    print(f"\nסך הכל: {len(rows)} תורים\n")

    for row in rows:
        appointment_id = row[0]
        client_name = row[1]
        treatment_name = row[2]
        date = row[3]
        time = row[4]
        status = row[5]

        print(f"  תור #{appointment_id}")
        print(f"     לקוח:   {client_name}")
        print(f"     טיפול:  {treatment_name}")
        print(f"     מועד:   {date} בשעה {time}")
        print(f"     סטטוס:  {status}")
        print()

    pause()


def update_appointment_status():
    """עדכון סטטוס של תור קיים"""
    print_header("עדכון סטטוס תור")

    appointment_id = ask_int("מזהה התור")
    if appointment_id is None:
        return

    appointment = appointment_manager.get_appointment_by_id(appointment_id)

    if appointment is None:
        print_error("התור לא נמצא")
        pause()
        return

    print_info(f"סטטוס נוכחי: {appointment.status}")

    new_status = ask_choice(
        "בחר סטטוס חדש:",
        ["pending", "completed", "cancelled"]
    )

    if new_status is None:
        return

    appointment.status = new_status
    success = appointment_manager.update_appointment(appointment)

    if success:
        print_success(f"הסטטוס עודכן ל-{new_status}")
    else:
        print_error("העדכון נכשל")

    pause()


def delete_appointment():
    """מחיקת תור"""
    print_header("מחיקת תור")

    appointment_id = ask_int("מזהה התור למחיקה")
    if appointment_id is None:
        return

    appointment = appointment_manager.get_appointment_by_id(appointment_id)

    if appointment is None:
        print_error("התור לא נמצא")
        pause()
        return

    print_info(f"התור: {appointment}")

    if not confirm("האם למחוק את התור?"):
        print_info("המחיקה בוטלה")
        pause()
        return

    success = appointment_manager.delete_appointment(appointment_id)

    if success:
        print_success("התור נמחק")
    else:
        print_error("המחיקה נכשלה")

    pause()


def appointments_menu():
    """תת-התפריט של ניהול תורים"""
    while True:
        print_header("ניהול תורים")
        print("  1. הוספת תור חדש")
        print("  2. הצגת כל התורים")
        print("  3. עדכון סטטוס תור")
        print("  4. מחיקת תור")
        print("  0. חזרה לתפריט הראשי")

        choice = input("\nבחירה: ").strip()

        if choice == "1":
            add_appointment()
        elif choice == "2":
            show_appointments()
        elif choice == "3":
            update_appointment_status()
        elif choice == "4":
            delete_appointment()
        elif choice == "0":
            return
        else:
            print_error("בחירה לא תקינה")


# ============================================================
# תפריט לקוחות
# ============================================================

def add_client():
    """מסך הוספת לקוח חדש"""
    print_header("הוספת לקוח חדש")

    full_name = ask_name()
    if full_name is None:
        return

    phone = ask_phone()
    if phone is None:
        return

    email = ask_email()
    address = ask_text("כתובת (רשות)", allow_empty=True)

    new_client = Client(
        full_name=full_name,
        phone=phone,
        email=email,
        address=address
    )

    result = client_manager.insert_client(new_client)

    if result is None:
        print_error(client_manager.last_error)
    else:
        print_success(f"נוסף לקוח #{result.client_id} - {result.full_name}")

    pause()


def show_clients():
    """מציג את כל הלקוחות"""
    print_header("רשימת לקוחות")

    clients = client_manager.get_all_clients()

    if len(clients) == 0:
        print_info("אין לקוחות במערכת")
        pause()
        return

    print(f"\nסך הכל: {len(clients)} לקוחות\n")

    for client in clients:
        print(f"  {client}")

    pause()


def show_client_history():
    """מציג היסטוריית תורים וחשבוניות של לקוח"""
    print_header("היסטוריית לקוח")

    client_id = ask_int("מזהה הלקוח")
    if client_id is None:
        return

    client = client_manager.get_client_by_id(client_id)

    if client is None:
        print_error("הלקוח לא נמצא")
        pause()
        return

    print_info(f"לקוח: {client.full_name} | {client.phone}")

    # התורים של הלקוח
    all_appointments = appointment_manager.get_all_appointments()
    client_appointments = []

    for appointment in all_appointments:
        if appointment.client_id == client_id:
            client_appointments.append(appointment)

    print(f"\nתורים ({len(client_appointments)}):")
    if len(client_appointments) == 0:
        print("   אין תורים")
    else:
        for appointment in client_appointments:
            print(f"   {appointment}")

    # החשבוניות של הלקוח
    all_invoices = invoice_manager.get_all_invoices()
    client_invoices = []
    total_amount = 0

    for invoice in all_invoices:
        if invoice.client_id == client_id:
            client_invoices.append(invoice)
            total_amount = total_amount + invoice.amount

    print(f"\nחשבוניות ({len(client_invoices)}):")
    if len(client_invoices) == 0:
        print("   אין חשבוניות")
    else:
        for invoice in client_invoices:
            print(f"   {invoice}")
        print(f"\n   סך הכל: {total_amount} שח")

    pause()


def update_client():
    """עדכון פרטי לקוח"""
    print_header("עדכון פרטי לקוח")

    client_id = ask_int("מזהה הלקוח")
    if client_id is None:
        return

    client = client_manager.get_client_by_id(client_id)

    if client is None:
        print_error("הלקוח לא נמצא")
        pause()
        return

    print_info(f"פרטים נוכחיים: {client}")

    field = ask_choice(
        "איזה שדה לעדכן?",
        ["שם מלא", "טלפון", "אימייל", "כתובת"]
    )

    if field is None:
        return

    if field == "שם מלא":
        new_value = ask_name("שם מלא חדש")
        if new_value is not None:
            client.full_name = new_value

    elif field == "טלפון":
        new_value = ask_phone("טלפון חדש")
        if new_value is not None:
            client.phone = new_value

    elif field == "אימייל":
        new_value = ask_email("אימייל חדש")
        client.email = new_value

    elif field == "כתובת":
        new_value = ask_text("כתובת חדשה", allow_empty=True)
        client.address = new_value

    success = client_manager.update_client(client)

    if success:
        print_success("הפרטים עודכנו")
    else:
        print_error("העדכון נכשל")

    pause()


def delete_client():
    """מחיקת לקוח"""
    print_header("מחיקת לקוח")

    client_id = ask_int("מזהה הלקוח למחיקה")
    if client_id is None:
        return

    client = client_manager.get_client_by_id(client_id)

    if client is None:
        print_error("הלקוח לא נמצא")
        pause()
        return

    print_info(f"הלקוח: {client}")

    if not confirm("האם למחוק את הלקוח?"):
        print_info("המחיקה בוטלה")
        pause()
        return

    success = client_manager.delete_client(client_id)

    if success:
        print_success("הלקוח נמחק")
    else:
        print_error(client_manager.last_error)

    pause()


def clients_menu():
    """תת-התפריט של ניהול לקוחות"""
    while True:
        print_header("ניהול לקוחות")
        print("  1. הוספת לקוח חדש")
        print("  2. הצגת כל הלקוחות")
        print("  3. היסטוריית לקוח")
        print("  4. עדכון פרטי לקוח")
        print("  5. מחיקת לקוח")
        print("  0. חזרה לתפריט הראשי")

        choice = input("\nבחירה: ").strip()

        if choice == "1":
            add_client()
        elif choice == "2":
            show_clients()
        elif choice == "3":
            show_client_history()
        elif choice == "4":
            update_client()
        elif choice == "5":
            delete_client()
        elif choice == "0":
            return
        else:
            print_error("בחירה לא תקינה")


# ============================================================
# תפריט טיפולים
# ============================================================

def add_treatment():
    """הוספת טיפול לקטלוג"""
    print_header("הוספת טיפול לקטלוג")

    treatment_name = ask_text("שם הטיפול")
    if treatment_name is None:
        return

    print_info("ניתן להזין כמה איזורים מופרדים בפסיק, למשל: פנים, שפם, סנטר")
    body_area = ask_text("איזור/ים")
    if body_area is None:
        return

    price = ask_number("מחיר בשקלים", "המחיר")
    if price is None:
        return

    duration = ask_number("משך הטיפול בדקות", "משך הטיפול")
    if duration is None:
        return

    new_treatment = Treatment(
        treatment_name=treatment_name,
        body_area=body_area,
        price=price,
        duration_minutes=int(duration)
    )

    result = treatment_manager.insert_treatment(new_treatment)

    if result is None:
        print_error("ההוספה נכשלה")
    else:
        print_success(f"נוסף טיפול #{result.treatment_id} - {result.treatment_name}")

    pause()


def show_treatments():
    """מציג את קטלוג הטיפולים"""
    print_header("קטלוג טיפולים")

    treatments = treatment_manager.get_all_treatments()

    if len(treatments) == 0:
        print_info("הקטלוג ריק")
        pause()
        return

    print(f"\nסך הכל: {len(treatments)} טיפולים\n")

    for treatment in treatments:
        print(f"  {treatment}")

    pause()


def update_treatment():
    """עדכון טיפול קיים"""
    print_header("עדכון טיפול")

    treatment_id = ask_int("מזהה הטיפול")
    if treatment_id is None:
        return

    treatment = treatment_manager.get_treatment_by_id(treatment_id)

    if treatment is None:
        print_error("הטיפול לא נמצא")
        pause()
        return

    print_info(f"פרטים נוכחיים: {treatment}")

    field = ask_choice(
        "איזה שדה לעדכן?",
        ["שם הטיפול", "איזורים", "מחיר", "משך בדקות"]
    )

    if field is None:
        return

    if field == "שם הטיפול":
        new_value = ask_text("שם חדש")
        if new_value is not None:
            treatment.treatment_name = new_value

    elif field == "איזורים":
        print_info("ניתן להזין כמה איזורים מופרדים בפסיק")
        new_value = ask_text("איזורים חדשים")
        if new_value is not None:
            treatment.body_area = new_value

    elif field == "מחיר":
        new_value = ask_number("מחיר חדש", "המחיר")
        if new_value is not None:
            treatment.price = new_value

    elif field == "משך בדקות":
        new_value = ask_number("משך חדש", "משך הטיפול")
        if new_value is not None:
            treatment.duration_minutes = int(new_value)

    success = treatment_manager.update_treatment(treatment)

    if success:
        print_success("הטיפול עודכן")
    else:
        print_error("העדכון נכשל")

    pause()


def treatments_menu():
    """תת-התפריט של קטלוג הטיפולים"""
    while True:
        print_header("קטלוג טיפולים")
        print("  1. הצגת הקטלוג")
        print("  2. הוספת טיפול")
        print("  3. עדכון טיפול")
        print("  4. אתחול קטלוג ראשוני")
        print("  0. חזרה לתפריט הראשי")

        choice = input("\nבחירה: ").strip()

        if choice == "1":
            show_treatments()
        elif choice == "2":
            add_treatment()
        elif choice == "3":
            update_treatment()
        elif choice == "4":
            added = treatment_manager.seed_catalog()
            if added > 0:
                print_success(f"נוספו {added} טיפולים")
            pause()
        elif choice == "0":
            return
        else:
            print_error("בחירה לא תקינה")


# ============================================================
# תפריט חשבוניות
# ============================================================

def create_invoice():
    """הפקת חשבונית חדשה"""
    print_header("הפקת חשבונית")

    clients = client_manager.get_all_clients()

    if len(clients) == 0:
        print_error("אין לקוחות במערכת")
        pause()
        return

    print("\nלקוחות:")
    for client in clients:
        print(f"  {client.client_id}. {client.full_name}")

    client_id = ask_int("\nמזהה הלקוח")
    if client_id is None:
        return

    if client_manager.get_client_by_id(client_id) is None:
        print_error("הלקוח לא נמצא")
        pause()
        return

    amount = ask_number("סכום החשבונית", "הסכום")
    if amount is None:
        return

    invoice_date = ask_date("תאריך החשבונית (YYYY-MM-DD)")
    if invoice_date is None:
        return

    # קישור לתור - רשות
    appointment_id = None
    if confirm("לקשר את החשבונית לתור מסוים?"):
        appointment_id = ask_int("מזהה התור")

    new_invoice = Invoice(
        client_id=client_id,
        amount=amount,
        invoice_date=invoice_date,
        appointment_id=appointment_id
    )

    result = invoice_manager.insert_invoice(new_invoice)

    if result is None:
        print_error("הפקת החשבונית נכשלה")
    else:
        print_success(f"הופקה חשבונית {result.invoice_number} על סך {result.amount} שח")

    pause()


def show_invoices():
    """מציג חשבוניות"""
    print_header("רשימת חשבוניות")

    include_cancelled = confirm("להציג גם חשבוניות מבוטלות?")

    invoices = invoice_manager.get_all_invoices(include_cancelled=include_cancelled)

    if len(invoices) == 0:
        print_info("אין חשבוניות")
        pause()
        return

    total = 0
    for invoice in invoices:
        if not invoice.is_cancelled:
            total = total + invoice.amount

    print(f"\nסך הכל: {len(invoices)} חשבוניות\n")

    for invoice in invoices:
        print(f"  {invoice}")

    print(f"\n  סכום כולל (פעילות בלבד): {total} שח")

    pause()


def cancel_invoice_menu():
    """ביטול חשבונית"""
    print_header("ביטול חשבונית")

    print_info("לפי חוק לא ניתן למחוק חשבונית - רק לבטל אותה")

    invoice_id = ask_int("מזהה החשבונית")
    if invoice_id is None:
        return

    invoice = invoice_manager.get_invoice_by_id(invoice_id)

    if invoice is None:
        print_error("החשבונית לא נמצאה")
        pause()
        return

    print_info(f"החשבונית: {invoice}")

    if not confirm("האם לבטל את החשבונית?"):
        print_info("הביטול בוטל")
        pause()
        return

    success = invoice_manager.cancel_invoice(invoice_id)

    if not success:
        print_error("הביטול נכשל")

    pause()


def invoices_menu():
    """תת-התפריט של חשבוניות"""
    while True:
        print_header("ניהול חשבוניות")
        print("  1. הפקת חשבונית")
        print("  2. הצגת חשבוניות")
        print("  3. ביטול חשבונית")
        print("  4. שחזור חשבונית מבוטלת")
        print("  0. חזרה לתפריט הראשי")

        choice = input("\nבחירה: ").strip()

        if choice == "1":
            create_invoice()
        elif choice == "2":
            show_invoices()
        elif choice == "3":
            cancel_invoice_menu()
        elif choice == "4":
            invoice_id = ask_int("מזהה החשבונית לשחזור")
            if invoice_id is not None:
                invoice_manager.restore_invoice(invoice_id)
            pause()
        elif choice == "0":
            return
        else:
            print_error("בחירה לא תקינה")


# ============================================================
# תפריט לידים
# ============================================================

def add_lead():
    """הוספת ליד חדש"""
    print_header("הוספת ליד חדש")

    full_name = ask_name()
    if full_name is None:
        return

    phone = ask_phone()
    if phone is None:
        return

    source = ask_choice(
        "מקור הפנייה:",
        ["facebook", "instagram", "google", "referral", "walk_in"]
    )

    if source is None:
        return

    notes = ask_text("הערות (רשות)", allow_empty=True)

    new_lead = Lead(
        full_name=full_name,
        phone=phone,
        source=source,
        notes=notes
    )

    result = lead_manager.insert_lead(new_lead)

    if result is None:
        print_error("ההוספה נכשלה")
    else:
        print_success(f"נוסף ליד #{result.lead_id} - {result.full_name}")

    pause()


def show_leads():
    """מציג את כל הלידים"""
    print_header("רשימת לידים")

    leads = lead_manager.get_all_leads()

    if len(leads) == 0:
        print_info("אין לידים במערכת")
        pause()
        return

    # ספירה לפי סטטוס
    active_count = 0
    converted_count = 0

    for lead in leads:
        if lead.is_active():
            active_count = active_count + 1
        if lead.is_converted():
            converted_count = converted_count + 1

    print(f"\nסך הכל: {len(leads)} לידים")
    print(f"פעילים: {active_count} | הומרו ללקוחות: {converted_count}\n")

    for lead in leads:
        print(f"  {lead}")

    pause()


def update_lead_status():
    """עדכון סטטוס ליד"""
    print_header("עדכון סטטוס ליד")

    lead_id = ask_int("מזהה הליד")
    if lead_id is None:
        return

    lead = lead_manager.get_lead_by_id(lead_id)

    if lead is None:
        print_error("הליד לא נמצא")
        pause()
        return

    print_info(f"סטטוס נוכחי: {lead.status}")

    new_status = ask_choice(
        "סטטוס חדש:",
        ["new", "in_progress", "converted", "rejected"]
    )

    if new_status is None:
        return

    lead.status = new_status
    success = lead_manager.update_lead(lead)

    if success:
        print_success(f"הסטטוס עודכן ל-{new_status}")
    else:
        print_error("העדכון נכשל")

    pause()


def convert_lead():
    """המרת ליד ללקוח"""
    print_header("המרת ליד ללקוח")

    lead_id = ask_int("מזהה הליד להמרה")
    if lead_id is None:
        return

    lead = lead_manager.get_lead_by_id(lead_id)

    if lead is None:
        print_error("הליד לא נמצא")
        pause()
        return

    if lead.is_converted():
        print_error("הליד כבר הומר ללקוח בעבר")
        pause()
        return

    print_info(f"הליד: {lead}")

    # פרטים נוספים שלא נאספו בשלב הליד
    email = ask_email("אימייל הלקוח (רשות)")
    address = ask_text("כתובת (רשות)", allow_empty=True)

    new_client = lead_manager.convert_lead_to_client(
        lead_id=lead_id,
        email=email,
        address=address
    )

    if new_client is None:
        print_error("ההמרה נכשלה")
    else:
        print_success(f"הליד הומר ללקוח #{new_client.client_id}")

    pause()


def leads_menu():
    """תת-התפריט של ניהול לידים"""
    while True:
        print_header("ניהול לידים")
        print("  1. הוספת ליד חדש")
        print("  2. הצגת כל הלידים")
        print("  3. עדכון סטטוס ליד")
        print("  4. המרת ליד ללקוח")
        print("  0. חזרה לתפריט הראשי")

        choice = input("\nבחירה: ").strip()

        if choice == "1":
            add_lead()
        elif choice == "2":
            show_leads()
        elif choice == "3":
            update_lead_status()
        elif choice == "4":
            convert_lead()
        elif choice == "0":
            return
        else:
            print_error("בחירה לא תקינה")


# ============================================================
# התפריט הראשי
# ============================================================

def main_menu():
    """הלולאה הראשית של המערכת"""
    while True:
        print_header("מערכת ניהול קליניקת לייזר")
        print("  1. ניהול תורים")
        print("  2. ניהול לקוחות")
        print("  3. קטלוג טיפולים")
        print("  4. ניהול חשבוניות")
        print("  5. ניהול לידים")
        print("  0. יציאה")

        choice = input("\nבחירה: ").strip()

        if choice == "1":
            appointments_menu()
        elif choice == "2":
            clients_menu()
        elif choice == "3":
            treatments_menu()
        elif choice == "4":
            invoices_menu()
        elif choice == "5":
            leads_menu()
        elif choice == "0":
            print("\nלהתראות!\n")
            return
        else:
            print_error("בחירה לא תקינה")


def main():
    """
    נקודת הכניסה למערכת.
    מאתחל את בסיס הנתונים ומפעיל את התפריט.
    """
    print("\nמאתחל את המערכת...")
    initialize_database()

    # מוודא שיש קטלוג טיפולים - חיוני לקביעת תורים
    treatments = treatment_manager.get_all_treatments()
    if len(treatments) == 0:
        print("הקטלוג ריק - טוען קטלוג ראשוני...")
        treatment_manager.seed_catalog()

    main_menu()


if __name__ == "__main__":
    main()