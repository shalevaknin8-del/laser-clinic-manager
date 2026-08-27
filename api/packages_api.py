# ============================================================
# api/packages_api.py
# קטלוג חבילות טיפולים + מכירת חבילה ללקוחה ספציפית.
#
# חבילה = N מפגשים של טיפול אחד. יצירת/עריכת הקטלוג (מחיר,
# מספר מפגשים) שמורה למנהלת (PACKAGE_MANAGE) - החלטה עסקית,
# בדיוק כמו שינוי מחיר טיפול. מכירת חבילה קיימת ללקוחה פתוחה
# לכל עובדת (PACKAGE_SELL) - פעולה יומיומית כמו הפקת חשבונית.
# ============================================================

from flask import Blueprint, jsonify, request

from managers.package_manager import PackageManager
from managers.client_manager import ClientManager
from auth.decorators import get_current_user, require_permission
from auth.permissions import PACKAGE_MANAGE, PACKAGE_SELL
from api.helpers import json_error, package_to_dict, client_package_to_dict


packages_bp = Blueprint("packages", __name__, url_prefix="/api/packages")

package_manager = PackageManager()
client_manager = ClientManager()


@packages_bp.before_request
def require_authenticated_user():
    if get_current_user() is None:
        return jsonify({"error": "נדרשת התחברות למערכת"}), 401


@packages_bp.route("", methods=["GET"])
def get_packages():
    """מחזיר את קטלוג החבילות - כולל לא-פעילות, לצורך היסטוריה."""
    packages = package_manager.get_all_packages()
    return jsonify([package_to_dict(package) for package in packages])


@packages_bp.route("", methods=["POST"])
@require_permission(PACKAGE_MANAGE)
def create_package():
    """מוסיף חבילה חדשה לקטלוג."""
    data = request.get_json(silent=True) or {}

    package = package_manager.create_package(
        name=data.get("name"),
        treatment_id=data.get("treatment_id"),
        total_sessions=data.get("total_sessions"),
        price=data.get("price"),
    )
    if package is None:
        return json_error(package_manager.last_error, status_code=400)

    return jsonify(package_to_dict(package)), 201


@packages_bp.route("/<int:package_id>/active", methods=["POST"])
@require_permission(PACKAGE_MANAGE)
def set_package_active(package_id):
    """מפעיל/משבית חבילה בקטלוג (למשל מבצע שהסתיים) - לא מוחק."""
    data = request.get_json(silent=True) or {}
    is_active = bool(data.get("is_active", True))

    if not package_manager.set_active(package_id, is_active):
        return json_error(package_manager.last_error, status_code=404)
    return jsonify({"success": True})


@packages_bp.route("/client/<int:client_id>", methods=["GET"])
def get_client_packages(client_id):
    """מחזיר את החבילות שנרכשו ע\"י לקוחה נתונה, כולל יתרת מפגשים."""
    if client_manager.get_client_by_id(client_id) is None:
        return json_error("הלקוח לא נמצא", status_code=404)

    client_packages = package_manager.get_client_packages(client_id)
    return jsonify([client_package_to_dict(cp) for cp in client_packages])


@packages_bp.route("/client/<int:client_id>/purchase", methods=["POST"])
@require_permission(PACKAGE_SELL)
def purchase_package(client_id):
    """
    רוכשת חבילה קיימת מהקטלוג עבור לקוחה - יוצרת ClientPackage עם
    יתרת מפגשים מלאה. הפקת חשבונית על הרכישה, אם רוצים, היא קריאה
    נפרדת ל-POST /api/invoices.
    """
    data = request.get_json(silent=True) or {}
    package_id = data.get("package_id")

    if package_id is None:
        return json_error("יש לבחור חבילה", field="package_id")

    client_package = package_manager.purchase_package_for_client(client_id, package_id)
    if client_package is None:
        return json_error(package_manager.last_error, status_code=400)

    return jsonify(client_package_to_dict(client_package)), 201
