# ============================================================
# api/chat_api.py
# נקודת הקצה של הצ'אטבוט.
#
# הקבוצה הזו פתוחה ללא התחברות בכוונה: הלקוחות של דנה
# אינן משתמשות במערכת ואין להן חשבון. האימות שלהן הוא
# זהותי ולא הרשאתי, והוא מתבצע בתוך השיחה עצמה.
#
# מזהה השיחה נשמר בעוגייה חתומה ולא בגוף הבקשה, כדי
# שלא ניתן יהיה להשתלט על שיחה מאומתת של מישהי אחרת
# באמצעות ניחוש מזהה.
# ============================================================

from flask import Blueprint, jsonify, request, session

from chatbot.state import conversation_store
from chatbot.flows import process_message
from api.helpers import json_error


chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")

# מפתח מזהה השיחה בתוך העוגייה החתומה
CHAT_SESSION_KEY = "chat_session_id"

# אורך מרבי להודעה. הודעה ארוכה מזה אינה שיחה אלא ניסיון הצפה
MAX_MESSAGE_LENGTH = 500


@chat_bp.route("", methods=["POST"])
def send_message():
    """
    מקבל הודעה מהלקוחה ומחזיר את תשובת הבוט.

    התגובה מכילה את המצב הנוכחי לצורך תצוגה בממשק,
    אך לעולם לא מכילה פרטים אישיים לפני אימות מלא.
    """
    data = request.get_json(silent=True) or {}
    message = data.get("message", "")

    if not message or not str(message).strip():
        return json_error("יש להזין הודעה", field="message")

    if len(str(message)) > MAX_MESSAGE_LENGTH:
        return json_error("ההודעה ארוכה מדי", field="message")

    # מזהה השיחה נשלף מהעוגייה, לא מגוף הבקשה
    session_id = session.get(CHAT_SESSION_KEY)
    conversation = conversation_store.get_or_create(session_id)

    # שמירת המזהה בחזרה, למקרה שנפתחה שיחה חדשה
    session[CHAT_SESSION_KEY] = conversation.session_id

    reply = process_message(conversation, str(message).strip())

    return jsonify({
        "reply": reply,
        "state": conversation.state,
        "verified": conversation.is_fully_verified(),
    })


@chat_bp.route("/reset", methods=["POST"])
def reset_conversation():
    """
    מסיים את השיחה הנוכחית ומתחיל חדשה.
    חשוב שיהיה זמין, כדי שלקוחה תוכל לנקות אחריה
    במחשב משותף.
    """
    session_id = session.get(CHAT_SESSION_KEY)

    if session_id:
        conversation_store.end(session_id)
        session.pop(CHAT_SESSION_KEY, None)

    return jsonify({"success": True})