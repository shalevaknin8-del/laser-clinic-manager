# ============================================================
# security_setup.py
# הקשחת אבטחה ברמת האפליקציה.
#
# מרכז שתי הגנות שחלות על כל הבקשות:
#   1. הגבלת קצב, נגד ניחוש סיסמאות וקודים ונגד הצפה
#   2. כותרות אבטחה, נגד מתקפות מצד הדפדפן
#
# הקובץ מופרד מ-app.py כדי שההגדרות יהיו במקום אחד
# ולא מפוזרות בתוך קוד יצירת האפליקציה.
# ============================================================

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import Config


def setup_rate_limiting(app):
    """
    מגדיר הגבלת קצב לפי כתובת IP.

    המגבלות מכוונות לרף שמשתמשת אמיתית לעולם לא תחצה,
    אך חוסם ניסיונות אוטומטיים.
    """
    limiter = Limiter(
        get_remote_address,
        app=app,
        # מגבלה כללית רחבה, כרשת ביטחון בלבד
        default_limits=["300 per hour"],
        storage_uri="memory://",
        strategy="fixed-window",
    )

    return limiter


def setup_security_headers(app):
    """
    מוסיף כותרות אבטחה לכל תגובה.
    הכותרות מנחות את הדפדפן להתנהג בזהירות עם התוכן.
    """

    @app.after_request
    def apply_security_headers(response):
        # מונע מהדפדפן לנחש סוג קובץ בניגוד למה שהצהרנו
        response.headers["X-Content-Type-Options"] = "nosniff"

        # מונע הטמעת האתר בתוך אתר אחר, הגנה מפני clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # מגביל את המידע שנשלח לאתרים חיצוניים בעת מעבר
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # מגדיר מאילו מקורות מותר לטעון תוכן.
        # unsafe-inline נדרש כי הסגנונות והסקריפטים משובצים
        # בתוך קבצי ה-HTML ולא בקבצים נפרדים
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'"
        )

        # מחייב HTTPS למשך שנה. מופעל בפרודקשן בלבד,
        # כי בפיתוח מקומי אין תעודה והדפדפן היה חוסם את האתר
        if Config.IS_PRODUCTION:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        return response


# מגבלות ייעודיות לנקודות קצה רגישות.
# הפורמט: נתיב מלא -> מגבלה
SENSITIVE_ENDPOINT_LIMITS = {
    # התחברות: היעד המרכזי לניחוש סיסמאות
    "/api/auth/login": "10 per minute",

    # שיחת הצ'אטבוט: מכילה ניחוש תעודת זהות וקוד אימות
    "/api/chat": "20 per minute",

    # שליחת קוד אימות: מונע הצפת לקוחה בהודעות
    "/api/verification/send-code": "5 per minute",
    "/api/verification/verify-code": "10 per minute",
    "/api/verification/national-id": "10 per minute",
}


def apply_security(app):
    """מפעיל את כל הקשחות האבטחה על האפליקציה."""
    setup_security_headers(app)
    limiter = setup_rate_limiting(app)

    # החלת המגבלות הייעודיות אחרי שכל ה-routes נרשמו.
    # הגישה דרך מפת ה-routes ולא דרך דקורטורים מונעת
    # ייבוא מעגלי בין קבצי ה-API לקובץ הזה
    for rule in app.url_map.iter_rules():
        limit = SENSITIVE_ENDPOINT_LIMITS.get(str(rule.rule))
        if limit:
            view_function = app.view_functions[rule.endpoint]
            app.view_functions[rule.endpoint] = limiter.limit(limit)(view_function)

    return limiter