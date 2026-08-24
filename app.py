# ============================================================
# app.py
# שרת ה-Web של מערכת ניהול קליניקת הלייזר.
#
# תפקיד הקובץ: לחשוף REST API (JSON) שמאפשר לממשק ה-Web
# (templates/index.html + static/app.js) לדבר עם המערכת הקיימת.
#
# חשוב: הקובץ הזה הוא רק "מעטפת" - הוא כמעט ולא מכיל SQL,
# ולא נוגע בבסיס הנתונים ישירות. כל פעולה עוברת דרך אחד
# מ-5 ה-Managers הקיימים (בדיוק כמו ש-main.py עושה).
# main.py ממשיך לעבוד בדיוק כמו קודם - הקובץ הזה לא נוגע בו.
#
# יוצא מן הכלל אחד: AppointmentTreatmentManager (קובץ חדש, ראו
# managers/appointment_treatment_manager.py) - מנהל "טיפול מרוכב"
# (כמה טיפולים לאותו תור), עם טבלת קישור משלו. זו החריגה היחידה
# שכן כוללת SQL חדש בפרויקט, באישור מפורש - כי אי אפשר לחשב
# מחיר/משך כולל שמשפיע נכון על הלוז בלי טבלת קישור אמיתית.
#
# הרצה:  python3 app.py
# ============================================================

import sqlite3
from datetime import datetime

from flask import Flask, jsonify, request

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
from managers.appointment_treatment_manager import AppointmentTreatmentManager

from utils.validators import (
    validate_name,
    validate_phone,
    validate_email,
    validate_date,
    validate_time,
    validate_positive_number,
    validate_appointment_status,
    validate_lead_status,
)
from utils.db_errors import translate_db_error


# ============================================================
# אתחול האפליקציה והמנהלים
# ============================================================

app = Flask(__name__)

# מונע escaping של תווים עבריים ל-\uXXXX בתגובות JSON - כך שגם
# בבדיקה ידנית (curl / כלי פיתוח בדפדפן) הטקסט קריא כרגיל
app.json.ensure_ascii = False

# ---- חיבור קבוצות ה-routes (Blueprints) ----
from api.leads_api import leads_bp
app.register_blueprint(leads_bp)

# בדיוק כמו ב-main.py: מופע אחד מכל מנהל, משותף לכל הבקשות
appointment_manager = AppointmentManager()
client_manager = ClientManager()
treatment_manager = TreatmentManager()
invoice_manager = InvoiceManager()
lead_manager = LeadManager()
appointment_treatment_manager = AppointmentTreatmentManager()

# מקורות פנייה חוקיים לליד - אותה רשימה שמוצגת בתפריט ה-CLI
# (main.py, add_lead) - אין ולידטור ייעודי בקובץ validators.py, לכן
# הרשימה מוגדרת כאן, בשכבת ה-API בלבד.
VALID_LEAD_SOURCES = ["facebook", "instagram", "google", "referral", "walk_in"]


# ============================================================
# פונקציות עזר כלליות
# ============================================================

def json_error(message, status_code=400, field=None):
    """
    בונה תגובת שגיאה אחידה בפורמט JSON.
    כל השגיאות במערכת (ולידציה, לא נמצא, התנגשות...) עוברות דרך כאן
    כדי שהצד לקוח (JS) תמיד ידע לצפות לאותו מבנה: {"error": "..."}
    """
    body = {"error": message}
    if field is not None:
        body["field"] = field
    return jsonify(body), status_code


def run_db_operation(operation, context):
    """
    מריץ פעולת DB שעלולה לזרוק שגיאת SQLite (למשל הפרת מפתח זר),
    ומתרגם את השגיאה לעברית באמצעות translate_db_error הקיים.

    זה נחוץ כי חלק מהמנהלים (למשל TreatmentManager, LeadManager)
    לא עוטפים את עצמם ב-try/except כמו ClientManager - אז שכבת
    ה-API היא זו שדואגת שהשרת לא יקרוס משגיאת DB לא צפויה.

    operation - פונקציה ללא פרמטרים שמבצעת את הפעולה (למשל lambda)
    context   - תיאור קצר לעברית, למשל "הוספת טיפול"

    מחזיר (result, error_message). אם error_message אינו None -
    הפעולה נכשלה ויש להציג אותו למשתמש.
    """
    try:
        result = operation()
        return result, None
    except sqlite3.Error as error:
        return None, translate_db_error(error, context)


# ---- טיפול מרוכב (כמה טיפולים לאותו תור) - פונקציות עזר ----

def parse_treatment_ids_from_json(data):
    """
    מפרש רשימת מזהי טיפולים מגוף בקשת JSON. תומך גם בטופס החדש
    (treatment_ids - רשימה, לטיפול מרוכב) וגם בטופס הישן
    (treatment_id - יחיד, לתאימות לאחור). מחזיר רשימת int, או
    None אם לא נשלח כלום.
    """
    treatment_ids = data.get("treatment_ids")
    if treatment_ids:
        return [int(t) for t in treatment_ids]

    treatment_id = data.get("treatment_id")
    if treatment_id is not None:
        return [int(treatment_id)]

    return None


