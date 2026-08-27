# ============================================================
# api/clients_api.py
# נקודות הקצה של ניהול לקוחות.
#
# הערה: endpoint ההיסטוריה כאן ישמש בהמשך גם את הצ'אטבוט,
# אחרי שהלקוחה תעבור אימות זהות מוצלח.
# ============================================================

import uuid
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file

from entities.client import Client
from managers.client_manager import ClientManager
from managers.appointment_manager import AppointmentManager
from managers.invoice_manager import InvoiceManager
from managers.package_manager import PackageManager

from utils.validators import validate_name, validate_phone, validate_email, normalize_phone
from auth.decorators import get_current_user
from auth.decorators import require_permission
from auth.permissions import CLIENT_DELETE
from flask import jsonify as _jsonify
from database import HEALTH_DECLARATIONS_DIR

from api.helpers import (
    json_error,
    run_db_operation,
    client_to_dict,
    invoice_to_dict,
    appointment_to_dict,
)


# סיומות קבצים מותרות להעלאת הצהרת בריאות - תמונה סרוקה או PDF בלבד
ALLOWED_HEALTH_DECLARATION_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
MAX_HEALTH_DECLARATION_SIZE_BYTES = 10 * 1024 * 1024  # 10MB - מספיק לסריקה/תמונה בודדת


clients_bp = Blueprint("clients", __name__, url_prefix="/api/clients")

client_manager = ClientManager()

# נחוצים להרכבת מסך ההיסטוריה של הלקוח
appointment_manager = AppointmentManager()
invoice_manager = InvoiceManager()
package_manager = PackageManager()

@clients_bp.before_request
def require_authenticated_user():
    """שער כניסה לכל נקודות הקצה של הלקוחות."""
    if get_current_user() is None:
        return _jsonify({"error": "נדרשת התחברות למערכת"}), 401


