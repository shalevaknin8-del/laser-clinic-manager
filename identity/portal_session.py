# ============================================================
# identity/portal_session.py
# אכיפת ה-session המאומת של הפורטל על נקודות קצה - מקביל בדיוק
# ל-auth/decorators.py אצל הצוות, אבל ל-Client ולא ל-User.
#
# Part 8 סעיף 1 במפרט: client_id תמיד מהטוקן המאומת, לעולם לא
# מפרמטר URL/גוף הבקשה. get_current_portal_client הוא המקום
# היחיד שבו client_id "נכנס" למערכת מבקשה נכנסת - כל route אחר
# משתמש רק ב-g.current_portal_client.client_id.
# ============================================================

from functools import wraps

from flask import request, jsonify, g

from db import get_session
from models import Client
from identity.tokens import decode_portal_token, TOKEN_TYPE_PORTAL_ACCESS
from auth.jwt_utils import TokenError


def _extract_bearer_token():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    return header[len("Bearer "):].strip()


def get_current_portal_client():
    """
    מחזירה את הלקוחה המאומתת (לפי access token בכותרת), או None.

    נשלפת מחדש מה-DB בכל בקשה ולא נשמרת בטוקן עצמו, כדי שלקוחה
    שנמחקה (למשל ע"י צוות) תאבד גישה מיידית - אותו עיקרון בדיוק
    כמו auth.decorators.get_current_user.
    """
    if hasattr(g, "current_portal_client"):
        return g.current_portal_client

    token = _extract_bearer_token()
    if token is None:
        g.current_portal_client = None
        return None

    try:
        payload = decode_portal_token(token, expected_type=TOKEN_TYPE_PORTAL_ACCESS)
    except TokenError:
        g.current_portal_client = None
        return None

    session = get_session()
    client = session.get(Client, int(payload["sub"]))

    g.current_portal_client = client
    return client


def require_portal_client(view_function):
    """חוסם גישה למי שאינה מאומתת (טוקן חסר/פג/לא תקף/לקוחה לא קיימת עוד)."""
    @wraps(view_function)
    def wrapper(*args, **kwargs):
        client = get_current_portal_client()
        if client is None:
            return jsonify({"error": "נדרש אימות"}), 401
        return view_function(*args, **kwargs)

    return wrapper
