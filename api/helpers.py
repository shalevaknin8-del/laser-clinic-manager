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