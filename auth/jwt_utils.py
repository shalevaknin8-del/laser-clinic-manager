# ============================================================
# auth/jwt_utils.py
# יצירה ואימות של access/refresh tokens.
#
# PyJWT נבחר במקום Flask-JWT-Extended בכוונה: ספרייה קטנה,
# חינמית, בלי "קסם" מוסתר - קל להסביר ולתחזק בצוות קטן.
#
# שני סוגי טוקן:
#   access  - קצר טווח (30 דקות), נשלח בכל בקשה כ-Bearer header
#   refresh - ארוך טווח (14 יום), משמש רק להנפקת access חדש
#
# refresh token מכיל גם token_version. אם הוא לא תואם לערך
# העדכני בטבלת users (למשל אחרי שינוי סיסמה או ניתוק יזום),
# הטוקן נחשב לא תקף גם אם תוקפו לא פג - זו הדרך לבטל refresh
# tokens בלי טבלת session/blacklist נפרדת.
# ============================================================

from datetime import datetime, timedelta, timezone

import jwt

from config import Config


ACCESS_TOKEN_MINUTES = 30
REFRESH_TOKEN_DAYS = 14

ALGORITHM = "HS256"

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


class TokenError(Exception):
    """נזרקת על כל טוקן לא תקין: פג תוקף, חתימה שגויה, או גרסה מבוטלת."""


def encode_token(payload, expires_delta):
    now = datetime.now(timezone.utc)
    full_payload = {
        **payload,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(full_payload, Config.SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(user):
    """טוקן קצר טווח - נושא את מה שנדרש לבדיקת הרשאות בכל בקשה, בלי לגעת ב-DB."""
    return encode_token(
        {
            "type": TOKEN_TYPE_ACCESS,
            "sub": str(user.user_id),
            "role": user.role,
        },
        timedelta(minutes=ACCESS_TOKEN_MINUTES),
    )


def create_refresh_token(user):
    """טוקן ארוך טווח - נושא רק מזהה + גרסה, לצורך אימות מול ה-DB בזמן רענון."""
    return encode_token(
        {
            "type": TOKEN_TYPE_REFRESH,
            "sub": str(user.user_id),
            "token_version": user.token_version,
        },
        timedelta(days=REFRESH_TOKEN_DAYS),
    )


def create_token_pair(user):
    """מחזיר (access_token, refresh_token) - זוג הטוקנים שמוחזר בהתחברות."""
    return create_access_token(user), create_refresh_token(user)


def decode_token(token, expected_type):
    """
    מפענח ומאמת טוקן: חתימה, תוקף, וסוג (access מול refresh).
    זורק TokenError בכל בעיה - קריאה אחת, בלי לבדוק שדות בנפרד
    בכל endpoint.
    """
    if not token:
        raise TokenError("Missing token")

    try:
        payload = jwt.decode(token, Config.SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise TokenError("Token expired")
    except jwt.InvalidTokenError:
        raise TokenError("Invalid token")

    if payload.get("type") != expected_type:
        raise TokenError(f"Expected {expected_type} token")

    return payload
