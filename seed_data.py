# ============================================================
# seed_data.py
# יוצר נתוני דמו מלאים לכל הישויות במערכת.
#
# הרצה:  python3 seed_data.py
#
# הנתונים בנויים בכוונה כך שיאפשרו להריץ את כל תרחישי
# הבדיקה של פרויקט הסיום:
#   - שתי לקוחות בשם רותם, לבדיקת בקשת הבהרה
#   - לקוחה ללא אף תור
#   - תור ב-19.01.2027 בשעה 19:00, התרחיש המרכזי מהבריף
#
# הסקריפט בטוח להרצה חוזרת: הוא מדלג על רשומות שכבר קיימות.
# ============================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from database import initialize_database
from entities.client import Client
from entities.appointment import Appointment
from entities.invoice import Invoice
from entities.lead import Lead

from managers.client_manager import ClientManager
from managers.treatment_manager import TreatmentManager
from managers.appointment_manager import AppointmentManager
from managers.appointment_treatment_manager import AppointmentTreatmentManager
from managers.invoice_manager import InvoiceManager
from managers.lead_manager import LeadManager


# ============================================================
# נתוני הלקוחות
# שדה תעודת הזהות נשמר כטביעת אצבע בלבד, לא כמספר
# ============================================================

CLIENTS_DATA = [
    # (שם מלא, טלפון, מייל, כתובת, תעודת זהות)
    ("רותם מירון",   "0521234567", "rotem.miron@example.com",  "הרצל 15, תל אביב",   "123456782"),
    ("רותם כהן",     "0532345678", "rotem.cohen@example.com",  "ביאליק 8, רמת גן",   "987654325"),
    ("נועה לוי",     "0543456789", "noa.levi@example.com",     "אלנבי 42, תל אביב",  "111111118"),
    ("מאיה שפירא",   "0504567890", "maya.shapira@example.com", "סוקולוב 3, הרצליה",  "222222226"),
    ("יעל אברהמי",   "0525678901", "yael.a@example.com",       "ויצמן 20, כפר סבא",  "333333334"),
    # הלקוחה הזו נשארת בכוונה בלי אף תור, עבור תרחיש בדיקה 4
    ("שירה דהן",     "0546789012", "shira.dahan@example.com",  "הנשיא 7, נתניה",     "444444442"),
]


# ============================================================
# נתוני התורים
# התור הראשון הוא התרחיש המרכזי מהבריף
# ============================================================

APPOINTMENTS_DATA = [
    # (שם הלקוחה, שם הטיפול, תאריך, שעה, סטטוס, הערות)
    ("רותם מירון",  "רגליים מלא",  "2027-01-19", "19:00", "confirmed", "התרחיש המרכזי מהבריף"),
    ("רותם כהן",    "בית שחי",     "2027-01-22", "10:30", "confirmed", None),
    ("נועה לוי",    "פנים מלא",    "2027-02-03", "14:00", "pending",   "לקוחה חדשה"),
    ("מאיה שפירא",  "קו ביקיני",   "2027-02-10", "16:30", "confirmed", None),
    ("יעל אברהמי",  "חצי רגליים",  "2027-02-15", "11:00", "pending",   None),
    ("נועה לוי",    "שפם",         "2026-12-01", "09:00", "completed", "טיפול שהושלם"),
]


# ============================================================
# נתוני החשבוניות
# ============================================================

INVOICES_DATA = [
    # (שם הלקוחה, סכום, תאריך)
    ("נועה לוי",    80.0,  "2026-12-01"),
    ("רותם מירון",  400.0, "2026-11-15"),
    ("רותם כהן",    120.0, "2026-11-20"),
    ("מאיה שפירא",  150.0, "2026-10-05"),
    ("יעל אברהמי",  250.0, "2026-10-18"),
    ("נועה לוי",    250.0, "2026-09-30"),
]


# ============================================================
# נתוני הלידים
# ============================================================

LEADS_DATA = [
    # (שם מלא, טלפון, מקור, סטטוס, הערות)
    ("דנה אלמוג",    "0521112222", "instagram", "new",         "פנתה דרך סטורי"),
    ("ליאור בן דוד", "0532223333", "facebook",  "in_progress", "מעוניינת בחבילה"),
    ("תמר גולן",     "0543334444", "google",    "new",         None),
    ("אורית פרץ",    "0504445555", "referral",  "in_progress", "הופנתה על ידי נועה"),
    ("הילה נחום",    "0525556666", "walk_in",   "new",         "נכנסה מהרחוב"),
    ("סיון ברק",     "0546667777", "instagram", "converted",   "הפכה ללקוחה"),
]


