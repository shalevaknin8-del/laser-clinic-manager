# ============================================================
# chatbot/schemas.py
# מבנה הנתונים שמנוע השפה מחזיר.
#
# הסכימה הזו משרתת שתי מטרות בו זמנית:
#   1. אכיפה על המודל להחזיר פורמט קבוע וניתן לפרסור
#   2. הגנה מפני הזרקת הוראות, כי כל שדה שאינו מוגדר
#      כאן פשוט נזרק ולא מגיע ללוגיקה שלנו
#
# שים לב: אין כאן שדה לתעודת זהות, ולא במקרה.
# תעודת זהות מחולצת בקוד ולא נשלחת למודל חיצוני.
#
# requested_treatment (שלב 4, קביעת תור מהצ'אט): המודל רק מציע
# שם טיפול "כמו שנשמע" - ההתאמה בפועל מול קטלוג הטיפולים האמיתי
# היא דטרמיניסטית לגמרי (ראו chatbot/flows.py), כדי שהמודל לעולם
# לא "יחליט" איזה טיפול או תור בפועל נקבע.
# ============================================================

from typing import Optional
from pydantic import BaseModel, Field


class ExtractedInfo(BaseModel):
    """
    המידע שחולץ מהודעה חופשית של המשתמשת.
    כל השדות אופציונליים, כי הודעה יכולה להכיל רק חלק מהם.
    """

    name: Optional[str] = Field(
        default=None,
        description="שם הלקוחה כפי שהופיע בהודעה, פרטי או מלא",
    )

    claimed_date: Optional[str] = Field(
        default=None,
        description="התאריך שהמשתמשת טענה או ביקשה, בפורמט YYYY-MM-DD",
    )

    claimed_time: Optional[str] = Field(
        default=None,
        description="השעה שהמשתמשת טענה או ביקשה, בפורמט HH:MM",
    )

    requested_treatment: Optional[str] = Field(
        default=None,
        description="שם הטיפול שהמשתמשת ביקשה לקבוע, כפי שהופיע בהודעה",
    )

    intent: Optional[str] = Field(
        default=None,
        description=(
            "כוונת ההודעה. אחד מהערכים: check_appointment לבירור תור, "
            "book_appointment לבקשת קביעת תור חדש, provide_name למסירת שם, "
            "confirm לאישור, deny לשלילה, other לכל דבר אחר"
        ),
    )


# הכוונות המוכרות. כל ערך אחר שיחזור מהמודל ייחשב other
VALID_INTENTS = [
    "check_appointment",
    "book_appointment",
    "provide_name",
    "confirm",
    "deny",
    "other",
]


def sanitize_extracted(data):
    """
    מנקה ומאמת את המידע שחזר מהמודל.

    זו שכבת ההגנה האחרונה לפני שהמידע נכנס ללוגיקה.
    היא מבטיחה שגם אם המודל יחזיר משהו לא צפוי, בין אם
    בגלל תקלה ובין אם בגלל ניסיון הזרקת הוראות בהודעה,
    מה שיעבור הלאה יהיה תמיד בפורמט מוכר ומוגבל.
    """
    if data is None:
        return ExtractedInfo()

    name = data.get("name")
    if name is not None:
        name = str(name).strip()
        # שם ארוך מדי אינו שם, אלא כנראה טקסט שהוזרק
        if not name or len(name) > 60:
            name = None

    claimed_date = data.get("claimed_date")
    if claimed_date is not None:
        claimed_date = str(claimed_date).strip()
        # פורמט קשיח: עשרה תווים בדיוק בתבנית תאריך
        if len(claimed_date) != 10 or claimed_date.count("-") != 2:
            claimed_date = None

    claimed_time = data.get("claimed_time")
    if claimed_time is not None:
        claimed_time = str(claimed_time).strip()
        if len(claimed_time) != 5 or ":" not in claimed_time:
            claimed_time = None

    requested_treatment = data.get("requested_treatment")
    if requested_treatment is not None:
        requested_treatment = str(requested_treatment).strip()
        if not requested_treatment or len(requested_treatment) > 60:
            requested_treatment = None

    intent = data.get("intent")
    if intent not in VALID_INTENTS:
        intent = "other"

    return ExtractedInfo(
        name=name,
        claimed_date=claimed_date,
        claimed_time=claimed_time,
        requested_treatment=requested_treatment,
        intent=intent,
    )
