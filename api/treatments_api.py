# ============================================================
# api/treatments_api.py
# נקודות הקצה של קטלוג הטיפולים.
#
# הערה: אין כאן מחיקת טיפול. טיפול מקושר לתורים היסטוריים,
# ומחיקתו הייתה שוברת את הקישור. בהמשך שינוי מחירים יוגבל
# למנהל בלבד, כי זו החלטה עסקית ולא פעולה יומיומית.
# ============================================================

from flask import Blueprint, jsonify, request

from entities.treatment import Treatment
from managers.treatment_manager import TreatmentManager

from utils.validators import validate_positive_number

from api.helpers import json_error, run_db_operation, treatment_to_dict
from auth.decorators import get_current_user
from flask import jsonify as _jsonify


treatments_bp = Blueprint("treatments", __name__, url_prefix="/api/treatments")

treatment_manager = TreatmentManager()

@treatments_bp.before_request
def require_authenticated_user():
    """שער כניסה לכל נקודות הקצה של הטיפולים."""
    if get_current_user() is None:
        return _jsonify({"error": "נדרשת התחברות למערכת"}), 401


def _validate_treatment_fields(treatment_name, body_area, price, duration_minutes):
    """
    ולידציה של שדות טיפול.
    אין ולידטור ייעודי לשם טיפול או איזור גוף בקובץ הוולידטורים,
    כי validate_name מיועד לשמות של אנשים ואוסר ספרות.
    לכן כאן נבדק רק שהשדה אינו ריק, ברוח שאר הוולידטורים.

    מחזיר שלשה: (is_valid, error_message, field_name)
    """
    if not treatment_name or not treatment_name.strip():
        return False, "שם הטיפול לא יכול להיות ריק", "treatment_name"

    if not body_area or not body_area.strip():
        return False, "יש להזין לפחות איזור אחד", "body_area"

    is_valid, error_message = validate_positive_number(price, "המחיר")
    if not is_valid:
        return False, error_message, "price"

    is_valid, error_message = validate_positive_number(duration_minutes, "משך הטיפול")
    if not is_valid:
        return False, error_message, "duration_minutes"

    return True, None, None


@treatments_bp.route("", methods=["GET"])
def get_treatments():
    """מחזיר את כל הטיפולים בקטלוג."""
    treatments = treatment_manager.get_all_treatments()
    return jsonify([treatment_to_dict(treatment) for treatment in treatments])


@treatments_bp.route("/seed", methods=["POST"])
def seed_treatments():
    """
    מאתחל את קטלוג הטיפולים ההתחלתי.
    הפעולה בטוחה להרצה חוזרת, היא מוסיפה רק מה שחסר.
    """
    added_count = treatment_manager.seed_catalog()
    return jsonify({"added_count": added_count})


@treatments_bp.route("", methods=["POST"])
def create_treatment():
    """מוסיף טיפול חדש לקטלוג."""
    data = request.get_json(silent=True) or {}

    treatment_name = data.get("treatment_name", "")
    body_area = data.get("body_area", "")
    price = data.get("price")
    duration_minutes = data.get("duration_minutes")

    is_valid, error_message, field = _validate_treatment_fields(
        treatment_name, body_area, price, duration_minutes
    )
    if not is_valid:
        return json_error(error_message, field=field)

    new_treatment = Treatment(
        treatment_name=treatment_name.strip(),
        body_area=body_area.strip(),
        price=float(price),
        duration_minutes=int(duration_minutes),
    )

    result, db_error = run_db_operation(
        lambda: treatment_manager.insert_treatment(new_treatment),
        "הוספת טיפול"
    )
    if db_error:
        return json_error(db_error, status_code=409)

    return jsonify(treatment_to_dict(result)), 201


@treatments_bp.route("/<int:treatment_id>", methods=["PUT"])
def update_treatment(treatment_id):
    """מעדכן טיפול קיים בקטלוג."""
    existing = treatment_manager.get_treatment_by_id(treatment_id)
    if existing is None:
        return json_error("הטיפול לא נמצא", status_code=404)

    data = request.get_json(silent=True) or {}

    treatment_name = data.get("treatment_name", existing.treatment_name)
    body_area = data.get("body_area", existing.body_area)
    price = data.get("price", existing.price)
    duration_minutes = data.get("duration_minutes", existing.duration_minutes)

    is_valid, error_message, field = _validate_treatment_fields(
        treatment_name, body_area, price, duration_minutes
    )
    if not is_valid:
        return json_error(error_message, field=field)

    existing.treatment_name = treatment_name.strip()
    existing.body_area = body_area.strip()
    existing.price = float(price)
    existing.duration_minutes = int(duration_minutes)

    success, db_error = run_db_operation(
        lambda: treatment_manager.update_treatment(existing),
        "עדכון טיפול"
    )
    if db_error:
        return json_error(db_error, status_code=409)
    if not success:
        return json_error("העדכון נכשל", status_code=404)

    return jsonify(treatment_to_dict(existing))