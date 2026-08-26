from flask import Blueprint, jsonify, request

from entities.appointment import Appointment
from managers.appointment_manager import AppointmentManager
from managers.appointment_treatment_manager import AppointmentTreatmentManager
from managers.client_manager import ClientManager
from managers.treatment_manager import TreatmentManager
from auth.decorators import get_current_user
from flask import jsonify as _jsonify
from auth.decorators import require_permission
from auth.permissions import APPOINTMENT_DELETE

from utils.validators import (
    validate_date,
    validate_time,
    validate_appointment_status,
)

from api.helpers import (
    json_error,
    run_db_operation,
    appointment_to_dict,
    appointment_row_to_dict,
    combo_fields_for_appointment,
    parse_treatment_ids_from_args,
    parse_treatment_ids_from_json,
)


appointments_bp = Blueprint("appointments", __name__, url_prefix="/api/appointments")

appointment_manager = AppointmentManager()
appointment_treatment_manager = AppointmentTreatmentManager()

# נחוצים לאימות שהלקוח והטיפולים שנבחרו קיימים
client_manager = ClientManager()
treatment_manager = TreatmentManager()

@appointments_bp.before_request
def require_authenticated_user():
    """שער כניסה לכל נקודות הקצה של התורים."""
    if get_current_user() is None:
        return _jsonify({"error": "נדרשת התחברות למערכת"}), 401

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

@appointments_bp.route("", methods=["POST"])
def create_appointment():
    """
    קובע תור חדש, עם טיפול אחד או כמה יחד.
    סדר הבדיקות: לקוח קיים, כל הטיפולים קיימים, תאריך תקין,
    שעה תקינה, אין התנגשות לפי המשך הכולל, ורק אז שומרים.
    """
    data = request.get_json(silent=True) or {}

    client_id = data.get("client_id")
    appointment_date = data.get("appointment_date", "")
    appointment_time = data.get("appointment_time", "")
    notes = data.get("notes")
    treatment_ids = parse_treatment_ids_from_json(data)

    if client_id is None or client_manager.get_client_by_id(client_id) is None:
        return json_error("לקוח לא נמצא", field="client_id")

    if not treatment_ids:
        return json_error("יש לבחור טיפול אחד לפחות", field="treatment_id")

    for treatment_id in treatment_ids:
        if treatment_manager.get_treatment_by_id(treatment_id) is None:
            return json_error("אחד הטיפולים שנבחרו לא נמצא", field="treatment_id")

    is_valid, error_message = validate_date(appointment_date)
    if not is_valid:
        return json_error(error_message, field="appointment_date")

    is_valid, error_message = validate_time(appointment_time)
    if not is_valid:
        return json_error(error_message, field="appointment_time")

    has_conflict, conflict_message = appointment_treatment_manager.check_combo_conflict(
        appointment_date, appointment_time, treatment_ids
    )
    if has_conflict:
        return json_error(conflict_message, status_code=409)

    # הטבלה המקורית שומרת מזהה טיפול יחיד. הטיפול הראשי הוא
    # הראשון שנבחר, והרשימה המלאה נשמרת בטבלת הקישור
    new_appointment = Appointment(
        client_id=client_id,
        treatment_id=treatment_ids[0],
        appointment_date=appointment_date,
        appointment_time=appointment_time,
        notes=notes,
    )

    result, db_error = run_db_operation(
        lambda: appointment_manager.insert_appointment(new_appointment),
        "הוספת תור"
    )
    if db_error:
        return json_error(db_error, status_code=409)

    appointment_treatment_manager.set_treatments_for_appointment(
        result.appointment_id, treatment_ids
    )

    return jsonify(appointment_to_dict(result)), 201


@appointments_bp.route("/<int:appointment_id>", methods=["PUT"])
def update_appointment(appointment_id):
    """
    מעדכן תור קיים, כולל שינוי סטטוס ושינוי רשימת הטיפולים.
    אם משתנים תאריך, שעה או טיפולים, נבדקת התנגשות מחדש
    תוך התעלמות מהתור הנוכחי עצמו.
    """
    existing = appointment_manager.get_appointment_by_id(appointment_id)
    if existing is None:
        return json_error("התור לא נמצא", status_code=404)

    data = request.get_json(silent=True) or {}

    # כל שדה שלא נשלח נשאר כפי שהיה
    client_id = data.get("client_id", existing.client_id)
    appointment_date = data.get("appointment_date", existing.appointment_date)
    appointment_time = data.get("appointment_time", existing.appointment_time)
    status = data.get("status", existing.status)
    notes = data.get("notes", existing.notes)

    # אם לא נשלחה רשימת טיפולים חדשה, משתמשים בקיימת של התור
    treatment_ids = parse_treatment_ids_from_json(data)
    if not treatment_ids:
        treatment_ids = appointment_treatment_manager.get_treatment_ids_for_appointment(
            appointment_id
        )
        if not treatment_ids:
            treatment_ids = [existing.treatment_id]

    if client_manager.get_client_by_id(client_id) is None:
        return json_error("לקוח לא נמצא", field="client_id")

    for treatment_id in treatment_ids:
        if treatment_manager.get_treatment_by_id(treatment_id) is None:
            return json_error("אחד הטיפולים שנבחרו לא נמצא", field="treatment_id")

    is_valid, error_message = validate_date(appointment_date)
    if not is_valid:
        return json_error(error_message, field="appointment_date")

    is_valid, error_message = validate_time(appointment_time)
    if not is_valid:
        return json_error(error_message, field="appointment_time")

    is_valid, error_message = validate_appointment_status(status)
    if not is_valid:
        return json_error(error_message, field="status")

    has_conflict, conflict_message = appointment_treatment_manager.check_combo_conflict(
        appointment_date, appointment_time, treatment_ids,
        exclude_appointment_id=appointment_id
    )
    if has_conflict:
        return json_error(conflict_message, status_code=409)

    existing.client_id = client_id
    existing.treatment_id = treatment_ids[0]
    existing.appointment_date = appointment_date
    existing.appointment_time = appointment_time
    existing.status = status
    existing.notes = notes

    success, db_error = run_db_operation(
        lambda: appointment_manager.update_appointment(existing),
        "עדכון תור"
    )
    if db_error:
        return json_error(db_error, status_code=409)
    if not success:
        return json_error("העדכון נכשל", status_code=404)

    appointment_treatment_manager.set_treatments_for_appointment(
        appointment_id, treatment_ids
    )

    return jsonify(appointment_to_dict(existing))


@appointments_bp.route("/<int:appointment_id>", methods=["DELETE"])
@require_permission(APPOINTMENT_DELETE)
def delete_appointment(appointment_id):
    """
    מוחק תור מהמערכת.
    שים לב שזו מחיקה אמיתית, בשונה מחשבוניות שרק מבוטלות.
    בהמשך המחיקה תוגבל למנהל בלבד, ועובדת תוכל רק לסמן כמבוטל.
    """
    success = appointment_manager.delete_appointment(appointment_id)
    if not success:
        return json_error("התור לא נמצא", status_code=404)
    return jsonify({"success": True})