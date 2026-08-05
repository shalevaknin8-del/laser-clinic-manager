# ============================================================
# utils/display.py
# כלי עזר לקלט ופלט בתפריט הראשי
# מרכז את כל הלוגיקה של בקשת קלט עם ולידציה
# ============================================================

from utils.validators import (
    validate_name,
    validate_phone,
    validate_email,
    validate_date,
    validate_time,
    validate_positive_number,
)


# ============================================================
# פונקציות תצוגה
# ============================================================

def print_header(title):
    """מדפיס כותרת מסגרת לתפריט"""
    print("\n" + "=" * 50)
    print(f"   {title}")
    print("=" * 50)


def print_success(message):
    """מדפיס הודעת הצלחה"""
    print(f"\n[V] {message}")


def print_error(message):
    """מדפיס הודעת שגיאה"""
    print(f"\n[X] {message}")


def print_info(message):
    """מדפיס הודעת מידע"""
    print(f"\n[i] {message}")


def pause():
    """עוצר עד שהמשתמש לוחץ Enter - כדי שיספיק לקרוא"""
    input("\nלחץ Enter להמשך...")


# ============================================================
# פונקציות קלט עם ולידציה
# ============================================================

def ask_text(prompt, validator=None, allow_empty=False):
    """
    מבקש טקסט מהמשתמש וחוזר על הבקשה עד שהקלט תקין.
    
    prompt      - השאלה שמוצגת
    validator   - פונקציית ולידציה, או None אם אין
    allow_empty - האם ריק מותר (לשדות רשות)
    
    מחזיר את הטקסט, או None אם המשתמש הקליד 0 לביטול.
    """
    while True:
        value = input(f"{prompt} (0 לביטול): ").strip()

        # אפשרות ביטול תמיד זמינה
        if value == "0":
            return None

        # שדה רשות שנשאר ריק
        if value == "" and allow_empty:
            return None

        # אם אין ולידטור - מקבלים כמו שהוא
        if validator is None:
            if value == "":
                print_error("השדה לא יכול להישאר ריק")
                continue
            return value

        # מפעילים את הולידטור
        is_valid, error_message = validator(value)

        if is_valid:
            return value

        print_error(error_message)


def ask_number(prompt, field_name="הערך", allow_empty=False):
    """
    מבקש מספר חיובי מהמשתמש.
    מחזיר float, או None אם בוטל.
    """
    while True:
        value = input(f"{prompt} (0 לביטול): ").strip()

        if value == "0":
            return None

        if value == "" and allow_empty:
            return None

        is_valid, error_message = validate_positive_number(value, field_name)

        if is_valid:
            return float(value)

        print_error(error_message)


def ask_int(prompt):
    """
    מבקש מספר שלם - למשל מזהה של לקוח או טיפול.
    מחזיר int, או None אם בוטל.
    """
    while True:
        value = input(f"{prompt} (0 לביטול): ").strip()

        if value == "0":
            return None

        if not value.isdigit():
            print_error("יש להזין מספר שלם")
            continue

        return int(value)


def ask_choice(prompt, options):
    """
    מבקש בחירה מתוך רשימת אפשרויות.
    
    options - רשימה של מחרוזות
    מחזיר את האפשרות שנבחרה, או None אם בוטל.
    """
    print(f"\n{prompt}")

    for index, option in enumerate(options, start=1):
        print(f"  {index}. {option}")

    while True:
        value = input("בחירה (0 לביטול): ").strip()

        if value == "0":
            return None

        if not value.isdigit():
            print_error("יש להזין מספר")
            continue

        choice_index = int(value)

        if choice_index < 1 or choice_index > len(options):
            print_error(f"יש לבחור מספר בין 1 ל-{len(options)}")
            continue

        return options[choice_index - 1]


def confirm(question):
    """
    שואל שאלת כן/לא. מחזיר True או False.
    """
    while True:
        answer = input(f"{question} (כ/ל): ").strip().lower()

        if answer in ("כ", "k", "y", "yes", "כן"):
            return True

        if answer in ("ל", "l", "n", "no", "לא"):
            return False

        print_error("יש להזין כ (כן) או ל (לא)")


# ============================================================
# פונקציות עזר ספציפיות - עם הולידטור המתאים כבר מחובר
# ============================================================

def ask_name(prompt="שם מלא"):
    """מבקש שם עם ולידציה"""
    return ask_text(prompt, validator=validate_name)


def ask_phone(prompt="טלפון"):
    """מבקש טלפון עם ולידציה"""
    return ask_text(prompt, validator=validate_phone)


def ask_email(prompt="אימייל (רשות)"):
    """מבקש אימייל - שדה רשות"""
    return ask_text(prompt, validator=validate_email, allow_empty=True)


def ask_date(prompt="תאריך (YYYY-MM-DD)"):
    """מבקש תאריך עם ולידציה"""
    return ask_text(prompt, validator=validate_date)


def ask_time(prompt="שעה (HH:MM)"):
    """מבקש שעה עם ולידציה"""
    return ask_text(prompt, validator=validate_time)