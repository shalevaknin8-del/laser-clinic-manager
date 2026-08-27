# ============================================================
# managers/appointment_treatment_manager.py
# מנהל "טיפול מרוכב" (כמה טיפולים באותו תור) + מנוע הזימון החכם.
#
# גרסת ORM (שלב 3 של הריפקטור). זהו הקובץ שמחזיק את כל לוגיקת
# בדיקת ההתנגשויות של המערכת - הבחירה המקורית (מפרויקט האמצע)
# הייתה לרכז כאן את כל חישוב ה"טווח שתור תופס", וזה עדיין הבית
# הנכון לאילוץ התלת-כיווני החדש (חדר + מכשיר + עובדת), כי הוא
# כבר יודע לחשב נכון את משך הזמן הכולל גם לתור רגיל וגם למרוכב.
#
# האילוץ התלת-כיווני: תור חדש מתנגש עם תור קיים אחר *רק* אם הם
# חולקים משאב משותף (אותו חדר, או אותו מכשיר, או אותה עובדת)
# וגם הזמנים חופפים. תור בחדר אחר עם עובדת אחרת יכול להתקיים
# באותה שעה בדיוק - זו בדיוק הנקודה של קליניקה עם כמה עובדות.
# משאב שלא צוין (None) לא נבדק כלל, כדי לתמוך במעבר הדרגתי.
# ============================================================

from datetime import datetime, timedelta

from db import get_session
from models import Appointment, AppointmentTreatment, Treatment
from managers.treatment_manager import TreatmentManager
from managers.staff_schedule_manager import StaffScheduleManager


