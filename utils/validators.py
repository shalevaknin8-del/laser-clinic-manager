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
    בודק שמספר טלפון נייד ישראלי תקין.

    מקבל כל פורמט שניתן לנרמל למספר נייד תקין (ראו normalize_phone):
    0501234567, 050-1234567, 050-123-4567, וגם קידומת בינלאומית +972.
    זו אותה בדיקת תקינות בדיוק שמשמשת בכניסת עובדות למערכת - חובה
    שהיא תהיה זהה, כי הבוט שולח קוד אימות למספר הזה בפועל.
    """
    if phone is None or phone.strip() == "":
        return False, "מספר הטלפון לא יכול להיות ריק"

    if normalize_phone(phone) is None:
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


def validate_positive_integer(value, field_name="הערך"):
    """
    בודק שהערך הוא מספר שלם חיובי.

    בשונה מ-validate_positive_number, כאן ערך כמו "10.5" נדחה.
    נחוץ לשדות שמייצגים דקות (duration_minutes) - מספר שלם
    שממשיך להיות מומר בקוד הקורא עם int(), ולכן חייב להיבדק
    כשלם כבר כאן ולא רק כחיובי.
    """
    if value is None or str(value).strip() == "":
        return False, f"{field_name} לא יכול להיות ריק"

    try:
        number = float(value)
    except ValueError:
        return False, f"{field_name} חייב להיות מספר"

    if number <= 0:
        return False, f"{field_name} חייב להיות גדול מאפס"

    if number != int(number):
        return False, f"{field_name} חייב להיות מספר שלם"

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

def validate_national_id(national_id):
    """
    בודק תקינות של מספר תעודת זהות ישראלית.

    הבדיקה כוללת שני שלבים:
    ראשית, שהקלט מכיל תשע ספרות בלבד.
    שנית, אימות ספרת הביקורת לפי האלגוריתם הרשמי.

    האלגוריתם: כל ספרה מוכפלת לסירוגין ב-1 וב-2. אם התוצאה
    דו-ספרתית, מקפלים אותה לסכום ספרותיה. סכום כל התוצאות
    חייב להתחלק ב-10 ללא שארית.

    מחזיר צמד (is_valid, error_message).
    """
    if national_id is None:
        return False, "יש להזין מספר תעודת זהות"

    # ניקוי רווחים ומקפים שמשתמשים נוטים להוסיף
    cleaned = str(national_id).strip().replace("-", "").replace(" ", "")

    if not cleaned:
        return False, "יש להזין מספר תעודת זהות"

    if not cleaned.isdigit():
        return False, "תעודת זהות יכולה להכיל ספרות בלבד"

    # תעודות זהות ישנות נכתבות לעיתים בלי אפסים מובילים
    if len(cleaned) > 9:
        return False, "תעודת זהות מכילה 9 ספרות"
    cleaned = cleaned.zfill(9)

    # חישוב ספרת הביקורת
    total = 0
    for index, digit_char in enumerate(cleaned):
        digit = int(digit_char)
        # ספרות במקום זוגי מוכפלות ב-1, ובמקום אי-זוגי ב-2
        multiplied = digit * (1 if index % 2 == 0 else 2)
        # תוצאה דו-ספרתית מקופלת לסכום ספרותיה
        if multiplied > 9:
            multiplied = multiplied - 9
        total += multiplied

    if total % 10 != 0:
        return False, "מספר תעודת הזהות אינו תקין"

    return True, None


def normalize_national_id(national_id):
    """
    מחזיר את תעודת הזהות בפורמט אחיד: תשע ספרות עם אפסים מובילים.

    הנרמול חיוני לאימות. בלעדיו, לקוחה שנרשמה עם 12345678
    לא תזוהה כשתקליד 012345678, למרות שמדובר באותה תעודה.
    """
    if national_id is None:
        return None
    cleaned = str(national_id).strip().replace("-", "").replace(" ", "")
    if not cleaned.isdigit():
        return None
    return cleaned.zfill(9)



def normalize_phone(phone):
    """
    מחזיר מספר טלפון ישראלי בפורמט אחיד: 05XXXXXXXX.

    הנרמול חיוני להתחברות. בלעדיו, משתמשת שנרשמה עם
    0521234567 לא תזוהה כשתקליד 052-123-4567, למרות
    שמדובר באותו מספר בדיוק.

    מחזיר None אם המספר אינו תקין.
    """
    if not phone:
        return None

    # הסרת כל מה שאינו ספרה או סימן פלוס
    cleaned = "".join(ch for ch in str(phone) if ch.isdigit() or ch == "+")

    # המרת קידומת בינלאומית לפורמט מקומי
    if cleaned.startswith("+972"):
        cleaned = "0" + cleaned[4:]
    elif cleaned.startswith("972"):
        cleaned = "0" + cleaned[3:]

    if not cleaned.isdigit():
        return None

    # מספר נייד ישראלי: עשר ספרות שמתחילות ב-05
    if len(cleaned) != 10 or not cleaned.startswith("05"):
        return None

    return cleaned