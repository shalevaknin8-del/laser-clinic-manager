"""
מודול ההגדרות המרכזי של המערכת.
קורא את כל ההגדרות מקובץ .env ונכשל מיידית אם חסר ערך קריטי.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# נתיב הבסיס של הפרויקט, מחושב יחסית למיקום הקובץ הזה
BASE_DIR = Path(__file__).resolve().parent

# טעינת קובץ הסביבה. הקובץ הזה לא נכנס לגיט ומכיל סודות
load_dotenv(BASE_DIR / ".env")


class ConfigError(Exception):
    """חריגה שנזרקת כאשר ההגדרות חסרות או שגויות."""


def _get_required(key):
    """
    מחזיר ערך חובה מהסביבה.
    אם הערך חסר, זורק שגיאה במקום להחזיר ברירת מחדל מסוכנת.
    """
    value = os.getenv(key)
    if not value:
        raise ConfigError(f"Missing required environment variable: {key}")
    return value


def _get_bool(key, default=False):
    """ממיר ערך טקסט מהסביבה לערך בוליאני."""
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


class Config:
    """כל הגדרות המערכת במקום אחד."""

    # ---------- סביבת הרצה ----------
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    IS_PRODUCTION = ENVIRONMENT == "production"

    # ---------- אבטחה ----------
    # המפתח שאיתו נחתמות העוגיות. חובה, ואין לו ברירת מחדל בכוונה
    SECRET_KEY = _get_required("SECRET_KEY")

    # ---------- מסד נתונים ----------
    DATABASE_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "clinic.db"))

    # ---------- מנוע הבנת השפה ----------
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.7-flash")

    # כתובת ה-API הפנימי שהצ'אטבוט פונה אליה
    INTERNAL_API_BASE_URL = os.getenv("INTERNAL_API_BASE_URL", "http://127.0.0.1:8000")

    # ---------- מדיניות אימות ----------
    # מספר הניסיונות המותר להזנת תעודת זהות לפני חסימת השיחה
    MAX_VERIFICATION_ATTEMPTS = int(os.getenv("MAX_VERIFICATION_ATTEMPTS", "3"))
    SESSION_TIMEOUT_MINUTES = int(os.getenv("SESSION_TIMEOUT_MINUTES", "15"))

    # ---------- הגדרות עוגיות ----------
    # חוסם גישה לעוגייה מקוד JavaScript, הגנה מפני גניבת session
    SESSION_COOKIE_HTTPONLY = True

    # מונע שליחת העוגייה מאתרים חיצוניים, הגנה בסיסית מפני CSRF
    SESSION_COOKIE_SAMESITE = "Lax"

    # שליחת העוגייה רק דרך HTTPS. נדלק אוטומטית בפרודקשן בלבד
    SESSION_COOKIE_SECURE = IS_PRODUCTION

    # מצב דיבאג מכובה אוטומטית בפרודקשן
    DEBUG = _get_bool("DEBUG", default=not IS_PRODUCTION)

    @classmethod
    def validate(cls):
        """
        בודק את תקינות ההגדרות בעת עליית המערכת.
        עדיף שהמערכת תיפול עכשיו מאשר שתרוץ עם הגדרות מסוכנות.
        """
        errors = []

        # מצב דיבאג בפרודקשן חושף את קוד המקור ומאפשר הרצת קוד מרחוק
        if cls.IS_PRODUCTION and cls.DEBUG:
            errors.append("DEBUG must be disabled in production")

        if cls.IS_PRODUCTION and len(cls.SECRET_KEY) < 32:
            errors.append("SECRET_KEY is too short for production")

        if cls.MAX_VERIFICATION_ATTEMPTS < 1:
            errors.append("MAX_VERIFICATION_ATTEMPTS must be at least 1")

        if errors:
            raise ConfigError(" | ".join(errors))

        return True