# ============================================================
# managers/client_manager.py
# מנהל הלקוחות - גרסת ORM (SQLAlchemy).
#
# חתימות המתודות ואופן הקריאה נשארו זהים לגרסה הקודמת (raw SQL)
# בכוונה: insert_client/update_client עדיין מקבלים אובייקט עם
# full_name/phone/email/address (למשל entities.client.Client),
# וכל מתודת get_* עדיין מחזירה אובייקט עם אותם שדות בדיוק -
# כך שהצ'אטבוט (chatbot/flows.py, chatbot/verification.py) וכל
# קוד אחר שכבר צורך את המנהל הזה ממשיכים לעבוד בלי שום שינוי.
# ============================================================

from models import Client as ClientModel
from db import get_session
from utils.db_errors import translate_db_error
from utils.datetime_utils import now_jerusalem


class ClientManager:
    """
    Manager Class לניהול לקוחות במערכת, מגובה ORM.

    בכל פעולה שנכשלת, הודעת השגיאה נשמרת ב-last_error
    וניתן לקרוא אותה מיד אחרי הקריאה.
    """

    def __init__(self):
        self.last_error = None

    @property
    def session(self):
        """
        get_session() נקרא בכל גישה מחדש (לא נשמר ב-__init__) כי
        ה-manager נוצר פעם אחת ברמת המודול, וזה scoped_session לפי
        thread - ראו ההסבר המלא ב-managers/user_manager.py.
        """
        return get_session()

    def insert_client(self, client):
        """
        מוסיף לקוח חדש לבסיס הנתונים.
        מחזיר את אובייקט ה-ORM עם client_id, או None אם נכשל.

        profile_completed_at מסומן "עכשיו" במפורש: זהו מסלול היצירה
        ה"רגיל" (טופס הצוות, בדיקות) - בניגוד ל"שלד" הזמני שהפורטל
        יוצר (identity.identify_or_create_shell, שעוקף את המנהל הזה
        ובונה Client ישירות עם profile_completed_at=None בכוונה).
        """
        self.last_error = None

        row = ClientModel(
            full_name=client.full_name,
            phone=client.phone,
            email=client.email,
            address=client.address,
            profile_completed_at=now_jerusalem().isoformat(),
        )

        try:
            self.session.add(row)
            self.session.commit()
            return row

        except Exception as error:
            self.session.rollback()
            self.last_error = translate_db_error(error, "הוספת לקוח")
            return None

    def get_client_by_id(self, client_id):
        """שולף לקוח בודד לפי מזהה. מחזיר None אם לא נמצא."""
        return self.session.get(ClientModel, client_id)

    def get_all_clients(self):
        """שולף את כל הלקוחות, ממויין לפי שם."""
        return (
            self.session.query(ClientModel)
            .order_by(ClientModel.full_name)
            .all()
        )

    def update_client(self, client):
        """
        מעדכן לקוח קיים. מחזיר True אם עודכן, False אם לא נמצא.
        """
        if client.client_id is None:
            return False

        row = self.session.get(ClientModel, client.client_id)
        if row is None:
            return False

        row.full_name = client.full_name
        row.phone = client.phone
        row.email = client.email
        row.address = client.address
        self.session.commit()

        return True

    def delete_client(self, client_id):
        """
        מוחק לקוח. מחזיר True אם נמחק, False אם לא נמצא או שיש
        רשומות מקושרות (תורים/חשבוניות) - FK constraint עדיין
        אוכף את זה ברמת ה-DB, בדיוק כמו קודם.
        """
        self.last_error = None

        row = self.session.get(ClientModel, client_id)
        if row is None:
            self.last_error = "הלקוח לא נמצא במערכת"
            return False

        try:
            self.session.delete(row)
            self.session.commit()
            return True

        except Exception as error:
            self.session.rollback()
            if "foreign key" in str(error).lower():
                self.last_error = (
                    "לא ניתן למחוק את הלקוח - קיימים לו תורים או חשבוניות. "
                    "יש למחוק אותם קודם."
                )
            else:
                self.last_error = translate_db_error(error, "מחיקת לקוח")
            return False

    def set_national_id(self, client_id, national_id):
        """שומר טביעת אצבע של תעודת זהות עבור לקוח. ראו utils/security.py."""
        from utils.validators import validate_national_id, normalize_national_id
        from utils.security import hash_national_id

        self.last_error = None

        is_valid, error_message = validate_national_id(national_id)
        if not is_valid:
            self.last_error = error_message
            return False

        row = self.session.get(ClientModel, client_id)
        if row is None:
            self.last_error = "הלקוח לא נמצא"
            return False

        normalized = normalize_national_id(national_id)
        row.national_id_hash = hash_national_id(normalized)
        self.session.commit()

        return True

    def verify_client_national_id(self, client_id, national_id):
        """
        בודק האם תעודת הזהות שהוזנה תואמת ללקוח. מחזיר True/False בלבד -
        לא מדליף מידע על הסיבה לכישלון, ולא על הערך השמור.
        """
        from utils.validators import normalize_national_id
        from utils.security import verify_national_id

        row = self.session.get(ClientModel, client_id)
        if row is None or row.national_id_hash is None:
            return False

        normalized = normalize_national_id(national_id)
        if normalized is None:
            return False

        return verify_national_id(normalized, row.national_id_hash)

    def has_national_id(self, client_id):
        """בודק האם ללקוח כבר שמורה תעודת זהות."""
        row = self.session.get(ClientModel, client_id)
        return row is not None and row.national_id_hash is not None

    def get_client_by_phone(self, phone):
        """
        שולף לקוח לפי טלפון מנורמל. מחזיר None אם לא נמצא או אם
        הטלפון לא תקין - הקוראת (identity/) אחראית להגיב זהה בשני
        המקרים, כדי לא לדלוף האם מספר קיים במערכת (סעיף 4 במפרט).
        """
        from utils.validators import normalize_phone

        normalized = normalize_phone(phone)
        if normalized is None:
            return None

        return (
            self.session.query(ClientModel)
            .filter(ClientModel.phone == normalized)
            .first()
        )

    def search_clients_by_name(self, name_query):
        """
        מחפש לקוחות לפי התאמה חלקית בשם (LIKE, מבוטח מהזרקת SQL
        כי ה-ORM תמיד מפרמט ערכים - בדיוק כמו סימני השאלה בגרסה
        הגולמית הקודמת).
        """
        if not name_query or not str(name_query).strip():
            return []

        pattern = f"%{str(name_query).strip()}%"

        return (
            self.session.query(ClientModel)
            .filter(ClientModel.full_name.like(pattern))
            .order_by(ClientModel.full_name)
            .all()
        )

    def set_health_declaration(self, client_id, file_path):
        """
        רושם שהלקוחה חתמה על הצהרת בריאות, ושומר את נתיב הקובץ
        המקומי (ראו api/clients_api.py - העלאת המסמך עצמה).
        אין S3, אין DocuSign - קובץ על הדיסק המקומי + נתיב ב-DB בלבד.
        """
        row = self.session.get(ClientModel, client_id)
        if row is None:
            self.last_error = "הלקוח לא נמצא"
            return False

        row.has_signed_health_declaration = True
        row.health_declaration_file_path = file_path
        self.session.commit()

        return True
