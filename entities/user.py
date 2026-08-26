# ============================================================
# entities/user.py
# ישות משתמש מערכת.
#
# שים לב: אין כאן שדה סיסמה, רק טביעת אצבע שלה.
# הסיסמה עצמה לא קיימת בזיכרון המערכת אחרי ההצפנה.
# ============================================================

from datetime import datetime


# התפקידים הקיימים במערכת
ROLE_ADMIN = "admin"
ROLE_EMPLOYEE = "employee"

VALID_ROLES = [ROLE_ADMIN, ROLE_EMPLOYEE]

# תרגום לעברית לצורך תצוגה בממשק
ROLE_LABELS = {
    ROLE_ADMIN: "מנהל",
    ROLE_EMPLOYEE: "עובד",
}


class User:
    """משתמש מערכת: דנה או אחת העובדות."""

    def __init__(self, phone, full_name, role=ROLE_EMPLOYEE,
                 password_hash=None, user_id=None, is_active=1,
                 failed_attempts=0, locked_until=None, last_login_at=None):
        self.user_id = user_id
        self.phone = phone
        self.full_name = full_name
        self.role = role
        self.password_hash = password_hash
        self.is_active = is_active
        self.failed_attempts = failed_attempts
        self.locked_until = locked_until
        self.last_login_at = last_login_at

    def is_admin(self):
        """מחזיר האם המשתמש הוא מנהל."""
        return self.role == ROLE_ADMIN

    def is_locked(self):
        """
        מחזיר האם החשבון נעול כרגע בעקבות ניסיונות כושלים.
        הנעילה זמנית ומתפוגגת מעצמה.
        """
        if not self.locked_until:
            return False
        return datetime.now() < datetime.fromisoformat(self.locked_until)

    def can_login(self):
        """מחזיר האם המשתמש רשאי להתחבר כרגע."""
        return bool(self.is_active) and not self.is_locked()

    def role_label(self):
        """מחזיר את שם התפקיד בעברית לתצוגה."""
        return ROLE_LABELS.get(self.role, self.role)

    def __str__(self):
        status = "פעיל" if self.is_active else "מושבת"
        return f"{self.full_name} ({self.phone}) - {self.role_label()} - {status}"