# ============================================================
# managers/user_manager.py
# ניהול משתמשי המערכת: יצירה, אימות, נעילה ואיפוס.
#
# עקרונות אבטחה שנאכפים כאן:
#   1. סיסמה נשמרת כטביעת אצבע בלבד
#   2. נעילה זמנית אחרי ניסיונות כושלים
#   3. הודעת כישלון אחידה, בלי לגלות אם המשתמש קיים
#   4. השבתה במקום מחיקה
# ============================================================

import sqlite3
from datetime import datetime, timedelta

from database import get_connection
from entities.user import User, VALID_ROLES, ROLE_EMPLOYEE
from utils.passwords import (
    hash_password,
    verify_password,
    validate_password_strength,
)
from utils.validators import normalize_phone
from utils.db_errors import translate_db_error


# מספר הכישלונות שאחריהם החשבון ננעל
MAX_FAILED_ATTEMPTS = 5

# משך הנעילה בדקות
LOCKOUT_MINUTES = 15


class UserManager:
    """מנהל את טבלת המשתמשים."""

    def __init__(self):
        self.last_error = None

    def _row_to_user(self, row):
        """ממיר שורה מהמסד לאובייקט משתמש."""
        if row is None:
            return None
        return User(
            user_id=row[0],
            phone=row[1],
            password_hash=row[2],
            full_name=row[3],
            role=row[4],
            is_active=row[5],
            failed_attempts=row[6],
            locked_until=row[7],
            last_login_at=row[8],
        )

    def create_user(self, phone, password, full_name, role=ROLE_EMPLOYEE):
        """
        יוצר משתמש חדש.
        המזהה הוא מספר הטלפון, כדי שלא יהיה מה לזכור
        וכדי שאיפוס סיסמה יוכל להישלח אליו.

        מחזיר אובייקט משתמש, או None אם היצירה נכשלה.
        """
        self.last_error = None

        normalized_phone = normalize_phone(phone)
        if normalized_phone is None:
            self.last_error = "מספר טלפון לא תקין"
            return None

        if not full_name or not str(full_name).strip():
            self.last_error = "יש להזין שם מלא"
            return None

        if role not in VALID_ROLES:
            self.last_error = "תפקיד לא תקין"
            return None

        is_valid, error_message = validate_password_strength(password)
        if not is_valid:
            self.last_error = error_message
            return None

        password_hash = hash_password(password)
        now = datetime.now().isoformat()

        connection = get_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(
                "INSERT INTO users "
                "(phone, password_hash, full_name, role, password_changed_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (normalized_phone, password_hash, str(full_name).strip(), role, now),
            )
            connection.commit()

            return User(
                user_id=cursor.lastrowid,
                phone=normalized_phone,
                full_name=str(full_name).strip(),
                role=role,
                password_hash=password_hash,
            )

        except sqlite3.IntegrityError:
            self.last_error = "מספר הטלפון כבר רשום במערכת"
            return None

        except sqlite3.Error as error:
            self.last_error = translate_db_error(error, "יצירת משתמש")
            return None

        finally:
            connection.close()

    def get_user_by_phone(self, phone):
        """מאתר משתמש לפי מספר טלפון, אחרי נרמול."""
        normalized_phone = normalize_phone(phone)
        if normalized_phone is None:
            return None

        connection = get_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(
                "SELECT user_id, phone, password_hash, full_name, role, "
                "is_active, failed_attempts, locked_until, last_login_at "
                "FROM users WHERE phone = ?",
                (normalized_phone,),
            )
            return self._row_to_user(cursor.fetchone())

        finally:
            connection.close()

    def get_user_by_id(self, user_id):
        """מאתר משתמש לפי מזהה. נחוץ לשחזור session."""
        connection = get_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(
                "SELECT user_id, phone , password_hash, full_name, role, "
                "is_active, failed_attempts, locked_until, last_login_at "
                "FROM users WHERE user_id = ?",
                (user_id,),
            )
            return self._row_to_user(cursor.fetchone())

        finally:
            connection.close()

    def get_all_users(self):
        """מחזיר את כל המשתמשים, כולל מושבתים."""
        connection = get_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(
                "SELECT user_id, phone, password_hash, full_name, role, "
                "is_active, failed_attempts, locked_until, last_login_at "
                "FROM users ORDER BY role, full_name"
            )
            return [self._row_to_user(row) for row in cursor.fetchall()]

        finally:
            connection.close()

    def _record_failed_attempt(self, user):
        """
        מגדיל את מונה הכישלונות ונועל את החשבון בעת הצורך.
        הנעילה זמנית ומתפוגגת מעצמה, כדי שטעות אנוש
        לא תנעל עובדת מחוץ למערכת לתמיד.
        """
        new_count = user.failed_attempts + 1
        locked_until = None

        if new_count >= MAX_FAILED_ATTEMPTS:
            locked_until = (datetime.now() + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()

        connection = get_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(
                "UPDATE users SET failed_attempts = ?, locked_until = ? "
                "WHERE user_id = ?",
                (new_count, locked_until, user.user_id),
            )
            connection.commit()
        finally:
            connection.close()

    def _record_successful_login(self, user):
        """מאפס את מונה הכישלונות ומעדכן את מועד הכניסה."""
        connection = get_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(
                "UPDATE users SET failed_attempts = 0, locked_until = NULL, "
                "last_login_at = ? WHERE user_id = ?",
                (datetime.now().isoformat(), user.user_id),
            )
            connection.commit()
        finally:
            connection.close()

    def authenticate(self, phone, password):
        """
        מאמת שם משתמש וסיסמה.

        מחזיר אובייקט משתמש בהצלחה, או None בכישלון.
        הודעת הכישלון אחידה בכוונה ואינה מלמדת האם שם
        המשתמש קיים. אחרת המערכת מאפשרת למפות משתמשים.

        מחזיר גם reason, לשימוש פנימי ביומן בלבד.
        """
        self.last_error = None

        user = self.get_user_by_phone(phone)

        if user is None:
            self.last_error = "מספר טלפון או סיסמה שגויים"
            return None, "unknown_user"

        if not user.is_active:
            self.last_error = "מספר טלפון או סיסמה שגויים"
            return None, "inactive"

        if user.is_locked():
            self.last_error = (
                f"החשבון נעול זמנית עקב ניסיונות כושלים. "
                f"יש לנסות שוב בעוד {LOCKOUT_MINUTES} דקות"
            )
            return None, "locked"

        if not verify_password(password, user.password_hash):
            self._record_failed_attempt(user)
            self.last_error = "שם משתמש או סיסמה שגויים"
            return None, "wrong_password"

        self._record_successful_login(user)
        return user, "ok"

    def set_password(self, user_id, new_password):
        """
        מגדיר סיסמה חדשה למשתמש.
        משמש גם ליצירה וגם לאיפוס על ידי מנהל.
        """
        self.last_error = None

        is_valid, error_message = validate_password_strength(new_password)
        if not is_valid:
            self.last_error = error_message
            return False

        connection = get_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(
                "UPDATE users SET password_hash = ?, password_changed_at = ?, "
                "failed_attempts = 0, locked_until = NULL WHERE user_id = ?",
                (hash_password(new_password), datetime.now().isoformat(), user_id),
            )
            connection.commit()

            if cursor.rowcount == 0:
                self.last_error = "המשתמש לא נמצא"
                return False

            return True

        finally:
            connection.close()

    def set_active(self, user_id, is_active):
        """
        מפעיל או משבית משתמש.
        השבתה מחליפה מחיקה, כדי שרשומות היומן יישארו מקושרות.
        """
        self.last_error = None

        connection = get_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(
                "UPDATE users SET is_active = ? WHERE user_id = ?",
                (1 if is_active else 0, user_id),
            )
            connection.commit()

            if cursor.rowcount == 0:
                self.last_error = "המשתמש לא נמצא"
                return False

            return True

        finally:
            connection.close()

    def count_active_admins(self):
        """
        סופר מנהלים פעילים.
        משמש כדי למנוע מצב שבו המנהל האחרון משבית את עצמו
        ואיש אינו יכול עוד לנהל את המערכת.
        """
        connection = get_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = 1"
            )
            return cursor.fetchone()[0]

        finally:
            connection.close()