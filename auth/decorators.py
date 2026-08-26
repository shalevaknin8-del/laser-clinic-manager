# ============================================================
# auth/decorators.py
# אכיפת הרשאות על נקודות הקצה.
#
# זו הנקודה היחידה במערכת שמחליטה אם בקשה מותרת.
# אין ואסור שיהיו בדיקות הרשאה מפוזרות בתוך ה-routes.
#
# שימוש:
#   @require_login
#   @require_permission(CLIENT_DELETE)
# ============================================================

from functools import wraps

from flask import session, jsonify, g

from managers.user_manager import UserManager
from auth.permissions import get_permissions_for_role
from managers.audit_manager import AuditManager, ACTION_PERMISSION_DENIED


user_manager = UserManager()
audit_manager = AuditManager()


def get_client_ip():
    """
    מחזיר את כתובת ה-IP של הפונה.
    מאחורי proxy כמו nginx, הכתובת האמיתית מגיעה בכותרת
    X-Forwarded-For ולא בשדה remote_addr.
    """
    from flask import request

    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr

# מפתח מזהה המשתמש בתוך העוגייה החתומה
SESSION_USER_KEY = "user_id"


def get_current_user():
    """
    מחזיר את המשתמש המחובר, או None אם אין כזה.

    המשתמש נשלף מחדש מהמסד בכל בקשה ולא נשמר בעוגייה.
    כך שינוי הרשאות או השבתת עובדת נכנסים לתוקף מיידית,
    ולא רק אחרי שהיא תתנתק.

    התוצאה נשמרת ב-g למשך הבקשה הנוכחית בלבד, כדי שלא
    נפנה למסד כמה פעמים באותה בקשה.
    """
    if hasattr(g, "current_user"):
        return g.current_user

    user_id = session.get(SESSION_USER_KEY)
    if user_id is None:
        g.current_user = None
        return None

    user = user_manager.get_user_by_id(user_id)

    # משתמשת שהושבתה מאבדת גישה מיידית, גם אם העוגייה תקפה
    if user is not None and not user.is_active:
        user = None

    g.current_user = user
    return user


def require_login(view_function):
    """
    חוסם גישה למי שאינו מחובר.
    מוחזר קוד 401 ולא הפניה, כי הפונקציות כאן מחזירות JSON.
    """
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

        if not user.is_admin():
            return jsonify({"error": "אין לך הרשאה לבצע פעולה זו"}), 403

        return view_function(*args, **kwargs)

    return wrapper


def login_user(user):
    """
    שומר את המשתמש בעוגיית ה-session.
    נשמר רק המזהה. כל שאר הפרטים נשלפים מהמסד בכל בקשה.
    """
    session.clear()
    session[SESSION_USER_KEY] = user.user_id
    session.permanent = True
    g.current_user = user


def logout_user():
    """מנקה את ה-session לחלוטין."""
    session.clear()
    if hasattr(g, "current_user"):
        g.current_user = None