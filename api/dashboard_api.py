# ============================================================
# api/dashboard_api.py
# נתוני המסך הראשי של המערכת.
#
# כל החישובים כאן נעשים בפייתון מעל הנתונים שהמנהלים מחזירים,
# בלי אף שאילתה חדשה למסד הנתונים.
#
# הערה לעתיד: דוחות ההכנסות שכאן יוגבלו למנהל בלבד,
# ועובדת תראה רק את תורי היום.
# ============================================================

from datetime import datetime

from flask import Blueprint, jsonify

from managers.appointment_manager import AppointmentManager
from managers.client_manager import ClientManager
from managers.invoice_manager import InvoiceManager
from managers.lead_manager import LeadManager

from api.helpers import appointment_row_to_dict, combo_fields_for_appointment


dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")

appointment_manager = AppointmentManager()
client_manager = ClientManager()
invoice_manager = InvoiceManager()
lead_manager = LeadManager()


@dashboard_bp.route("", methods=["GET"])
def get_dashboard():
    """
    מרכיב תמונת מצב יומית: תורי היום, מספר הלקוחות,
    הכנסות החודש, ולידים פתוחים.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    current_month_prefix = datetime.now().strftime("%Y-%m")

    # תורי היום, מסוננים מתוך הרשימה המלאה עם הפרטים
    all_rows = appointment_manager.get_all_appointments_with_details()
    today_rows = [row for row in all_rows if row[3] == today]

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

    # לידים פתוחים, כלומר בסטטוס חדש או בטיפול
    all_leads = lead_manager.get_all_leads()
    open_leads = sum(1 for lead in all_leads if lead.is_active())

    return jsonify({
        "today_appointments": today_appointments,
        "clients_count": clients_count,
        "month_revenue": month_revenue,
        "open_leads": open_leads,
    })