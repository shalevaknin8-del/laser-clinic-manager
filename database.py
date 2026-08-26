# ============================================================
# database.py
# ניהול חיבור לבסיס הנתונים SQLite
# ============================================================
import sqlite3
from pathlib import Path

from config import Config


# תיקיית הבסיס של הפרויקט, מחושבת יחסית למיקום הקובץ הזה.
# כך הנתיבים עובדים בלי קשר לתיקייה שממנה הורצה הפקודה
BASE_DIR = Path(__file__).resolve().parent

# נתיב לקובץ בסיס הנתונים, נקרא מקובץ הסביבה.
# בפרודקשן הוא מצביע מחוץ לתיקיית הפרויקט, כדי ש-git pull
# לא ידרוס את המסד של הקליניקה בעדכון קוד
DATABASE_PATH = Path(Config.DATABASE_PATH)
if not DATABASE_PATH.is_absolute():
    DATABASE_PATH = BASE_DIR / DATABASE_PATH

# יצירת התיקייה אם אינה קיימת, כדי שהמערכת תעלה
# גם בהתקנה נקייה בלי הכנה ידנית
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

# נתיב לקובץ הסכמה
SCHEMA_PATH = BASE_DIR / "schema.sql"

def get_connection():
    """
    מחזיר חיבור פעיל לבסיס הנתונים.
    כל פעם שקוראים לפונקציה הזאת - מקבלים חיבור חדש.
    """
    # פותח חיבור לקובץ ה-DB (יוצר אותו אם לא קיים)
    connection = sqlite3.connect(DATABASE_PATH)
    
    # מפעיל בדיקת מפתחות זרים (Foreign Keys)
    # ברירת המחדל של SQLite היא כבויה מסיבות היסטוריות
    connection.execute("PRAGMA foreign_keys = ON")
    
    # מצב WAL - מפריד בין יומן הכתיבה לקובץ הראשי
    # התוצאה: קריאות וכתיבות יכולות להתבצע במקביל בלי לחסום זו את זו
    connection.execute("PRAGMA journal_mode = WAL")
    
    # ממתין עד 5 שניות אם הקובץ נעול במקום להיכשל מיד
    connection.execute("PRAGMA busy_timeout = 5000")
    
    return connection


def initialize_database():
    """
    יוצר את כל הטבלאות בבסיס הנתונים לפי schema.sql.
    בטוח להריץ שוב ושוב - הפקודות משתמשות ב-IF NOT EXISTS.
    """
    # קורא את תוכן קובץ הסכמה
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    
    # פותח חיבור ל-DB
    connection = get_connection()
    
    # מריץ את כל הפקודות שבקובץ הסכמה בבת אחת
    connection.executescript(schema_sql)
    
    # שומר את השינויים
    connection.commit()
    
    # סוגר את החיבור
    connection.close()
    
    print("Database initialized successfully")


# בדיקה - אם מריצים את הקובץ ישירות, האתחול יתבצע
if __name__ == "__main__":
    initialize_database()