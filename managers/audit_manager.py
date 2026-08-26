# ============================================================
# managers/audit_manager.py
# יומן פעולות המערכת.
#
# מתעד מי ביצע מה, על איזו רשומה, ומתי.
# היומן משרת שתי מטרות: מענה לשאלה העסקית "מי ביטל
# את התור הזה", ושרשרת אחריות במקרה של חשד לשימוש לרעה.
#
# עיקרון: היומן אינו מכיל פרטים אישיים של לקוחות.
# הוא מתעד מזהים ופעולות בלבד.
# ============================================================

import sqlite3

from database import get_connection


# סוגי הפעולות המתועדות
ACTION_LOGIN_SUCCESS = "login.success"
ACTION_LOGIN_FAILED = "login.failed"
ACTION_LOGOUT = "logout"
ACTION_CREATE = "create"
ACTION_UPDATE = "update"
ACTION_DELETE = "delete"
ACTION_CANCEL = "cancel"
ACTION_PERMISSION_DENIED = "permission.denied"


class AuditManager:
    """כותב וקורא את יומן הפעולות."""

    def __init__(self):
        self.last_error = None

    def log(self, action, user=None, entity_type=None, entity_id=None,
            details=None, ip_address=None):
        """
        רושם פעולה ביומן.

        הכתיבה לעולם לא מפילה את הבקשה. אם היומן נכשל,
        הפעולה העסקית עצמה חייבת להמשיך כרגיל, כי חשוב
        יותר שדנה תוכל לעבוד מאשר שכל פעולה תתועד.
        """
        connection = get_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(
                "INSERT INTO audit_log "
                "(user_id, username, action, entity_type, entity_id, details, ip_address) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    user.user_id if user else None,
                    user.full_name if user else None,
                    action,
                    entity_type,
                    entity_id,
                    details,
                    ip_address,
                ),
            )
            connection.commit()
            return True

        except sqlite3.Error as error:
            self.last_error = str(error)
            return False

        finally:
            connection.close()

    def get_recent(self, limit=100):
        """
        מחזיר את הרשומות האחרונות ביומן.
        מיועד למסך הביקורת של המנהלת.
        """
        connection = get_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(
                "SELECT audit_id, user_id, username, action, entity_type, "
                "entity_id, details, ip_address, created_at "
                "FROM audit_log ORDER BY audit_id DESC LIMIT ?",
                (limit,),
            )

            return [
                {
                    "audit_id": row[0],
                    "user_id": row[1],
                    "user_name": row[2],
                    "action": row[3],
                    "entity_type": row[4],
                    "entity_id": row[5],
                    "details": row[6],
                    "ip_address": row[7],
                    "created_at": row[8],
                }
                for row in cursor.fetchall()
            ]

        finally:
            connection.close()