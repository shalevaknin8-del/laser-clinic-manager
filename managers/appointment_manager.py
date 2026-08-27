# ============================================================
# managers/appointment_manager.py
# מנהל התורים - CRUD בסיסי, גרסת ORM (שלב 3 של הריפקטור).
#
# insert/get/update/delete/list עברו ל-SQLAlchemy כדי לתמוך
# בעמודות המשאבים החדשות (room_id/machine_id/staff_user_id/
# client_package_id). חתימות המתודות נשארו זהות בכוונה - קוד
# קורא קיים (הצ'אטבוט, הדשבורד, main.py) ממשיך לעבוד בלי שינוי.
#
# check_conflict / get_available_slots / _get_treatment_duration
# נשארו *בכוונה* על SQL גולמי, ללא שינוי מהגרסה המקורית: אלה
# המתודות שבהן משתמש main.py (התפריט הטקסטואלי המקורי), שמניח
# ציר זמן גלובלי יחיד בלי משאבים (חדר/מכשיר/עובדת) - התנהגות
# שונה בכוונה מהזימון החכם החדש (ראו check_resource_conflict
# ב-managers/appointment_treatment_manager.py), כדי לא לשבור
# את התפריט הקיים.
# ============================================================
from datetime import datetime, timedelta

from database import get_connection
from db import get_session
from models import Appointment as AppointmentModel
from models import Client as ClientModel
from models import Treatment as TreatmentModel


