# ============================================================
# managers/appointment_treatment_manager.py
# מנהל "טיפול מרוכב" - כמה טיפולים באותו תור.
#
# ------------------------------------------------------------
# הערה חשובה על היוצא-דופן הזה בפרויקט:
# זהו הקובץ היחיד שכן כותב SQL חדש, כולל יצירת טבלה חדשה
# (appointment_treatments). זו חריגה מודעת ומאושרת - כדי לאפשר
# לדנה לקבוע תור עם כמה טיפולים יחד (למשל: שפם + סנטר באותו
# ביקור), כשהמחיר והזמן הכולל מחושבים אוטומטית ומשפיעים נכון
# על בדיקת ההתנגשויות והשעות הפנויות (הלוז).
#
# הקובץ הזה לא נוגע ב-managers/appointment_manager.py המקורי,
# וגם לא ב-schema.sql / database.py - כדי ש-main.py והתפריט
# הקיים ימשיכו לעבוד בדיוק כמו היום, בלי שום שינוי. טבלת
# appointments המקורית עדיין שומרת treatment_id יחיד (הטיפול
# ה"ראשי" - הראשון שנבחר), בדיוק כמו קודם. הטבלה החדשה כאן היא
# תוספת בלבד מעליה, לשימוש ה-Web בלבד.
# ------------------------------------------------------------

from datetime import datetime, timedelta

from database import get_connection
from managers.treatment_manager import TreatmentManager


