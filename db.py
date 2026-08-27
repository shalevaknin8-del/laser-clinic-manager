# ============================================================
# db.py
# חיבור ה-ORM (SQLAlchemy) לאותו קובץ SQLite בדיוק שבו משתמש
# database.py הגולמי - שני המנגנונים חיים זה לצד זה במהלך
# המעבר ההדרגתי (ראו models.py).
#
# session אחד לכל בקשה, נסגר תמיד ב-teardown - אותו עיקרון
# בדיוק כמו database.get_connection() שנסגר בסוף כל פעולה.
# ============================================================

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, scoped_session

from database import DATABASE_PATH

engine = create_engine(
    f"sqlite:///{DATABASE_PATH}",
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _enforce_foreign_keys(dbapi_connection, connection_record):
    """
    מפעיל בדיקת מפתחות זרים על כל חיבור חדש - בדיוק כמו
    database.get_connection() הגולמי. ברירת המחדל של SQLite היא
    כבויה (מסיבות היסטוריות), ו-SQLAlchemy לא מדליק אותה לבד.
    בלעדי זה, מחיקת לקוח עם תורים/חשבוניות מקושרים הייתה מצליחה
    בשקט במקום להיחסם - יתמות רשומות בלי שאף אחד ידע.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()

# scoped_session -> session נפרד ובטוח לכל thread של הבקשה,
# בדיוק כמו שכל קריאה ל-get_connection() פותחת חיבור עצמאי משלה
#
# expire_on_commit=False בכוונה: ברירת המחדל של SQLAlchemy מפקיעה
# (expire) את כל השדות של כל אובייקט אחרי כל commit, כדי להבטיח
# קריאה טרייה מה-DB בפעם הבאה שניגשים אליהם. אבל הדפוס הרגיל בקוד
# הזה הוא שמנהל מחזיר אובייקט (למשל client_manager.insert_client)
# והקוד הקורא ממשיך לקרוא ממנו שדות (result.client_id) אחרי
# ה-commit, ולפעמים אחרי שה-session כבר הוסר (teardown של בקשה
# קודמת). בלי הדגל הזה כל גישה כזאת הייתה יכולה לזרוק
# DetachedInstanceError. המחיר: אם מישהו אחר שינה את הרשומה
# בינתיים, האובייקט בזיכרון לא יתעדכן לבד - זה תמיד היה גם
# המצב בגרסת ה-SQL הגולמי (כל get_connection() חדש קרא ערכים
# פעם אחת ולא "עקב" אחרי שינויים חיצוניים).
SessionLocal = scoped_session(
    sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
)


def get_session():
    """מחזיר את ה-session הפעיל של ה-thread/בקשה הנוכחית."""
    return SessionLocal()


def remove_session(exception=None):
    """
    סוגר ומנקה את ה-session בסוף הבקשה.
    נרשם כ-teardown ב-app.py, כדי שאף session לא יישאר פתוח
    בין בקשה לבקשה (אותה סיבה בדיוק שבגללה get_connection()
    הרגיל תמיד נסגר ב-finally).
    """
    SessionLocal.remove()


def init_orm_tables():
    """
    יוצר את הטבלאות החדשות לגמרי (rooms/machines/staff_availability/
    staff_time_off/packages/client_packages) אם הן לא קיימות.

    לא נוגע בטבלאות הקיימות (clients/users/...) - אלה מנוהלות
    ע"י database.initialize_database() + migrations/, כדי שלא
    יהיו שני מקורות אמת סותרים לאותה טבלה.
    """
    from models import Base, Room, Machine, StaffAvailability, StaffTimeOff, Package, ClientPackage

    new_only_tables = [
        Room.__table__, Machine.__table__, StaffAvailability.__table__,
        StaffTimeOff.__table__, Package.__table__, ClientPackage.__table__,
    ]
    Base.metadata.create_all(engine, tables=new_only_tables)
