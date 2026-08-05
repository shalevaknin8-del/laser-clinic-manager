# ============================================================
# database.py
# ניהול חיבור לבסיס הנתונים SQLite
# ============================================================

import sqlite3
from pathlib import Path


# נתיב לקובץ בסיס הנתונים
DATABASE_PATH = Path("data/clinic.db")

# נתיב לקובץ הסכמה
SCHEMA_PATH = Path("schema.sql")


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