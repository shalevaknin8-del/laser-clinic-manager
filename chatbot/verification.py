# ============================================================
# chatbot/verification.py
# שער האימות של הצ'אטבוט.
#
# זו נקודת המעבר היחידה במערכת בין שיחה לא מאומתת
# לבין מידע אישי. כל שליפת נתונים עוברת דרך כאן.
#
# הסיבה לריכוז: פיזור בדיקות בכל handler בנפרד יוצר
# מצב שבו מספיק לשכוח בדיקה אחת כדי לדלוף מידע.
# עם שער יחיד, אי אפשר לשכוח.
#
# מבנה האימות: שני שלבים עצמאיים.
#   שלב א - תעודת זהות, מוכיח ידע
#   שלב ב - קוד לטלפון, מוכיח החזקה
# שניהם חייבים לעבור.
# ============================================================

from config import Config
from managers.client_manager import ClientManager
from utils.otp import create_and_send_otp, verify_otp

from chatbot.state import (
    STATE_AWAITING_ID,
    STATE_AWAITING_OTP,
    STATE_VERIFIED,
    STATE_LOCKED,
)


client_manager = ClientManager()


# ============================================================
# תוצאות אפשריות של ניסיון אימות
# ============================================================

RESULT_OK = "ok"
RESULT_WRONG = "wrong"
RESULT_LOCKED = "locked"
RESULT_NO_DATA = "no_data"
RESULT_SEND_FAILED = "send_failed"


def verify_identity_document(conversation, national_id):
    """
    שלב אימות ראשון: תעודת זהות.

    מחזיר את אחת הקבועים שלמעלה. אינו מחזיר שום פרט
    על הלקוחה, גם לא בהצלחה.
    """
    if conversation.state == STATE_LOCKED:
        return RESULT_LOCKED

    if conversation.candidate_client_id is None:
        return RESULT_NO_DATA

    is_match = client_manager.verify_client_national_id(
        conversation.candidate_client_id, national_id
    )

    if is_match:
        conversation.id_verified = True
        conversation.state = STATE_AWAITING_OTP
        return RESULT_OK

    # מונה הניסיונות עולה גם בכישלון, אחרת אין הגבלה בפועל
    conversation.id_attempts += 1

    if conversation.id_attempts >= Config.MAX_VERIFICATION_ATTEMPTS:
        conversation.lock()
        return RESULT_LOCKED

    return RESULT_WRONG


def send_verification_code(conversation):
    """
    שולח קוד אימות ללקוחה.

    נקודת האבטחה המרכזית: היעד נשלף מהרשומה במסד ולעולם
    לא מקלט המשתמשת. שליחה ליעד שהוקלד מוכיחה רק שהמשתמשת
    מחזיקה טלפון כלשהו, ולא שהיא הלקוחה הנכונה.

    מחזיר צמד (result, masked_destination).
    """
    if conversation.state == STATE_LOCKED:
        return RESULT_LOCKED, None

    # שלב האימות הראשון חייב לעבור לפני שנשלח קוד
    if not conversation.id_verified:
        return RESULT_NO_DATA, None

    client = client_manager.get_client_by_id(conversation.candidate_client_id)
    if client is None or not client.phone:
        return RESULT_NO_DATA, None

    success, info = create_and_send_otp(
        client.client_id, client.phone, channel="phone"
    )

    if not success:
        return RESULT_SEND_FAILED, None

    return RESULT_OK, info["masked_destination"]


def verify_code(conversation, code):
    """
    שלב אימות שני: קוד חד פעמי.

    רק אחרי הצלחה כאן המצב עובר ל-VERIFIED,
    וזה התנאי היחיד לחשיפת מידע.
    """
    if conversation.state == STATE_LOCKED:
        return RESULT_LOCKED

    if not conversation.id_verified:
        return RESULT_NO_DATA

    is_valid, reason = verify_otp(conversation.candidate_client_id, code)

    if is_valid:
        conversation.otp_verified = True
        conversation.state = STATE_VERIFIED
        return RESULT_OK

    conversation.otp_attempts += 1

    if reason == "too_many_attempts" or \
            conversation.otp_attempts >= Config.MAX_VERIFICATION_ATTEMPTS:
        conversation.lock()
        return RESULT_LOCKED

    return RESULT_WRONG


# ============================================================
# השער עצמו
# ============================================================

class NotVerifiedError(Exception):
    """
    נזרקת כאשר מנסים לשלוף מידע בשיחה שלא אומתה.

    זו חריגה ולא ערך מוחזר בכוונה. ערך מוחזר אפשר
    להתעלם ממנו בטעות, חריגה עוצרת את הזרימה.
    """


def require_verified(conversation):
    """
    השער. כל פונקציה ששולפת מידע אישי חייבת לקרוא לו ראשונה.

    אם השיחה לא אומתה במלואה, נזרקת חריגה והזרימה נעצרת.
    """
    if conversation is None or not conversation.is_fully_verified():
        raise NotVerifiedError("Attempted data access without full verification")

    return conversation.candidate_client_id


def get_verified_client(conversation):
    """
    מחזיר את רשומת הלקוחה, אך ורק אחרי אימות מלא.
    זו הפונקציה היחידה שמותר לה להחזיר פרטי לקוחה.
    """
    client_id = require_verified(conversation)
    return client_manager.get_client_by_id(client_id)