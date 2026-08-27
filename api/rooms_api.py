# ============================================================
# api/rooms_api.py
# ניהול חדרי הטיפול - משאב ראשון באילוץ הזימון החכם התלת-כיווני.
# ============================================================

from flask import Blueprint, jsonify, request

from managers.room_manager import RoomManager
from auth.decorators import get_current_user, require_permission
from auth.permissions import ROOM_MANAGE
from api.helpers import json_error, room_to_dict


rooms_bp = Blueprint("rooms", __name__, url_prefix="/api/rooms")

room_manager = RoomManager()


@rooms_bp.before_request
def require_authenticated_user():
    if get_current_user() is None:
        return jsonify({"error": "נדרשת התחברות למערכת"}), 401


@rooms_bp.route("", methods=["GET"])
def get_rooms():
    """מחזיר את כל החדרים - כולל לא-פעילים, לצורך תצוגה בהיסטוריה."""
    rooms = room_manager.get_all_rooms()
    return jsonify([room_to_dict(room) for room in rooms])


@rooms_bp.route("", methods=["POST"])
@require_permission(ROOM_MANAGE)
def create_room():
    """מוסיף חדר חדש. הקמת חדרים היא החלטה ניהולית - שמורה למנהלת."""
    data = request.get_json(silent=True) or {}
    room = room_manager.create_room(data.get("name"))
    if room is None:
        return json_error(room_manager.last_error, status_code=400)
    return jsonify(room_to_dict(room)), 201


@rooms_bp.route("/<int:room_id>/active", methods=["POST"])
@require_permission(ROOM_MANAGE)
def set_room_active(room_id):
    """מפעיל/משבית חדר (למשל חדר בשיפוץ) - לא מוחק, כדי לשמר היסטוריית תורים."""
    data = request.get_json(silent=True) or {}
    is_active = bool(data.get("is_active", True))

    if not room_manager.set_active(room_id, is_active):
        return json_error(room_manager.last_error, status_code=404)
    return jsonify({"success": True})
