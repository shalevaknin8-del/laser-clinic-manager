# ============================================================
# utils/db_errors.py
# תרגום שגיאות SQLite להודעות ברורות בעברית
# מרכז את כל הטיפול בשגיאות DB במקום אחד
# ============================================================

import sqlite3


def translate_db_error(error, context=""):
    """
    ממיר שגיאת SQLite להודעה ברורה בעברית.
    
    error   - אובייקט השגיאה שנתפס
    context - תיאור קצר של הפעולה, למשל "הוספת תור"
    
    מחזיר מחרוזת הודעה מוכנה להצגה למשתמש.
    """
    error_text = str(error).lower()

    # ---- שגיאות שלמות נתונים ----
    if isinstance(error, sqlite3.IntegrityError):

        # מפתח זר נכשל - מפנה לישות שלא קיימת
        if "foreign key" in error_text:
            return "אחד הפריטים המקושרים לא קיים במערכת (לקוח, טיפול או תור)"

        # ערך ייחודי כבר קיים
        if "unique" in error_text:
            if "invoice_number" in error_text:
                return "מספר החשבונית כבר קיים במערכת"
            return "הערך שהוזן כבר קיים במערכת"

        # שדה חובה חסר
        if "not null" in error_text:
            # מנסים לחלץ את שם השדה מההודעה
            field = _extract_field_name(error_text)
            if field:
                return f"השדה '{field}' הוא שדה חובה ולא יכול להישאר ריק"
            return "אחד משדות החובה נשאר ריק"

        return "הנתונים שהוזנו אינם תקינים"

    # ---- שגיאות תפעול ----
    if isinstance(error, sqlite3.OperationalError):

        if "locked" in error_text:
            return "בסיס הנתונים תפוס כרגע - נסה שוב בעוד רגע"

        if "no such table" in error_text:
            return "טבלה חסרה בבסיס הנתונים - יש להריץ database.py"

        return "בעיה בגישה לבסיס הנתונים"

    # ---- כל השאר ----
    if context:
        return f"שגיאה לא צפויה ב{context}"

    return "שגיאה לא צפויה"


def _extract_field_name(error_text):
    """
    מחלץ שם שדה מהודעת שגיאה של NOT NULL.
    ההודעה נראית כך: 'not null constraint failed: clients.full_name'
    
    פונקציה פנימית.
    """
    # מחפשים את החלק אחרי הנקודתיים
    if ":" not in error_text:
        return None

    after_colon = error_text.split(":")[-1].strip()

    # מפרידים table.column ולוקחים את העמודה
    if "." in after_colon:
        return after_colon.split(".")[-1]

    return after_colon


# מיפוי שמות שדות לעברית - להודעות ידידותיות יותר
FIELD_NAMES_HEBREW = {
    "full_name": "שם מלא",
    "phone": "טלפון",
    "email": "אימייל",
    "address": "כתובת",
    "appointment_date": "תאריך התור",
    "appointment_time": "שעת התור",
    "treatment_name": "שם הטיפול",
    "price": "מחיר",
    "duration_minutes": "משך הטיפול",
    "invoice_number": "מספר חשבונית",
    "amount": "סכום",
    "invoice_date": "תאריך חשבונית",
    "status": "סטטוס",
}


def get_hebrew_field_name(field):
    """מחזיר את שם השדה בעברית, או את השם המקורי אם לא נמצא"""
    return FIELD_NAMES_HEBREW.get(field, field)