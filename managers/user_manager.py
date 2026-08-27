# ============================================================
# managers/user_manager.py
# ניהול משתמשי המערכת: יצירה, אימות, נעילה ואיפוס.
#
# גרסת ORM (SQLAlchemy) - הפעולות וההתנהגות העסקית זהות
# ל-100% לגרסה הקודמת (raw SQL), רק שכבת הגישה לנתונים השתנתה.
# חתימות המתודות נשארו זהות בכוונה, כדי שקוד קורא קיים (API,
# בדיקות) ימשיך לעבוד בלי שינוי.
#
# עקרונות אבטחה שנאכפים כאן (ללא שינוי):
#   1. סיסמה נשמרת כטביעת אצבע בלבד
#   2. נעילה זמנית אחרי ניסיונות כושלים
#   3. הודעת כישלון אחידה, בלי לגלות אם המשתמש קיים
#   4. השבתה במקום מחיקה
# ============================================================

from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError

from db import get_session
from models import User as UserModel
from entities.user import VALID_ROLES, ROLE_EMPLOYEE
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
    """מנהל את טבלת המשתמשים דרך ה-ORM."""

    def __init__(self):
        self.last_error = None

    @property
    def session(self):
        """
        לא נשמר session בודד ב-__init__ בכוונה: ה-manager נוצר
        פעם אחת ברמת המודול (למשל user_manager = UserManager()
        ב-api/auth_api.py), אבל get_session() חייב להיקרא בכל
        פעולה מחדש - הוא scoped_session לפי thread, ותפיסת מופע
        יחיד ב-__init__ הייתה "נועלת" את כל הבקשות העתידיות ל-
        thread שבו ה-manager נוצר (thread הטעינה של האפליקציה).
        ה-property הזה שקוף לכל שאר הקוד במחלקה - self.session
        תמיד מחזיר את ה-session הנכון של ה-thread/בקשה הנוכחית.
        """
        return get_session()

    def create_user(self, phone, password, full_name, role=ROLE_EMPLOYEE):
        """
        יוצר משתמש חדש.
        המזהה הוא מספר הטלפון, כדי שלא יהיה מה לזכור
        וכדי שאיפוס סיסמה יוכל להישלח אליו.

        מחזיר אובייקט User (מודל ה-ORM), או None אם היצירה נכשלה.
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

        user = UserModel(
            phone=normalized_phone,
            password_hash=hash_password(password),
            full_name=str(full_name).strip(),
            role=role,
            password_changed_at=datetime.now().isoformat(),
        )

        try:
            self.session.add(user)
            self.session.commit()
            return user

        except IntegrityError:
            self.session.rollback()
            self.last_error = "מספר הטלפון כבר רשום במערכת"
            return None

        except Exception as error:
            self.session.rollback()
            self.last_error = translate_db_error(error, "יצירת משתמש")
            return None

    def get_user_by_phone(self, phone):
        """מאתר משתמש לפי מספר טלפון, אחרי נרמול."""
        normalized_phone = normalize_phone(phone)
        if normalized_phone is None:
            return None

        return (
            self.session.query(UserModel)
            .filter_by(phone=normalized_phone)
            .first()
        )

    def get_user_by_id(self, user_id):
        """מאתר משתמש לפי מזהה. נחוץ לאימות טוקן ה-access בכל בקשה."""
        return self.session.get(UserModel, user_id)

    def get_all_users(self):
        """מחזיר את כל המשתמשים, כולל מושבתים."""
        return (
            self.session.query(UserModel)
            .order_by(UserModel.role, UserModel.full_name)
            .all()
        )

    def _is_locked(self, user):
        if not user.locked_until:
            return False
        return datetime.now() < datetime.fromisoformat(user.locked_until)

    def _record_failed_attempt(self, user):
        """
        מגדיל את מונה הכישלונות ונועל את החשבון בעת הצורך.
        הנעילה זמנית ומתפוגגת מעצמה, כדי שטעות אנוש
        לא תנעל עובדת מחוץ למערכת לתמיד.
        """
        user.failed_attempts = (user.failed_attempts or 0) + 1

        if user.failed_attempts >= MAX_FAILED_ATTEMPTS:
            user.locked_until = (datetime.now() + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()

        self.session.commit()

    def _record_successful_login(self, user):
        """מאפס את מונה הכישלונות ומעדכן את מועד הכניסה."""
        user.failed_attempts = 0
        user.locked_until = None
        user.last_login_at = datetime.now().isoformat()
        self.session.commit()

    def authenticate(self, phone, password):
        """
        מאמת מספר טלפון וסיסמה.

        מחזיר אובייקט User בהצלחה, או None בכישלון.
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

        if self._is_locked(user):
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

        מעלה גם את token_version, כדי שכל refresh token שהונפק
        לפני שינוי הסיסמה יפסיק לעבוד מיידית - אחרת מישהי שגנבה
        טוקן ישן יכולה להמשיך להשתמש בו אחרי שהבעלים כבר החליפה סיסמה.
        """
        self.last_error = None

        is_valid, error_message = validate_password_strength(new_password)
        if not is_valid:
            self.last_error = error_message
            return False

        user = self.get_user_by_id(user_id)
        if user is None:
            self.last_error = "המשתמש לא נמצא"
            return False

        user.password_hash = hash_password(new_password)
        user.password_changed_at = datetime.now().isoformat()
        user.failed_attempts = 0
        user.locked_until = None
        user.token_version = (user.token_version or 0) + 1
        self.session.commit()

        return True

    def set_active(self, user_id, is_active):
        """
        מפעיל או משבית משתמש.
        השבתה מחליפה מחיקה, כדי שרשומות היומן יישארו מקושרות.

        השבתה גם מעלה token_version, כדי שרענון טוקן קיים לא
        ימשיך לעבוד אחרי שהעובדת כבר לא פעילה.
        """
        self.last_error = None

        user = self.get_user_by_id(user_id)
        if user is None:
            self.last_error = "המשתמש לא נמצא"
            return False

        user.is_active = 1 if is_active else 0
        if not is_active:
            user.token_version = (user.token_version or 0) + 1
        self.session.commit()

        return True

    def count_active_admins(self):
        """
        סופר מנהלים פעילים.
        משמש כדי למנוע מצב שבו המנהל האחרון משבית את עצמו
        ואיש אינו יכול עוד לנהל את המערכת.
        """
        return (
            self.session.query(UserModel)
            .filter_by(role="admin", is_active=1)
            .count()
        )
