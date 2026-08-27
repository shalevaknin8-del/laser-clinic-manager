# ============================================================
# api/dashboard_api.py
# נתוני המסך הראשי של המערכת.
#
# כל החישובים כאן נעשים בפייתון מעל הנתונים שהמנהלים מחזירים,
# בלי אף שאילתה חדשה למסד הנתונים.
#
# מגמות ההשוואה (revenue_trend/leads_trend/appointments_trend)
# מחושבות מנתונים אמיתיים בלבד - הכנסה מול החודש הקודם ממש,
# לידים מול החודש הקודם ממש, ותורים מול אותו יום בשבוע שעבר.
# אף ערך כאן אינו מומצא - זו הייתה הבעיה בעיצוב המקורי (ראו
# DESIGN_NOTES.md), ותוקנה כאן בפועל ולא רק בתיעוד.
#
# הערה לעתיד: דוחות ההכנסות שכאן יוגבלו למנהל בלבד,
# ועובדת תראה רק את תורי היום.
# ============================================================

from datetime import datetime, timedelta

from flask import Blueprint, jsonify

from managers.appointment_manager import AppointmentManager
from managers.client_manager import ClientManager
from managers.invoice_manager import InvoiceManager
from managers.lead_manager import LeadManager

from api.helpers import appointment_row_to_dict, combo_fields_for_appointment
from auth.decorators import get_current_user
from flask import jsonify as _jsonify

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")

appointment_manager = AppointmentManager()
client_manager = ClientManager()
invoice_manager = InvoiceManager()
lead_manager = LeadManager()

@dashboard_bp.before_request
def require_authenticated_user():
    """שער כניסה לנתוני המסך הראשי."""
    if get_current_user() is None:
        return _jsonify({"error": "נדרשת התחברות למערכת"}), 401


def _month_prefix(reference_date):
    return reference_date.strftime("%Y-%m")


def _previous_month_reference(reference_date):
    """מחזיר תאריך כלשהו בתוך החודש הקודם, מספיק כדי לחשב prefix ממנו."""
    first_of_this_month = reference_date.replace(day=1)
    return first_of_this_month - timedelta(days=1)


@dashboard_bp.route("", methods=["GET"])
def get_dashboard():
    """
    מרכיב תמונת מצב יומית: תורי היום (עם מגמה מול אותו יום
    בשבוע שעבר), מספר הלקוחות, הכנסות החודש (מול החודש הקודם),
    ולידים חדשים החודש (מול החודש הקודם, כולל פילוח לפי מקור).
    """
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")

    current_month_prefix = _month_prefix(now)
    previous_month_prefix = _month_prefix(_previous_month_reference(now))

    # תורי היום, מסוננים מתוך הרשימה המלאה עם הפרטים
    all_rows = appointment_manager.get_all_appointments_with_details()
    today_rows = [row for row in all_rows if row[3] == today]
    week_ago_rows = [row for row in all_rows if row[3] == week_ago]

    today_appointments = []
    for row in today_rows:
        appointment_id = row[0]
        appointment = appointment_manager.get_appointment_by_id(appointment_id)
        fallback_treatment_id = appointment.treatment_id if appointment else None
        combo = combo_fields_for_appointment(appointment_id, fallback_treatment_id)

        item = appointment_row_to_dict(row)
        item["treatment_name"] = ", ".join(combo["treatment_names"]) or item["treatment_name"]
        item.update(combo)
        today_appointments.append(item)

    clients_count = len(client_manager.get_all_clients())

    # הכנסות החודש, מחושבות מחשבוניות פעילות בלבד
    active_invoices = invoice_manager.get_all_invoices(include_cancelled=False)
    month_revenue = sum(
        invoice.amount for invoice in active_invoices
        if invoice.invoice_date.startswith(current_month_prefix)
    )
    previous_month_revenue = sum(
        invoice.amount for invoice in active_invoices
        if invoice.invoice_date.startswith(previous_month_prefix)
    )

    # לידים פתוחים, כלומר בסטטוס חדש או בטיפול
    all_leads = lead_manager.get_all_leads()
    open_leads = sum(1 for lead in all_leads if lead.is_active())

    new_leads_this_month = [
        lead for lead in all_leads
        if lead.created_at and lead.created_at.startswith(current_month_prefix)
    ]
    new_leads_previous_month = sum(
        1 for lead in all_leads
        if lead.created_at and lead.created_at.startswith(previous_month_prefix)
    )

    source_counts = {}
    for lead in new_leads_this_month:
        key = lead.source or "אחר"
        source_counts[key] = source_counts.get(key, 0) + 1

    # לידים שדורשים מעקב - פעילים, הישנים ביותר קודם (ממתינים הכי הרבה זמן)
    active_leads_oldest_first = sorted(
        (lead for lead in all_leads if lead.is_active()),
        key=lambda lead: lead.created_at or "",
    )
    needs_follow_up = [
        {"lead_id": lead.lead_id, "full_name": lead.full_name, "source": lead.source}
        for lead in active_leads_oldest_first[:3]
    ]

    return jsonify({
        "today_appointments": today_appointments,
        "clients_count": clients_count,
        "month_revenue": month_revenue,
        "open_leads": open_leads,
        "appointments_trend": {
            "today_count": len(today_rows),
            "same_weekday_last_week_count": len(week_ago_rows),
        },
        "revenue_trend": {
            "this_month": month_revenue,
            "previous_month": previous_month_revenue,
        },
        "leads_trend": {
            "this_month": len(new_leads_this_month),
            "previous_month": new_leads_previous_month,
            "by_source": source_counts,
        },
        "needs_follow_up": needs_follow_up,
    })
