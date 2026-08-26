# ============================================================
# utils/passwords.py
# הצפנת סיסמאות ואימותן.
#
# הסיסמה עצמה לא נשמרת בשום מקום ולא ניתנת לשחזור.
# גם דנה לא יכולה לראות את הסיסמה של עובדת, היא רק
# יכולה לאפס אותה לסיסמה חדשה.
#
# מימוש: scrypt דרך werkzeug, שמגיע מובנה עם Flask.
# scrypt דורש גם זיכרון וגם זמן חישוב, ולכן קשה להאצה
# באמצעות חומרה ייעודית, בשונה מאלגוריתמים ישנים יותר.
# ============================================================

from werkzeug.security import generate_password_hash, check_password_hash


# אורך מינימלי לסיסמה. קצר מזה ניתן לניחוש בזמן סביר
MIN_PASSWORD_LENGTH = 8


def hash_password(password):
    """
    ממיר סיסמה לטביעת אצבע מאובטחת.
    המלח נוצר אוטומטית ונשמר בתוך המחרוזת המוחזרת.
    """
    return generate_password_hash(password, method="scrypt")


def verify_password(password, stored_hash):
    """
    בודק האם סיסמה תואמת לטביעת האצבע השמורה.
    ההשוואה עצמה חסינה להתקפת תזמון.
    """
    if not password or not stored_hash:
        return False
    return check_password_hash(stored_hash, password)


def validate_password_strength(password):
    """
    בודק שהסיסמה עומדת בדרישות מינימום.

    הדרישות מכוונות בכוונה לרף סביר ולא מחמיר מדי.
    דרישות מוגזמות גורמות לאנשים לכתוב סיסמאות על פתק
    ליד המחשב, וזה מסוכן יותר מסיסמה קצת פשוטה יותר.

    מחזיר צמד (is_valid, error_message).
    """
    if not password:
        return False, "יש להזין סיסמה"

    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"הסיסמה חייבת להכיל לפחות {MIN_PASSWORD_LENGTH} תווים"

    if password.isdigit():
        return False, "הסיסמה לא יכולה להכיל ספרות בלבד"

    if password.lower() in ("password", "12345678", "qwerty123", "admin123"):
        return False, "הסיסמה נפוצה מדי, יש לבחור סיסמה אחרת"

    return True, None