# ============================================================
# api/machines_api.py
# ניהול מכשירי הלייזר - משאב שני באילוץ הזימון החכם התלת-כיווני.
# ============================================================

from flask import Blueprint, jsonify, request

from managers.machine_manager import MachineManager
from auth.decorators import get_current_user, require_permission
from auth.permissions import MACHINE_MANAGE
from api.helpers import json_error, machine_to_dict


machines_bp = Blueprint("machines", __name__, url_prefix="/api/machines")

machine_manager = MachineManager()


@machines_bp.before_request
def require_authenticated_user():
    if get_current_user() is None:
        return jsonify({"error": "נדרשת התחברות למערכת"}), 401


@machines_bp.route("", methods=["GET"])
def get_machines():
    """מחזיר את כל המכשירים - כולל לא-פעילים."""
    machines = machine_manager.get_all_machines()
    return jsonify([machine_to_dict(machine) for machine in machines])


@machines_bp.route("", methods=["POST"])
@require_permission(MACHINE_MANAGE)
def create_machine():
    """מוסיף מכשיר חדש. רכישת ציוד היא החלטה ניהולית - שמורה למנהלת."""
    data = request.get_json(silent=True) or {}
    machine = machine_manager.create_machine(
        name=data.get("name"),
        model=data.get("model"),
        machine_type=data.get("machine_type"),
        room_id=data.get("room_id"),
    )
    if machine is None:
        return json_error(machine_manager.last_error, status_code=400)
    return jsonify(machine_to_dict(machine)), 201


@machines_bp.route("/<int:machine_id>/active", methods=["POST"])
@require_permission(MACHINE_MANAGE)
def set_machine_active(machine_id):
    """מפעיל/משבית מכשיר (למשל בתיקון) - לא מוחק."""
    data = request.get_json(silent=True) or {}
    is_active = bool(data.get("is_active", True))

    if not machine_manager.set_active(machine_id, is_active):
        return json_error(machine_manager.last_error, status_code=404)
    return jsonify({"success": True})