class AppointmentTreatmentManager:
    """
    מנהל הקישור בין תור לכמה טיפולים (many-to-many).
    בונה מעל טבלת appointments הקיימת, בלי לשנות אותה.
    """

    def __init__(self):
        # שימוש חוזר במנהל הטיפולים הקיים - כל שליפת טיפול בודד
        # עוברת דרכו, לא כותבים שוב שאילתת SELECT על treatments
        self.treatment_manager = TreatmentManager()

    def ensure_table(self):
        """
        יוצר את טבלת appointment_treatments אם היא עוד לא קיימת.
        בטוח להריץ שוב ושוב (IF NOT EXISTS) - נקרא פעם אחת
        מ-app.py בעת עליית השרת, בדיוק כמו initialize_database().

        ON DELETE CASCADE - אם תור נמחק (דרך delete_appointment
        הרגיל שב-AppointmentManager), השורות שלו כאן נמחקות
        אוטומטית ע"י SQLite עצמו, בלי לגעת בפונקציית המחיקה ההיא.
        """
        connection = get_connection()
        connection.execute("""
            CREATE TABLE IF NOT EXISTS appointment_treatments (
                appointment_id     INTEGER NOT NULL,
                treatment_id       INTEGER NOT NULL,

                PRIMARY KEY (appointment_id, treatment_id),
                FOREIGN KEY (appointment_id) REFERENCES appointments(appointment_id)
                    ON DELETE CASCADE,
                FOREIGN KEY (treatment_id) REFERENCES treatments(treatment_id)
            )
        """)
        connection.commit()
        connection.close()

    def set_treatments_for_appointment(self, appointment_id, treatment_ids):
        """
        קובע את רשימת הטיפולים המלאה של תור נתון: מוחק את הרשימה
        הישנה וכותב את החדשה, בטרנזקציה אחת. נקרא בכל הוספה/עדכון
        של תור דרך ה-Web, כך שהרשימה תמיד מדויקת ועדכנית.
        """
        connection = get_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(
                "DELETE FROM appointment_treatments WHERE appointment_id = ?",
                (appointment_id,)
            )

            for treatment_id in treatment_ids:
                cursor.execute("""
                    INSERT INTO appointment_treatments (appointment_id, treatment_id)
                    VALUES (?, ?)
                """, (appointment_id, treatment_id))

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

    def get_treatment_ids_for_appointment(self, appointment_id):
        """מחזיר רשימת מזהי טיפולים (מספרים) המקושרים לתור נתון"""
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(
            "SELECT treatment_id FROM appointment_treatments WHERE appointment_id = ?",
            (appointment_id,)
        )
        rows = cursor.fetchall()
        connection.close()

        return [row[0] for row in rows]

    def get_treatments_for_appointment(self, appointment_id, fallback_treatment_id=None):
        """
        מחזיר רשימת אובייקטי Treatment מלאים לתור.

        אם אין רשומות בטבלת הקישור (למשל תור שנוצר דרך main.py,
        לפני שהתכונה הזאת הייתה קיימת, או תור "רגיל" עם טיפול
        יחיד) - חוזרים לטיפול הראשי הבודד של אותו תור.
        """
        treatment_ids = self.get_treatment_ids_for_appointment(appointment_id)

        if not treatment_ids and fallback_treatment_id is not None:
            treatment_ids = [fallback_treatment_id]

        treatments = []
        for treatment_id in treatment_ids:
            treatment = self.treatment_manager.get_treatment_by_id(treatment_id)
            if treatment is not None:
                treatments.append(treatment)

        return treatments

    def calculate_combo_totals(self, treatment_ids):
        """
        מחשב מחיר כולל ומשך כולל (בדקות) לרשימת מזהי טיפולים.
        זהו הלב של התכונה - "עלות ומשך שמחושבים לפי מכלול הטיפולים".
        משתמש ב-TreatmentManager הקיים לשליפת כל טיפול - אין כאן
        שאילתת SELECT חדשה על טבלת treatments.
        """
        total_price = 0
        total_duration = 0

        for treatment_id in treatment_ids:
            treatment = self.treatment_manager.get_treatment_by_id(treatment_id)
            if treatment is not None:
                total_price += treatment.price
                total_duration += treatment.duration_minutes

        return total_price, total_duration

    def get_appointment_total_duration(self, appointment_id, fallback_treatment_id):
        """
        משך הזמן האמיתי שתור נתון תופס בלוז - סכום כל הטיפולים
        המקושרים אליו (או משך הטיפול הראשי אם אין קישורים).
        """
        treatment_ids = self.get_treatment_ids_for_appointment(appointment_id)

        if not treatment_ids:
            treatment_ids = [fallback_treatment_id]

        _, total_duration = self.calculate_combo_totals(treatment_ids)
        return total_duration

    def check_combo_conflict(self, appointment_date, appointment_time,
                              treatment_ids, exclude_appointment_id=None):
        """
        גרסה "מודעת-שילוב" של AppointmentManager.check_conflict:
        באותו אלגוריתם בדיוק (חפיפת טווחי זמן), אבל במקום להסתמך
        על משך הטיפול הבודד של כל תור קיים, שולפת לכל תור קיים
        באותו יום את משך הזמן האמיתי שלו (כולל אם גם הוא טיפול
        מרוכב) - ובודקת חפיפה מול הזמן הכולל של הבקשה החדשה.

        מחזירה (has_conflict, message) - אותו פורמט בדיוק כמו
        AppointmentManager.check_conflict, כדי שהצד הלקוח יוכל
        להתייחס לשתי הפונקציות באותה צורה.
        """
        _, new_duration = self.calculate_combo_totals(treatment_ids)

        new_start = datetime.strptime(
            f"{appointment_date} {appointment_time}", "%Y-%m-%d %H:%M"
        )
        new_end = new_start + timedelta(minutes=new_duration)

        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT a.appointment_id, a.appointment_time, a.treatment_id, c.full_name
            FROM appointments a
            JOIN clients c ON a.client_id = c.client_id
            WHERE a.appointment_date = ?
              AND a.status != 'cancelled'
        """, (appointment_date,))
        rows = cursor.fetchall()
        connection.close()

        for row in rows:
            existing_id, existing_time, existing_primary_treatment_id, client_name = row

            # בעדכון - מדלגים על התור שאנחנו מעדכנים (כמו במנהל המקורי)
            if exclude_appointment_id is not None and existing_id == exclude_appointment_id:
                continue

            existing_duration = self.get_appointment_total_duration(
                existing_id, existing_primary_treatment_id
            )
            existing_start = datetime.strptime(
                f"{appointment_date} {existing_time}", "%Y-%m-%d %H:%M"
            )
            existing_end = existing_start + timedelta(minutes=existing_duration)

            if new_start < existing_end and existing_start < new_end:
                message = (
                    f"התנגשות עם תור #{existing_id} של {client_name} "
                    f"בשעה {existing_time} "
                    f"(מסתיים ב-{existing_end.strftime('%H:%M')})"
                )
                return True, message

        return False, None

    def get_combo_available_slots(self, appointment_date, treatment_ids,
                                   work_start="09:00", work_end="18:00"):
        """
        שעות פנויות ליום נתון עבור שילוב טיפולים - אותו רעיון כמו
        AppointmentManager.get_available_slots, אבל לפי משך הזמן
        הכולל של כל הטיפולים שנבחרו יחד.
        """
        _, duration = self.calculate_combo_totals(treatment_ids)

        day_start = datetime.strptime(f"{appointment_date} {work_start}", "%Y-%m-%d %H:%M")
        day_end = datetime.strptime(f"{appointment_date} {work_end}", "%Y-%m-%d %H:%M")

        available = []
        current = day_start

        while current + timedelta(minutes=duration) <= day_end:
            time_string = current.strftime("%H:%M")

            has_conflict, _ = self.check_combo_conflict(
                appointment_date, time_string, treatment_ids
            )

            if not has_conflict:
                available.append(time_string)

            current = current + timedelta(minutes=15)

        return available
