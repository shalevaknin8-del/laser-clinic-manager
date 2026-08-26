# ============================================================
# chatbot/flows.py
# מכונת המצבים של הצ'אטבוט.
#
# לכל מצב שיחה יש handler נפרד. הרישום נעשה במילון
# בתחתית הקובץ, ולכן הוספת יכולת חדשה בעתיד היא
# הוספת פונקציה ורישום שלה, בלי לגעת בקוד קיים.
#
# כל handler מקבל (conversation, message, extracted)
# ומחזיר את הטקסט שיוצג ללקוחה.
# ============================================================

from managers.client_manager import ClientManager
from managers.appointment_manager import AppointmentManager
from managers.treatment_manager import TreatmentManager

from chatbot.nlu import extract_info, extract_national_id, extract_otp_code
from chatbot.state import (
    STATE_START,
    STATE_IDENTIFYING,
    STATE_DISAMBIGUATING,
    STATE_AWAITING_ID,
    STATE_AWAITING_OTP,
    STATE_VERIFIED,
    STATE_LOCKED,
)
from chatbot import verification
from chatbot.verification import (
    RESULT_OK,
    RESULT_WRONG,
    RESULT_LOCKED,
    RESULT_NO_DATA,
    RESULT_SEND_FAILED,
)


client_manager = ClientManager()
appointment_manager = AppointmentManager()
treatment_manager = TreatmentManager()


# תורים בסטטוסים האלה אינם נחשבים תור פעיל
INACTIVE_STATUSES = {"cancelled", "completed"}


# ============================================================
# פונקציות עזר
# ============================================================

def _find_candidates(name):
    """מאתר לקוחות שהשם שלהן תואם."""
    if not name:
        return []
    return client_manager.search_clients_by_name(name)


def _get_active_appointments(client_id):
    """
    מחזיר את התורים הפעילים של לקוחה, ממוינים לפי תאריך.
    תורים שבוטלו או הושלמו אינם נכללים.
    """
    all_appointments = appointment_manager.get_all_appointments()

    active = [
        appointment for appointment in all_appointments
        if appointment.client_id == client_id
        and appointment.status not in INACTIVE_STATUSES
    ]

    active.sort(key=lambda a: (a.appointment_date, a.appointment_time))
    return active


def _format_date(iso_date):
    """ממיר תאריך מפורמט מסד לפורמט קריא בעברית."""
    if not iso_date or len(iso_date) != 10:
        return iso_date
    year, month, day = iso_date.split("-")
    return f"{day}.{month}.{year}"


def _start_verification(conversation, client):
    """
    מעביר את השיחה לשלב בקשת תעודת הזהות.
    שים לב שההודעה אינה חושפת שום פרט על הלקוחה.
    """
    conversation.candidate_client_id = client.client_id
    conversation.state = STATE_AWAITING_ID

    return (
        f"מצאתי אותך במערכת. "
        f"לפני שאוכל להציג פרטים, אני צריך לאמת את הזהות שלך.\n"
        f"מה מספר תעודת הזהות שלך?"
    )


# ============================================================
# ה-handlers
# ============================================================

def handle_start(conversation, message, extracted):
    """מצב פתיחה. מצפה לשם."""
    return handle_identifying(conversation, message, extracted)


def handle_identifying(conversation, message, extracted):
    """
    מאתר את הלקוחה לפי השם שנמסר.
    כשיש כמה התאמות, מבקש הבהרה ואינו מנחש.
    """
    # שמירת מה שהמשתמשת טענה, לצורך השוואה בסוף
    if extracted.claimed_date:
        conversation.claimed_date = extracted.claimed_date
    if extracted.claimed_time:
        conversation.claimed_time = extracted.claimed_time

    if not extracted.name:
        conversation.state = STATE_IDENTIFYING
        return "שלום. איך קוראים לך?"

    candidates = _find_candidates(extracted.name)

    if not candidates:
        conversation.state = STATE_IDENTIFYING
        return (
            f"לא מצאתי במערכת לקוחה בשם {extracted.name}. "
            f"אפשר לנסות שוב עם השם המלא?"
        )

    if len(candidates) == 1:
        return _start_verification(conversation, candidates[0])

    # כמה התאמות. מבקשים הבהרה במקום לנחש
    conversation.candidates = [c.client_id for c in candidates]
    conversation.state = STATE_DISAMBIGUATING

    names = "\n".join(f"  - {c.full_name}" for c in candidates)
    return (
        f"מצאתי כמה לקוחות בשם הזה:\n{names}\n"
        f"אפשר את השם המלא?"
    )


def handle_disambiguating(conversation, message, extracted):
    """
    ממתין לשם מלא כדי לבחור בין כמה מועמדות.
    החיפוש מוגבל לרשימת המועמדות מהשלב הקודם.
    """
    if not extracted.name:
        return "אפשר בבקשה את השם המלא?"

    matches = _find_candidates(extracted.name)

    # רק מועמדות מהרשימה המקורית נחשבות
    narrowed = [c for c in matches if c.client_id in conversation.candidates]

    if len(narrowed) == 1:
        return _start_verification(conversation, narrowed[0])

    if not narrowed:
        conversation.reset_identity()
        conversation.state = STATE_IDENTIFYING
        return "לא מצאתי התאמה לשם הזה. אפשר לנסות שוב?"

    return "עדיין יש כמה התאמות. אפשר את השם המלא במדויק?"


