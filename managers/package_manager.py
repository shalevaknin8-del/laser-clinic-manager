# ============================================================
# managers/package_manager.py
# ניהול חבילות טיפולים: קטלוג חבילות (Package) וחבילות שנרכשו
# ע"י לקוחות ספציפיות (ClientPackage), כולל הפחתת מפגשים.
#
# חבילה = N מפגשים של טיפול *אחד* (לא חבילות מעורבות) - החלטה
# מכוונת לגודל הקליניקה, ראו models.Package.
#
# הכלל העסקי המרכזי (decrement_session_for_completed_appointment):
# כשתור שמקושר לחבילה משתנה לסטטוס 'completed', יורד מפגש אחד
# מיתרת החבילה של הלקוחה. זה נקרא מ-api/appointments_api.py בדיוק
# ברגע שהסטטוס עובר ל-completed, לא בשום מקום אחר - כך אי אפשר
# "לשכוח" להפחית, ואי אפשר גם להפחית פעמיים באותו מעבר סטטוס.
# ============================================================

from datetime import datetime, timezone

from db import get_session
from models import Package, ClientPackage, Treatment, Client


class PackageManager:
    def __init__(self):
        self.last_error = None

    @property
    def session(self):
        return get_session()

    # ---------- קטלוג חבילות ----------

    def create_package(self, name, treatment_id, total_sessions, price):
        self.last_error = None

        if not name or not str(name).strip():
            self.last_error = "יש להזין שם לחבילה"
            return None

        if self.session.get(Treatment, treatment_id) is None:
            self.last_error = "הטיפול שנבחר לא נמצא"
            return None

        try:
            total_sessions = int(total_sessions)
            price = float(price)
        except (TypeError, ValueError):
            self.last_error = "מספר המפגשים והמחיר חייבים להיות מספרים"
            return None

        if total_sessions <= 0:
            self.last_error = "מספר המפגשים בחבילה חייב להיות גדול מאפס"
            return None

        package = Package(
            name=str(name).strip(),
            treatment_id=treatment_id,
            total_sessions=total_sessions,
            price=price,
            is_active=True,
        )
        self.session.add(package)
        self.session.commit()
        return package

    def get_package_by_id(self, package_id):
        return self.session.get(Package, package_id)

    def get_all_packages(self, include_inactive=True):
        query = self.session.query(Package)
        if not include_inactive:
            query = query.filter_by(is_active=True)
        return query.order_by(Package.name).all()

    def set_active(self, package_id, is_active):
        package = self.get_package_by_id(package_id)
        if package is None:
            self.last_error = "החבילה לא נמצאה"
            return False
        package.is_active = bool(is_active)
        self.session.commit()
        return True

    # ---------- חבילות של לקוחה ספציפית ----------

    def purchase_package_for_client(self, client_id, package_id):
        """
        רוכשת חבילה עבור לקוחה: יוצרת ClientPackage עם יתרת מפגשים
        מלאה (total_sessions של החבילה). לא נוגעת בחשבוניות - הפקת
        חשבונית על הרכישה, אם רוצים, נשארת פעולה נפרדת ב-invoices_api.
        """
        self.last_error = None

        if self.session.get(Client, client_id) is None:
            self.last_error = "הלקוחה לא נמצאה"
            return None

        package = self.get_package_by_id(package_id)
        if package is None:
            self.last_error = "החבילה לא נמצאה"
            return None

        if not package.is_active:
            self.last_error = "החבילה אינה פעילה עוד"
            return None

        client_package = ClientPackage(
            client_id=client_id,
            package_id=package_id,
            sessions_remaining=package.total_sessions,
            is_active=True,
        )
        self.session.add(client_package)
        self.session.commit()
        return client_package

    def get_client_package_by_id(self, client_package_id):
        return self.session.get(ClientPackage, client_package_id)

    def get_all_usable_client_packages(self):
        """
        מחזירה את כל החבילות הפעילות עם יתרת מפגשים, לכל הלקוחות.
        משמשת למסך רשימת הלקוחות כדי להציג "חבילה פעילה" לכל אחת
        בלי N+1 שאילתות - שליפה אחת, סינון/קיבוץ לפי client_id
        בפייתון, באותה גישה שכבר נהוגה ב-api/dashboard_api.py.
        """
        return (
            self.session.query(ClientPackage)
            .filter(ClientPackage.is_active == True, ClientPackage.sessions_remaining > 0)  # noqa: E712
            .all()
        )

    def get_client_packages(self, client_id, only_usable=False):
        """
        מחזיר את חבילות הלקוחה. only_usable=True מסנן רק חבילות
        פעילות עם מפגשים שנותרו - אלה שרלוונטיות לקביעת תור חדש.
        """
        query = self.session.query(ClientPackage).filter_by(client_id=client_id)
        if only_usable:
            query = query.filter(
                ClientPackage.is_active == True,  # noqa: E712
                ClientPackage.sessions_remaining > 0,
            )
        return query.order_by(ClientPackage.purchased_at.desc()).all()

    def decrement_session_for_completed_appointment(self, client_package_id):
        """
        מפחיתה מפגש אחד מיתרת החבילה. נקראת פעם אחת בדיוק, ברגע
        שתור מקושר לחבילה עובר לסטטוס 'completed' (ראו
        api/appointments_api.py). כשהיתרה מגיעה לאפס, החבילה
        מסומנת לא-פעילה - אי אפשר יותר לשבץ תור חדש נגדה.

        מחזירה True אם הופחת בהצלחה, False אם לא נמצאה חבילה
        כזו או שאין לה יתרה להפחית (מגן מפני הפחתה כפולה בטעות).
        """
        client_package = self.get_client_package_by_id(client_package_id)
        if client_package is None:
            self.last_error = "החבילה המקושרת לא נמצאה"
            return False

        if client_package.sessions_remaining <= 0:
            self.last_error = "אין יתרת מפגשים להפחתה בחבילה זו"
            return False

        client_package.sessions_remaining -= 1
        if client_package.sessions_remaining == 0:
            client_package.is_active = False

        self.session.commit()
        return True
