# ============================================================
# managers/lead_manager.py
# מנהל הלידים - אחראי על ניהול לקוחות פוטנציאליים
# מכיל 5 מתודות CRUD + convert_lead_to_client להמרת ליד ללקוח
# ============================================================

from database import get_connection
from entities.lead import Lead
from entities.client import Client


class LeadManager:
    """
    Manager Class לניהול לידים.
    מספק פונקציה מיוחדת convert_lead_to_client להמרת ליד ללקוח.
    """

    def insert_lead(self, lead):
        """
        מוסיף ליד חדש לבסיס הנתונים.
        מקבל אובייקט Lead ומחזיר אותו עם ה-lead_id שהוקצה.
        """
        connection = get_connection()
        cursor = connection.cursor()
        
        sql_query = """
            INSERT INTO leads (
                full_name, phone, source, status, notes
            ) VALUES (?, ?, ?, ?, ?)
        """
        
        values = (
            lead.full_name,
            lead.phone,
            lead.source,
            lead.status,
            lead.notes
        )
        
        cursor.execute(sql_query, values)
        lead.lead_id = cursor.lastrowid
        
        connection.commit()
        connection.close()
        
        return lead


    def get_lead_by_id(self, lead_id):
        """
        שולף ליד לפי מזהה.
        מחזיר אובייקט Lead, או None אם לא נמצא.
        """
        connection = get_connection()
        cursor = connection.cursor()
        
        sql_query = "SELECT * FROM leads WHERE lead_id = ?"
        cursor.execute(sql_query, (lead_id,))
        
        row = cursor.fetchone()
        connection.close()
        
        if row is None:
            return None
        
        # סדר השדות ב-DB:
        # lead_id, full_name, phone, source, status, notes, created_at
        lead = Lead(
            lead_id=row[0],
            full_name=row[1],
            phone=row[2],
            source=row[3],
            status=row[4],
            notes=row[5]
        )
        
        return lead


    def get_all_leads(self):
        """
        שולף את כל הלידים במערכת.
        ממוין לפי תאריך יצירה - החדשים ראשונים (לדחיפות).
        """
        connection = get_connection()
        cursor = connection.cursor()
        
        # DESC = חדש לישן - כדי שדנה תראה קודם את הלידים החדשים
        sql_query = "SELECT * FROM leads ORDER BY created_at DESC"
        cursor.execute(sql_query)
        
        rows = cursor.fetchall()
        connection.close()
        
        leads = []
        for row in rows:
            lead = Lead(
                lead_id=row[0],
                full_name=row[1],
                phone=row[2],
                source=row[3],
                status=row[4],
                notes=row[5],
                created_at=row[6]
            )
            leads.append(lead)
        
        return leads


    def update_lead(self, lead):
        """
        מעדכן ליד קיים.
        מחזיר True אם עודכן, False אם לא נמצא.
        """
        if lead.lead_id is None:
            return False
        
        connection = get_connection()
        cursor = connection.cursor()
        
        sql_query = """
            UPDATE leads
            SET full_name = ?,
                phone = ?,
                source = ?,
                status = ?,
                notes = ?
            WHERE lead_id = ?
        """
        
        values = (
            lead.full_name,
            lead.phone,
            lead.source,
            lead.status,
            lead.notes,
            lead.lead_id
        )
        
        cursor.execute(sql_query, values)
        rows_affected = cursor.rowcount
        
        connection.commit()
        connection.close()
        
        return rows_affected > 0


    def delete_lead(self, lead_id):
        """
        מוחק ליד מבסיס הנתונים.
        לידים שלא הפכו ללקוחות ניתן למחוק ללא בעיה.
        מחזיר True אם נמחק, False אם לא נמצא.
        """
        connection = get_connection()
        cursor = connection.cursor()
        
        sql_query = "DELETE FROM leads WHERE lead_id = ?"
        cursor.execute(sql_query, (lead_id,))
        
        rows_affected = cursor.rowcount
        
        connection.commit()
        connection.close()
        
        return rows_affected > 0


    def convert_lead_to_client(self, lead_id, email=None, address=None):
        """
        ממיר ליד ללקוח - הפעולה העסקית המרכזית של המנהל.
        
        התהליך:
        1. שולפים את הליד
        2. בודקים שהוא עדיין לא הומר (למניעת כפילויות)
        3. יוצרים לקוח חדש עם פרטי הליד + email/address חדשים
        4. מעדכנים את סטטוס הליד ל-'converted'
        
        הפעולה מבוצעת כטרנזקציה - או שהכל מצליח, או שכלום לא קורה.
        
        פרמטרים:
        - lead_id: מזהה הליד שרוצים להמיר
        - email: אימייל הלקוח (אופציונלי - לא נאסף בליד)
        - address: כתובת הלקוח (אופציונלי - לא נאסף בליד)
        
        מחזירה: אובייקט Client חדש אם הצליח, None אם נכשל.
        """
        # שלב 1: שולפים את הליד
        lead = self.get_lead_by_id(lead_id)
        
        # בדיקה שהליד קיים
        if lead is None:
            print(f"ליד #{lead_id} לא נמצא")
            return None
        
        # שלב 2: בודקים שהוא עדיין לא הומר
        if lead.is_converted():
            print(f"ליד #{lead_id} כבר הומר ללקוח בעבר")
            return None
        
        # שלב 3+4: מבצעים את שתי הפעולות בטרנזקציה
        connection = get_connection()
        cursor = connection.cursor()
        
        try:
            # פעולה 1: יצירת לקוח חדש עם פרטי הליד
            cursor.execute("""
                INSERT INTO clients (full_name, phone, email, address)
                VALUES (?, ?, ?, ?)
            """, (lead.full_name, lead.phone, email, address))
            
            # שומרים את ה-ID של הלקוח החדש
            new_client_id = cursor.lastrowid
            
            # פעולה 2: מעדכנים את סטטוס הליד ל-'converted'
            cursor.execute("""
                UPDATE leads
                SET status = 'converted'
                WHERE lead_id = ?
            """, (lead_id,))
            
            # אם הגענו לכאן - שתי הפעולות הצליחו. שומרים.
            connection.commit()
            
            # יוצרים אובייקט Client להחזרה
            new_client = Client(
                client_id=new_client_id,
                full_name=lead.full_name,
                phone=lead.phone,
                email=email,
                address=address
            )
            
            print(f"ליד #{lead_id} הומר בהצלחה ללקוח #{new_client_id}")
            return new_client
            
        except Exception as error:
            # אם קרתה שגיאה - מבטלים הכל
            connection.rollback()
            print(f"שגיאה בהמרת ליד: {error}")
            return None
            
        finally:
            # תמיד סוגרים חיבור - גם אם הצליח וגם אם נכשל
            connection.close()