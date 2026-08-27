# ============================================================
# services/scheduling.py
# ליבת "מי פנוי מתי" - משותפת ל-availability_service (ספירה
# בלבד, לא חושפת אילו משאבים) ול-booking_service (שיבוץ בפועל).
#
# חובה שתהיה בדיוק אותה לוגיקה בשני המקומות: אם availability_service
# מציגה שעה כפנויה על סמך חישוב אחד, ו-booking_service בודק
# התנגשות (Layer 2) על סמך חישוב אחר, ייתכן מצב שבו לקוחה רואה
# "פנוי" ומקבלת סירוב באישור - בדיוק הבאג שריכוז הלוגיקה כאן מונע.
#
# האילוץ התלת-כיווני (חדר+מכשיר+עובדת) כבר קיים ומיושם ב-
# AppointmentTreatmentManager.check_combo_conflict, אבל הוא בנוי
# לבדיקת *משאב ספציפי שכבר נבחר* (התאמה למסך הצוות, שבו יש בורר).
# בפורטל/צ'אטבוט אין בורר משאב בכלל (הלקוחה בוחרת רק טיפול+שעה) -
# צריך "יש בכלל משאב פנוי כלשהו מכל סוג" (ספירה) ו"תן לי אחד ספציפי"
# (שיבוץ), ושני אלה נבנים כאן על אותו חישוב interval בדיוק.
# ============================================================

from datetime import timedelta

from db import get_session
from models import Appointment, Room, Machine, StaffAvailability, StaffTimeOff, User
from managers.appointment_treatment_manager import AppointmentTreatmentManager
from utils.datetime_utils import combine_local, day_of_week

combo_manager = AppointmentTreatmentManager()


class DayContext:
    """
    כל המידע הדרוש כדי לבדוק זמינות משאבים ליום נתון - נטען פעם
    אחת ליום (לא בכל משבצת 15 דקות בנפרד), כדי לא להפציץ את ה-DB
    בשאילתות זהות שוב ושוב על פני עשרות משבצות וימים.
    """

    def __init__(self, date_str, requires_machine):
        self.date_str = date_str
        session = get_session()

        appointments = (
            session.query(Appointment)
            .filter(Appointment.appointment_date == date_str, Appointment.status != "cancelled")
            .all()
        )
        # (staff_user_id, room_id, machine_id, start_dt, end_dt) לכל תור קיים -
        # מחושב פעם אחת כאן, כדי שבדיקת חפיפה בלולאת המשבצות תהיה בזיכרון בלבד
        self.appointment_intervals = []
        for appointment in appointments:
            duration = combo_manager.get_appointment_total_duration(
                appointment.appointment_id, appointment.treatment_id
            )
            start_dt = combine_local(date_str, appointment.appointment_time)
            end_dt = start_dt + timedelta(minutes=duration)
            self.appointment_intervals.append(
                (appointment.staff_user_id, appointment.room_id, appointment.machine_id,
                 start_dt, end_dt)
            )

        self.staff_list = session.query(User).filter(User.is_active == 1).all()

        availability_by_staff = {}
        for row in session.query(StaffAvailability).filter(
            StaffAvailability.day_of_week == day_of_week(date_str)
        ).all():
            availability_by_staff.setdefault(row.staff_user_id, []).append(row)
        self.availability_by_staff = availability_by_staff

        self.staff_on_leave = {
            row.staff_user_id
            for row in session.query(StaffTimeOff)
            .filter(StaffTimeOff.start_date <= date_str, StaffTimeOff.end_date >= date_str)
            .all()
        }

        self.rooms = session.query(Room).filter(Room.is_active == 1).all()
        self.machines = (
            session.query(Machine).filter(Machine.is_active == 1).all()
            if requires_machine else []
        )


def _resource_is_free(resource_id, resource_field_index, context, start_dt, end_dt):
    """resource_field_index: 0=staff_user_id, 1=room_id, 2=machine_id בתוך appointment_intervals."""
    for interval in context.appointment_intervals:
        occupant = interval[resource_field_index]
        if occupant == resource_id and start_dt < interval[4] and interval[3] < end_dt:
            return False
    return True


def _staff_covers_interval(templates, start_str, end_str):
    return any(t.start_time <= start_str and t.end_time >= end_str for t in templates)


def free_staff_ids(context, start_str, end_str, start_dt, end_dt):
    """מזהי כל עובדת פעילה שהתבנית השבועית שלה מכסה את הטווח, לא בחופשה, ולא כבר משובצת."""
    free_ids = []
    for staff in context.staff_list:
        if staff.user_id in context.staff_on_leave:
            continue
        templates = context.availability_by_staff.get(staff.user_id, [])
        if not _staff_covers_interval(templates, start_str, end_str):
            continue
        if _resource_is_free(staff.user_id, 0, context, start_dt, end_dt):
            free_ids.append(staff.user_id)
    return free_ids


def free_room_ids(context, start_dt, end_dt):
    return [room.room_id for room in context.rooms
            if _resource_is_free(room.room_id, 1, context, start_dt, end_dt)]


def free_machine_ids(context, start_dt, end_dt):
    """רשימה ריקה אם requires_machine=False (context.machines כבר נבנה ריק במקרה הזה)."""
    return [machine.machine_id for machine in context.machines
            if _resource_is_free(machine.machine_id, 2, context, start_dt, end_dt)]