class AppointmentManager:
    """
    Manager Class לניהול תורים במערכת.
    ה-CRUD הבסיסי מגובה ORM; check_conflict/get_available_slots
    (המסלול הישן, ל-CLI בלבד) עדיין SQL גולמי - ראו הסבר למעלה.
    """

    @property
    def session(self):
        """
        get_session() נקרא בכל גישה מחדש, לא נשמר ב-__init__, כי
        ה-manager נוצר פעם אחת ברמת המודול וזה scoped_session לפי
        thread - ראו ההסבר המלא ב-managers/user_manager.py.
        """
        return get_session()

    def insert_appointment(self, appointment):
        """
        מוסיף תור חדש. מקבל אובייקט עם client_id/treatment_id/
        appointment_date/appointment_time/status/notes (למשל
        entities.appointment.Appointment), ומחזיר את שורת ה-ORM
        עם appointment_id שהוקצה.

        שדות המשאבים החדשים (room_id וכו') אופציונליים - קוד ישן
        שלא מכיר אותם פשוט לא מעביר אותם, וברירת המחדל היא None.
        """
        row = AppointmentModel(
            client_id=appointment.client_id,
            treatment_id=appointment.treatment_id,
            appointment_date=appointment.appointment_date,
            appointment_time=appointment.appointment_time,
            status=getattr(appointment, "status", "pending") or "pending",
            notes=getattr(appointment, "notes", None),
            room_id=getattr(appointment, "room_id", None),
            machine_id=getattr(appointment, "machine_id", None),
            staff_user_id=getattr(appointment, "staff_user_id", None),
            client_package_id=getattr(appointment, "client_package_id", None),
        )
        self.session.add(row)
        self.session.commit()
        return row

    def get_appointment_by_id(self, appointment_id):
        """שולף תור בודד לפי מזהה. מחזיר None אם לא נמצא."""
        return self.session.get(AppointmentModel, appointment_id)

    def get_all_appointments(self):
        """שולף את כל התורים, ממוין לפי תאריך ושעה."""
        return (
            self.session.query(AppointmentModel)
            .order_by(AppointmentModel.appointment_date, AppointmentModel.appointment_time)
            .all()
        )

    def update_appointment(self, appointment):
        """
        מעדכן תור קיים. מחזיר True אם עודכן, False אם לא נמצא.
        שדות המשאבים מתעדכנים רק אם סופקו במפורש (getattr עם
        ברירת מחדל = הערך הקיים) - כך קוד ישן שלא יודע עליהם
        לא "מוחק" אותם בטעות בכל עדכון.
        """
        if appointment.appointment_id is None:
            return False

        row = self.session.get(AppointmentModel, appointment.appointment_id)
        if row is None:
            return False

        row.client_id = appointment.client_id
        row.treatment_id = appointment.treatment_id
        row.appointment_date = appointment.appointment_date
        row.appointment_time = appointment.appointment_time
        row.status = appointment.status
        row.notes = appointment.notes
        row.room_id = getattr(appointment, "room_id", row.room_id)
        row.machine_id = getattr(appointment, "machine_id", row.machine_id)
        row.staff_user_id = getattr(appointment, "staff_user_id", row.staff_user_id)
        row.client_package_id = getattr(appointment, "client_package_id", row.client_package_id)
        self.session.commit()

        return True

    def delete_appointment(self, appointment_id):
        """מוחק תור. מחזיר True אם נמחק, False אם לא נמצא."""
        row = self.session.get(AppointmentModel, appointment_id)
        if row is None:
            return False

        self.session.delete(row)
        self.session.commit()
        return True

    def get_all_appointments_with_details(self):
        """
        שולף את כל התורים עם שם הלקוח ושם הטיפול, ל-JOIN שכבר
        קיים מקודם. מחזיר רשימת tuples במבנה זהה לגרסה הקודמת:
        (appointment_id, client_name, treatment_name, date, time, status)
        """
        rows = (
            self.session.query(
                AppointmentModel.appointment_id,
                ClientModel.full_name,
                TreatmentModel.treatment_name,
                AppointmentModel.appointment_date,
                AppointmentModel.appointment_time,
                AppointmentModel.status,
            )
            .join(ClientModel, AppointmentModel.client_id == ClientModel.client_id)
            .join(TreatmentModel, AppointmentModel.treatment_id == TreatmentModel.treatment_id)
            .order_by(AppointmentModel.appointment_date, AppointmentModel.appointment_time)
            .all()
        )
        return [tuple(row) for row in rows]

    # ============================================================
    # מסלול ה-CLI הישן (main.py) - SQL גולמי, ללא שינוי מהמקור.
    # ציר זמן גלובלי יחיד, בלי מודעות למשאבים (חדר/מכשיר/עובדת).
    # ============================================================

    def _get_treatment_duration(self, treatment_id):
        connection = get_connection()
        cursor = connection.cursor()

        sql_query = "SELECT duration_minutes FROM treatments WHERE treatment_id = ?"
        cursor.execute(sql_query, (treatment_id,))

        row = cursor.fetchone()
        connection.close()

        if row is None:
            return 30

        return row[0]

    def check_conflict(self, appointment_date, appointment_time,
                       treatment_id, exclude_appointment_id=None):
        duration = self._get_treatment_duration(treatment_id)

        new_start = datetime.strptime(
            f"{appointment_date} {appointment_time}",
            "%Y-%m-%d %H:%M"
        )
        new_end = new_start + timedelta(minutes=duration)

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

        for row in rows:
            existing_id = row[0]
            existing_time = row[1]
            existing_duration = row[2]
            client_name = row[3]

            if exclude_appointment_id is not None:
                if existing_id == exclude_appointment_id:
                    continue

            existing_start = datetime.strptime(
                f"{appointment_date} {existing_time}",
                "%Y-%m-%d %H:%M"
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

    def get_available_slots(self, appointment_date, treatment_id,
                            work_start="09:00", work_end="18:00"):
        duration = self._get_treatment_duration(treatment_id)

        day_start = datetime.strptime(f"{appointment_date} {work_start}", "%Y-%m-%d %H:%M")
        day_end = datetime.strptime(f"{appointment_date} {work_end}", "%Y-%m-%d %H:%M")

        available = []
        current = day_start

        while current + timedelta(minutes=duration) <= day_end:
            time_string = current.strftime("%H:%M")

            has_conflict, message = self.check_conflict(
                appointment_date, time_string, treatment_id
            )

            if not has_conflict:
                available.append(time_string)

            current = current + timedelta(minutes=15)

        return available
