# ============================================================
# services/availability_service.py
# Principle 3 במפרט: נקודת כניסה יחידה - get_public_availability -
# שמחזירה *רק* שעות פנויות. לעולם לא תור קיים, לא כמה תורים יש
# ביום, לא אילו משאבים תפוסים (ראו Part 19 במפרט - זה בדיוק ההבדל
# בין "שעות פנויות מחושבות בשרת" לבין "כל התורים, מפולטרים ב-JS"
# שהמפרט אוסר בפירוש).
#
# שכבה 1 מתוך 3 של ההגנה מפני double-booking: שריון פעיל
# (slot_reservations שלא פג תוקפו) חוסם את השעה באופן מיידי,
# ללא קשר אם היא הפכה לתור בפועל.
# ============================================================

from datetime import timedelta

from db import get_session
from models import SlotReservation
from managers.treatment_manager import TreatmentManager
from managers.clinic_settings_manager import ClinicSettingsManager
from services.scheduling import DayContext, free_staff_ids, free_room_ids, free_machine_ids
from utils.datetime_utils import (
    today_jerusalem, parse_date_str, to_date_str, to_time_str,
    combine_local, day_of_week, hours_until, has_expired,
)

SLOT_STEP_MINUTES = 15

treatment_manager = TreatmentManager()
settings_manager = ClinicSettingsManager()


class AvailabilityError(Exception):
    """קלט לא תקין לבקשת זמינות (טווח תאריכים הפוך, טיפול לא קיים וכו')."""


def cleanup_expired_reservations():
    """
    מוחקת שריונים שפג תוקפם. נקראת בתחילת כל קריאה לשירות, כדי
    שסלוט ששוחרר יופיע כפנוי מיד ולא יחכה לתהליך רקע נפרד (Part 6).
    """
    session = get_session()
    reservations = session.query(SlotReservation).all()
    expired_ids = [r.reservation_id for r in reservations if has_expired(r.expires_at)]

    if expired_ids:
        (session.query(SlotReservation)
         .filter(SlotReservation.reservation_id.in_(expired_ids))
         .delete(synchronize_session=False))
        session.commit()


def load_treatments_or_raise(treatment_ids):
    if not treatment_ids:
        raise AvailabilityError("יש לבחור לפחות טיפול אחד")

    treatments = []
    for treatment_id in treatment_ids:
        treatment = treatment_manager.get_treatment_by_id(treatment_id)
        if treatment is None:
            # מקרה קצה מפורש במפרט (Part 11): טיפול שנמחק מהקטלוג
            # אחרי שהלקוחה כבר בחרה אותו באשף
            raise AvailabilityError(f"טיפול מספר {treatment_id} כבר לא קיים בקטלוג")
        treatments.append(treatment)

    return treatments


def _capacity_for_interval(context, requires_machine, start_str, end_str, start_dt, end_dt):
    """
    כמה "יחידות קיבולת" פנויות בדיוק במשבצת הזו - המינימום מבין
    עובדות/חדרים/מכשירים פנויים בו-זמנית. אין אילוץ מכשיר כלל אם
    הטיפול לא דורש אחד (context.machines כבר ריק אז ב-DayContext,
    ולכן פשוט לא נכנס לחישוב ה-min בכלל).
    """
    free_staff = free_staff_ids(context, start_str, end_str, start_dt, end_dt)
    free_rooms = free_room_ids(context, start_dt, end_dt)

    if requires_machine:
        free_machines = free_machine_ids(context, start_dt, end_dt)
        return min(len(free_staff), len(free_rooms), len(free_machines))

    return min(len(free_staff), len(free_rooms))


def get_slot_capacity(date_str, time_str, duration_minutes, requires_machine):
    """
    בדיקת קיבולת נקודתית (משבצת בודדת) - משמשת את booking_service
    ל-Layer 2 (re-check בתוך הטרנזקציה, רגע לפני הכתיבה בפועל).
    בונה DayContext טרי משלה בכוונה: זו קריאה חד-פעמית לפני כתיבה
    אמיתית, לא לולאה על עשרות משבצות כמו _free_slots_for_date.
    """
    context = DayContext(date_str, requires_machine)
    start_dt = combine_local(date_str, time_str)
    end_dt = start_dt + timedelta(minutes=duration_minutes)
    return _capacity_for_interval(context, requires_machine, time_str, to_time_str(end_dt),
                                   start_dt, end_dt)


