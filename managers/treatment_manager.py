# ============================================================
# managers/treatment_manager.py
# מנהל הטיפולים - אחראי על קטלוג הטיפולים של הקליניקה
# מכיל 5 מתודות CRUD + פונקציית seed_catalog לאתחול ראשוני
# ============================================================

from database import get_connection
from entities.treatment import Treatment


class TreatmentManager:
    """
    Manager Class לניהול קטלוג הטיפולים.
    כולל פונקציה מיוחדת seed_catalog לאתחול הקטלוג ההתחלתי.
    """

    def insert_treatment(self, treatment):
        """
        מוסיף טיפול חדש לקטלוג.
        מקבל אובייקט Treatment ומחזיר אותו עם ה-treatment_id שהוקצה.
        """
        connection = get_connection()
        cursor = connection.cursor()
        
        sql_query = """
            INSERT INTO treatments (
                treatment_name, body_area, price, duration_minutes
            ) VALUES (?, ?, ?, ?)
        """
        
        values = (
            treatment.treatment_name,
            treatment.body_area,
            treatment.price,
            treatment.duration_minutes
        )
        
        cursor.execute(sql_query, values)
        treatment.treatment_id = cursor.lastrowid
        
        connection.commit()
        connection.close()
        
        return treatment


    def get_treatment_by_id(self, treatment_id):
        """
        שולף טיפול לפי מזהה.
        מחזיר אובייקט Treatment, או None אם לא נמצא.
        """
        connection = get_connection()
        cursor = connection.cursor()
        
        sql_query = "SELECT * FROM treatments WHERE treatment_id = ?"
        cursor.execute(sql_query, (treatment_id,))
        
        row = cursor.fetchone()
        connection.close()
        
        if row is None:
            return None
        
        treatment = Treatment(
            treatment_id=row[0],
            treatment_name=row[1],
            body_area=row[2],
            price=row[3],
            duration_minutes=row[4]
        )
        
        return treatment


    def get_all_treatments(self):
        """
        שולף את כל הטיפולים בקטלוג.
        ממוין לפי מחיר - מהזול לגבוה - לתצוגה נוחה בתפריט.
        """
        connection = get_connection()
        cursor = connection.cursor()
        
        sql_query = "SELECT * FROM treatments ORDER BY price"
        cursor.execute(sql_query)
        
        rows = cursor.fetchall()
        connection.close()
        
        treatments = []
        for row in rows:
            treatment = Treatment(
                treatment_id=row[0],
                treatment_name=row[1],
                body_area=row[2],
                price=row[3],
                duration_minutes=row[4]
            )
            treatments.append(treatment)
        
        return treatments


    def update_treatment(self, treatment):
        """
        מעדכן טיפול קיים בקטלוג.
        מחזיר True אם עודכן, False אם הטיפול לא נמצא.
        """
        if treatment.treatment_id is None:
            return False
        
        connection = get_connection()
        cursor = connection.cursor()
        
        sql_query = """
            UPDATE treatments
            SET treatment_name = ?,
                body_area = ?,
                price = ?,
                duration_minutes = ?
            WHERE treatment_id = ?
        """
        
        values = (
            treatment.treatment_name,
            treatment.body_area,
            treatment.price,
            treatment.duration_minutes,
            treatment.treatment_id
        )
        
        cursor.execute(sql_query, values)
        rows_affected = cursor.rowcount
        
        connection.commit()
        connection.close()
        
        return rows_affected > 0


    def delete_treatment(self, treatment_id):
        """
        מוחק טיפול מהקטלוג.
        מחזיר True אם נמחק, False אם הטיפול לא נמצא.
        
        שים לב: אם קיימים תורים המפנים לטיפול, SQLite יעצור את המחיקה
        בזכות FK constraint.
        """
        connection = get_connection()
        cursor = connection.cursor()
        
        sql_query = "DELETE FROM treatments WHERE treatment_id = ?"
        cursor.execute(sql_query, (treatment_id,))
        
        rows_affected = cursor.rowcount
        
        connection.commit()
        connection.close()
        
        return rows_affected > 0


    def seed_catalog(self):
        """
        מאתחל את קטלוג הטיפולים עם 13 טיפולים ראשוניים בעברית.
        רץ רק אם הקטלוג ריק - כדי שלא ניצור כפילויות בהרצות חוזרות.
        מחזיר את מספר הטיפולים שנוספו.
        """
        # בודקים אם כבר יש טיפולים במערכת
        existing_treatments = self.get_all_treatments()
        if len(existing_treatments) > 0:
            print(f"הקטלוג כבר מכיל {len(existing_treatments)} טיפולים - דילוג על seed")
            return 0
        
        # רשימת הטיפולים ההתחלתיים - שם, איזור/ים, מחיר, משך בדקות
        initial_catalog = [
            ("פנים מלא",          "פנים",                 250, 20),
            ("שפם",              "שפם",                  80,  10),
            ("סנטר",             "סנטר",                 80,  10),
            ("קו ביקיני",         "קו ביקיני",            150, 15),
            ("ביקיני מלא",        "ביקיני מלא",           250, 25),
            ("ברזילאי",          "ביקיני, בין ישבנים",    300, 30),
            ("בית שחי",          "בית שחי",              120, 10),
            ("חצי ידיים",         "אמות",                 150, 20),
            ("ידיים מלא",         "אמות, זרועות",         250, 30),
            ("חצי רגליים",        "שוקיים",               250, 30),
            ("רגליים מלא",        "שוקיים, ירכיים",       400, 45),
            ("גב",               "גב",                   300, 30),
            ("בטן",              "בטן",                  200, 20),
        ]
        
        # מוסיפים כל טיפול לקטלוג דרך insert_treatment הרגיל
        added_count = 0
        for name, area, price, duration in initial_catalog:
            treatment = Treatment(
                treatment_name=name,
                body_area=area,
                price=price,
                duration_minutes=duration
            )
            self.insert_treatment(treatment)
            added_count += 1
        
        print(f"נוספו {added_count} טיפולים לקטלוג")
        return added_count