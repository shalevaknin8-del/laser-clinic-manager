# ============================================================
# api/leads_api.py
# נקודות הקצה של ניהול לידים (לקוחות פוטנציאליים).
#
# כל הכתובות כאן מתחילות ב-/api/leads, בדיוק כמו קודם.
# ============================================================

from flask import Blueprint, jsonify, request

from entities.lead import Lead
from managers.lead_manager import LeadManager

from utils.validators import validate_name, validate_phone, validate_lead_status

from api.helpers import json_error, run_db_operation, lead_to_dict, VALID_LEAD_SOURCES


# יצירת הקופסה. url_prefix קובע שכל route כאן מתחיל ב-/api/leads
leads_bp = Blueprint("leads", __name__, url_prefix="/api/leads")

# מופע אחד של המנהל, משותף לכל הבקשות בקובץ הזה
lead_manager = LeadManager()


@leads_bp.route("", methods=["GET"])
def get_leads():
    """מחזיר את כל הלידים במערכת."""
    leads = lead_manager.get_all_leads()
    return jsonify([lead_to_dict(lead) for lead in leads])