# ============================================================
# api/appointments_api.py
# נקודות הקצה של ניהול תורים.
#
# זו הקבוצה המרכזית במערכת. היא מכילה את מניעת ההתנגשויות
# ואת חישוב השעות הפנויות, שהם הלוגיקה העסקית הרגישה ביותר.
#
# הערה חשובה: כל חישובי הזמינות וההתנגשות עוברים דרך
# AppointmentTreatmentManager ולא דרך AppointmentManager,
# כי רק הוא יודע לחשב את המשך האמיתי של תורים מרוכבים קיימים.
# ============================================================

from flask import Blueprint, jsonify, request

from managers.appointment_manager import AppointmentManager
from managers.appointment_treatment_manager import AppointmentTreatmentManager

from utils.validators import validate_date

from api.helpers import (
    json_error,
    appointment_to_dict,
    appointment_row_to_dict,
    combo_fields_for_appointment,
    parse_treatment_ids_from_args,
)


appointments_bp = Blueprint("appointments", __name__, url_prefix="/api/appointments")

appointment_manager = AppointmentManager()
appointment_treatment_manager = AppointmentTreatmentManager()


@appointments_bp.route("", methods=["GET"])
def get_appointments():
    """
    מחזיר את כל התורים, כולל שם הלקוח ושמות כל הטיפולים.
    שם הלקוח מגיע מהשאילתה המשולבת שבמנהל, ורשימת הטיפולים
    המלאה מגיעה ממנהל הטיפול המרוכב.
    """
    rows = appointment_manager.get_all_appointments_with_details()

    result = []
    for row in rows:
        appointment_id = row[0]
        appointment = appointment_manager.get_appointment_by_id(appointment_id)
        fallback_treatment_id = appointment.treatment_id if appointment else None
        combo = combo_fields_for_appointment(appointment_id, fallback_treatment_id)

        item = appointment_row_to_dict(row)
        # עמודת שם הטיפול מציגה את כל הטיפולים המקושרים, לא רק את הראשי
        item["treatment_name"] = ", ".join(combo["treatment_names"]) or item["treatment_name"]
        item.update(combo)
        result.append(item)

    return jsonify(result)


@appointments_bp.route("/<int:appointment_id>", methods=["GET"])
def get_appointment(appointment_id):
    """
    מחזיר תור בודד עם השדות הגולמיים.
    נחוץ לטופס העריכה, כי הרשימה המלאה מחזירה רק שמות לתצוגה
    ובלי המזהים אי אפשר למלא מראש את שדות הבחירה בטופס.
    """
    appointment = appointment_manager.get_appointment_by_id(appointment_id)
    if appointment is None:
        return json_error("התור לא נמצא", status_code=404)
    return jsonify(appointment_to_dict(appointment))


@appointments_bp.route("/available-slots", methods=["GET"])
def get_available_slots():
    """
    מחזיר את השעות הפנויות ביום נתון, עבור טיפול יחיד או מרוכב.

    חשוב מבחינת פרטיות: הפונקציה מחזירה אך ורק את השעות הפנויות.
    היא לא מחזירה את התורים התפוסים ולא שום פרט על לקוחות אחרים.
    """
    appointment_date = request.args.get("date", "")

    is_valid, error_message = validate_date(appointment_date)
    if not is_valid:
        return json_error(error_message, field="date")

    treatment_ids = parse_treatment_ids_from_args(request.args)
    if not treatment_ids:
        return json_error("יש לבחור טיפול אחד לפחות", field="treatment_id")

    slots = appointment_treatment_manager.get_combo_available_slots(
        appointment_date, treatment_ids
    )
    return jsonify({"available_slots": slots})


@appointments_bp.route("/check-conflict", methods=["GET"])
def check_appointment_conflict():
    """
    בודק התנגשות בזמן אמת, בלי לשמור את התור.
    הבדיקה מתבצעת מול המשך האמיתי של התורים הקיימים.
    """
    appointment_date = request.args.get("date", "")
    appointment_time = request.args.get("time", "")
    exclude_id = request.args.get("exclude_appointment_id")

    treatment_ids = parse_treatment_ids_from_args(request.args)
    if not treatment_ids:
        return json_error("יש לבחור טיפול אחד לפחות", field="treatment_id")

    exclude_appointment_id = int(exclude_id) if exclude_id and exclude_id.isdigit() else None

    has_conflict, message = appointment_treatment_manager.check_combo_conflict(
        appointment_date, appointment_time, treatment_ids,
        exclude_appointment_id=exclude_appointment_id
    )
    return jsonify({"has_conflict": has_conflict, "message": message})