@clients_bp.route("", methods=["GET"])
def get_clients():
    """
    מחזיר את כל הלקוחות, כולל סיכום הכנסה וחבילה פעילה לכל אחת.

    הסיכום מחושב בשליפה אחת של כל החשבוניות/החבילות ולא N+1
    שאילתות ללקוח - אותה גישה בדיוק כמו api/dashboard_api.py.
    ב-200 לקוחות (גודל הקליניקה היעד) זו עדיין שליפה זולה.
    """
    clients = client_manager.get_all_clients()

    revenue_by_client = {}
    for invoice in invoice_manager.get_all_invoices(include_cancelled=False):
        revenue_by_client[invoice.client_id] = revenue_by_client.get(invoice.client_id, 0) + invoice.amount

    package_by_client = {}
    for client_package in package_manager.get_all_usable_client_packages():
        # אם יש כמה חבילות פעילות, מציגים את האחרונה שנרכשה
        existing = package_by_client.get(client_package.client_id)
        if existing is None or client_package.purchased_at > existing.purchased_at:
            package_by_client[client_package.client_id] = client_package

    result = []
    for client in clients:
        item = client_to_dict(client)
        item["total_revenue"] = revenue_by_client.get(client.client_id, 0)

        active_package = package_by_client.get(client.client_id)
        if active_package is not None:
            item["active_package"] = {
                "name": active_package.package.name,
                "sessions_remaining": active_package.sessions_remaining,
                "total_sessions": active_package.package.total_sessions,
            }
        else:
            item["active_package"] = None

        result.append(item)

    return jsonify(result)


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

    # הטלפון נשמר מנורמל (05XXXXXXXX) ולא כמו שהוקלד - זהו מפתח
    # החיפוש היחיד של הפורטל (identity/), וחייב להיות עקבי כדי
    # שלקוחה קיימת עם מספר בפורמט אחר לא "תיעלם" מהחיפוש
    new_client = Client(full_name=full_name.strip(), phone=normalize_phone(phone),
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
    existing.phone = normalize_phone(phone)
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
@require_permission(CLIENT_DELETE)
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


# ============================================================
# הצהרת בריאות חתומה - אחסון מקומי בלבד, בלי S3 ובלי DocuSign.
#
# הקובץ נשמר בתיקייה מוגנת מחוץ ל-static/ (ראו database.py:
# HEALTH_DECLARATIONS_DIR), עם שם קובץ אקראי (uuid4) שלא חושף
# את שם הלקוחה או המזהה שלה. הורדה עוברת תמיד דרך ה-endpoint
# המאומת למטה - לעולם לא URL ציבורי ישיר לקובץ.
# ============================================================

@clients_bp.route("/<int:client_id>/health-declaration", methods=["POST"])
def upload_health_declaration(client_id):
    """
    מעלה הצהרת בריאות חתומה עבור לקוחה קיימת.
    מצפה ל-multipart/form-data עם שדה בשם "file".
    """
    client = client_manager.get_client_by_id(client_id)
    if client is None:
        return json_error("הלקוח לא נמצא", status_code=404)

    uploaded_file = request.files.get("file")
    if uploaded_file is None or not uploaded_file.filename:
        return json_error("יש לצרף קובץ", field="file")

    extension = Path(uploaded_file.filename).suffix.lower()
    if extension not in ALLOWED_HEALTH_DECLARATION_EXTENSIONS:
        allowed = " / ".join(sorted(ALLOWED_HEALTH_DECLARATION_EXTENSIONS))
        return json_error(f"סוג קובץ לא נתמך - האפשרויות הן: {allowed}", field="file")

    # קריאת התוכן פעם אחת כדי לבדוק גודל לפני שמירה בפועל,
    # ואז איפוס המצביע כדי ש-save() ישמור את כל הקובץ
    uploaded_file.seek(0, 2)
    size_bytes = uploaded_file.tell()
    uploaded_file.seek(0)

    if size_bytes > MAX_HEALTH_DECLARATION_SIZE_BYTES:
        max_mb = MAX_HEALTH_DECLARATION_SIZE_BYTES // (1024 * 1024)
        return json_error(f"הקובץ גדול מדי - עד {max_mb}MB", field="file")

    # שם קובץ אקראי, לא תלוי בקלט המשתמש (לא path, לא שם מקורי) -
    # מונע גם Path Traversal וגם דליפת פרטי לקוחה משם הקובץ בדיסק
    stored_filename = f"{uuid.uuid4().hex}{extension}"
    uploaded_file.save(HEALTH_DECLARATIONS_DIR / stored_filename)

    if not client_manager.set_health_declaration(client_id, stored_filename):
        return json_error(client_manager.last_error, status_code=400)

    return jsonify(client_to_dict(client_manager.get_client_by_id(client_id)))


@clients_bp.route("/<int:client_id>/health-declaration", methods=["GET"])
def download_health_declaration(client_id):
    """
    מוריד את קובץ הצהרת הבריאות של לקוחה, למי שכבר מחובר למערכת.

    הנתיב לעולם לא מגיע מהבקשה עצמה - רק מהרשומה השמורה במסד
    עבור client_id הזה בדיוק, כדי שאי אפשר יהיה לבקש קובץ של
    לקוחה אחרת ע"י ניחוש/שינוי שם קובץ.
    """
    client = client_manager.get_client_by_id(client_id)
    if client is None or not client.health_declaration_file_path:
        return json_error("לא נמצאה הצהרת בריאות עבור לקוח זה", status_code=404)

    file_path = (HEALTH_DECLARATIONS_DIR / client.health_declaration_file_path).resolve()

    # הגנת עומק: גם אם משהו ישתבש בנתיב השמור, לעולם לא משרתים
    # קובץ שיצא מחוץ לתיקיית ההצהרות המוגנת
    if HEALTH_DECLARATIONS_DIR.resolve() not in file_path.parents or not file_path.is_file():
        return json_error("הקובץ לא נמצא", status_code=404)

    return send_file(file_path)