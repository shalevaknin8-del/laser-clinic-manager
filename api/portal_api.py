# ============================================================
# api/portal_api.py
# Blueprint הפורטל - Part 9 במפרט. REST טהור, ללא עוגיות, ללא
# HTML - מיועד ל-frontend נפרד (React/Next.js headless).
#
# פתוח ללא אימות: /identify, /verify בלבד. כל שאר ה-routes
# דורשים @require_portal_client, שמקבל client_id רק מתוך ה-JWT
# (Authorization: Bearer) - לעולם לא מפרמטר URL/גוף (Part 8 סעיף 1).
#
# תחום השלב הזה (P0, לפי Part 10 בתכנית הביצוע): identify/verify/
# register/me/history/treatments/availability/reserve/book/
# appointments/logout. cancel ו-reschedule מפורשות P1 ("11.
# Cancellation and rescheduling") ולכן לא כלולות כאן.
# ============================================================

from flask import Blueprint, jsonify, request

import identity
from identity.tokens import create_portal_token_pair, bump_client_token_version
from identity.portal_session import require_portal_client, get_current_portal_client

from db import get_session
from entities.lead import Lead
from managers.lead_manager import LeadManager
from managers.treatment_manager import TreatmentManager
from managers.appointment_manager import AppointmentManager
from managers.invoice_manager import InvoiceManager
from managers.appointment_treatment_manager import AppointmentTreatmentManager

from services import availability_service, booking_service
from services.booking_service import BookingError, SOURCE_PORTAL
from services.availability_service import AvailabilityError

from api.helpers import (
    json_error, client_to_dict, treatment_to_dict, invoice_to_dict,
    appointment_to_dict, parse_treatment_ids_from_args,
)
from utils.validators import validate_name, validate_email, normalize_phone
from utils.datetime_utils import now_jerusalem, combine_local


portal_bp = Blueprint("portal", __name__, url_prefix="/api/portal")

lead_manager = LeadManager()
treatment_manager = TreatmentManager()
appointment_manager = AppointmentManager()
invoice_manager = InvoiceManager()
appointment_treatment_manager = AppointmentTreatmentManager()


# ============================================================
# זיהוי ואימות (פתוח - בלי session)
# ============================================================

@portal_bp.route("/identify", methods=["POST"])
def identify():
    """
    Part 4 Step 1: שם + טלפון, שולח קוד. התשובה זהה-בייט קיים/לא
    קיים (Part 8 סעיף 2) - הזיהוי (מציאת לקוחה קיימת, או יצירת
    "שלד" לטלפון חדש - ראו identity.identify_or_create_shell)
    קורה כאן פנימית ולעולם לא נחשף החוצה.
    """
    data = request.get_json(silent=True) or {}
    full_name = data.get("full_name", "")
    phone = data.get("phone", "")

    if not phone or normalize_phone(phone) is None:
        return json_error("מספר טלפון לא תקין", status_code=400)

    if not full_name or not str(full_name).strip():
        full_name = "לקוחה חדשה"

    client = identity.identify_or_create_shell(full_name, phone)
    result, masked = identity.send_otp(client.client_id, purpose=identity.PURPOSE_PORTAL_LOGIN)

    return jsonify({
        "success": result == identity.RESULT_OK,
        "masked_destination": masked,
    })


@portal_bp.route("/verify", methods=["POST"])
def verify():
    """
    Part 4 Step 2: אימות הקוד, פותח session (JWT). is_new בתשובה
    קובע אם ה-frontend מציג את טופס ההרשמה הקצר (Step 3) - זה
    מותר להיחשף רק כאן, אחרי אימות מלא (ראו Part 4 Step 3 במפרט).
    """
    data = request.get_json(silent=True) or {}
    phone = data.get("phone", "")
    code = data.get("code", "")

    client = identity.find_client_by_phone(phone)
    if client is None:
        return json_error("קוד שגוי או שפג תוקפו", status_code=401)

    result, _reason = identity.confirm_otp(client.client_id, code,
                                            purpose=identity.PURPOSE_PORTAL_LOGIN)

    if result == identity.RESULT_LOCKED:
        return json_error("יותר מדי ניסיונות - יש לבקש קוד חדש", status_code=423)
    if result != identity.RESULT_OK:
        return json_error("קוד שגוי או שפג תוקפו", status_code=401)

    access_token, refresh_token = create_portal_token_pair(client)

    return jsonify({
        "success": True,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "is_new": identity.is_new_client(client),
    })


# ============================================================
# פרופיל (דורש session מאומת)
# ============================================================

@portal_bp.route("/register", methods=["POST"])
@require_portal_client
def register():
    """Part 4 Step 3, ענף 'חדשה': טופס רישום קצר + יצירת ליד source='portal'."""
    client = get_current_portal_client()

    if client.profile_completed_at is not None:
        return json_error("ההרשמה כבר הושלמה", status_code=400)

    data = request.get_json(silent=True) or {}
    full_name = data.get("full_name", client.full_name)
    email = data.get("email")
    address = data.get("address")

    is_valid, error_message = validate_name(full_name)
    if not is_valid:
        return json_error(error_message, field="full_name")

    is_valid, error_message = validate_email(email)
    if not is_valid:
        return json_error(error_message, field="email")

    session = get_session()
    client.full_name = full_name.strip()
    client.email = email
    client.address = address
    client.profile_completed_at = now_jerusalem().isoformat()
    session.commit()

    # status='converted' ישירות (לא 'new'): הלקוחה כבר קיימת בפועל
    # ברגע הזה, בניגוד לליד רגיל שממתין לטיפול צוות. חשוב גם כדי
    # שאיש צוות לא ינסה "להמיר" את הליד הזה ל-LeadManager.convert_lead_to_client
    # וייצור בטעות לקוחה כפולה עם אותו טלפון
    lead_manager.insert_lead(Lead(
        full_name=client.full_name, phone=client.phone,
        source="portal", status="converted",
        notes="נרשמה עצמאית דרך הפורטל",
    ))

    return jsonify({"success": True, "client": client_to_dict(client)})