def parse_treatment_ids_from_args(args):
    """גרסה של הפונקציה הנ"ל לפרמטרים ב-query string (בקשות GET)"""
    treatment_ids_param = args.get("treatment_ids", "")
    if treatment_ids_param:
        parts = [t.strip() for t in treatment_ids_param.split(",") if t.strip()]
        if parts and all(t.isdigit() for t in parts):
            return [int(t) for t in parts]
        return None

    treatment_id_param = args.get("treatment_id", "")
    if treatment_id_param.isdigit():
        return [int(treatment_id_param)]

    return None


def combo_fields_for_appointment(appointment_id, fallback_treatment_id):
    """
    שדות "טיפול מרוכב" משותפים לתגובות API של תור: רשימת מזהי
    הטיפולים, שמותיהם, ומחיר/משך כולל (מחושבים דרך
    AppointmentTreatmentManager - ראו שם את ההסבר המלא).
    fallback_treatment_id משמש לתורים "רגילים" בלי רשומות בטבלת
    הקישור (למשל תורים שנוצרו דרך main.py).
    """
    treatments = appointment_treatment_manager.get_treatments_for_appointment(
        appointment_id, fallback_treatment_id
    )
    return {
        "treatment_ids": [t.treatment_id for t in treatments],
        "treatment_names": [t.treatment_name for t in treatments],
        "total_price": sum(t.price for t in treatments),
        "total_duration_minutes": sum(t.duration_minutes for t in treatments),
    }


# ---- המרת אובייקטי Entity למילונים (dict) לצורך JSON ----
# כל ישות מקבלת פונקציית המרה משלה, כי לכל אחת שדות שונים.

def appointment_to_dict(appointment):
    result = {
        "appointment_id": appointment.appointment_id,
        "client_id": appointment.client_id,
        "treatment_id": appointment.treatment_id,
        "appointment_date": appointment.appointment_date,
        "appointment_time": appointment.appointment_time,
        "status": appointment.status,
        "notes": appointment.notes,
    }
    result.update(combo_fields_for_appointment(appointment.appointment_id, appointment.treatment_id))
    return result


def appointment_row_to_dict(row):
    """
    ממיר שורת תוצאה מ-get_all_appointments_with_details (tuple)
    למילון קריא. סדר העמודות בשאילתה:
    (appointment_id, client_name, treatment_name, date, time, status)
    """
    return {
        "appointment_id": row[0],
        "client_name": row[1],
        "treatment_name": row[2],
        "appointment_date": row[3],
        "appointment_time": row[4],
        "status": row[5],
    }


def client_to_dict(client):
    return {
        "client_id": client.client_id,
        "full_name": client.full_name,
        "phone": client.phone,
        "email": client.email,
        "address": client.address,
    }


def treatment_to_dict(treatment):
    return {
        "treatment_id": treatment.treatment_id,
        "treatment_name": treatment.treatment_name,
        "body_area": treatment.body_area,
        "price": treatment.price,
        "duration_minutes": treatment.duration_minutes,
    }


def invoice_to_dict(invoice):
    return {
        "invoice_id": invoice.invoice_id,
        "invoice_number": invoice.invoice_number,
        "client_id": invoice.client_id,
        "appointment_id": invoice.appointment_id,
        "amount": invoice.amount,
        "invoice_date": invoice.invoice_date,
        "is_cancelled": bool(invoice.is_cancelled),
        "cancelled_at": invoice.cancelled_at,
    }


def lead_to_dict(lead):
    return {
        "lead_id": lead.lead_id,
        "full_name": lead.full_name,
        "phone": lead.phone,
        "source": lead.source,
        "status": lead.status,
        "notes": lead.notes,
    }


@app.after_request
def add_no_cache_headers(response):
    """
    מונע מהדפדפן לשמור תשובות API בזיכרון מטמון.
    חשוב באפליקציית ניהול - תמיד רוצים נתונים עדכניים.
    """
    response.headers["Cache-Control"] = "no-store"
    return response


# ============================================================
# הגשת עמוד הבית (ה-SPA)
# ============================================================

@app.route("/")
def index():
    """מגיש את עמוד ה-HTML הראשי. Flask מחפש אותו אוטומטית ב-templates/"""
    from flask import render_template
    return render_template("index.html")


# ============================================================
# דשבורד - נתונים מסוכמים למסך הראשי
# ============================================================

