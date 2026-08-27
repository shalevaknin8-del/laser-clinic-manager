# ============================================================
# utils/datetime_utils.py
# נקודת המרכוז היחידה לכל חישוב זמן במערכת, עם אזור זמן מפורש
# Asia/Jerusalem.
#
# למה זה קריטי: כל התאריכים/שעות במערכת נשמרים כמחרוזות "naive"
# (בלי אזור זמן), וכל חישוב "כמה שעות נשארו" שנעשה עד היום בכל
# קובץ בנפרד (chatbot, appointment_manager, otp...) הניח בלי
# להגיד את זה בקול שהשעון המקומי הוא תמיד ישראל. זה עובד 363
# ימים בשנה ונשבר פעמיים - במעבר לשעון קיץ/חורף - כי ההפרש בין
# UTC למקומי משתנה. באג שקשה לשחזר כי הוא תלוי בתאריך ההרצה.
#
# הכלל: כל שאר הקוד עובד רק עם התאריך/שעה "כמו שרואים על הקיר"
# (מחרוזות "YYYY-MM-DD"/"HH:MM", בדיוק כמו שהיה קודם) ועם
# datetime מודע-אזור (aware) שיוצא רק מכאן. אף קובץ אחר לא קורא
# ל-datetime.now() או ל-zoneinfo ישירות.
# ============================================================

from datetime import datetime, timedelta, date, time as time_cls
from zoneinfo import ZoneInfo

JERUSALEM_TZ = ZoneInfo("Asia/Jerusalem")

DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M"


def now_jerusalem():
    """הרגע הנוכחי, מודע לאזור הזמן של ישראל. נקודת הכניסה היחידה ל'עכשיו'."""
    return datetime.now(JERUSALEM_TZ)


def today_jerusalem():
    """התאריך של היום, לפי השעון בישראל (לא לפי UTC של השרת)."""
    return now_jerusalem().date()


def combine_local(date_str, time_str):
    """
    הופך תאריך+שעה כפי שנשמרים במערכת ("YYYY-MM-DD"+"HH:MM")
    ל-datetime מודע-אזור בישראל. זו נקודת הכניסה מ"מחרוזות" ל"זמן אמיתי".
    """
    naive = datetime.strptime(f"{date_str} {time_str}", f"{DATE_FORMAT} {TIME_FORMAT}")
    return naive.replace(tzinfo=JERUSALEM_TZ)


def to_date_str(value):
    """ממיר date/datetime למחרוזת "YYYY-MM-DD", כמו שהעמודות במסד מצפות."""
    if isinstance(value, datetime):
        value = value.date()
    return value.strftime(DATE_FORMAT)


def to_time_str(value):
    """ממיר time/datetime למחרוזת "HH:MM", כמו שהעמודות במסד מצפות."""
    if isinstance(value, datetime):
        value = value.time()
    return value.strftime(TIME_FORMAT)


def parse_date_str(date_str):
    """הופך "YYYY-MM-DD" לאובייקט date. זורק ValueError על פורמט לא תקין."""
    return datetime.strptime(date_str, DATE_FORMAT).date()


def parse_time_str(time_str):
    """הופך "HH:MM" לאובייקט time. זורק ValueError על פורמט לא תקין."""
    return datetime.strptime(time_str, TIME_FORMAT).time()


def day_of_week(date_str):
    """
    מחזיר את יום השבוע לפי המוסכמה הקיימת במערכת: 0=שני ... 6=ראשון
    (עקבי עם StaffAvailability.day_of_week ועם date.weekday() של פייתון).
    """
    return parse_date_str(date_str).weekday()


def is_in_past(date_str, time_str):
    """בודק האם תאריך+שעה נתונים כבר חלפו, ביחס לרגע האמיתי הנוכחי בישראל."""
    return combine_local(date_str, time_str) < now_jerusalem()


def hours_until(date_str, time_str):
    """
    מספר השעות (עשרוני, יכול להיות שלילי) מעכשיו ועד לתאריך+שעה נתונים.
    משמש לבדיקות כמו min_hours_before_booking ו-cancellation_deadline_hours -
    שתיהן דורשות הפרש אמיתי, לא הפרש נאיבי של timedelta על מחרוזות.
    """
    delta = combine_local(date_str, time_str) - now_jerusalem()
    return delta.total_seconds() / 3600


def add_minutes(date_str, time_str, minutes):
    """מוסיף דקות לתאריך+שעה נתונים ומחזיר צמד ("YYYY-MM-DD", "HH:MM") חדש."""
    result = combine_local(date_str, time_str) + timedelta(minutes=minutes)
    return to_date_str(result), to_time_str(result)


def expires_at_iso(minutes_from_now):
    """
    מחזיר חותמת תפוגה (ISO, מודעת-אזור) בעוד X דקות מעכשיו - לשימוש
    בעמודות expires_at (slot_reservations, otp_codes וכו').
    """
    return (now_jerusalem() + timedelta(minutes=minutes_from_now)).isoformat()


def has_expired(expires_at_str):
    """
    בודק האם חותמת תפוגה שמורה (ISO) כבר חלפה. תומך גם בחותמות ישנות
    שנשמרו בלי אזור זמן (naive) - אלה מפורשות כזמן מקומי ישראלי,
    כדי לא לשבור רשומות שנוצרו לפני המעבר למודול הזה.
    """
    parsed = datetime.fromisoformat(expires_at_str)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=JERUSALEM_TZ)
    return now_jerusalem() > parsed
