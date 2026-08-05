# ============================================================
# managers/appointment_manager.py
# מנהל התורים - אחראי על כל הפעולות מול טבלת appointments
# מכיל 5 מתודות CRUD: insert, get_by_id, get_all, update, delete
# ============================================================
from datetime import datetime, timedelta
from database import get_connection
from entities.appointment import Appointment
from database import get_connection
from entities.appointment import Appointment


class AppointmentManager:
    """
    Manager Class לניהול תורים במערכת.
    כל הפעולות מול טבלת appointments עוברות דרך המחלקה הזאת.
    """

    def insert_appointment(self, appointment):
        """
        מוסיף תור חדש לבסיס הנתונים.
        מקבל אובייקט Appointment ומחזיר אותו עם ה-appointment_id שהוקצה.
        """
        # פותח חיבור ל-DB
        connection = get_connection()
        cursor = connection.cursor()
        
        # שאילתת ההוספה - סימני שאלה למניעת SQL Injection
        sql_query = """
            INSERT INTO appointments (
                client_id, treatment_id, appointment_date,
                appointment_time, status, notes
            ) VALUES (?, ?, ?, ?, ?, ?)
        """
        
        # הערכים שיוזרקו למקום סימני השאלה - חייבים באותו סדר!
        values = (
            appointment.client_id,
            appointment.treatment_id,
            appointment.appointment_date,
            appointment.appointment_time,
            appointment.status,
            appointment.notes
        )
        
        # הרצת השאילתה
        cursor.execute(sql_query, values)
        
        # שמירת ה-ID החדש שהוקצה אוטומטית
        appointment.appointment_id = cursor.lastrowid
        
        # שמירת השינויים וסגירת החיבור
        connection.commit()
        connection.close()
        
        return appointment

    def get_appointment_by_id(self, appointment_id):
        """
        שולף תור בודד לפי מזהה.
        מחזיר אובייקט Appointment, או None אם התור לא נמצא.
        """
        # פותח חיבור ל-DB
        connection = get_connection()
        cursor = connection.cursor()
        
        # שאילתת שליפה עם WHERE - מסנן לפי appointment_id
        sql_query = "SELECT * FROM appointments WHERE appointment_id = ?"
        
        # הרצת השאילתה עם ה-ID כפרמטר
        cursor.execute(sql_query, (appointment_id,))
        
        # שליפת שורה אחת (או None אם לא נמצא)
        row = cursor.fetchone()
        
        # סגירת החיבור
        connection.close()
        
        # אם לא נמצא תור - מחזירים None
        if row is None:
            return None
        
        # ממירים את השורה (tuple) לאובייקט Appointment
        appointment = Appointment(
            appointment_id=row[0],
            client_id=row[1],
            treatment_id=row[2],
            appointment_date=row[3],
            appointment_time=row[4],
            status=row[5],
            notes=row[6]
        )
        
        return appointment


    def get_all_appointments(self):
        """
        שולף את כל התורים במערכת.
        מחזיר רשימה של אובייקטי Appointment (יכולה להיות ריקה).
        """
        # פותח חיבור ל-DB
        connection = get_connection()
        cursor = connection.cursor()
        
        # שאילתת שליפה של הכל, ממויין לפי תאריך ושעה
        sql_query = "SELECT * FROM appointments ORDER BY appointment_date, appointment_time"
        
        # הרצת השאילתה
        cursor.execute(sql_query)
        
        # שליפת כל השורות כרשימה של tuples
        rows = cursor.fetchall()
        
        # סגירת החיבור
        connection.close()
        
        # רשימה ריקה שתכיל את התוצאה
        appointments = []
        
        # ממירים כל שורה לאובייקט Appointment ומוסיפים לרשימה
        for row in rows:
            appointment = Appointment(
                appointment_id=row[0],
                client_id=row[1],
                treatment_id=row[2],
                appointment_date=row[3],
                appointment_time=row[4],
                status=row[5],
                notes=row[6]
            )
            appointments.append(appointment)
        
        return appointments
    def _get_treatment_duration(self, treatment_id):
        """
        שולף את משך הטיפול בדקות מטבלת treatments.
        מחזיר את המשך, או 30 כברירת מחדל אם הטיפול לא נמצא.
        
        פונקציה פנימית - משמשת רק את בדיקת ההתנגשויות.
        """
        connection = get_connection()
        cursor = connection.cursor()

        sql_query = "SELECT duration_minutes FROM treatments WHERE treatment_id = ?"
        cursor.execute(sql_query, (treatment_id,))

        row = cursor.fetchone()
        connection.close()

        if row is None:
            # ברירת מחדל בטוחה אם הטיפול לא נמצא
            return 30

        return row[0]


    def check_conflict(self, appointment_date, appointment_time,
                       treatment_id, exclude_appointment_id=None):
        """
        בודק אם התור המבוקש מתנגש עם תור קיים.
        
        מחזיר (has_conflict, message):
        - (False, None) אם השעה פנויה
        - (True, "הודעה") אם יש התנגשות
        
        exclude_appointment_id משמש בעדכון תור קיים - כדי שהתור
        לא ייחשב כמתנגש עם עצמו.
        """
        # מחשבים את טווח הזמן של התור החדש
        duration = self._get_treatment_duration(treatment_id)

        new_start = datetime.strptime(
            f"{appointment_date} {appointment_time}",
            "%Y-%m-%d %H:%M"
        )
        new_end = new_start + timedelta(minutes=duration)

        # שולפים את כל התורים באותו תאריך שלא בוטלו
        connection = get_connection()
        cursor = connection.cursor()

        sql_query = """
            SELECT a.appointment_id, a.appointment_time, t.duration_minutes, c.full_name
            FROM appointments a
            JOIN treatments t ON a.treatment_id = t.treatment_id
            JOIN clients c ON a.client_id = c.client_id
            WHERE a.appointment_date = ?
              AND a.status != 'cancelled'
        """

        cursor.execute(sql_query, (appointment_date,))
        rows = cursor.fetchall()
        connection.close()

        # עוברים על כל תור קיים ובודקים חפיפה
        for row in rows:
            existing_id = row[0]
            existing_time = row[1]
            existing_duration = row[2]
            client_name = row[3]

            # בעדכון - מדלגים על התור שאנחנו מעדכנים
            if exclude_appointment_id is not None:
                if existing_id == exclude_appointment_id:
                    continue

            # מחשבים את טווח הזמן של התור הקיים
            existing_start = datetime.strptime(
                f"{appointment_date} {existing_time}",
                "%Y-%m-%d %H:%M"
            )
            existing_end = existing_start + timedelta(minutes=existing_duration)

            # נוסחת החפיפה: שני טווחים חופפים אם
            # ההתחלה של כל אחד מגיעה לפני הסיום של השני
            if new_start < existing_end and existing_start < new_end:
                message = (
                    f"התנגשות עם תור #{existing_id} של {client_name} "
                    f"בשעה {existing_time} "
                    f"(מסתיים ב-{existing_end.strftime('%H:%M')})"
                )
                return True, message

        # לא נמצאה התנגשות
        return False, None


    def get_available_slots(self, appointment_date, treatment_id,
                            work_start="09:00", work_end="18:00"):
        """
        מחזיר רשימה של שעות פנויות ביום מסוים עבור טיפול נתון.
        בודק כל 15 דקות בין שעות הפעילות.
        
        שימושי בתפריט - במקום שדנה תנחש, המערכת מציעה.
        """
        duration = self._get_treatment_duration(treatment_id)

        day_start = datetime.strptime(f"{appointment_date} {work_start}", "%Y-%m-%d %H:%M")
        day_end = datetime.strptime(f"{appointment_date} {work_end}", "%Y-%m-%d %H:%M")

        available = []
        current = day_start

        # עוברים על היום בקפיצות של 15 דקות
        while current + timedelta(minutes=duration) <= day_end:
            time_string = current.strftime("%H:%M")

            has_conflict, message = self.check_conflict(
                appointment_date, time_string, treatment_id
            )

            if not has_conflict:
                available.append(time_string)

            current = current + timedelta(minutes=15)

        return available
    
    def update_appointment(self, appointment):
        """
        מעדכן תור קיים בבסיס הנתונים.
        מקבל אובייקט Appointment עם appointment_id של תור קיים.
        מחזיר True אם עודכן בהצלחה, False אם התור לא נמצא.
        """
        # בדיקה שיש appointment_id - אחרת אין מה לעדכן
        if appointment.appointment_id is None:
            return False
        
        # פותח חיבור ל-DB
        connection = get_connection()
        cursor = connection.cursor()
        
        # שאילתת עדכון - עם WHERE! חשוב מאוד למניעת עדכון של כל הטבלה
        sql_query = """
            UPDATE appointments
            SET client_id = ?,
                treatment_id = ?,
                appointment_date = ?,
                appointment_time = ?,
                status = ?,
                notes = ?
            WHERE appointment_id = ?
        """
        
        # הערכים - סדר חשוב! ה-appointment_id בסוף (מתאים ל-WHERE)
        values = (
            appointment.client_id,
            appointment.treatment_id,
            appointment.appointment_date,
            appointment.appointment_time,
            appointment.status,
            appointment.notes,
            appointment.appointment_id
        )
        
        # הרצת השאילתה
        cursor.execute(sql_query, values)
        
        # בדיקה כמה שורות עודכנו (0 = לא נמצא תור עם ה-ID הזה)
        rows_affected = cursor.rowcount
        
        # שמירה וסגירה
        connection.commit()
        connection.close()
        
        # מחזיר True רק אם עודכנה לפחות שורה אחת
        return rows_affected > 0


    def delete_appointment(self, appointment_id):
        """
        מוחק תור מבסיס הנתונים לפי מזהה.
        מחזיר True אם נמחק בהצלחה, False אם התור לא נמצא.
        """
        # פותח חיבור ל-DB
        connection = get_connection()
        cursor = connection.cursor()
        
        # שאילתת מחיקה - עם WHERE! חובה
        sql_query = "DELETE FROM appointments WHERE appointment_id = ?"
        
        # הרצת השאילתה
        cursor.execute(sql_query, (appointment_id,))
        
        # בדיקה כמה שורות נמחקו
        rows_affected = cursor.rowcount
        
        # שמירה וסגירה
        connection.commit()
        connection.close()
        
        # מחזיר True רק אם נמחקה לפחות שורה אחת
        return rows_affected > 0
    def get_all_appointments_with_details(self):
        """
        שולף את כל התורים עם שם הלקוח ושם הטיפול.
        משתמש ב-JOIN כדי לחבר 3 טבלאות בשאילתה אחת:
        appointments + clients + treatments.
        
        מחזיר רשימה של tuples במבנה:
        (appointment_id, client_name, treatment_name, date, time, status)
        """
        connection = get_connection()
        cursor = connection.cursor()
        
        # שאילתה עם 2 JOINS - מחברת 3 טבלאות
        # a, c, t = כינויים מקוצרים (aliases) לטבלאות
        sql_query = """
            SELECT 
                a.appointment_id,
                c.full_name,
                t.treatment_name,
                a.appointment_date,
                a.appointment_time,
                a.status
            FROM appointments a
            JOIN clients c ON a.client_id = c.client_id
            JOIN treatments t ON a.treatment_id = t.treatment_id
            ORDER BY a.appointment_date, a.appointment_time
        """
        
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        connection.close()
        
        # מחזירים את הרשימה ישירות - זו רשימה של tuples
        # (לא ממירים לאובייקטים כי זו תצוגה בלבד)
        return rows