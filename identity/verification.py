# ============================================================
# identity/verification.py
# הפרימיטיבים המשותפים של שתי שיטות הכניסה - שם+ת.ז.+OTP (צ'אטבוט)
# וטלפון+OTP (פורטל).
#
# מה שנשאר כאן בכוונה גנרי: אין כאן ConversationState, אין כאן
# JWT, ואין כאן ספירת ניסיונות/נעילה - אלה שייכים לצרכן (לצ'אטבוט
# יש ConversationState.id_attempts משלו, לפורטל יהיה rate limiting
# לפי IP). הספירה של ניסיונות *קוד* כבר מטופלת גנרית בתוך
# utils/otp.py (attempts_used) ומשותפת אוטומטית לשני הצרכנים.
#
# עקרון האבטחה שחוזר בשתי השיטות: היעד שאליו נשלח הקוד תמיד
# נשלף מרשומת הלקוחה במסד, לעולם לא מהקלט של המשתמשת.
# ============================================================

from db import get_session
from models import Client
from managers.client_manager import ClientManager
from utils.otp import create_and_send_otp, verify_otp
from utils.validators import normalize_phone


client_manager = ClientManager()


# תוצאות אפשריות - זהות לשתי השיטות, כדי ששתי השכבות שמעל (chatbot,
# portal) יוכלו לטפל בתגובה באותו אופן בדיוק
RESULT_OK = "ok"
RESULT_WRONG = "wrong"
RESULT_LOCKED = "locked"
RESULT_NO_DATA = "no_data"
RESULT_SEND_FAILED = "send_failed"

# purpose נפרד לכל שיטת כניסה בטבלת otp_codes - כך קוד שנשלח
# לצ'אטבוט לא ניתן למימוש בזרימת הפורטל ולהפך, גם אם איכשהו
# שתי הבקשות התרחשו קרוב זו לזו עבור אותה לקוחה
PURPOSE_CHATBOT_IDENTITY = "identity_verification"
PURPOSE_PORTAL_LOGIN = "portal_login"


def check_national_id(client_id, national_id):
    """
    שלב אימות א' של הצ'אטבוט: תעודת זהות מוכיחה ידע.
    מחזיר True/False בלבד - לא מדליף מידע על הלקוחה.
    """
    if client_id is None:
        return False
    return client_manager.verify_client_national_id(client_id, national_id)


def identify_or_create_shell(full_name, phone):
    """
    Part 4 Step 1 של הפורטל: מזהה לקוחה קיימת לפי טלפון, או יוצרת
    "שלד" (שם+טלפון בלבד, profile_completed_at=NULL) עבור טלפון
    חדש - כי טבלת otp_codes דורשת client_id קיים לפני ששולחים קוד
    (ראו migrations/013). שני המסלולים מבצעים בדיוק אותה רצף
    פעולות מכאן והלאה (שליחת קוד לטלפון שברשומה), כדי שהתשובה
    ל-/identify תהיה זהה-בייט (סעיף 4 במפרט) - הזיהוי עצמו קורה
    כאן, לפני שנשלחת שום תשובה החוצה.

    מחזיר את רשומת הלקוחה (קיימת או חדשה), או None אם הטלפון
    עצמו לא תקין (הקוראת מטפלת בזה כשגיאת קלט רגילה, לא כדליפה -
    טלפון לא תקין אינו שאלה של "האם זו לקוחה קיימת").
    """
    normalized = normalize_phone(phone)
    if normalized is None:
        return None

    existing = client_manager.get_client_by_phone(normalized)
    if existing is not None:
        return existing

    session = get_session()
    shell = Client(full_name=str(full_name).strip() if full_name else "לקוחה חדשה",
                    phone=normalized, profile_completed_at=None)
    session.add(shell)
    session.commit()
    return shell


def is_new_client(client):
    """שלד ממתין להשלמת הרשמה (Part 4 Step 3) - profile_completed_at עדיין NULL."""
    return client.profile_completed_at is None


def find_client_by_phone(phone):
    """
    שלב זיהוי של הפורטל: מאתר לקוחה לפי טלפון מנורמל.
    מחזיר את רשומת הלקוחה או None - הקוראת (api/portal_api.py)
    אחראית להגיב זהה-בייט בשני המקרים (סעיף 4 במפרט), כדי שהמערכת
    לא תהפוך לכלי לבדיקת מי הוא לקוח קיים.
    """
    return client_manager.get_client_by_phone(phone)


def send_otp(client_id, purpose):
    """
    שולח קוד אימות ללקוחה - היעד תמיד נשלף מהרשומה במסד.

    מחזיר צמד (result, masked_destination_or_None).
    """
    client = client_manager.get_client_by_id(client_id)
    if client is None or not client.phone:
        return RESULT_NO_DATA, None

    success, info = create_and_send_otp(client.client_id, client.phone,
                                        channel="phone", purpose=purpose)
    if not success:
        return RESULT_SEND_FAILED, None

    return RESULT_OK, info["masked_destination"]


def confirm_otp(client_id, code, purpose):
    """
    מאמת קוד חד-פעמי שהוזן מול הקוד הפעיל של הלקוחה.

    מחזיר צמד (result, reason) - reason מפורט (ok/no_code/expired/
    too_many_attempts/wrong_code) לצורך לוגיקה פנימית של הקוראת;
    ההודעה שמוצגת למשתמשת נשארת כללית בשכבה שמעל.
    """
    is_valid, reason = verify_otp(client_id, code, purpose=purpose)

    if is_valid:
        return RESULT_OK, reason

    if reason == "too_many_attempts":
        return RESULT_LOCKED, reason

    return RESULT_WRONG, reason
