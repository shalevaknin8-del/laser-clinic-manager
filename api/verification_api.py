# ============================================================
# api/verification_api.py
# נקודות הקצה של אימות זהות לקוחה.
#
# זו שכבת האימות המשותפת: הצ'אטבוט משתמש בה היום,
# ופורטל הלקוחות ישתמש באותן נקודות קצה בדיוק בהמשך.
#
# עקרונות פרטיות שנאכפים כאן:
#   1. יעד השליחה נלקח מהמסד, לעולם לא מקלט המשתמש
#   2. היעד מוחזר מוסתר בלבד
#   3. הודעות הכישלון כלליות ולא מלמדות על מצב המערכת
#   4. שום פרט אישי לא מוחזר לפני אימות מוצלח
# ============================================================

from flask import Blueprint, jsonify, request

from managers.client_manager import ClientManager

from utils.otp import create_and_send_otp, verify_otp
from api.helpers import json_error


verification_bp = Blueprint("verification", __name__, url_prefix="/api/verification")

client_manager = ClientManager()


# הודעה אחידה לכל סוגי כישלון האימות.
# הודעה מפורטת הייתה מלמדת תוקף אם הקוד קיים, פג, או שגוי
GENERIC_FAILURE_MESSAGE = "הקוד שהוזן אינו תקין"


@verification_bp.route("/national-id", methods=["POST"])
def verify_national_id_endpoint():
    """
    שלב אימות ראשון: תעודת זהות.

    מחזיר תוצאה בוליאנית בלבד, בלי שום פרט על הלקוחה.
    """
    data = request.get_json(silent=True) or {}

    client_id = data.get("client_id")
    national_id = data.get("national_id")

    if client_id is None:
        return json_error("חסר מזהה לקוח", field="client_id")

    if not national_id:
        return json_error("יש להזין תעודת זהות", field="national_id")

    is_verified = client_manager.verify_client_national_id(client_id, national_id)

    return jsonify({"verified": is_verified})


@verification_bp.route("/send-code", methods=["POST"])
def send_verification_code():
    """
    שלב אימות שני, חלק ראשון: שליחת קוד.

    היעד נשלף מרשומת הלקוחה במסד. אם המשתמש שולח יעד
    בגוף הבקשה, הוא נזרק ומתעלמים ממנו לחלוטין.
    """
    data = request.get_json(silent=True) or {}

    client_id = data.get("client_id")
    preferred_channel = data.get("channel", "phone")

    if client_id is None:
        return json_error("חסר מזהה לקוח", field="client_id")

    client = client_manager.get_client_by_id(client_id)
    if client is None:
        # אותה תגובה כמו לקוח שקיים אך אין לו יעד, כדי לא
        # לאפשר גילוי אילו מזהי לקוח קיימים במערכת
        return json_error("לא ניתן לשלוח קוד אימות", status_code=400)

    # בחירת היעד מתוך הרשומה. הטלפון הוא ערוץ החובה
    if preferred_channel == "email" and client.email:
        destination = client.email
        channel = "email"
    else:
        destination = client.phone
        channel = "phone"

    if not destination:
        return json_error("לא ניתן לשלוח קוד אימות", status_code=400)

    success, info = create_and_send_otp(client.client_id, destination, channel=channel)

    if not success:
        return json_error("שליחת הקוד נכשלה, יש לנסות שוב", status_code=502)

    return jsonify({
        "sent": True,
        "channel": channel,
        "masked_destination": info["masked_destination"],
        "expires_in_minutes": info["expires_in_minutes"],
    })


@verification_bp.route("/verify-code", methods=["POST"])
def verify_verification_code():
    """
    שלב אימות שני, חלק שני: בדיקת הקוד.

    כל סוגי הכישלון מוחזרים באותה הודעה כללית.
    היוצא היחיד הוא חסימה, כי המשתמש חייב לדעת
    שאין טעם להמשיך לנסות.
    """
    data = request.get_json(silent=True) or {}

    client_id = data.get("client_id")
    code = data.get("code")

    if client_id is None:
        return json_error("חסר מזהה לקוח", field="client_id")

    if not code:
        return json_error("יש להזין את הקוד", field="code")

    is_valid, reason = verify_otp(client_id, code)

    if is_valid:
        return jsonify({"verified": True})

    if reason == "too_many_attempts":
        return jsonify({
            "verified": False,
            "locked": True,
            "message": "חרגת ממספר הניסיונות המותר",
        }), 429

    return jsonify({
        "verified": False,
        "locked": False,
        "message": GENERIC_FAILURE_MESSAGE,
    }), 401