class AppointmentTreatmentManager:
    """
    מנהל הקישור בין תור לכמה טיפולים (many-to-many), ומנוע בדיקת
    ההתנגשויות המלא (שעות פעילות + משאבים + זמינות עובדת).
    """

    def __init__(self):
        self.treatment_manager = TreatmentManager()
        self.staff_schedule_manager = StaffScheduleManager()

    @property
    def session(self):
        return get_session()

    def ensure_table(self):
        """
        שומר לתאימות לאחור בלבד: הטבלה עצמה נוצרת היום דרך
        db.init_orm_tables() / migrations/004_orm_refactor.py.
        קריאה חוזרת כאן בטוחה (create_all הוא idempotent).
        """
        from db import engine
        from models import Base
        Base.metadata.create_all(engine, tables=[AppointmentTreatment.__table__])

    def set_treatments_for_appointment(self, appointment_id, treatment_ids):
        """מוחק את רשימת הטיפולים הישנה של תור וכותב את החדשה, בטרנזקציה אחת."""
        session = self.session
        session.query(AppointmentTreatment).filter_by(appointment_id=appointment_id).delete()
        for treatment_id in treatment_ids:
            session.add(AppointmentTreatment(appointment_id=appointment_id, treatment_id=treatment_id))
        session.commit()

    def get_treatment_ids_for_appointment(self, appointment_id):
        rows = (
            self.session.query(AppointmentTreatment.treatment_id)
            .filter_by(appointment_id=appointment_id)
            .all()
        )
        return [row[0] for row in rows]

    def get_treatments_for_appointment(self, appointment_id, fallback_treatment_id=None):
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
        total_price = 0
        total_duration = 0

        for treatment_id in treatment_ids:
            treatment = self.treatment_manager.get_treatment_by_id(treatment_id)
            if treatment is not None:
                total_price += treatment.price
                total_duration += treatment.duration_minutes

        return total_price, total_duration

    def get_appointment_total_duration(self, appointment_id, fallback_treatment_id):
        treatment_ids = self.get_treatment_ids_for_appointment(appointment_id)

        if not treatment_ids:
            treatment_ids = [fallback_treatment_id]

        _, total_duration = self.calculate_combo_totals(treatment_ids)
        return total_duration

    def check_combo_conflict(self, appointment_date, appointment_time,
                              treatment_ids, exclude_appointment_id=None,
                              client_id=None, room_id=None, machine_id=None,
                              staff_user_id=None,
                              work_start="09:00", work_end="18:00"):
        """
        הבדיקה המלאה לפני קביעת/עדכון תור:
          1. שעות הפעילות
          2. זמינות העובדת (תבנית שבועית + חופשות), אם צוינה
          3. התנגשות משאבים (לקוח/חדר/מכשיר/עובדת) עם תורים אחרים
             חופפים בזמן, רק מול תורים שחולקים משאב בפועל

        client_id אינו אופציונלי מבחינה עסקית כמו שאר המשאבים -
        לקוחה לא יכולה להיות בשני תורים בו-זמנית, גם אם עדיין לא
        שויכו חדר/מכשיר/עובדת לאף אחד מהתורים. לכן, בשונה מ-
        room_id/machine_id/staff_user_id, ה-None כאן אמור לקרות
        רק בקריאות בדיקה כלליות (למשל "יש שעות פנויות היום בכלל"),
        לא כשבאמת שומרים תור קונקרטי ללקוחה.

        מחזירה (has_conflict, message).
        """
        _, new_duration = self.calculate_combo_totals(treatment_ids)

        new_start = datetime.strptime(
            f"{appointment_date} {appointment_time}", "%Y-%m-%d %H:%M"
        )
        new_end = new_start + timedelta(minutes=new_duration)

        day_start = datetime.strptime(f"{appointment_date} {work_start}", "%Y-%m-%d %H:%M")
        day_end = datetime.strptime(f"{appointment_date} {work_end}", "%Y-%m-%d %H:%M")

        if new_start < day_start or new_end > day_end:
            return True, f"השעה המבוקשת מחוץ לשעות הפעילות ({work_start}-{work_end})"

        if staff_user_id is not None:
            is_available, reason = self.staff_schedule_manager.is_staff_available(
                staff_user_id, appointment_date, appointment_time, new_end.strftime("%H:%M")
            )
            if not is_available:
                return True, reason

        query = self.session.query(Appointment).filter(
            Appointment.appointment_date == appointment_date,
            Appointment.status != "cancelled",
        )
        if exclude_appointment_id is not None:
            query = query.filter(Appointment.appointment_id != exclude_appointment_id)

        for existing in query.all():
            shares_client = client_id is not None and existing.client_id == client_id
            shares_room = room_id is not None and existing.room_id == room_id
            shares_machine = machine_id is not None and existing.machine_id == machine_id
            shares_staff = staff_user_id is not None and existing.staff_user_id == staff_user_id

            if not (shares_client or shares_room or shares_machine or shares_staff):
                # אין משאב משותף - אין דרך שהתורים "יתנגשו" זה בזה,
                # גם אם הזמנים חופפים (לקוחות/חדרים/עובדות שונים לגמרי)
                continue

            existing_duration = self.get_appointment_total_duration(
                existing.appointment_id, existing.treatment_id
            )
            existing_start = datetime.strptime(
                f"{appointment_date} {existing.appointment_time}", "%Y-%m-%d %H:%M"
            )
            existing_end = existing_start + timedelta(minutes=existing_duration)

            if new_start < existing_end and existing_start < new_end:
                if shares_client:
                    resource_phrase = "ללקוחה כבר יש תור חופף"
                elif shares_room:
                    resource_phrase = "החדר כבר תפוס"
                elif shares_machine:
                    resource_phrase = "המכשיר כבר תפוס"
                else:
                    resource_phrase = "העובדת כבר תפוסה"
                message = (
                    f"{resource_phrase} בשעה {existing.appointment_time} "
                    f"(תור #{existing.appointment_id}, מסתיים ב-{existing_end.strftime('%H:%M')})"
                )
                return True, message

        return False, None

    def get_combo_available_slots(self, appointment_date, treatment_ids,
                                   client_id=None, room_id=None, machine_id=None,
                                   staff_user_id=None,
                                   work_start="09:00", work_end="18:00"):
        """שעות פנויות ליום נתון, מודעות למשאבים אם סופקו."""
        _, duration = self.calculate_combo_totals(treatment_ids)

        day_start = datetime.strptime(f"{appointment_date} {work_start}", "%Y-%m-%d %H:%M")
        day_end = datetime.strptime(f"{appointment_date} {work_end}", "%Y-%m-%d %H:%M")

        available = []
        current = day_start

        while current + timedelta(minutes=duration) <= day_end:
            time_string = current.strftime("%H:%M")

            has_conflict, _ = self.check_combo_conflict(
                appointment_date, time_string, treatment_ids,
                client_id=client_id, room_id=room_id, machine_id=machine_id,
                staff_user_id=staff_user_id,
                work_start=work_start, work_end=work_end,
            )

            if not has_conflict:
                available.append(time_string)

            current = current + timedelta(minutes=15)

        return available