@app.route("/api/dashboard")
def get_dashboard():
    """
    מרכיב תמונת מצב יומית: תורים היום, מספר לקוחות, הכנסות החודש,
    ולידים פתוחים. כל החישוב נעשה כאן בפייתון, מעל הנתונים
    שמוחזרים ע"י ה-Managers הקיימים - בלי אף שאילתת SQL חדשה.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    current_month_prefix = datetime.now().strftime("%Y-%m")

    # תורים של היום - מסננים מתוך הרשימה המלאה עם הפרטים
    all_rows = appointment_manager.get_all_appointments_with_details()
    today_rows = [row for row in all_rows if row[3] == today]

    today_appointments = []
    for row in today_rows:
        appointment_id = row[0]
        appointment = appointment_manager.get_appointment_by_id(appointment_id)
        fallback_treatment_id = appointment.treatment_id if appointment else None
        combo = combo_fields_for_appointment(appointment_id, fallback_treatment_id)

        item = appointment_row_to_dict(row)
        item["treatment_name"] = ", ".join(combo["treatment_names"]) or item["treatment_name"]
        item.update(combo)
        today_appointments.append(item)

    # מספר לקוחות
    clients_count = len(client_manager.get_all_clients())

    # הכנסות החודש - סכום חשבוניות פעילות (לא מבוטלות) שתאריכן בחודש הנוכחי
    active_invoices = invoice_manager.get_all_invoices(include_cancelled=False)
    month_revenue = sum(
        invoice.amount for invoice in active_invoices
        if invoice.invoice_date.startswith(current_month_prefix)
    )

    # לידים פתוחים - סטטוס new או in_progress (is_active הקיים בישות Lead)
    all_leads = lead_manager.get_all_leads()
    open_leads = sum(1 for lead in all_leads if lead.is_active())

    return jsonify({
        "today_appointments": today_appointments,
        "clients_count": clients_count,
        "month_revenue": month_revenue,
        "open_leads": open_leads,
    })


# ============================================================
# API - תורים
# ============================================================

@app.route("/api/appointments", methods=["GET"])
def get_appointments():
    """
    מחזיר את כל התורים, כולל שם לקוח ושמות כל הטיפולים (יחיד או
    מרוכב) ומחיר/משך כולל. שם הלקוח מגיע מה-JOIN הקיים במנהל;
    רשימת הטיפולים המלאה מגיעה מ-AppointmentTreatmentManager.
    """
    rows = appointment_manager.get_all_appointments_with_details()

    result = []
    for row in rows:
        appointment_id = row[0]
        appointment = appointment_manager.get_appointment_by_id(appointment_id)
        fallback_treatment_id = appointment.treatment_id if appointment else None
        combo = combo_fields_for_appointment(appointment_id, fallback_treatment_id)

        item = appointment_row_to_dict(row)
        # "שם הטיפול" בטבלה מציג את כל הטיפולים המקושרים, לא רק את הראשי
        item["treatment_name"] = ", ".join(combo["treatment_names"]) or item["treatment_name"]
        item.update(combo)
        result.append(item)

    return jsonify(result)


@app.route("/api/appointments/<int:appointment_id>", methods=["GET"])
def get_appointment(appointment_id):
    """
    מחזיר תור בודד עם השדות הגולמיים (client_id, treatment_id, notes...).
    נחוץ לטופס העריכה - רשימת get_appointments מחזירה רק שמות תצוגה
    (JOIN), לא מזהים - וללא זה אי אפשר למלא מראש את ה-select-ים בטופס.
    """
    appointment = appointment_manager.get_appointment_by_id(appointment_id)
    if appointment is None:
        return json_error("התור לא נמצא", status_code=404)
    return jsonify(appointment_to_dict(appointment))


@app.route("/api/appointments/available-slots", methods=["GET"])
def get_available_slots():
    """
    מחזיר שעות פנויות ביום נתון עבור טיפול אחד (?treatment_id=5)
    או טיפול מרוכב (?treatment_ids=5,8,2).

    תמיד משתמשים ב-AppointmentTreatmentManager (גם לטיפול יחיד!) -
    כי הוא היחיד שיודע לחשב את משך הזמן ה*אמיתי* של תורים קיימים
    אחרים באותו יום, כולל אם גם הם עצמם טיפול מרוכב. שימוש ב-
    AppointmentManager.get_available_slots הרגיל היה "מתעלם"
    מהמשך הכולל של תורים מרוכבים קיימים ומציע שעות שלמעשה תפוסות.
    """
    appointment_date = request.args.get("date", "")

    is_valid, error_message = validate_date(appointment_date)
    if not is_valid:
        return json_error(error_message, field="date")

    treatment_ids = parse_treatment_ids_from_args(request.args)
    if not treatment_ids:
        return json_error("יש לבחור טיפול אחד לפחות", field="treatment_id")

    slots = appointment_treatment_manager.get_combo_available_slots(appointment_date, treatment_ids)
    return jsonify({"available_slots": slots})


@app.route("/api/appointments/check-conflict", methods=["GET"])
def check_appointment_conflict():
    """
    בודק התנגשות בזמן-אמת - טיפול יחיד או מרוכב, ותמיד מול משך
    הזמן ה*אמיתי* של תורים קיימים (ראו הערה ב-get_available_slots
    לעיל). בלי לשמור עדיין את התור.
    """
    appointment_date = request.args.get("date", "")
    appointment_time = request.args.get("time", "")
    exclude_id = request.args.get("exclude_appointment_id")

    treatment_ids = parse_treatment_ids_from_args(request.args)
    if not treatment_ids:
        return json_error("יש לבחור טיפול אחד לפחות", field="treatment_id")

    exclude_appointment_id = int(exclude_id) if exclude_id and exclude_id.isdigit() else None

    has_conflict, message = appointment_treatment_manager.check_combo_conflict(
        appointment_date, appointment_time, treatment_ids,
        exclude_appointment_id=exclude_appointment_id
    )
    return jsonify({"has_conflict": has_conflict, "message": message})


@app.route("/api/appointments", methods=["POST"])
def create_appointment():
    """
    קובע תור חדש - עם טיפול אחד או כמה יחד (טיפול מרוכב, ראו
    managers/appointment_treatment_manager.py). שלבי הבדיקה:
    לקוח קיים -> כל הטיפולים קיימים -> תאריך תקין -> שעה תקינה ->
    אין התנגשות (לפי משך הזמן הכולל) -> רק אז שומרים.
    """
    data = request.get_json(silent=True) or {}

    client_id = data.get("client_id")
    appointment_date = data.get("appointment_date", "")
    appointment_time = data.get("appointment_time", "")
    notes = data.get("notes")
    treatment_ids = parse_treatment_ids_from_json(data)

    # בדיקה שהלקוח קיים
    if client_id is None or client_manager.get_client_by_id(client_id) is None:
        return json_error("לקוח לא נמצא", field="client_id")

    # בדיקה שנבחר לפחות טיפול אחד, ושכל טיפול שנבחר קיים באמת
    if not treatment_ids:
        return json_error("יש לבחור טיפול אחד לפחות", field="treatment_id")

    for treatment_id in treatment_ids:
        if treatment_manager.get_treatment_by_id(treatment_id) is None:
            return json_error("אחד הטיפולים שנבחרו לא נמצא", field="treatment_id")

    is_valid, error_message = validate_date(appointment_date)
    if not is_valid:
        return json_error(error_message, field="appointment_date")

    is_valid, error_message = validate_time(appointment_time)
    if not is_valid:
        return json_error(error_message, field="appointment_time")

    # בדיקת התנגשות - תמיד מול AppointmentTreatmentManager, גם
    # לטיפול יחיד! הוא היחיד שיודע לחשב נכון את משך הזמן האמיתי
    # של תורים קיימים אחרים (כולל אם הם עצמם טיפול מרוכב) - ראו
    # הערה מפורטת ב-get_available_slots למעלה.
    has_conflict, conflict_message = appointment_treatment_manager.check_combo_conflict(
        appointment_date, appointment_time, treatment_ids
    )
    if has_conflict:
        return json_error(conflict_message, status_code=409)

    # טבלת appointments המקורית שומרת treatment_id יחיד - הטיפול
    # ה"ראשי" הוא הראשון שנבחר. הרשימה המלאה נשמרת בהמשך בטבלת הקישור
    new_appointment = Appointment(
        client_id=client_id,
        treatment_id=treatment_ids[0],
        appointment_date=appointment_date,
        appointment_time=appointment_time,
        notes=notes,
    )

    result, db_error = run_db_operation(
        lambda: appointment_manager.insert_appointment(new_appointment),
        "הוספת תור"
    )
    if db_error:
        return json_error(db_error, status_code=409)

    appointment_treatment_manager.set_treatments_for_appointment(
        result.appointment_id, treatment_ids
    )

    return jsonify(appointment_to_dict(result)), 201


@app.route("/api/appointments/<int:appointment_id>", methods=["PUT"])
def update_appointment(appointment_id):
    """
    מעדכן תור קיים - כולל שינוי סטטוס, וכולל שינוי רשימת הטיפולים
    (הוספה/הסרה מטיפול מרוכב). אם משנים תאריך/שעה/טיפולים -
    בודקים התנגשות מחדש, תוך התעלמות מהתור הנוכחי עצמו.
    """
    existing = appointment_manager.get_appointment_by_id(appointment_id)
    if existing is None:
        return json_error("התור לא נמצא", status_code=404)

    data = request.get_json(silent=True) or {}

    # כל שדה שלא נשלח - נשאר כפי שהיה
    client_id = data.get("client_id", existing.client_id)
    appointment_date = data.get("appointment_date", existing.appointment_date)
    appointment_time = data.get("appointment_time", existing.appointment_time)
    status = data.get("status", existing.status)
    notes = data.get("notes", existing.notes)

    # אם לא נשלחה רשימת טיפולים חדשה - משתמשים ברשימה הקיימת של התור
    treatment_ids = parse_treatment_ids_from_json(data)
    if not treatment_ids:
        treatment_ids = appointment_treatment_manager.get_treatment_ids_for_appointment(appointment_id)
        if not treatment_ids:
            treatment_ids = [existing.treatment_id]

    if client_manager.get_client_by_id(client_id) is None:
        return json_error("לקוח לא נמצא", field="client_id")

    for treatment_id in treatment_ids:
        if treatment_manager.get_treatment_by_id(treatment_id) is None:
            return json_error("אחד הטיפולים שנבחרו לא נמצא", field="treatment_id")

    is_valid, error_message = validate_date(appointment_date)
    if not is_valid:
        return json_error(error_message, field="appointment_date")

    is_valid, error_message = validate_time(appointment_time)
    if not is_valid:
        return json_error(error_message, field="appointment_time")

    is_valid, error_message = validate_appointment_status(status)
    if not is_valid:
        return json_error(error_message, field="status")

    # תמיד מול AppointmentTreatmentManager - ראו הערה ב-create_appointment
    has_conflict, conflict_message = appointment_treatment_manager.check_combo_conflict(
        appointment_date, appointment_time, treatment_ids,
        exclude_appointment_id=appointment_id
    )
    if has_conflict:
        return json_error(conflict_message, status_code=409)

    existing.client_id = client_id
    existing.treatment_id = treatment_ids[0]
    existing.appointment_date = appointment_date
    existing.appointment_time = appointment_time
    existing.status = status
    existing.notes = notes

    success, db_error = run_db_operation(
        lambda: appointment_manager.update_appointment(existing),
        "עדכון תור"
    )
    if db_error:
        return json_error(db_error, status_code=409)
    if not success:
        return json_error("העדכון נכשל", status_code=404)

    appointment_treatment_manager.set_treatments_for_appointment(appointment_id, treatment_ids)

    return jsonify(appointment_to_dict(existing))


@app.route("/api/appointments/<int:appointment_id>", methods=["DELETE"])
def delete_appointment(appointment_id):
    """מוחק תור. שים לב - זו מחיקה אמיתית (לא כמו חשבוניות)."""
    success = appointment_manager.delete_appointment(appointment_id)
    if not success:
        return json_error("התור לא נמצא", status_code=404)
    return jsonify({"success": True})


# ============================================================
# API - לקוחות
# ============================================================

@app.route("/api/clients", methods=["GET"])
def get_clients():
    clients = client_manager.get_all_clients()
    return jsonify([client_to_dict(client) for client in clients])


@app.route("/api/clients/<int:client_id>", methods=["GET"])
def get_client(client_id):
    client = client_manager.get_client_by_id(client_id)
    if client is None:
        return json_error("הלקוח לא נמצא", status_code=404)
    return jsonify(client_to_dict(client))


@app.route("/api/clients/<int:client_id>/history", methods=["GET"])
def get_client_history(client_id):
    """
    מחזיר את היסטוריית התורים והחשבוניות של לקוח - בדיוק כמו
    show_client_history ב-main.py: מסננים בפייתון מתוך הרשימות
    המלאות, בלי לכתוב שאילתה חדשה.
    """
    client = client_manager.get_client_by_id(client_id)
    if client is None:
        return json_error("הלקוח לא נמצא", status_code=404)

    # תורים של הלקוח - appointment_to_dict כבר מעשיר עם רשימת
    # שמות הטיפולים המלאה (טיפול יחיד או מרוכב) ומחיר/משך כולל
    all_appointments = appointment_manager.get_all_appointments()
    client_appointments = []
    for appointment in all_appointments:
        if appointment.client_id == client_id:
            item = appointment_to_dict(appointment)
            item["treatment_name"] = ", ".join(item["treatment_names"]) or None
            client_appointments.append(item)

    # חשבוניות של הלקוח (כולל מבוטלות - לתצוגה מלאה בהיסטוריה)
    all_invoices = invoice_manager.get_all_invoices(include_cancelled=True)
    client_invoices = [
        invoice_to_dict(invoice) for invoice in all_invoices
        if invoice.client_id == client_id
    ]
    total_active_amount = sum(
        invoice.amount for invoice in all_invoices
        if invoice.client_id == client_id and not invoice.is_cancelled
    )

    return jsonify({
        "client": client_to_dict(client),
        "appointments": client_appointments,
        "invoices": client_invoices,
        "total_active_amount": total_active_amount,
    })


@app.route("/api/clients", methods=["POST"])
def create_client():
    data = request.get_json(silent=True) or {}

    full_name = data.get("full_name", "")
    phone = data.get("phone", "")
    email = data.get("email")
    address = data.get("address")

    is_valid, error_message = validate_name(full_name)
    if not is_valid:
        return json_error(error_message, field="full_name")

    is_valid, error_message = validate_phone(phone)
    if not is_valid:
        return json_error(error_message, field="phone")

    is_valid, error_message = validate_email(email)
    if not is_valid:
        return json_error(error_message, field="email")

    new_client = Client(full_name=full_name.strip(), phone=phone.strip(),
                         email=email, address=address)

    result = client_manager.insert_client(new_client)
    if result is None:
        # ClientManager שומר את הסיבה המדויקת ב-last_error
        return json_error(client_manager.last_error, status_code=409)

    return jsonify(client_to_dict(result)), 201


@app.route("/api/clients/<int:client_id>", methods=["PUT"])
def update_client(client_id):
    existing = client_manager.get_client_by_id(client_id)
    if existing is None:
        return json_error("הלקוח לא נמצא", status_code=404)

    data = request.get_json(silent=True) or {}

    full_name = data.get("full_name", existing.full_name)
    phone = data.get("phone", existing.phone)
    email = data.get("email", existing.email)
    address = data.get("address", existing.address)

    is_valid, error_message = validate_name(full_name)
    if not is_valid:
        return json_error(error_message, field="full_name")

    is_valid, error_message = validate_phone(phone)
    if not is_valid:
        return json_error(error_message, field="phone")

    is_valid, error_message = validate_email(email)
    if not is_valid:
        return json_error(error_message, field="email")

    existing.full_name = full_name.strip()
    existing.phone = phone.strip()
    existing.email = email
    existing.address = address

    success, db_error = run_db_operation(
        lambda: client_manager.update_client(existing),
        "עדכון לקוח"
    )
    if db_error:
        return json_error(db_error, status_code=409)
    if not success:
        return json_error("העדכון נכשל", status_code=404)

    return jsonify(client_to_dict(existing))


@app.route("/api/clients/<int:client_id>", methods=["DELETE"])
def delete_client(client_id):
    """
    מוחק לקוח. אם יש לו תורים/חשבוניות מקושרים - ClientManager
    יתפוס את שגיאת ה-FK ויסביר בעברית דרך last_error.
    """
    success = client_manager.delete_client(client_id)
    if not success:
        status_code = 404 if "לא נמצא" in (client_manager.last_error or "") else 409
        return json_error(client_manager.last_error, status_code=status_code)
    return jsonify({"success": True})


# ============================================================
# API - טיפולים
# ============================================================

def _validate_treatment_fields(treatment_name, body_area, price, duration_minutes):
    """
    ולידציה של שדות טיפול. אין ולידטור ייעודי לשם טיפול/איזור
    ב-utils/validators.py (validate_name מיועד לשמות אנשים ואוסר
    ספרות) - לכן נבדק כאן רק שהשדה לא ריק, ברוח שאר הוולידטורים
    שמחזירים (is_valid, error_message).
    """
    if not treatment_name or not treatment_name.strip():
        return False, "שם הטיפול לא יכול להיות ריק", "treatment_name"

    if not body_area or not body_area.strip():
        return False, "יש להזין לפחות איזור אחד", "body_area"

    is_valid, error_message = validate_positive_number(price, "המחיר")
    if not is_valid:
        return False, error_message, "price"

    is_valid, error_message = validate_positive_number(duration_minutes, "משך הטיפול")
    if not is_valid:
        return False, error_message, "duration_minutes"

    return True, None, None


@app.route("/api/treatments", methods=["GET"])
def get_treatments():
    treatments = treatment_manager.get_all_treatments()
    return jsonify([treatment_to_dict(treatment) for treatment in treatments])


@app.route("/api/treatments/seed", methods=["POST"])
def seed_treatments():
    """מאתחל את קטלוג הטיפולים ההתחלתי (13 טיפולים) - רץ רק אם ריק"""
    added_count = treatment_manager.seed_catalog()
    return jsonify({"added_count": added_count})


@app.route("/api/treatments", methods=["POST"])
def create_treatment():
    data = request.get_json(silent=True) or {}

    treatment_name = data.get("treatment_name", "")
    body_area = data.get("body_area", "")
    price = data.get("price")
    duration_minutes = data.get("duration_minutes")

    is_valid, error_message, field = _validate_treatment_fields(
        treatment_name, body_area, price, duration_minutes
    )
    if not is_valid:
        return json_error(error_message, field=field)

    new_treatment = Treatment(
        treatment_name=treatment_name.strip(),
        body_area=body_area.strip(),
        price=float(price),
        duration_minutes=int(duration_minutes),
    )

    result, db_error = run_db_operation(
        lambda: treatment_manager.insert_treatment(new_treatment),
        "הוספת טיפול"
    )
    if db_error:
        return json_error(db_error, status_code=409)

    return jsonify(treatment_to_dict(result)), 201


@app.route("/api/treatments/<int:treatment_id>", methods=["PUT"])
def update_treatment(treatment_id):
    existing = treatment_manager.get_treatment_by_id(treatment_id)
    if existing is None:
        return json_error("הטיפול לא נמצא", status_code=404)

    data = request.get_json(silent=True) or {}

    treatment_name = data.get("treatment_name", existing.treatment_name)
    body_area = data.get("body_area", existing.body_area)
    price = data.get("price", existing.price)
    duration_minutes = data.get("duration_minutes", existing.duration_minutes)

    is_valid, error_message, field = _validate_treatment_fields(
        treatment_name, body_area, price, duration_minutes
    )
    if not is_valid:
        return json_error(error_message, field=field)

    existing.treatment_name = treatment_name.strip()
    existing.body_area = body_area.strip()
    existing.price = float(price)
    existing.duration_minutes = int(duration_minutes)

    success, db_error = run_db_operation(
        lambda: treatment_manager.update_treatment(existing),
        "עדכון טיפול"
    )
    if db_error:
        return json_error(db_error, status_code=409)
    if not success:
        return json_error("העדכון נכשל", status_code=404)

    return jsonify(treatment_to_dict(existing))


# ============================================================
# API - חשבוניות
# ============================================================

@app.route("/api/invoices", methods=["GET"])
def get_invoices():
    """
    ?include_cancelled=true מציג גם חשבוניות מבוטלות (לביקורת).
    ברירת המחדל - רק פעילות, בדיוק כמו ברירת המחדל של המנהל.
    """
    include_cancelled = request.args.get("include_cancelled", "false").lower() == "true"
    invoices = invoice_manager.get_all_invoices(include_cancelled=include_cancelled)
    return jsonify([invoice_to_dict(invoice) for invoice in invoices])


@app.route("/api/invoices", methods=["POST"])
def create_invoice():
    """
    מפיק חשבונית חדשה. מספר החשבונית נוצר אוטומטית בתוך
    InvoiceManager.insert_invoice - לא נוגעים בזה כאן.
    """
    data = request.get_json(silent=True) or {}

    client_id = data.get("client_id")
    amount = data.get("amount")
    invoice_date = data.get("invoice_date", "")
    appointment_id = data.get("appointment_id")

    if client_id is None or client_manager.get_client_by_id(client_id) is None:
        return json_error("לקוח לא נמצא", field="client_id")

    is_valid, error_message = validate_positive_number(amount, "הסכום")
    if not is_valid:
        return json_error(error_message, field="amount")

    is_valid, error_message = validate_date(invoice_date)
    if not is_valid:
        return json_error(error_message, field="invoice_date")

    # קישור לתור - רשות, אבל אם נשלח חייב להתקיים
    if appointment_id is not None:
        if appointment_manager.get_appointment_by_id(appointment_id) is None:
            return json_error("התור המקושר לא נמצא", field="appointment_id")

    new_invoice = Invoice(
        client_id=client_id,
        amount=float(amount),
        invoice_date=invoice_date,
        appointment_id=appointment_id,
    )

    result, db_error = run_db_operation(
        lambda: invoice_manager.insert_invoice(new_invoice),
        "הפקת חשבונית"
    )
    if db_error:
        return json_error(db_error, status_code=409)

    return jsonify(invoice_to_dict(result)), 201


@app.route("/api/invoices/<int:invoice_id>/cancel", methods=["POST"])
def cancel_invoice(invoice_id):
    """
    מבטל חשבונית (Soft Delete בלבד - InvoiceManager.cancel_invoice).
    לפי חוק, אין ולעולם לא תהיה מחיקה אמיתית של חשבונית.
    """
    invoice = invoice_manager.get_invoice_by_id(invoice_id)
    if invoice is None:
        return json_error("החשבונית לא נמצאה", status_code=404)

    if invoice.is_cancelled:
        return json_error("החשבונית כבר מבוטלת", status_code=409)

    success = invoice_manager.cancel_invoice(invoice_id)
    if not success:
        return json_error("הביטול נכשל", status_code=409)

    return jsonify({"success": True})


@app.route("/api/invoices/<int:invoice_id>/restore", methods=["POST"])
def restore_invoice(invoice_id):
    """משחזר חשבונית שבוטלה בטעות (InvoiceManager.restore_invoice)"""
    invoice = invoice_manager.get_invoice_by_id(invoice_id)
    if invoice is None:
        return json_error("החשבונית לא נמצאה", status_code=404)

    if not invoice.is_cancelled:
        return json_error("החשבונית כבר פעילה", status_code=409)

    success = invoice_manager.restore_invoice(invoice_id)
    if not success:
        return json_error("השחזור נכשל", status_code=409)

    return jsonify({"success": True})


# ============================================================
# API - לידים
# ============================================================



@app.route("/api/leads", methods=["POST"])
def create_lead():
    data = request.get_json(silent=True) or {}

    full_name = data.get("full_name", "")
    phone = data.get("phone", "")
    source = data.get("source")
    notes = data.get("notes")

    is_valid, error_message = validate_name(full_name)
    if not is_valid:
        return json_error(error_message, field="full_name")

    is_valid, error_message = validate_phone(phone)
    if not is_valid:
        return json_error(error_message, field="phone")

    if source is not None and source not in VALID_LEAD_SOURCES:
        options = " / ".join(VALID_LEAD_SOURCES)
        return json_error(f"מקור לא תקין - האפשרויות הן: {options}", field="source")

    new_lead = Lead(full_name=full_name.strip(), phone=phone.strip(),
                     source=source, notes=notes)

    result, db_error = run_db_operation(
        lambda: lead_manager.insert_lead(new_lead),
        "הוספת ליד"
    )
    if db_error:
        return json_error(db_error, status_code=409)

    return jsonify(lead_to_dict(result)), 201


@app.route("/api/leads/<int:lead_id>", methods=["PUT"])
def update_lead(lead_id):
    """מעדכן ליד - השימוש הנפוץ ביותר הוא עדכון סטטוס"""
    existing = lead_manager.get_lead_by_id(lead_id)
    if existing is None:
        return json_error("הליד לא נמצא", status_code=404)

    data = request.get_json(silent=True) or {}

    full_name = data.get("full_name", existing.full_name)
    phone = data.get("phone", existing.phone)
    source = data.get("source", existing.source)
    status = data.get("status", existing.status)
    notes = data.get("notes", existing.notes)

    is_valid, error_message = validate_name(full_name)
    if not is_valid:
        return json_error(error_message, field="full_name")

    is_valid, error_message = validate_phone(phone)
    if not is_valid:
        return json_error(error_message, field="phone")

    if source is not None and source not in VALID_LEAD_SOURCES:
        options = " / ".join(VALID_LEAD_SOURCES)
        return json_error(f"מקור לא תקין - האפשרויות הן: {options}", field="source")

    is_valid, error_message = validate_lead_status(status)
    if not is_valid:
        return json_error(error_message, field="status")

    existing.full_name = full_name.strip()
    existing.phone = phone.strip()
    existing.source = source
    existing.status = status
    existing.notes = notes

    success, db_error = run_db_operation(
        lambda: lead_manager.update_lead(existing),
        "עדכון ליד"
    )
    if db_error:
        return json_error(db_error, status_code=409)
    if not success:
        return json_error("העדכון נכשל", status_code=404)

    return jsonify(lead_to_dict(existing))


@app.route("/api/leads/<int:lead_id>", methods=["DELETE"])
def delete_lead(lead_id):
    success = lead_manager.delete_lead(lead_id)
    if not success:
        return json_error("הליד לא נמצא", status_code=404)
    return jsonify({"success": True})


@app.route("/api/leads/<int:lead_id>/convert", methods=["POST"])
def convert_lead(lead_id):
    """ממיר ליד ללקוח (LeadManager.convert_lead_to_client - טרנזקציה אחת)"""
    lead = lead_manager.get_lead_by_id(lead_id)
    if lead is None:
        return json_error("הליד לא נמצא", status_code=404)

    if lead.is_converted():
        return json_error("הליד כבר הומר ללקוח בעבר", status_code=409)

    data = request.get_json(silent=True) or {}
    email = data.get("email")
    address = data.get("address")

    is_valid, error_message = validate_email(email)
    if not is_valid:
        return json_error(error_message, field="email")

    new_client, db_error = run_db_operation(
        lambda: lead_manager.convert_lead_to_client(lead_id, email=email, address=address),
        "המרת ליד ללקוח"
    )
    if db_error:
        return json_error(db_error, status_code=409)
    if new_client is None:
        return json_error("ההמרה נכשלה", status_code=409)

    return jsonify(client_to_dict(new_client)), 201


# ============================================================
# הרצה
# ============================================================

if __name__ == "__main__":
    # אותו אתחול שקורה ב-main.py - בטוח להריץ שוב ושוב (IF NOT EXISTS)
    initialize_database()

    # יצירת טבלת הקישור לטיפול מרוכב (ראו appointment_treatment_manager.py)
    # בטוח להריץ שוב ושוב - IF NOT EXISTS
    appointment_treatment_manager.ensure_table()

    # מוודאים שיש קטלוג טיפולים - בלי זה אי אפשר לקבוע תורים
    if len(treatment_manager.get_all_treatments()) == 0:
        treatment_manager.seed_catalog()

    # host=127.0.0.1 - שרת מקומי בלבד, לא נגיש מרשת חיצונית
    # פורט 5001 ולא 5000 - ב-macOS שירות AirPlay Receiver תופס את 5000 כברירת מחדל
    app.run(host="127.0.0.1", port=5001, debug=True)
