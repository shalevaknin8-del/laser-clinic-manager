# ============================================================
# managers/client_manager.py
# מנהל הלקוחות - אחראי על כל הפעולות מול טבלת clients
# מכיל 5 מתודות CRUD: insert, get_by_id, get_all, update, delete
# ============================================================

from database import get_connection
from entities.client import Client
from utils.db_errors import translate_db_error

class ClientManager:
    """
    Manager Class לניהול לקוחות במערכת.
    כל הפעולות מול טבלת clients עוברות דרך המחלקה הזאת.
    
    בכל פעולה שנכשלת, הודעת השגיאה נשמרת ב-last_error
    וניתן לקרוא אותה מיד אחרי הקריאה.
    """

    def __init__(self):
        # הודעת השגיאה האחרונה - None כשהכל תקין
        self.last_error = None

    def insert_client(self, client):
        """
        מוסיף לקוח חדש לבסיס הנתונים.
        מחזיר את האובייקט עם client_id, או None אם נכשל.
        במקרה כישלון - ההסבר נמצא ב-self.last_error
        """
        # מאפסים שגיאה קודמת בתחילת כל פעולה
        self.last_error = None
        connection = None

        try:
            connection = get_connection()
            cursor = connection.cursor()

            sql_query = """
                INSERT INTO clients (
                    full_name, phone, email, address
                ) VALUES (?, ?, ?, ?)
            """

            values = (
                client.full_name,
                client.phone,
                client.email,
                client.address
            )

            cursor.execute(sql_query, values)
            client.client_id = cursor.lastrowid

            connection.commit()
            return client

        except Exception as error:
            # מבטלים שינויים חלקיים
            if connection is not None:
                connection.rollback()

            self.last_error = translate_db_error(error, "הוספת לקוח")
            return None

        finally:
            # תמיד סוגרים - גם בהצלחה וגם בכישלון
            if connection is not None:
                connection.close()


    def get_client_by_id(self, client_id):
        """
        שולף לקוח בודד לפי מזהה.
        מחזיר אובייקט Client, או None אם הלקוח לא נמצא.
        """
        connection = get_connection()
        cursor = connection.cursor()
        
        sql_query = "SELECT * FROM clients WHERE client_id = ?"
        cursor.execute(sql_query, (client_id,))
        
        row = cursor.fetchone()
        connection.close()
        
        # אם לא נמצא לקוח - מחזירים None
        if row is None:
            return None
        
        # ממירים את השורה (tuple) לאובייקט Client
        client = Client(
            client_id=row[0],
            full_name=row[1],
            phone=row[2],
            email=row[3],
            address=row[4]
        )
        
        return client


    def get_all_clients(self):
        """
        שולף את כל הלקוחות במערכת.
        מחזיר רשימה של אובייקטי Client (יכולה להיות ריקה).
        """
        connection = get_connection()
        cursor = connection.cursor()
        
        # ממויין לפי שם - כדי שקל יהיה למצוא לקוחות בתפריט
        sql_query = "SELECT * FROM clients ORDER BY full_name"
        cursor.execute(sql_query)
        
        rows = cursor.fetchall()
        connection.close()
        
        clients = []
        
        # ממירים כל שורה לאובייקט Client ומוסיפים לרשימה
        for row in rows:
            client = Client(
                client_id=row[0],
                full_name=row[1],
                phone=row[2],
                email=row[3],
                address=row[4]
            )
            clients.append(client)
        
        return clients


    def update_client(self, client):
        """
        מעדכן לקוח קיים בבסיס הנתונים.
        מחזיר True אם עודכן בהצלחה, False אם הלקוח לא נמצא.
        """
        # בדיקה שיש client_id - אחרת אין מה לעדכן
        if client.client_id is None:
            return False
        
        connection = get_connection()
        cursor = connection.cursor()
        
        # שאילתת עדכון - עם WHERE! חשוב מאוד למניעת עדכון של כל הטבלה
        sql_query = """
            UPDATE clients
            SET full_name = ?,
                phone = ?,
                email = ?,
                address = ?
            WHERE client_id = ?
        """
        
        # הערכים - ה-client_id בסוף (מתאים ל-WHERE)
        values = (
            client.full_name,
            client.phone,
            client.email,
            client.address,
            client.client_id
        )
        
        cursor.execute(sql_query, values)
        rows_affected = cursor.rowcount
        
        connection.commit()
        connection.close()
        
        return rows_affected > 0


    def delete_client(self, client_id):
        """
        מוחק לקוח מבסיס הנתונים.
        מחזיר True אם נמחק, False אם לא נמצא או שיש רשומות מקושרות.
        
        אם ללקוח יש תורים או חשבוניות, SQLite יעצור את המחיקה
        וההסבר יופיע ב-self.last_error
        """
        self.last_error = None
        connection = None

        try:
            connection = get_connection()
            cursor = connection.cursor()

            sql_query = "DELETE FROM clients WHERE client_id = ?"
            cursor.execute(sql_query, (client_id,))

            rows_affected = cursor.rowcount
            connection.commit()

            if rows_affected == 0:
                self.last_error = "הלקוח לא נמצא במערכת"
                return False

            return True

        except Exception as error:
            if connection is not None:
                connection.rollback()

            # מקרה נפוץ - יש תורים או חשבוניות מקושרים
            if "foreign key" in str(error).lower():
                self.last_error = (
                    "לא ניתן למחוק את הלקוח - קיימים לו תורים או חשבוניות. "
                    "יש למחוק אותם קודם."
                )
            else:
                self.last_error = translate_db_error(error, "מחיקת לקוח")

            return False

        finally:
            if connection is not None:
                connection.close()