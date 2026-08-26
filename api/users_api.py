# ============================================================
# api/users_api.py
# ניהול משתמשי המערכת ויומן הפעולות.
#
# כל נקודות הקצה כאן מוגבלות למנהל בלבד.
#
# הערה: אין כאן מחיקת משתמש. עובדת שעוזבת מושבתת,
# כדי שרשומות היומן שלה יישארו מקושרות לשם אמיתי.
# ============================================================

from flask import Blueprint, jsonify, request

from managers.user_manager import UserManager
from managers.audit_manager import AuditManager, ACTION_CREATE, ACTION_UPDATE
from entities.user import VALID_ROLES, ROLE_LABELS

from auth.decorators import require_permission, get_current_user, get_client_ip
from auth.permissions import USER_MANAGE, AUDIT_VIEW
from api.helpers import json_error


users_bp = Blueprint("users", __name__, url_prefix="/api/users")

user_manager = UserManager()
audit_manager = AuditManager()


def _user_to_dict(user):
    """
    ממיר משתמש למילון לתגובת JSON.
    טביעת האצבע של הסיסמה לא נכללת כאן ולעולם לא תיכלל.
    """
    return {
        "user_id": user.user_id,
        "phone": user.phone,
        "full_name": user.full_name,
        "role": user.role,
        "role_label": user.role_label(),
        "is_active": bool(user.is_active),
        "is_locked": user.is_locked(),
        "last_login_at": user.last_login_at,
    }


@users_bp.route("", methods=["GET"])
@require_permission(USER_MANAGE)
def get_users():
    """מחזיר את כל משתמשי המערכת, כולל מושבתים."""
    users = user_manager.get_all_users()
    return jsonify({
        "users": [_user_to_dict(user) for user in users],
        "roles": [{"value": r, "label": ROLE_LABELS[r]} for r in VALID_ROLES],
    })


@users_bp.route("", methods=["POST"])
@require_permission(USER_MANAGE)
def create_user():
    """יוצר משתמש חדש, בדרך כלל עובדת חדשה בקליניקה."""
    data = request.get_json(silent=True) or {}

    new_user = user_manager.create_user(
        phone=data.get("phone"),
        password=data.get("password"),
        full_name=data.get("full_name"),
        role=data.get("role", "employee"),
    )

    if new_user is None:
        return json_error(user_manager.last_error, status_code=400)

    audit_manager.log(
        action=ACTION_CREATE,
        user=get_current_user(),
        entity_type="user",
        entity_id=new_user.user_id,
        details=f"role={new_user.role}",
        ip_address=get_client_ip(),
    )

    return jsonify(_user_to_dict(new_user)), 201


@users_bp.route("/<int:user_id>/password", methods=["POST"])
@require_permission(USER_MANAGE)
def reset_user_password(user_id):
    """
    מאפס סיסמה של משתמש.
    המנהלת אינה רואה את הסיסמה הישנה, היא רק קובעת חדשה.
    """
    data = request.get_json(silent=True) or {}

    if not user_manager.set_password(user_id, data.get("new_password")):
        return json_error(user_manager.last_error, status_code=400)

    audit_manager.log(
        action=ACTION_UPDATE,
        user=get_current_user(),
        entity_type="user",
        entity_id=user_id,
        details="password reset",
        ip_address=get_client_ip(),
    )

    return jsonify({"success": True})


@users_bp.route("/<int:user_id>/active", methods=["POST"])
@require_permission(USER_MANAGE)
def set_user_active(user_id):
    """
    מפעיל או משבית משתמש.

    שתי הגנות מובנות: מנהלת אינה יכולה להשבית את עצמה,
    ואי אפשר להשבית את המנהלת הפעילה האחרונה. בלי ההגנות
    האלה אפשר להגיע למצב שבו איש אינו יכול לנהל את המערכת.
    """
    data = request.get_json(silent=True) or {}
    is_active = bool(data.get("is_active", True))

    current_user = get_current_user()

    if not is_active and current_user.user_id == user_id:
        return json_error("לא ניתן להשבית את המשתמש שלך", status_code=400)

    target_user = user_manager.get_user_by_id(user_id)
    if target_user is None:
        return json_error("המשתמש לא נמצא", status_code=404)

    if not is_active and target_user.is_admin():
        if user_manager.count_active_admins() <= 1:
            return json_error("לא ניתן להשבית את המנהל האחרון", status_code=400)

    if not user_manager.set_active(user_id, is_active):
        return json_error(user_manager.last_error, status_code=400)

    audit_manager.log(
        action=ACTION_UPDATE,
        user=current_user,
        entity_type="user",
        entity_id=user_id,
        details=f"is_active={is_active}",
        ip_address=get_client_ip(),
    )

    return jsonify({"success": True})


@users_bp.route("/audit", methods=["GET"])
@require_permission(AUDIT_VIEW)
def get_audit_log():
    """מחזיר את רשומות היומן האחרונות."""
    limit = request.args.get("limit", "100")
    limit = int(limit) if limit.isdigit() else 100
    limit = min(limit, 500)

    return jsonify({"entries": audit_manager.get_recent(limit)})