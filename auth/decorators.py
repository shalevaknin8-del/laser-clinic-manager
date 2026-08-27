# ============================================================
# auth/decorators.py
# אכיפת הרשאות על נקודות הקצה - גרסת JWT.
#
# זו הנקודה היחידה במערכת שמחליטה אם בקשה מותרת.
# אין ואסור שיהיו בדיקות הרשאה מפוזרות בתוך ה-routes.
#
# שינוי מהגרסה הקודמת (session cookie): המשתמשת המחוברת מזוהה
# עכשיו מתוך כותרת "Authorization: Bearer <access_token>" ולא
# מעוגיית session. זו הדרישה הבסיסית של ארכיטקטורה headless -
# frontend נפרד (React/Next) לא יכול לשמור session בצד השרת.
#
# שימוש (ללא שינוי מבחינת מי שכותב route):
#   @require_login
#   @require_permission(CLIENT_DELETE)
# ============================================================

from functools import wraps

from flask import request, jsonify, g

from db import get_session
from models import User
from auth.jwt_utils import decode_token, TokenError, TOKEN_TYPE_ACCESS
from auth.permissions import get_permissions_for_role
from managers.audit_manager import AuditManager, ACTION_PERMISSION_DENIED


audit_manager = AuditManager()


def get_client_ip():
    """
    מחזיר את כתובת ה-IP של הפונה.
    מאחורי proxy כמו nginx, הכתובת האמיתית מגיעה בכותרת
    X-Forwarded-For ולא בשדה remote_addr.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr


def _extract_bearer_token():
    """שולף את הטוקן מכותרת Authorization, בפורמט 'Bearer <token>'."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    return header[len("Bearer "):].strip()


def get_current_user():
    """
    מחזיר את המשתמשת המחוברת (לפי ה-access token בכותרת), או None.

    המשתמשת נשלפת מחדש מה-DB בכל בקשה ולא נשמרת בטוקן עצמו -
    כך השבתת עובדת נכנסת לתוקף מיידית, גם אם ה-access token
    שלה עדיין "בתוקף" מבחינת זמן. התוצאה נשמרת ב-g למשך הבקשה
    הנוכחית בלבד, כדי שלא נפנה למסד כמה פעמים באותה בקשה.
    """
    if hasattr(g, "current_user"):
        return g.current_user

    token = _extract_bearer_token()
    if token is None:
        g.current_user = None
        return None

    try:
        payload = decode_token(token, expected_type=TOKEN_TYPE_ACCESS)
    except TokenError:
        g.current_user = None
        return None

    session = get_session()
    user = session.get(User, int(payload["sub"]))

    # משתמשת שהושבתה מאבדת גישה מיידית, גם אם הטוקן חתום ותקף
    if user is not None and not user.is_active:
        user = None

    g.current_user = user
    return user


def require_login(view_function):
    """חוסם גישה למי שאינו מחובר (טוקן חסר/פג/לא תקף/משתמשת מושבתת)."""
    @wraps(view_function)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return jsonify({"error": "נדרשת התחברות למערכת"}), 401
        return view_function(*args, **kwargs)

    return wrapper


def require_permission(permission):
    """
    חוסם גישה למי שאין לו את היכולת הנדרשת.
    כולל בתוכו גם את בדיקת ההתחברות.
    """
    def decorator(view_function):
        @wraps(view_function)
        def wrapper(*args, **kwargs):
            user = get_current_user()

            if user is None:
                return jsonify({"error": "נדרשת התחברות למערכת"}), 401

            if permission not in get_permissions_for_role(user.role):
                # ניסיון חריגה מהרשאות מתועד ביומן. זה מאפשר
                # לזהות גם טעות בהגדרות וגם ניסיון שימוש לרעה
                audit_manager.log(
                    action=ACTION_PERMISSION_DENIED,
                    user=user,
                    details=permission,
                    ip_address=get_client_ip(),
                )
                # ההודעה לא מפרטת איזו יכולת חסרה, כדי לא
                # לחשוף את מבנה ההרשאות הפנימי של המערכת
                return jsonify({"error": "אין לך הרשאה לבצע פעולה זו"}), 403

            return view_function(*args, **kwargs)

        return wrapper

    return decorator


def require_admin(view_function):
    """קיצור נוח לפעולות שמיועדות למנהל בלבד."""
    @wraps(view_function)
    def wrapper(*args, **kwargs):
        user = get_current_user()

        if user is None:
            return jsonify({"error": "נדרשת התחברות למערכת"}), 401

        if user.role != "admin":
            return jsonify({"error": "אין לך הרשאה לבצע פעולה זו"}), 403

        return view_function(*args, **kwargs)

    return wrapper


def bump_token_version(user):
    """
    מעלה את token_version של המשתמשת ב-1, ובכך מבטלת מיידית כל
    refresh token קודם שהונפק לה (logout יזום, שינוי סיסמה, או
    השבתה). לא דורש טבלת session/blacklist נפרדת - ראו auth/jwt_utils.py.
    """
    session = get_session()
    user.token_version = (user.token_version or 0) + 1
    session.add(user)
    session.commit()