def _free_slots_for_date(date_str, duration_minutes, requires_machine,
                          work_start, work_end, min_hours_before_booking):
    session = get_session()
    held_counts = {}
    for reservation in session.query(SlotReservation).filter(
        SlotReservation.appointment_date == date_str
    ).all():
        held_counts[reservation.appointment_time] = held_counts.get(reservation.appointment_time, 0) + 1

    context = DayContext(date_str, requires_machine)

    day_start = combine_local(date_str, work_start)
    day_end = combine_local(date_str, work_end)

    free_slots = []
    current = day_start

    while current + timedelta(minutes=duration_minutes) <= day_end:
        time_str = to_time_str(current)
        end_dt = current + timedelta(minutes=duration_minutes)
        end_str = to_time_str(end_dt)

        if hours_until(date_str, time_str) >= min_hours_before_booking:
            capacity = _capacity_for_interval(context, requires_machine, time_str, end_str,
                                               current, end_dt)
            held = held_counts.get(time_str, 0)

            if capacity - held > 0:
                free_slots.append(time_str)

        current += timedelta(minutes=SLOT_STEP_MINUTES)

    return free_slots


def get_public_availability(date_from, date_to, treatment_ids):
    """
    נקודת הכניסה היחידה של Principle 3.

    מחזיר:
      {"days": [{"date": "YYYY-MM-DD", "slots": ["09:00", ...]}, ...],
       "total_duration_minutes": N}

    בכוונה שהמבנה לא מכיל שום שדה על תורים תפוסים - שדה שלא קיים
    לא יכול לדלוף בטעות בעדכון עתידי (Part 19.3 במפרט).
    """
    cleanup_expired_reservations()

    treatments = load_treatments_or_raise(treatment_ids)
    total_duration = sum(t.duration_minutes for t in treatments)
    requires_machine = any(getattr(t, "requires_machine", True) for t in treatments)

    window_days = settings_manager.get_int("booking_window_days", 60)
    min_hours_before_booking = settings_manager.get_int("min_hours_before_booking", 4)
    work_start = settings_manager.get_str("working_hours_start", "09:00")
    work_end = settings_manager.get_str("working_hours_end", "20:00")
    working_days = settings_manager.get_working_days()

    today = today_jerusalem()
    max_date = today + timedelta(days=window_days)

    try:
        requested_start = parse_date_str(date_from)
        requested_end = parse_date_str(date_to)
    except ValueError:
        raise AvailabilityError("פורמט תאריך לא תקין - נדרש YYYY-MM-DD")

    if requested_end < requested_start:
        raise AvailabilityError("טווח התאריכים הפוך")

    range_start = max(requested_start, today)
    range_end = min(requested_end, max_date)

    days_out = []
    current_date = range_start
    while current_date <= range_end:
        date_str = to_date_str(current_date)

        if day_of_week(date_str) not in working_days:
            days_out.append({"date": date_str, "slots": []})
        else:
            slots = _free_slots_for_date(date_str, total_duration, requires_machine,
                                          work_start, work_end, min_hours_before_booking)
            days_out.append({"date": date_str, "slots": slots})

        current_date += timedelta(days=1)

    return {"days": days_out, "total_duration_minutes": total_duration}


def is_slot_currently_free(date_str, time_str, treatment_ids):
    """
    בדיקת נקודה בודדת (לא טווח) - משמשת את booking_service לפני
    יצירת שריון (Layer 1), רגע לפני שהלקוחה "תופסת" את השעה.
    """
    cleanup_expired_reservations()

    treatments = load_treatments_or_raise(treatment_ids)
    total_duration = sum(t.duration_minutes for t in treatments)
    requires_machine = any(getattr(t, "requires_machine", True) for t in treatments)

    min_hours_before_booking = settings_manager.get_int("min_hours_before_booking", 4)
    work_start = settings_manager.get_str("working_hours_start", "09:00")
    work_end = settings_manager.get_str("working_hours_end", "20:00")
    working_days = settings_manager.get_working_days()

    if day_of_week(date_str) not in working_days:
        return False

    day_start = combine_local(date_str, work_start)
    day_end = combine_local(date_str, work_end)
    start_dt = combine_local(date_str, time_str)

    if start_dt < day_start or start_dt + timedelta(minutes=total_duration) > day_end:
        return False

    if hours_until(date_str, time_str) < min_hours_before_booking:
        return False

    slots = _free_slots_for_date(date_str, total_duration, requires_machine,
                                  work_start, work_end, min_hours_before_booking)
    return time_str in slots
