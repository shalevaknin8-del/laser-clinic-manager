# ============================================================
# api/auth_api.py
# נקודות הקצה של התחברות, רענון טוקן, והתנתקות - גרסת JWT.
#
# זו הקבוצה היחידה במערכת שנשארת פתוחה ללא התחברות (חוץ
# מ-/refresh, /me, /change-password שדורשים טוקן תקף) - אי אפשר
# להתחבר אם צריך להיות מחובר.
#
# שינוי ארכיטקטוני מהגרסה הקודמת (session cookie):
#   - /login לא פותח session בצד השרת, אלא מחזיר זוג טוקנים
#     (access קצר טווח + refresh ארוך טווח) שה-frontend שומר בעצמו.
#   - /refresh מנפיק access token חדש מתוך refresh token תקף.
#   - /logout לא "מוחק session" (אין כזה) - הוא מבטל את כל
#     ה-refresh tokens הקיימים של המשתמשת דרך token_version.
#
# בגלל זה היא גם המטרה המרכזית לניסיונות פריצה,
# ולכן יש עליה הגבלת קצב ונעילה אחרי כישלונות (ראו security_setup.py).
# ============================================================

from flask import Blueprint, jsonify, request

from managers.user_manager import UserManager
from auth.decorators import require_login, get_current_user, get_client_ip, bump_token_version
from auth.jwt_utils import create_token_pair, create_access_token, decode_token, TokenError, TOKEN_TYPE_REFRESH
from auth.permissions import get_permissions_for_role
from api.helpers import json_error
from managers.audit_manager import (
    AuditManager,
    ACTION_LOGIN_SUCCESS,
    ACTION_LOGIN_FAILED,
    ACTION_LOGOUT,
)


auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

user_manager = UserManager()
audit_manager = AuditManager()


def _user_to_dict(user):
    """
    ממיר משתמש למילון לתגובת JSON.
    שדה טביעת האצבע של הסיסמה לא נכלל כאן ולעולם לא ייכלל.
    """
    return {
        "user_id": user.user_id,
        "phone": user.phone,
        "full_name": user.full_name,
        "role": user.role,
        "role_label": user.role_label(),
        "permissions": sorted(get_permissions_for_role(user.role)),
    }


@auth_bp.route("/login", methods=["POST"])
def login():
    """
    מאמת מספר טלפון וסיסמה ומחזיר זוג טוקנים (access + refresh).

    בכישלון מוחזרת הודעה אחידה שאינה מלמדת האם המספר
    רשום במערכת, כדי שלא ניתן יהיה למפות את המשתמשים.
    """
    data = request.get_json(silent=True) or {}

    phone = data.get("phone", "")
    password = data.get("password", "")

    if not phone or not password:
        return json_error("יש להזין מספר טלפון וסיסמה", status_code=400)

    user, reason = user_manager.authenticate(phone, password)

    if user is None:
        # ניסיון כושל מתועד עם סיבת הכישלון ומספר הטלפון,
        # כדי שאפשר יהיה לזהות ניסיון פריצה שיטתי
        audit_manager.log(
            action=ACTION_LOGIN_FAILED,
            details=f"{reason} / {phone}",
            ip_address=get_client_ip(),
        )
        # חשבון נעול מקבל הודעה מפורשת, כי המשתמשת חייבת
        # לדעת שאין טעם להמשיך לנסות באותו רגע
        status_code = 423 if reason == "locked" else 401
        return json_error(user_manager.last_error, status_code=status_code)

    access_token, refresh_token = create_token_pair(user)

    audit_manager.log(
        action=ACTION_LOGIN_SUCCESS,
        user=user,
        ip_address=get_client_ip(),
    )

    return jsonify({
        "success": True,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": _user_to_dict(user),
    })


@auth_bp.route("/refresh", methods=["POST"])
def refresh():
    """
    מנפיק access token חדש מתוך refresh token תקף.

    בודק גם ש-token_version בטוקן תואם לערך העדכני במסד - אם
    בוצעה השבתה, שינוי סיסמה, או logout מאז שהטוקן הונפק, הבקשה
    נדחית גם אם הטוקן עצמו עדיין לא פג מבחינת זמן.
    """
    data = request.get_json(silent=True) or {}
    refresh_token = data.get("refresh_token", "")

    try:
        payload = decode_token(refresh_token, expected_type=TOKEN_TYPE_REFRESH)
    except TokenError:
        return json_error("טוקן רענון לא תקין או פג תוקף", status_code=401)

    user = user_manager.get_user_by_id(int(payload["sub"]))

    if user is None or not user.is_active:
        return json_error("טוקן רענון לא תקין או פג תוקף", status_code=401)

    if payload.get("token_version") != (user.token_version or 0):
        return json_error("טוקן רענון לא תקין או פג תוקף", status_code=401)

    return jsonify({"access_token": create_access_token(user)})


@auth_bp.route("/logout", methods=["POST"])
@require_login
def logout():
    """
    'מתנתק' - מבטל את כל ה-refresh tokens הקיימים של המשתמשת
    (ראו bump_token_version). אין session למחוק בארכיטקטורה הזו;
    access token שכבר הונפק ימשיך להיות תקף עד שיפוג מעצמו
    (עד 30 דקות) - זה משך הזמן המרבי לחשיפה, בדומה לכל מערכת JWT.
    """
    user = get_current_user()

    audit_manager.log(
        action=ACTION_LOGOUT,
        user=user,
        ip_address=get_client_ip(),
    )

    bump_token_version(user)
    return jsonify({"success": True})


@auth_bp.route("/me", methods=["GET"])
@require_login
def get_me():
    """
    מחזיר את המשתמש המחובר ואת היכולות שלו.

    הממשק משתמש בזה כדי להסתיר כפתורים שהמשתמשת אינה
    רשאית להשתמש בהם. חשוב להבין שזו נוחות בלבד ולא אבטחה,
    כי ההרשאה נאכפת בשרת בכל מקרה.
    """
    user = get_current_user()
    return jsonify({
        "authenticated": True,
        "user": _user_to_dict(user),
    })


@auth_bp.route("/change-password", methods=["POST"])
@require_login
def change_password():
    """
    מאפשר למשתמשת לשנות את הסיסמה שלה.
    נדרשת הסיסמה הנוכחית, כדי שמי שהשתלט על מכשיר פתוח
    לא יוכל לנעול את המשתמשת האמיתית מחוץ לחשבון שלה.

    שינוי סיסמה מבטל אוטומטית את כל ה-refresh tokens הקיימים
    (ראו UserManager.set_password) - המשתמשת תצטרך להתחבר מחדש
    בכל מכשיר אחר שבו הייתה מחוברת.
    """
    user = get_current_user()
    data = request.get_json(silent=True) or {}

    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")

    verified, _ = user_manager.authenticate(user.phone, current_password)
    if verified is None:
        return json_error("הסיסמה הנוכחית שגויה", status_code=401)

    if not user_manager.set_password(user.user_id, new_password):
        return json_error(user_manager.last_error, status_code=400)

    return jsonify({"success": True})