def seed_clients(client_manager):
    """יוצר את הלקוחות ושומר להם תעודות זהות."""
    created = 0
    existing_names = {c.full_name for c in client_manager.get_all_clients()}

    for full_name, phone, email, address, national_id in CLIENTS_DATA:
        if full_name in existing_names:
            continue

        new_client = Client(full_name=full_name, phone=phone,
                            email=email, address=address)
        result = client_manager.insert_client(new_client)

        if result is None:
            print(f"  skipped client {full_name}: {client_manager.last_error}")
            continue

        # שמירת תעודת הזהות מתבצעת בנפרד, כטביעת אצבע
        client_manager.set_national_id(result.client_id, national_id)
        created += 1

    return created


def seed_appointments(client_manager, treatment_manager,
                      appointment_manager, appointment_treatment_manager):
    """יוצר את התורים ומקשר אותם לטיפולים."""
    created = 0

    clients_by_name = {c.full_name: c for c in client_manager.get_all_clients()}
    treatments_by_name = {t.treatment_name: t for t in treatment_manager.get_all_treatments()}

    existing = {
        (a.client_id, a.appointment_date, a.appointment_time)
        for a in appointment_manager.get_all_appointments()
    }

    for client_name, treatment_name, date, time, status, notes in APPOINTMENTS_DATA:
        client = clients_by_name.get(client_name)
        treatment = treatments_by_name.get(treatment_name)

        if client is None or treatment is None:
            print(f"  skipped appointment for {client_name}: missing client or treatment")
            continue

        if (client.client_id, date, time) in existing:
            continue

        new_appointment = Appointment(
            client_id=client.client_id,
            treatment_id=treatment.treatment_id,
            appointment_date=date,
            appointment_time=time,
            status=status,
            notes=notes,
        )

        result = appointment_manager.insert_appointment(new_appointment)
        if result is None:
            print(f"  skipped appointment for {client_name}")
            continue

        appointment_treatment_manager.set_treatments_for_appointment(
            result.appointment_id, [treatment.treatment_id]
        )
        created += 1

    return created


def seed_invoices(client_manager, invoice_manager):
    """יוצר את החשבוניות."""
    created = 0

    clients_by_name = {c.full_name: c for c in client_manager.get_all_clients()}
    existing_count = len(invoice_manager.get_all_invoices(include_cancelled=True))

    if existing_count >= len(INVOICES_DATA):
        return 0

    for client_name, amount, invoice_date in INVOICES_DATA:
        client = clients_by_name.get(client_name)
        if client is None:
            continue

        new_invoice = Invoice(
            client_id=client.client_id,
            amount=amount,
            invoice_date=invoice_date,
        )

        result = invoice_manager.insert_invoice(new_invoice)
        if result is not None:
            created += 1

    return created


def seed_leads(lead_manager):
    """יוצר את הלידים."""
    created = 0
    existing_names = {lead.full_name for lead in lead_manager.get_all_leads()}

    for full_name, phone, source, status, notes in LEADS_DATA:
        if full_name in existing_names:
            continue

        new_lead = Lead(full_name=full_name, phone=phone,
                        source=source, notes=notes)
        result = lead_manager.insert_lead(new_lead)

        if result is None:
            continue

        # הסטטוס מוגדר בנפרד, כי בבנייה הוא תמיד מתחיל כחדש
        if status != "new":
            result.status = status
            lead_manager.update_lead(result)

        created += 1

    return created


def main():
    """מריץ את כל שלבי יצירת הנתונים לפי סדר התלויות."""
        # מנגנון בטיחות: הסקריפט הזה יוצר נתוני דמו בלבד ואסור
    # שירוץ על שרת פרודקשן עם נתוני לקוחות אמיתיים
    from config import Config
    if Config.IS_PRODUCTION:
        print("ERROR: seed_data.py must never run in production.")
        print("This script creates demo records with fake identity numbers.")
        return
    print("Initializing database...")
    initialize_database()

    client_manager = ClientManager()
    treatment_manager = TreatmentManager()
    appointment_manager = AppointmentManager()
    appointment_treatment_manager = AppointmentTreatmentManager()
    invoice_manager = InvoiceManager()
    lead_manager = LeadManager()

    appointment_treatment_manager.ensure_table()

    # קטלוג הטיפולים חייב להתקיים לפני יצירת תורים
    if len(treatment_manager.get_all_treatments()) == 0:
        added = treatment_manager.seed_catalog()
        print(f"Treatments seeded: {added}")

    print(f"Clients created:     {seed_clients(client_manager)}")
    print(f"Appointments created:{seed_appointments(client_manager, treatment_manager, appointment_manager, appointment_treatment_manager)}")
    print(f"Invoices created:    {seed_invoices(client_manager, invoice_manager)}")
    print(f"Leads created:       {seed_leads(lead_manager)}")

    print("\n--- Final counts ---")
    print(f"clients:      {len(client_manager.get_all_clients())}")
    print(f"treatments:   {len(treatment_manager.get_all_treatments())}")
    print(f"appointments: {len(appointment_manager.get_all_appointments())}")
    print(f"invoices:     {len(invoice_manager.get_all_invoices(include_cancelled=True))}")
    print(f"leads:        {len(lead_manager.get_all_leads())}")


if __name__ == "__main__":
    main()