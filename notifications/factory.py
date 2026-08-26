# ============================================================
# notifications/factory.py
# בוחר את ספק ההתראות הפעיל לפי הגדרות הסביבה.
#
# זו הנקודה היחידה במערכת שיודעת אילו ספקים קיימים.
# שאר הקוד מבקש ספק ומקבל אותו, בלי לדעת מי הוא.
#
# החלפת ערוץ: שינוי NOTIFICATION_PROVIDER בקובץ .env.
# הוספת ערוץ חדש: הוספת שורה למילון שלמטה.
# ============================================================

from config import Config

from notifications.base import NotificationProvider, NotificationError
from notifications.console_provider import ConsoleProvider
from notifications.email_provider import EmailProvider


def _build_console():
    """בונה ספק מסוף."""
    return ConsoleProvider()


def _build_email():
    """בונה ספק דואר אלקטרוני מתוך הגדרות הסביבה."""
    return EmailProvider(
        host=Config.SMTP_HOST,
        port=Config.SMTP_PORT,
        username=Config.SMTP_USERNAME,
        password=Config.SMTP_PASSWORD,
        sender=Config.SMTP_SENDER,
    )


# רישום הספקים הזמינים. להוספת ערוץ חדש מוסיפים כאן שורה
PROVIDER_BUILDERS = {
    "console": _build_console,
    "email": _build_email,
}


def get_notification_provider():
    """
    מחזיר את ספק ההתראות הפעיל.

    אם הספק המבוקש אינו מוכר או אינו מוגדר כראוי, נזרקת
    חריגה מיידית. זה עדיף על נפילה שקטה בזמן שליחה, כי אז
    לקוחה הייתה ממתינה לקוד שלעולם לא יגיע.
    """
    provider_name = (Config.NOTIFICATION_PROVIDER or "console").strip().lower()

    # שכבת בטיחות: ספק המסוף מדפיס קודי אימות לטרמינל,
    # ולכן אסור שיפעל על שרת עם לקוחות אמיתיים
    if Config.IS_PRODUCTION and provider_name == "console":
        raise NotificationError(
            "Console provider is not allowed in production. "
            "Set NOTIFICATION_PROVIDER to a real channel."
        )

    builder = PROVIDER_BUILDERS.get(provider_name)
    if builder is None:
        available = ", ".join(PROVIDER_BUILDERS.keys())
        raise NotificationError(
            f"Unknown notification provider '{provider_name}'. Available: {available}"
        )

    provider = builder()

    if not provider.is_configured():
        raise NotificationError(
            f"Notification provider '{provider_name}' is missing configuration"
        )

    return provider