def handle_awaiting_id(conversation, message, extracted):
    """
    ממתין לתעודת זהות.
    המספר מחולץ בקוד ולא נשלח לשום שירות חיצוני.
    """
    national_id = extract_national_id(message)

    if not national_id:
        return "לא זיהיתי מספר תעודת זהות. אפשר להזין אותו שוב?"

    result = verification.verify_identity_document(conversation, national_id)

    if result == RESULT_LOCKED:
        return (
            "חרגת ממספר הניסיונות המותר. "
            "לצורך אבטחת המידע השיחה נחסמה. "
            "אפשר לפנות לקליניקה ישירות."
        )

    if result == RESULT_NO_DATA:
        conversation.reset_identity()
        conversation.state = STATE_IDENTIFYING
        return "משהו השתבש. אפשר להתחיל מחדש עם השם שלך?"

    if result == RESULT_WRONG:
        remaining = 3 - conversation.id_attempts
        return (
            f"מספר תעודת הזהות אינו תואם. "
            f"נותרו {remaining} ניסיונות."
        )

    # תעודת הזהות אומתה. שולחים קוד לטלפון שרשום במערכת
    send_result, masked = verification.send_verification_code(conversation)

    if send_result == RESULT_SEND_FAILED:
        return "לא הצלחתי לשלוח קוד אימות כרגע. אפשר לנסות שוב בעוד רגע?"

    if send_result != RESULT_OK:
        return "לא הצלחתי לשלוח קוד אימות. אפשר לפנות לקליניקה ישירות."

    return (
        f"תעודת הזהות אומתה. "
        f"שלחתי קוד בן 6 ספרות למספר שמסתיים ב-{masked}.\n"
        f"מה הקוד?"
    )


def handle_awaiting_otp(conversation, message, extracted):
    """ממתין לקוד האימות שנשלח לטלפון."""
    code = extract_otp_code(message)

    if not code:
        return "לא זיהיתי קוד בן 6 ספרות. אפשר להזין אותו שוב?"

    result = verification.verify_code(conversation, code)

    if result == RESULT_LOCKED:
        return (
            "חרגת ממספר הניסיונות המותר. "
            "לצורך אבטחת המידע השיחה נחסמה."
        )

    if result == RESULT_WRONG:
        return "הקוד אינו תקין. אפשר לנסות שוב?"

    if result != RESULT_OK:
        return "משהו השתבש באימות. אפשר לפנות לקליניקה ישירות."

    # אומת במלואו. רק עכשיו מותר לחשוף מידע
    return handle_verified(conversation, message, extracted)


def handle_verified(conversation, message, extracted):
    """
    השלב היחיד שבו נחשף מידע.
    הגישה לנתונים עוברת דרך השער, שיזרוק חריגה אם
    השיחה אינה מאומתת במלואה.
    """
    client = verification.get_verified_client(conversation)

    if client is None:
        return "משהו השתבש. אפשר לפנות לקליניקה ישירות."

    appointments = _get_active_appointments(client.client_id)

    if not appointments:
        return (
            f"שלום {client.full_name}, "
            f"לא מצאתי תורים פתוחים על שמך במערכת. "
            f"אפשר לפנות לקליניקה כדי לקבוע תור."
        )

    appointment = appointments[0]
    real_date = _format_date(appointment.appointment_date)
    real_time = appointment.appointment_time

    treatment = treatment_manager.get_treatment_by_id(appointment.treatment_id)
    treatment_name = treatment.treatment_name if treatment else "טיפול"

    # השוואה לתאריך שהמשתמשת טענה
    claimed = conversation.claimed_date
    has_mismatch = claimed and claimed != appointment.appointment_date

    if has_mismatch:
        claimed_readable = _format_date(claimed)
        return (
            f"מצאתי אותך, {client.full_name}.\n"
            f"שימי לב: התור שלך בפועל הוא ב-{real_date} בשעה {real_time} "
            f"({treatment_name}), ולא ב-{claimed_readable} כפי שציינת."
        )

    return (
        f"מצאתי אותך, {client.full_name}.\n"
        f"התור שלך הוא ב-{real_date} בשעה {real_time} ({treatment_name})."
    )


def handle_locked(conversation, message, extracted):
    """שיחה נעולה. אין דרך חזרה בלי להתחיל מחדש."""
    return (
        "השיחה נחסמה מטעמי אבטחת מידע. "
        "אפשר לפנות לקליניקה ישירות."
    )


# ============================================================
# רישום ה-handlers
# הוספת מצב חדש בעתיד היא הוספת שורה כאן בלבד
# ============================================================

STATE_HANDLERS = {
    STATE_START: handle_start,
    STATE_IDENTIFYING: handle_identifying,
    STATE_DISAMBIGUATING: handle_disambiguating,
    STATE_AWAITING_ID: handle_awaiting_id,
    STATE_AWAITING_OTP: handle_awaiting_otp,
    STATE_VERIFIED: handle_verified,
    STATE_LOCKED: handle_locked,
}


def process_message(conversation, message):
    """
    נקודת הכניסה היחידה של הצ'אטבוט.

    מנתבת את ההודעה ל-handler המתאים למצב הנוכחי.
    כל תקלה בלתי צפויה נתפסת כאן, כדי שהבוט לא יחשוף
    פרטי שגיאה פנימיים ללקוחה.
    """
    extracted = extract_info(message)

    handler = STATE_HANDLERS.get(conversation.state, handle_start)

    try:
        return handler(conversation, message, extracted)

    except verification.NotVerifiedError:
        # השער עצר גישה לא מורשית. זו הגנה שעבדה
        conversation.reset_identity()
        conversation.state = STATE_IDENTIFYING
        return "משהו השתבש בתהליך האימות. אפשר להתחיל מחדש עם השם שלך?"

    except Exception:
        return "משהו השתבש. אפשר לנסות שוב בעוד רגע?"