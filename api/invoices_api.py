# ============================================================
# api/invoices_api.py
# נקודות הקצה של ניהול חשבוניות.
#
# הערה חשובה: אין כאן מחיקה אמיתית של חשבונית.
# לפי חוק, חשבונית מבוטלת בלבד (Soft Delete) ומספרה
# נשמר לצמיתות. לכן יש כאן cancel ו-restore, ואין DELETE.
# ============================================================

from flask import Blueprint, jsonify, request

from entities.invoice import Invoice
from managers.invoice_manager import InvoiceManager
from managers.client_manager import ClientManager
from managers.appointment_manager import AppointmentManager

from utils.validators import validate_date, validate_positive_number

from api.helpers import json_error, run_db_operation, invoice_to_dict
from auth.decorators import get_current_user
from flask import jsonify as _jsonify


invoices_bp = Blueprint("invoices", __name__, url_prefix="/api/invoices")

invoice_manager = InvoiceManager()

@invoices_bp.before_request
def require_authenticated_user():
    """שער כניסה לכל נקודות הקצה של החשבוניות."""
    if get_current_user() is None:
        return _jsonify({"error": "נדרשת התחברות למערכת"}), 401

# שני המנהלים האלה נחוצים רק לאימות שהלקוח והתור המקושרים קיימים
client_manager = ClientManager()
appointment_manager = AppointmentManager()


@invoices_bp.route("", methods=["GET"])
def get_invoices():
    """
    מחזיר את רשימת החשבוניות.
    הפרמטר include_cancelled=true מציג גם חשבוניות מבוטלות, לצורך ביקורת.
    ברירת המחדל מציגה רק חשבוניות פעילות.
    """
    include_cancelled = request.args.get("include_cancelled", "false").lower() == "true"
    invoices = invoice_manager.get_all_invoices(include_cancelled=include_cancelled)
    return jsonify([invoice_to_dict(invoice) for invoice in invoices])


@invoices_bp.route("", methods=["POST"])
def create_invoice():
    """
    מפיק חשבונית חדשה.
    מספר החשבונית נוצר אוטומטית בתוך המנהל, לא כאן.
    """
    data = request.get_json(silent=True) or {}

    client_id = data.get("client_id")
    amount = data.get("amount")
    invoice_date = data.get("invoice_date", "")
    appointment_id = data.get("appointment_id")

    if client_id is None or client_manager.get_client_by_id(client_id) is None:
        return json_error("לקוח לא נמצא", field="client_id")

    is_valid, error_message = validate_positive_number(amount, "הסכום")
    if not is_valid:
        return json_error(error_message, field="amount")

    is_valid, error_message = validate_date(invoice_date)
    if not is_valid:
        return json_error(error_message, field="invoice_date")

    # קישור לתור הוא רשות, אבל אם נשלח הוא חייב להתקיים
    if appointment_id is not None:
        if appointment_manager.get_appointment_by_id(appointment_id) is None:
            return json_error("התור המקושר לא נמצא", field="appointment_id")

    new_invoice = Invoice(
        client_id=client_id,
        amount=float(amount),
        invoice_date=invoice_date,
        appointment_id=appointment_id,
    )

    result, db_error = run_db_operation(
        lambda: invoice_manager.insert_invoice(new_invoice),
        "הפקת חשבונית"
    )
    if db_error:
        return json_error(db_error, status_code=409)

    return jsonify(invoice_to_dict(result)), 201


@invoices_bp.route("/<int:invoice_id>/cancel", methods=["POST"])
def cancel_invoice(invoice_id):
    """
    מבטל חשבונית בביטול רך בלבד.
    לפי חוק אין ולעולם לא תהיה מחיקה אמיתית של חשבונית.
    """
    invoice = invoice_manager.get_invoice_by_id(invoice_id)
    if invoice is None:
        return json_error("החשבונית לא נמצאה", status_code=404)

    if invoice.is_cancelled:
        return json_error("החשבונית כבר מבוטלת", status_code=409)

    success = invoice_manager.cancel_invoice(invoice_id)
    if not success:
        return json_error("הביטול נכשל", status_code=409)

    return jsonify({"success": True})


@invoices_bp.route("/<int:invoice_id>/restore", methods=["POST"])
def restore_invoice(invoice_id):
    """משחזר חשבונית שבוטלה בטעות."""
    invoice = invoice_manager.get_invoice_by_id(invoice_id)
    if invoice is None:
        return json_error("החשבונית לא נמצאה", status_code=404)

    if not invoice.is_cancelled:
        return json_error("החשבונית כבר פעילה", status_code=409)

    success = invoice_manager.restore_invoice(invoice_id)
    if not success:
        return json_error("השחזור נכשל", status_code=409)

    return jsonify({"success": True})