# ============================================================
# api/auth_api.py
# נקודות הקצה של התחברות והתנתקות.
#
# זו הקבוצה היחידה במערכת שנשארת פתוחה ללא התחברות,
# מסיבה מובנת: אי אפשר להתחבר אם צריך להיות מחובר.
#
# בגלל זה היא גם המטרה המרכזית לניסיונות פריצה,
# ולכן יש עליה הגבלת קצב ונעילה אחרי כישלונות.
# ============================================================

from flask import Blueprint, jsonify, request

from managers.user_manager import UserManager
from auth.decorators import login_user, logout_user, get_current_user, require_login
from auth.permissions import get_permissions_for_role
from api.helpers import json_error
from managers.audit_manager import (
    AuditManager,
    ACTION_LOGIN_SUCCESS,
    ACTION_LOGIN_FAILED,
    ACTION_LOGOUT,
)
from auth.decorators import get_client_ip


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
    מאמת מספר טלפון וסיסמה ופותח session.

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

    login_user(user)

    audit_manager.log(
        action=ACTION_LOGIN_SUCCESS,
        user=user,
        ip_address=get_client_ip(),
    )

    return jsonify({
        "success": True,
        "user": _user_to_dict(user),
    })


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """סוגר את ה-session הנוכחי."""
    user = get_current_user()

    if user is not None:
        audit_manager.log(
            action=ACTION_LOGOUT,
            user=user,
            ip_address=get_client_ip(),
        )

    logout_user()
    return jsonify({"success": True})
def get_me():
    """
    מחזיר את המשתמש המחובר ואת היכולות שלו.

    הממשק משתמש בזה כדי להסתיר כפתורים שהמשתמשת אינה
    רשאית להשתמש בהם. חשוב להבין שזו נוחות בלבד ולא אבטחה,
    כי ההרשאה נאכפת בשרת בכל מקרה.
    """
    user = get_current_user()

    if user is None:
        return jsonify({"authenticated": False}), 401

    return jsonify({
        "authenticated": True,
        "user": _user_to_dict(user),
    })


@auth_bp.route("/change-password", methods=["POST"])
@require_login
def change_password():
    """
    מאפשר למשתמשת לשנות את הסיסמה שלה.
    נדרשת הסיסמה הנוכחית, כדי שמי שהשתלט על מחשב פתוח
    לא יוכל לנעול את המשתמשת האמיתית מחוץ לחשבון שלה.
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