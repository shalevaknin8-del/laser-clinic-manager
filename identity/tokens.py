# ============================================================
# identity/tokens.py
# הנפקה ואימות של JWT ל-session המאומת של הפורטל.
#
# בכוונה *לא* משתמש ב-auth/jwt_utils.py הקיים: זה מיועד למשתמשות
# צוות (User, לפי user_id+role) והפורטל מיועד ללקוחות (Client,
# לפי client_id, בלי role בכלל). שני סוגי הטוקן חייבים להיות
# בלתי-ניתנים-להחלפה: "type" שונה לגמרי (portal_access/portal_refresh
# מול access/refresh הקיימים) מבטיח שטוקן לקוחה לעולם לא יתקבל
# ע"י auth/decorators.require_login של הצוות ולהפך, גם אם מישהו
# ינסה להעביר טוקן אחד במקום השני.
#
# אותה סיבה בדיוק ל-token_version על clients (migrations/012):
# מבטל refresh tokens קיימים ב-/logout או בכל ניתוק יזום, בלי
# טבלת session נפרדת - ראו auth/decorators.bump_token_version.
# ============================================================

from datetime import timedelta

from auth.jwt_utils import encode_token, decode_token, TokenError

PORTAL_ACCESS_TOKEN_MINUTES = 30
PORTAL_REFRESH_TOKEN_DAYS = 14

TOKEN_TYPE_PORTAL_ACCESS = "portal_access"
TOKEN_TYPE_PORTAL_REFRESH = "portal_refresh"


def create_portal_access_token(client):
    """טוקן קצר טווח - נושא רק את מזהה הלקוחה, בלי לגעת ב-DB בכל בקשה."""
    return encode_token(
        {"type": TOKEN_TYPE_PORTAL_ACCESS, "sub": str(client.client_id)},
        timedelta(minutes=PORTAL_ACCESS_TOKEN_MINUTES),
    )


def create_portal_refresh_token(client):
    """טוקן ארוך טווח - נושא גם token_version, לאימות מול ה-DB בזמן רענון."""
    return encode_token(
        {
            "type": TOKEN_TYPE_PORTAL_REFRESH,
            "sub": str(client.client_id),
            "token_version": client.token_version,
        },
        timedelta(days=PORTAL_REFRESH_TOKEN_DAYS),
    )


def create_portal_token_pair(client):
    """מוחזר אחרי /verify מוצלח - זוג הטוקנים שפותח את ה-session של הפורטל."""
    return create_portal_access_token(client), create_portal_refresh_token(client)


def decode_portal_token(token, expected_type):
    """
    מפענח ומאמת טוקן פורטל: חתימה, תוקף, וסוג. זורק TokenError
    (אותה מחלקה בדיוק כמו auth/jwt_utils.py) בכל בעיה.
    """
    return decode_token(token, expected_type=expected_type)


def bump_client_token_version(client, session):
    """
    מעלה את token_version של הלקוחה ב-1, ובכך מבטלת מיידית כל
    portal_refresh token קודם שהונפק לה - ראו auth/decorators.bump_token_version
    לאותו רעיון בדיוק אצל הצוות.
    """
    client.token_version = (client.token_version or 0) + 1
    session.add(client)
    session.commit()
