# ============================================================
# utils/validators.py
# שכבת ולידציה - בדיקת תקינות קלט לפני כניסה לבסיס הנתונים
# כל פונקציה מחזירה (is_valid, error_message)
# error_message הוא None כשהקלט תקין
# ============================================================

import re
from datetime import datetime


# ============================================================
# ולידציה של שמות
# ============================================================

def validate_name(name):
    """
    בודק ששם תקין: לא ריק, לא מכיל ספרות, אורך סביר.
    מחזיר (True, None) אם תקין, אחרת (False, הודעת שגיאה).
    """
    # בדיקה שהשדה לא ריק
    if name is None or name.strip() == "":
        return False, "השם לא יכול להיות ריק"

    clean_name = name.strip()

    # בדיקת אורך מינימלי
    if len(clean_name) < 2:
        return False, "השם קצר מדי - נדרשים לפחות 2 תווים"

    # בדיקת אורך מקסימלי
    if len(clean_name) > 50:
        return False, "השם ארוך מדי - עד 50 תווים"

    # בדיקה שאין ספרות בשם
    for char in clean_name:
        if char.isdigit():
            return False, "השם לא יכול להכיל ספרות"

    return True, None


# ============================================================
# ולידציה של טלפון
# ============================================================

def validate_phone(phone):
    """
    בודק שמספר טלפון ישראלי תקין.
    מקבל פורמטים: 0501234567 או 050-1234567
    """
    if phone is None or phone.strip() == "":
        return False, "מספר הטלפון לא יכול להיות ריק"

    clean_phone = phone.strip()

    # התבנית: מתחיל ב-0, אחריו 1-2 ספרות, מקף אופציונלי, ואז 7 ספרות
    pattern = r"^0\d{1,2}-?\d{7}$"

    if not re.match(pattern, clean_phone):
        return False, "מספר טלפון לא תקין - נדרש פורמט כמו 0501234567"

    return True, None


# ============================================================
# ולידציה של אימייל
# ============================================================

def validate_email(email):
    """
    בודק שכתובת אימייל תקינה.
    שדה רשות - ריק נחשב תקין.
    """
    # אימייל הוא שדה רשות - ריק זה בסדר
    if email is None or email.strip() == "":
        return True, None

    clean_email = email.strip()

    # בדיקה ספציפית לשגיאה הנפוצה ביותר
    if "@" not in clean_email:
        return False, "כתובת אימייל לא תקינה - חסר סימן @"

    if "." not in clean_email.split("@")[-1]:
        return False, "כתובת אימייל לא תקינה - חסרה סיומת (למשל .com)"

    # התבנית המלאה
    pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

    if not re.match(pattern, clean_email):
        return False, "כתובת אימייל לא תקינה"

    return True, None


# ============================================================
# ולידציה של תאריך
# ============================================================

def validate_date(date_string):
    """
    בודק שהתאריך בפורמט YYYY-MM-DD ושהוא תאריך אמיתי.
    """
    if date_string is None or date_string.strip() == "":
        return False, "התאריך לא יכול להיות ריק"

    clean_date = date_string.strip()

    # strptime זורק שגיאה אם הפורמט לא מתאים או התאריך לא קיים
    try:
        datetime.strptime(clean_date, "%Y-%m-%d")
    except ValueError:
        return False, "תאריך לא תקין - נדרש פורמט YYYY-MM-DD (למשל 2026-03-15)"

    return True, None


# ============================================================
# ולידציה של שעה
# ============================================================

def validate_time(time_string):
    """
    בודק שהשעה בפורמט HH:MM ושהיא שעה אמיתית.
    """
    if time_string is None or time_string.strip() == "":
        return False, "השעה לא יכולה להיות ריקה"

    clean_time = time_string.strip()

    try:
        datetime.strptime(clean_time, "%H:%M")
    except ValueError:
        return False, "שעה לא תקינה - נדרש פורמט HH:MM (למשל 14:30)"

    return True, None


# ============================================================
# ולידציה של מספרים
# ============================================================

def validate_positive_number(value, field_name="הערך"):
    """
    בודק שהערך הוא מספר חיובי.
    field_name מאפשר הודעת שגיאה מותאמת לכל שדה.
    """
    if value is None or str(value).strip() == "":
        return False, f"{field_name} לא יכול להיות ריק"

    # ניסיון המרה למספר
    try:
        number = float(value)
    except ValueError:
        return False, f"{field_name} חייב להיות מספר"

    if number <= 0:
        return False, f"{field_name} חייב להיות גדול מאפס"

    return True, None


# ============================================================
# ולידציה של סטטוסים
# ============================================================

# הסטטוסים החוקיים במערכת - מוגדרים במקום אחד
VALID_APPOINTMENT_STATUSES = ["pending", "completed", "cancelled"]
VALID_LEAD_STATUSES = ["new", "in_progress", "converted", "rejected"]


def validate_appointment_status(status):
    """בודק שסטטוס התור הוא אחד מהסטטוסים החוקיים"""
    if status not in VALID_APPOINTMENT_STATUSES:
        options = " / ".join(VALID_APPOINTMENT_STATUSES)
        return False, f"סטטוס לא תקין - האפשרויות הן: {options}"

    return True, None


def validate_lead_status(status):
    """בודק שסטטוס הליד הוא אחד מהסטטוסים החוקיים"""
    if status not in VALID_LEAD_STATUSES:
        options = " / ".join(VALID_LEAD_STATUSES)
        return False, f"סטטוס לא תקין - האפשרויות הן: {options}"

    return True, None