# ============================================================
# chatbot/verification.py
# שער האימות של הצ'אטבוט.
#
# Release 2 (Principle 1): הלוגיקה עצמה עברה ל-identity/verification.py,
# המשותפת גם לפורטל. הקובץ הזה נשאר בתור מתאם דק שמנהל את מצב
# השיחה (ConversationState) - id_attempts/otp_attempts/lock/state -
# שזה עניין ספציפי לצ'אטבוט ולא לזהות עצמה. שום קוד קורא (chatbot/flows.py)
# לא צריך להשתנות: אותם שמות פונקציות, אותה חתימה, אותה התנהגות.
#
# מבנה האימות: שני שלבים עצמאיים.
#   שלב א - תעודת זהות, מוכיח ידע
#   שלב ב - קוד לטלפון, מוכיח החזקה
# שניהם חייבים לעבור.
# ============================================================

from config import Config
from managers.client_manager import ClientManager

from identity.verification import (
    RESULT_OK,
    RESULT_WRONG,
    RESULT_LOCKED,
    RESULT_NO_DATA,
    RESULT_SEND_FAILED,
    PURPOSE_CHATBOT_IDENTITY,
    check_national_id,
    send_otp,
    confirm_otp,
)

from chatbot.state import (
    STATE_AWAITING_ID,
    STATE_AWAITING_OTP,
    STATE_VERIFIED,
    STATE_LOCKED,
)


client_manager = ClientManager()


def verify_identity_document(conversation, national_id):
    """
    שלב אימות ראשון: תעודת זהות.

    מחזיר את אחד הקבועים שלמעלה. אינו מחזיר שום פרט
    על הלקוחה, גם לא בהצלחה.
    """
    if conversation.state == STATE_LOCKED:
        return RESULT_LOCKED

    if conversation.candidate_client_id is None:
        return RESULT_NO_DATA

    is_match = check_national_id(conversation.candidate_client_id, national_id)

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

    return send_otp(conversation.candidate_client_id, purpose=PURPOSE_CHATBOT_IDENTITY)


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

    result, _reason = confirm_otp(conversation.candidate_client_id, code,
                                   purpose=PURPOSE_CHATBOT_IDENTITY)

    if result == RESULT_OK:
        conversation.otp_verified = True
        conversation.state = STATE_VERIFIED
        return RESULT_OK

    conversation.otp_attempts += 1

    if result == RESULT_LOCKED or conversation.otp_attempts >= Config.MAX_VERIFICATION_ATTEMPTS:
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
