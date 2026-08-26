# ============================================================
# utils/otp.py
# מנגנון קודי אימות חד-פעמיים.
#
# עקרונות האבטחה המיושמים כאן:
#   1. הקוד נשמר כטביעת אצבע, לא כטקסט
#   2. הקוד נשלח ליעד שרשום במסד, לא ליעד שהמשתמש הקליד
#   3. מספר הניסיונות מוגבל
#   4. לקוד יש תוקף קצר
#   5. קוד שמומש נפסל מיידית
#   6. יצירת קוד חדש מבטלת את הקודמים
# ============================================================

import secrets
from datetime import datetime, timedelta

from config import Config
from database import get_connection
from utils.security import hash_national_id, verify_national_id
from notifications.factory import get_notification_provider
from notifications.base import NotificationError


# תבנית ההודעה הנשלחת ללקוחה
MESSAGE_TEMPLATE = (
    "קוד האימות שלך לקליניקה הוא: {code}\n"
    "הקוד תקף ל-{minutes} דקות.\n"
    "אם לא ביקשת את הקוד, אפשר להתעלם מההודעה."
)


def generate_code(length=None):
    """
    יוצר קוד מספרי אקראי.

    השימוש ב-secrets ולא ב-random מכוון: random מיועד
    לסימולציות והרצף שלו ניתן לחיזוי. secrets נועד לאבטחה.
    """
    length = length or Config.OTP_LENGTH
    return "".join(secrets.choice("0123456789") for _ in range(length))


def mask_destination(destination):
    """
    מסתיר את רוב היעד לצורך הצגה למשתמש.

    הבוט אומר ללקוחה לאן נשלח הקוד, בלי לחשוף את הפרט המלא.
    בלי זה, המערכת הופכת לכלי לשליפת מספרי טלפון של לקוחות.
    """
    if not destination:
        return ""

    text = str(destination).strip()

    # כתובת מייל: נחשפת האות הראשונה והדומיין
    if "@" in text:
        local, _, domain = text.partition("@")
        visible = local[0] if local else ""
        return f"{visible}***@{domain}"

    # מספר טלפון: נחשפות ארבע הספרות האחרונות
    if len(text) <= 4:
        return "*" * len(text)
    return f"***{text[-4:]}"


def _invalidate_previous_codes(cursor, client_id, purpose):
    """
    מבטל קודים קודמים שטרם מומשו.
    כך תמיד קיים קוד פעיל אחד בלבד ללקוחה.
    """
    cursor.execute(
        "UPDATE otp_codes SET is_used = 1 "
        "WHERE client_id = ? AND purpose = ? AND is_used = 0",
        (client_id, purpose),
    )


def create_and_send_otp(client_id, destination, channel="email",
                        purpose="identity_verification"):
    """
    יוצר קוד אימות, שומר את טביעת האצבע שלו, ושולח אותו.

    destination חייב להגיע מהרשומה במסד ולא מקלט המשתמש.
    זו נקודת האבטחה המרכזית של המנגנון כולו: שליחה ליעד
    שהמשתמש הקליד מוכיחה רק שהוא מחזיק טלפון כלשהו.

    מחזיר צמד (success, info).
    info מכיל את היעד המוסתר ואת מועד התפוגה, או הודעת שגיאה.
    """
    if not destination:
        return False, {"error": "אין דרך ליצור קשר עם הלקוחה"}

    code = generate_code()
    code_hash = hash_national_id(code)

    expires_at = datetime.now() + timedelta(minutes=Config.OTP_EXPIRY_MINUTES)

    connection = get_connection()
    cursor = connection.cursor()

    try:
        _invalidate_previous_codes(cursor, client_id, purpose)

        cursor.execute(
            "INSERT INTO otp_codes "
            "(client_id, code_hash, channel, purpose, expires_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (client_id, code_hash, channel, purpose, expires_at.isoformat()),
        )
        connection.commit()

    finally:
        connection.close()

    message = MESSAGE_TEMPLATE.format(
        code=code,
        minutes=Config.OTP_EXPIRY_MINUTES,
    )

    try:
        provider = get_notification_provider()
        provider.send(destination, "קוד אימות", message)

    except NotificationError as error:
        return False, {"error": "שליחת הקוד נכשלה", "detail": str(error)}

    return True, {
        "masked_destination": mask_destination(destination),
        "expires_in_minutes": Config.OTP_EXPIRY_MINUTES,
    }


def verify_otp(client_id, submitted_code, purpose="identity_verification"):
    """
    בודק קוד שהוזן מול הקוד הפעיל של הלקוחה.

    מחזיר צמד (is_valid, reason).
    reason הוא אחד מ: ok, no_code, expired, too_many_attempts, wrong_code.

    הודעות הכישלון נשארות כלליות בשכבה שמעל, כדי לא ללמד
    תוקף האם הקוד קיים, פג, או פשוט שגוי.
    """
    if not submitted_code:
        return False, "wrong_code"

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            "SELECT otp_id, code_hash, attempts_used, expires_at "
            "FROM otp_codes "
            "WHERE client_id = ? AND purpose = ? AND is_used = 0 "
            "ORDER BY otp_id DESC LIMIT 1",
            (client_id, purpose),
        )
        row = cursor.fetchone()

        if row is None:
            return False, "no_code"

        otp_id, code_hash, attempts_used, expires_at_text = row

        if attempts_used >= Config.OTP_MAX_ATTEMPTS:
            return False, "too_many_attempts"

        if datetime.now() > datetime.fromisoformat(expires_at_text):
            return False, "expired"

        cleaned_code = str(submitted_code).strip()
        is_match = verify_national_id(cleaned_code, code_hash)

        if not is_match:
            # מונה הניסיונות עולה גם בכישלון, אחרת אין הגבלה בפועל
            cursor.execute(
                "UPDATE otp_codes SET attempts_used = attempts_used + 1 "
                "WHERE otp_id = ?",
                (otp_id,),
            )
            connection.commit()

            remaining = Config.OTP_MAX_ATTEMPTS - (attempts_used + 1)
            if remaining <= 0:
                return False, "too_many_attempts"
            return False, "wrong_code"

        # קוד שמומש נפסל מיידית ולא ניתן לשימוש חוזר
        cursor.execute(
            "UPDATE otp_codes SET is_used = 1 WHERE otp_id = ?",
            (otp_id,),
        )
        connection.commit()

        return True, "ok"

    finally:
        connection.close()