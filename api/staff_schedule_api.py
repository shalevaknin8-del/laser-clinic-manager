# ============================================================
# api/staff_schedule_api.py
# זמינות עובדות - משאב שלישי באילוץ הזימון החכם התלת-כיווני.
# תבנית שבועית חוזרת + חופשות/מחלה בטווח תאריכים.
# ============================================================

from flask import Blueprint, jsonify, request

from managers.staff_schedule_manager import StaffScheduleManager
from utils.validators import validate_date, validate_time
from auth.decorators import get_current_user, require_permission
from auth.permissions import STAFF_SCHEDULE_MANAGE
from api.helpers import json_error, staff_availability_to_dict, staff_time_off_to_dict


staff_schedule_bp = Blueprint("staff_schedule", __name__, url_prefix="/api/staff")

staff_schedule_manager = StaffScheduleManager()


@staff_schedule_bp.before_request
def require_authenticated_user():
    if get_current_user() is None:
        return jsonify({"error": "נדרשת התחברות למערכת"}), 401


@staff_schedule_bp.route("/<int:staff_user_id>/availability", methods=["GET"])
def get_availability(staff_user_id):
    """מחזיר את תבנית שעות העבודה השבועית של עובדת."""
    slots = staff_schedule_manager.get_availability_for_staff(staff_user_id)
    return jsonify([staff_availability_to_dict(slot) for slot in slots])


@staff_schedule_bp.route("/<int:staff_user_id>/availability", methods=["POST"])
@require_permission(STAFF_SCHEDULE_MANAGE)
def add_availability(staff_user_id):
    """
    מוסיף משבצת שעות עבודה קבועה ביום מסוים בשבוע.
    day_of_week: 0=שני ... 6=ראשון (עקבי עם date.weekday() של פייתון).
    """
    data = request.get_json(silent=True) or {}

    day_of_week = data.get("day_of_week")
    start_time = data.get("start_time", "")
    end_time = data.get("end_time", "")

    if not isinstance(day_of_week, int):
        return json_error("יש לציין יום בשבוע (0-6)", field="day_of_week")

    is_valid, error_message = validate_time(start_time)
    if not is_valid:
        return json_error(error_message, field="start_time")

    is_valid, error_message = validate_time(end_time)
    if not is_valid:
        return json_error(error_message, field="end_time")

    slot = staff_schedule_manager.add_availability(staff_user_id, day_of_week, start_time, end_time)
    if slot is None:
        return json_error(staff_schedule_manager.last_error, status_code=400)

    return jsonify(staff_availability_to_dict(slot)), 201


@staff_schedule_bp.route("/availability/<int:availability_id>", methods=["DELETE"])
@require_permission(STAFF_SCHEDULE_MANAGE)
def delete_availability(availability_id):
    """מוחק משבצת שעות עבודה קבועה."""
    if not staff_schedule_manager.delete_availability(availability_id):
        return json_error(staff_schedule_manager.last_error, status_code=404)
    return jsonify({"success": True})


@staff_schedule_bp.route("/<int:staff_user_id>/time-off", methods=["GET"])
def get_time_off(staff_user_id):
    """מחזיר את רשומות החופשה/מחלה של עובדת."""
    records = staff_schedule_manager.get_time_off_for_staff(staff_user_id)
    return jsonify([staff_time_off_to_dict(record) for record in records])


@staff_schedule_bp.route("/<int:staff_user_id>/time-off", methods=["POST"])
@require_permission(STAFF_SCHEDULE_MANAGE)
def add_time_off(staff_user_id):
    """מוסיף חופשה/מחלה בטווח תאריכים - חוסמת שיבוץ בלי לגעת בתבנית השבועית."""
    data = request.get_json(silent=True) or {}

    start_date = data.get("start_date", "")
    end_date = data.get("end_date", "")

    is_valid, error_message = validate_date(start_date)
    if not is_valid:
        return json_error(error_message, field="start_date")

    is_valid, error_message = validate_date(end_date)
    if not is_valid:
        return json_error(error_message, field="end_date")

    time_off = staff_schedule_manager.add_time_off(
        staff_user_id, start_date, end_date, reason=data.get("reason")
    )
    if time_off is None:
        return json_error(staff_schedule_manager.last_error, status_code=400)

    return jsonify(staff_time_off_to_dict(time_off)), 201


@staff_schedule_bp.route("/time-off/<int:time_off_id>", methods=["DELETE"])
@require_permission(STAFF_SCHEDULE_MANAGE)
def delete_time_off(time_off_id):
    """מוחק רשומת חופשה/מחלה."""
    if not staff_schedule_manager.delete_time_off(time_off_id):
        return json_error(staff_schedule_manager.last_error, status_code=404)
    return jsonify({"success": True})
