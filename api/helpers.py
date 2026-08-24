# ============================================================
# api/helpers.py
# פונקציות עזר משותפות לכל שכבת ה-API.
#
# הקובץ הזה לא מכיל routes ולא נוגע במסד הנתונים ישירות.
# תפקידו היחיד: לספק כלים שכל קבצי ה-API משתמשים בהם -
# בניית תגובות שגיאה אחידות, הרצת פעולות DB בבטחה,
# והמרת אובייקטים לפורמט JSON.
# ============================================================

import sqlite3

from flask import jsonify

from utils.db_errors import translate_db_error
from managers.appointment_treatment_manager import AppointmentTreatmentManager


# מקורות פנייה חוקיים לליד, אותה רשימה שמוצגת בתפריט ה-CLI
VALID_LEAD_SOURCES = ["facebook", "instagram", "google", "referral", "walk_in"]


# ============================================================
# תגובות ושגיאות
# ============================================================

def json_error(message, status_code=400, field=None):
    """
    בונה תגובת שגיאה אחידה בפורמט JSON.
    כל השגיאות במערכת עוברות דרך כאן כדי שצד הלקוח
    תמיד יקבל את אותו מבנה תגובה.
    """
    body = {"error": message}
    if field is not None:
        body["field"] = field
    return jsonify(body), status_code


def run_db_operation(operation, context):
    """
    מריץ פעולת מסד נתונים שעלולה לזרוק שגיאה, ומתרגם
    את השגיאה להודעה בעברית.

    operation - פונקציה ללא פרמטרים שמבצעת את הפעולה
    context   - תיאור קצר בעברית, למשל "הוספת טיפול"

    מחזיר צמד (result, error_message).
    אם error_message אינו None, הפעולה נכשלה.
    """
    try:
        result = operation()
        return result, None
    except sqlite3.Error as error:
        return None, translate_db_error(error, context)


# ============================================================
# המרת אובייקטים למילון לצורך JSON
# ============================================================

def client_to_dict(client):
    """ממיר אובייקט לקוח למילון שניתן להחזיר כ-JSON."""
    return {
        "client_id": client.client_id,
        "full_name": client.full_name,
        "phone": client.phone,
        "email": client.email,
        "address": client.address,
    }


def lead_to_dict(lead):
    """ממיר אובייקט ליד למילון שניתן להחזיר כ-JSON."""
    return {
        "lead_id": lead.lead_id,
        "full_name": lead.full_name,
        "phone": lead.phone,
        "source": lead.source,
        "status": lead.status,
        "notes": lead.notes,
    }



def invoice_to_dict(invoice):
    """ממיר אובייקט חשבונית למילון שניתן להחזיר כ-JSON."""
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



def treatment_to_dict(treatment):
    """ממיר אובייקט טיפול למילון שניתן להחזיר כ-JSON."""
    return {
        "treatment_id": treatment.treatment_id,
        "treatment_name": treatment.treatment_name,
        "body_area": treatment.body_area,
        "price": treatment.price,
        "duration_minutes": treatment.duration_minutes,
    }



# ============================================================
# טיפול מרוכב (כמה טיפולים לאותו תור)
# ============================================================

# מנהל הקישור בין תור לטיפולים. מוגדר כאן כי גם התורים
# וגם היסטוריית הלקוח צריכים את אותה לוגיקת חישוב
appointment_treatment_manager = AppointmentTreatmentManager()


def combo_fields_for_appointment(appointment_id, fallback_treatment_id):
    """
    מחזיר את שדות הטיפול המרוכב של תור: רשימת מזהי הטיפולים,
    שמותיהם, והמחיר והמשך הכוללים.

    fallback_treatment_id משמש לתורים רגילים שאין להם רשומות
    בטבלת הקישור, למשל תורים שנוצרו דרך תפריט ה-CLI.
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


def appointment_to_dict(appointment):
    """ממיר אובייקט תור למילון, כולל שדות הטיפול המרוכב."""
    result = {
        "appointment_id": appointment.appointment_id,
        "client_id": appointment.client_id,
        "treatment_id": appointment.treatment_id,
        "appointment_date": appointment.appointment_date,
        "appointment_time": appointment.appointment_time,
        "status": appointment.status,
        "notes": appointment.notes,
    }
    result.update(
        combo_fields_for_appointment(appointment.appointment_id, appointment.treatment_id)
    )
    return result


def appointment_row_to_dict(row):
    """
    ממיר שורת תוצאה מהשאילתה המשולבת למילון קריא.
    סדר העמודות בשאילתה:
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



# ============================================================
# פירוש רשימת מזהי טיפולים מהבקשה
# ============================================================

def parse_treatment_ids_from_json(data):
    """
    מפרש רשימת מזהי טיפולים מגוף בקשת JSON.
    תומך גם בטופס החדש עם רשימה לטיפול מרוכב, וגם בטופס הישן
    עם מזהה יחיד לצורך תאימות לאחור.
    מחזיר רשימת מספרים, או None אם לא נשלח כלום.
    """
    treatment_ids = data.get("treatment_ids")
    if treatment_ids:
        return [int(t) for t in treatment_ids]

    treatment_id = data.get("treatment_id")
    if treatment_id is not None:
        return [int(treatment_id)]

    return None


def parse_treatment_ids_from_args(args):
    """
    אותה לוגיקה כמו הפונקציה שמעל, אבל עבור פרמטרים
    שמגיעים בכתובת ה-URL בבקשות מסוג GET.
    """
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