@portal_bp.route("/me", methods=["GET"])
@require_portal_client
def get_me():
    client = get_current_portal_client()
    return jsonify({"client": client_to_dict(client)})


@portal_bp.route("/history", methods=["GET"])
@require_portal_client
def get_history():
    """טיפולים וסכומים ששולמו - client_id תמיד מהטוקן, לא מ-URL (Part 8 סעיף 1)."""
    client = get_current_portal_client()

    all_appointments = appointment_manager.get_all_appointments()
    client_appointments = []
    for appointment in all_appointments:
        if appointment.client_id == client.client_id:
            item = appointment_to_dict(appointment)
            item["treatment_name"] = ", ".join(item["treatment_names"]) or None
            client_appointments.append(item)

    all_invoices = invoice_manager.get_all_invoices(include_cancelled=True)
    client_invoices = [
        invoice_to_dict(invoice) for invoice in all_invoices
        if invoice.client_id == client.client_id
    ]
    total_active_amount = sum(
        invoice.amount for invoice in all_invoices
        if invoice.client_id == client.client_id and not invoice.is_cancelled
    )

    return jsonify({
        "appointments": client_appointments,
        "invoices": client_invoices,
        "total_active_amount": total_active_amount,
    })


@portal_bp.route("/appointments", methods=["GET"])
@require_portal_client
def list_my_appointments():
    """התורים העתידיים של הלקוחה בלבד - שום פרט על לקוחות אחרות (Part 8 סעיף 14)."""
    client = get_current_portal_client()
    now = now_jerusalem()

    upcoming = []
    for appointment in appointment_manager.get_all_appointments():
        if appointment.client_id != client.client_id or appointment.status == "cancelled":
            continue
        appointment_dt = combine_local(appointment.appointment_date, appointment.appointment_time)
        if appointment_dt >= now:
            item = appointment_to_dict(appointment)
            item["treatment_name"] = ", ".join(item["treatment_names"]) or None
            upcoming.append(item)

    upcoming.sort(key=lambda item: (item["appointment_date"], item["appointment_time"]))
    return jsonify({"appointments": upcoming})


@portal_bp.route("/logout", methods=["POST"])
@require_portal_client
def logout():
    """מבטל את כל ה-portal_refresh tokens הקיימים - אותו עיקרון בדיוק כמו auth_api.logout."""
    client = get_current_portal_client()
    bump_client_token_version(client, get_session())
    return jsonify({"success": True})


# ============================================================
# קטלוג וזמינות (דורש session מאומת)
# ============================================================

@portal_bp.route("/treatments", methods=["GET"])
@require_portal_client
def list_treatments():
    return jsonify({"treatments": [treatment_to_dict(t) for t in treatment_manager.get_all_treatments()]})


@portal_bp.route("/availability", methods=["GET"])
@require_portal_client
def get_availability():
    """Part 19: מחזיר *רק* שעות פנויות. הגבלת קצב 30/דקה - ראו security_setup.py."""
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    treatment_ids = parse_treatment_ids_from_args(request.args)

    if not date_from or not date_to or not treatment_ids:
        return json_error("יש לספק date_from, date_to, ו-treatment_ids", status_code=400)

    try:
        result = availability_service.get_public_availability(date_from, date_to, treatment_ids)
    except AvailabilityError as error:
        return json_error(str(error), status_code=400)

    return jsonify(result)


# ============================================================
# הזמנת תור (דורש session מאומת)
# ============================================================

@portal_bp.route("/reserve", methods=["POST"])
@require_portal_client
def reserve_slot():
    """Part 4 Step 6 / Part 19.7: שריון זמני של 10 דקות."""
    client = get_current_portal_client()
    data = request.get_json(silent=True) or {}

    appointment_date = data.get("appointment_date", "")
    appointment_time = data.get("appointment_time", "")
    treatment_ids = data.get("treatment_ids")

    if not appointment_date or not appointment_time or not treatment_ids:
        return json_error("יש לספק appointment_date, appointment_time, ו-treatment_ids",
                           status_code=400)

    try:
        treatment_ids = [int(t) for t in treatment_ids]
    except (TypeError, ValueError):
        return json_error("treatment_ids לא תקין", status_code=400)

    try:
        reservation = booking_service.create_reservation(client.client_id, appointment_date,
                                                           appointment_time, treatment_ids)
    except (BookingError, AvailabilityError) as error:
        return json_error(str(error), status_code=409)

    return jsonify({
        "reservation_id": reservation.reservation_id,
        "expires_at": reservation.expires_at,
    })


@portal_bp.route("/book", methods=["POST"])
@require_portal_client
def book_appointment():
    """Part 4 Step 7 / Part 9: מאשר שריון -> תור ב-pending_approval."""
    client = get_current_portal_client()
    data = request.get_json(silent=True) or {}

    reservation_id = data.get("reservation_id")
    if reservation_id is None:
        return json_error("יש לספק reservation_id", status_code=400)

    try:
        appointment = booking_service.confirm_booking(client.client_id, int(reservation_id),
                                                        source=SOURCE_PORTAL)
    except (BookingError, AvailabilityError) as error:
        return json_error(str(error), status_code=409)
    except (TypeError, ValueError):
        return json_error("reservation_id לא תקין", status_code=400)

    return jsonify({
        "success": True,
        "appointment": appointment_to_dict(appointment),
    })
