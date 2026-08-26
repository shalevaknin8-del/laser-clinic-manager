# ============================================================
# api/leads_api.py
# נקודות הקצה של ניהול לידים (לקוחות פוטנציאליים).
#
# כל הכתובות כאן מתחילות ב-/api/leads, בדיוק כמו קודם.
# ============================================================

from flask import Blueprint, jsonify, request

from entities.lead import Lead
from managers.lead_manager import LeadManager

from utils.validators import (
    validate_name,
    validate_phone,
    validate_email,
    validate_lead_status,
)

from api.helpers import (
    json_error,
    run_db_operation,
    lead_to_dict,
    client_to_dict,
    VALID_LEAD_SOURCES,
)
from auth.decorators import get_current_user
from flask import jsonify as _jsonify


# יצירת הקופסה. url_prefix קובע שכל route כאן מתחיל ב-/api/leads
leads_bp = Blueprint("leads", __name__, url_prefix="/api/leads")

# מופע אחד של המנהל, משותף לכל הבקשות בקובץ הזה
lead_manager = LeadManager()


@leads_bp.before_request
def require_authenticated_user():
    """
    שער כניסה לכל נקודות הקצה בקבוצה הזו.

    זו הנקודה המרכזית של כל הריפקטור מיום 2: ההגנה נכתבת
    פעם אחת וחלה על כל ה-routes, כולל כאלה שיתווספו בעתיד.
    אי אפשר לשכוח להגן על endpoint חדש.
    """
    if get_current_user() is None:
        return _jsonify({"error": "נדרשת התחברות למערכת"}), 401


@leads_bp.route("", methods=["GET"])
def get_leads():
    """מחזיר את כל הלידים במערכת."""
    leads = lead_manager.get_all_leads()
    return jsonify([lead_to_dict(lead) for lead in leads])


@leads_bp.route("", methods=["POST"])
def create_lead():
    """יוצר ליד חדש."""
    data = request.get_json(silent=True) or {}

    full_name = data.get("full_name", "")
    phone = data.get("phone", "")
    source = data.get("source")
    notes = data.get("notes")

    is_valid, error_message = validate_name(full_name)
    if not is_valid:
        return json_error(error_message, field="full_name")

    is_valid, error_message = validate_phone(phone)
    if not is_valid:
        return json_error(error_message, field="phone")

    if source is not None and source not in VALID_LEAD_SOURCES:
        options = " / ".join(VALID_LEAD_SOURCES)
        return json_error(f"מקור לא תקין - האפשרויות הן: {options}", field="source")

    new_lead = Lead(full_name=full_name.strip(), phone=phone.strip(),
                    source=source, notes=notes)

    result, db_error = run_db_operation(
        lambda: lead_manager.insert_lead(new_lead),
        "הוספת ליד"
    )
    if db_error:
        return json_error(db_error, status_code=409)

    return jsonify(lead_to_dict(result)), 201


@leads_bp.route("/<int:lead_id>", methods=["PUT"])
def update_lead(lead_id):
    """מעדכן ליד. השימוש הנפוץ ביותר הוא עדכון סטטוס."""
    existing = lead_manager.get_lead_by_id(lead_id)
    if existing is None:
        return json_error("הליד לא נמצא", status_code=404)

    data = request.get_json(silent=True) or {}

    full_name = data.get("full_name", existing.full_name)
    phone = data.get("phone", existing.phone)
    source = data.get("source", existing.source)
    status = data.get("status", existing.status)
    notes = data.get("notes", existing.notes)

    is_valid, error_message = validate_name(full_name)
    if not is_valid:
        return json_error(error_message, field="full_name")

    is_valid, error_message = validate_phone(phone)
    if not is_valid:
        return json_error(error_message, field="phone")

    if source is not None and source not in VALID_LEAD_SOURCES:
        options = " / ".join(VALID_LEAD_SOURCES)
        return json_error(f"מקור לא תקין - האפשרויות הן: {options}", field="source")

    is_valid, error_message = validate_lead_status(status)
    if not is_valid:
        return json_error(error_message, field="status")

    existing.full_name = full_name.strip()
    existing.phone = phone.strip()
    existing.source = source
    existing.status = status
    existing.notes = notes

    success, db_error = run_db_operation(
        lambda: lead_manager.update_lead(existing),
        "עדכון ליד"
    )
    if db_error:
        return json_error(db_error, status_code=409)
    if not success:
        return json_error("העדכון נכשל", status_code=404)

    return jsonify(lead_to_dict(existing))


@leads_bp.route("/<int:lead_id>", methods=["DELETE"])
def delete_lead(lead_id):
    """מוחק ליד."""
    success = lead_manager.delete_lead(lead_id)
    if not success:
        return json_error("הליד לא נמצא", status_code=404)
    return jsonify({"success": True})


@leads_bp.route("/<int:lead_id>/convert", methods=["POST"])
def convert_lead(lead_id):
    """ממיר ליד ללקוח. הפעולה מתבצעת כטרנזקציה אחת במנהל."""
    lead = lead_manager.get_lead_by_id(lead_id)
    if lead is None:
        return json_error("הליד לא נמצא", status_code=404)

    if lead.is_converted():
        return json_error("הליד כבר הומר ללקוח בעבר", status_code=409)

    data = request.get_json(silent=True) or {}
    email = data.get("email")
    address = data.get("address")

    is_valid, error_message = validate_email(email)
    if not is_valid:
        return json_error(error_message, field="email")

    new_client, db_error = run_db_operation(
        lambda: lead_manager.convert_lead_to_client(lead_id, email=email, address=address),
        "המרת ליד ללקוח"
    )
    if db_error:
        return json_error(db_error, status_code=409)
    if new_client is None:
        return json_error("ההמרה נכשלה", status_code=409)

    return jsonify(client_to_dict(new_client)), 201