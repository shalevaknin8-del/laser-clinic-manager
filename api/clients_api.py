# ============================================================
# api/clients_api.py
# נקודות הקצה של ניהול לקוחות.
#
# הערה: endpoint ההיסטוריה כאן ישמש בהמשך גם את הצ'אטבוט,
# אחרי שהלקוחה תעבור אימות זהות מוצלח.
# ============================================================

from flask import Blueprint, jsonify, request

from entities.client import Client
from managers.client_manager import ClientManager
from managers.appointment_manager import AppointmentManager
from managers.invoice_manager import InvoiceManager

from utils.validators import validate_name, validate_phone, validate_email
from auth.decorators import get_current_user
from flask import jsonify as _jsonify

from api.helpers import (
    json_error,
    run_db_operation,
    client_to_dict,
    invoice_to_dict,
    appointment_to_dict,
)


clients_bp = Blueprint("clients", __name__, url_prefix="/api/clients")

client_manager = ClientManager()

# נחוצים להרכבת מסך ההיסטוריה של הלקוח
appointment_manager = AppointmentManager()
invoice_manager = InvoiceManager()

@clients_bp.before_request
def require_authenticated_user():
    """שער כניסה לכל נקודות הקצה של הלקוחות."""
    if get_current_user() is None:
        return _jsonify({"error": "נדרשת התחברות למערכת"}), 401


@clients_bp.route("", methods=["GET"])
def get_clients():
    """מחזיר את כל הלקוחות."""
    clients = client_manager.get_all_clients()
    return jsonify([client_to_dict(client) for client in clients])


@clients_bp.route("/<int:client_id>", methods=["GET"])
def get_client(client_id):
    """מחזיר לקוח בודד לפי מזהה."""
    client = client_manager.get_client_by_id(client_id)
    if client is None:
        return json_error("הלקוח לא נמצא", status_code=404)
    return jsonify(client_to_dict(client))


@clients_bp.route("/<int:client_id>/history", methods=["GET"])
def get_client_history(client_id):
    """
    מחזיר את היסטוריית התורים והחשבוניות של לקוח.
    הסינון מתבצע בפייתון מתוך הרשימות המלאות, בלי שאילתה חדשה.
    """
    client = client_manager.get_client_by_id(client_id)
    if client is None:
        return json_error("הלקוח לא נמצא", status_code=404)

    # תורים של הלקוח, כולל שמות הטיפולים והמחיר הכולל
    all_appointments = appointment_manager.get_all_appointments()
    client_appointments = []
    for appointment in all_appointments:
        if appointment.client_id == client_id:
            item = appointment_to_dict(appointment)
            item["treatment_name"] = ", ".join(item["treatment_names"]) or None
            client_appointments.append(item)

    # חשבוניות של הלקוח, כולל מבוטלות לצורך תצוגה מלאה
    all_invoices = invoice_manager.get_all_invoices(include_cancelled=True)
    client_invoices = [
        invoice_to_dict(invoice) for invoice in all_invoices
        if invoice.client_id == client_id
    ]

    # הסכום הכולל מחושב מחשבוניות פעילות בלבד
    total_active_amount = sum(
        invoice.amount for invoice in all_invoices
        if invoice.client_id == client_id and not invoice.is_cancelled
    )

    return jsonify({
        "client": client_to_dict(client),
        "appointments": client_appointments,
        "invoices": client_invoices,
        "total_active_amount": total_active_amount,
    })


@clients_bp.route("", methods=["POST"])
def create_client():
    """יוצר לקוח חדש."""
    data = request.get_json(silent=True) or {}

    full_name = data.get("full_name", "")
    phone = data.get("phone", "")
    email = data.get("email")
    address = data.get("address")

    is_valid, error_message = validate_name(full_name)
    if not is_valid:
        return json_error(error_message, field="full_name")

    is_valid, error_message = validate_phone(phone)
    if not is_valid:
        return json_error(error_message, field="phone")

    is_valid, error_message = validate_email(email)
    if not is_valid:
        return json_error(error_message, field="email")

    new_client = Client(full_name=full_name.strip(), phone=phone.strip(),
                        email=email, address=address)

    result = client_manager.insert_client(new_client)
    if result is None:
        # המנהל שומר את הסיבה המדויקת בשדה last_error
        return json_error(client_manager.last_error, status_code=409)

    return jsonify(client_to_dict(result)), 201


@clients_bp.route("/<int:client_id>", methods=["PUT"])
def update_client(client_id):
    """מעדכן פרטי לקוח קיים."""
    existing = client_manager.get_client_by_id(client_id)
    if existing is None:
        return json_error("הלקוח לא נמצא", status_code=404)

    data = request.get_json(silent=True) or {}

    full_name = data.get("full_name", existing.full_name)
    phone = data.get("phone", existing.phone)
    email = data.get("email", existing.email)
    address = data.get("address", existing.address)

    is_valid, error_message = validate_name(full_name)
    if not is_valid:
        return json_error(error_message, field="full_name")

    is_valid, error_message = validate_phone(phone)
    if not is_valid:
        return json_error(error_message, field="phone")

    is_valid, error_message = validate_email(email)
    if not is_valid:
        return json_error(error_message, field="email")

    existing.full_name = full_name.strip()
    existing.phone = phone.strip()
    existing.email = email
    existing.address = address

    success, db_error = run_db_operation(
        lambda: client_manager.update_client(existing),
        "עדכון לקוח"
    )
    if db_error:
        return json_error(db_error, status_code=409)
    if not success:
        return json_error("העדכון נכשל", status_code=404)

    return jsonify(client_to_dict(existing))


@clients_bp.route("/<int:client_id>", methods=["DELETE"])
def delete_client(client_id):
    """
    מוחק לקוח.
    אם יש לו תורים או חשבוניות מקושרים, המנהל יתפוס את שגיאת
    המפתח הזר ויסביר אותה בעברית דרך last_error.
    """
    success = client_manager.delete_client(client_id)
    if not success:
        status_code = 404 if "לא נמצא" in (client_manager.last_error or "") else 409
        return json_error(client_manager.last_error, status_code=status_code)
    return jsonify({"success": True})



@clients_bp.route("/search", methods=["GET"])
def search_clients():
    """
    מחפש לקוחות לפי שם חלקי.

    ה-endpoint הזה משמש את הצ'אטבוט לאיתור מועמדת לפי השם
    שהלקוחה מסרה. הוא מחזיר את מספר ההתאמות כדי שהבוט יידע
    אם עליו לבקש הבהרה במקום לנחש.

    מבחינת פרטיות: מוחזרים רק שם ומזהה, בלי טלפון, מייל וכתובת.
    בשלב החיפוש עדיין לא בוצע אימות, ולכן אין להחזיר פרטי קשר.
    """
    name_query = request.args.get("name", "")

    if not name_query.strip():
        return json_error("יש להזין שם לחיפוש", field="name")

    matches = client_manager.search_clients_by_name(name_query)

    # מבנה תגובה מצומצם בכוונה, ללא פרטים אישיים
    results = [
        {"client_id": client.client_id, "full_name": client.full_name}
        for client in matches
    ]

    return jsonify({
        "query": name_query.strip(),
        "match_count": len(results),
        "matches": results,
    })