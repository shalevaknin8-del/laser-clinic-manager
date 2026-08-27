# ============================================================
# services/booking_service.py
# Principle 2 במפרט: הרכיב היחיד שכותב תורים. הפורטל, הצ'אטבוט,
# ובעתיד גם ממשק הצוות - כולם קוראים לכאן, ולא כותבים ל-appointments
# ישירות. "לעולם לא שתי דרכים ליצור תור."
#
# ההגנה התלת-שכבתית מפני double-booking (Part 6 במפרט):
#   Layer 1 - create_reservation: שריון 10 דקות, נבדק מול
#             availability_service (שמתעלמת משריונים שפגו).
#   Layer 2 - confirm_booking: בדיקה חוזרת בתוך אותה טרנזקציה
#             שבה נכתב התור - לא לפני. אם משאב שהיה פנוי רגע קודם
#             כבר נתפס, הבקשה נדחית כאן, לפני כל כתיבה.
#   Layer 3 - האינדקסים הייחודיים החלקיים (migrations/010): רשת
#             ביטחון סופית ברמת ה-DB. IntegrityError כאן מטופלת
#             כ"השעה נתפסה" ולא כתקלת מערכת.
# ============================================================

import json
from datetime import timedelta

from sqlalchemy.exc import IntegrityError

from db import get_session
from models import SlotReservation, Appointment
from managers.appointment_treatment_manager import AppointmentTreatmentManager
from managers.clinic_settings_manager import ClinicSettingsManager
from managers.package_manager import PackageManager
from managers.audit_manager import AuditManager, ACTION_CREATE
from services import availability_service
from services.scheduling import DayContext, free_staff_ids, free_room_ids, free_machine_ids
from utils.datetime_utils import (
    now_jerusalem, combine_local, to_time_str, expires_at_iso, has_expired,
)

RESERVATION_HOLD_MINUTES = 10

SOURCE_STAFF = "staff"
SOURCE_PORTAL = "portal"
SOURCE_CHATBOT = "chatbot"

APPROVAL_PENDING = "pending_approval"
APPROVAL_CONFIRMED = "confirmed"

combo_manager = AppointmentTreatmentManager()
settings_manager = ClinicSettingsManager()
package_manager = PackageManager()
audit_manager = AuditManager()


class BookingError(Exception):
    """שגיאה עסקית ברורה למשתמשת הקצה. ההודעה תמיד בעברית וללא חשיפת מבנה פנימי."""


# ============================================================
# Layer 1 - שריון זמני
# ============================================================

def create_reservation(client_id, appointment_date, appointment_time, treatment_ids):
    """
    Part 4 Step 6 / Part 19.7: קליק על שעה יוצר שריון ל-10 דקות,
    והשעה נעלמת מיד מזמינות שאר הלקוחות (availability_service
    מתחשבת בשריונים פעילים).
    """
    treatment_ids = list(treatment_ids)

    if not availability_service.is_slot_currently_free(appointment_date, appointment_time,
                                                         treatment_ids):
        raise BookingError("השעה המבוקשת כבר לא פנויה")

    session = get_session()
    reservation = SlotReservation(
        client_id=client_id,
        appointment_date=appointment_date,
        appointment_time=appointment_time,
        treatment_ids=json.dumps(treatment_ids),
        expires_at=expires_at_iso(RESERVATION_HOLD_MINUTES),
    )
    session.add(reservation)
    session.commit()
    return reservation


# ============================================================
# שיבוץ משאבים (הפורטל/הצ'אטבוט לא בוחרים חדר/מכשיר/עובדת בעצמם)
# ============================================================

def _assign_resources(date_str, time_str, duration_minutes, requires_machine):
    """
    בוחרת עובדת/חדר/מכשיר ספציפיים מתוך מי שפנוי ברגע הזה בדיוק
    (services/scheduling.py - אותה לוגיקה בדיוק ששימשה לספירה
    ב-availability_service). מחזירה None אם אין שילוב אפשרי -
    Layer 2 יתייחס לזה כאל "השעה תפוסה", לא כתקלה.
    """
    context = DayContext(date_str, requires_machine)
    start_dt = combine_local(date_str, time_str)
    end_dt = start_dt + timedelta(minutes=duration_minutes)
    end_str = to_time_str(end_dt)

    staff_ids = free_staff_ids(context, time_str, end_str, start_dt, end_dt)
    room_ids = free_room_ids(context, start_dt, end_dt)
    machine_ids = free_machine_ids(context, start_dt, end_dt) if requires_machine else []

    if not staff_ids or not room_ids or (requires_machine and not machine_ids):
        return None

    return staff_ids[0], room_ids[0], (machine_ids[0] if requires_machine else None)


# ============================================================
# מגבלת תורים פתוחים (Part 13.4) וחבילות
# ============================================================

def _find_usable_package(client_id, treatment_ids):
    """
    חבילה תקפה רק לתור *טיפול יחיד* (לא קומבו) שתואם בדיוק לטיפול
    שהחבילה מיועדת לו - חבילות אינן מעורבות (ראו models.Package).
    """
    if len(treatment_ids) != 1:
        return None

    for client_package in package_manager.get_client_packages(client_id, only_usable=True):
        if client_package.package.treatment_id == treatment_ids[0]:
            return client_package

    return None


def _count_open_appointments(client_id):
    """תורים עתידיים שעדיין לא בוטלו ועדיין בתהליך (ממתין לאישור/מאושר)."""
    session = get_session()
    count = 0
    for appointment in session.query(Appointment).filter(
        Appointment.client_id == client_id,
        Appointment.status != "cancelled",
        Appointment.approval_status.in_((APPROVAL_PENDING, APPROVAL_CONFIRMED)),
    ).all():
        appointment_dt = combine_local(appointment.appointment_date, appointment.appointment_time)
        if appointment_dt >= now_jerusalem():
            count += 1
    return count


# ============================================================
# Layer 2 + 3 - אישור השריון ליצירת תור בפועל
# ============================================================

def confirm_booking(client_id, reservation_id, source, created_by_user_id=None):
    """
    Part 4 Step 7 / Part 9 (POST /book): הופכת שריון תקף לתור
    ב-pending_approval (או confirmed מיידית אם source='staff' -
    צוות שקבע תור ישירות כבר "אישר" אותו בעצם הפעולה).

    reservation_id נבדק תמיד מול client_id - שריון של לקוחה אחרת
    לעולם לא ניתן לאישור, גם אם המזהה נוחש נכון.
    """
    if source not in (SOURCE_STAFF, SOURCE_PORTAL, SOURCE_CHATBOT):
        raise BookingError("מקור תור לא תקין")

    session = get_session()
    reservation = (
        session.query(SlotReservation)
        .filter(SlotReservation.reservation_id == reservation_id,
                SlotReservation.client_id == client_id)
        .first()
    )
    if reservation is None:
        raise BookingError("השריון לא נמצא")

    if has_expired(reservation.expires_at):
        session.delete(reservation)
        session.commit()
        raise BookingError("תוקף השריון פג - יש לבחור שעה מחדש")

    treatment_ids = json.loads(reservation.treatment_ids)
    treatments = availability_service.load_treatments_or_raise(treatment_ids)
    total_duration = sum(t.duration_minutes for t in treatments)
    requires_machine = any(getattr(t, "requires_machine", True) for t in treatments)

    usable_package = _find_usable_package(client_id, treatment_ids)

    if usable_package is None:
        max_open = settings_manager.get_int("max_open_appointments_per_client", 3)
        if _count_open_appointments(client_id) >= max_open:
            raise BookingError(
                f"יש לך כבר {max_open} תורים פתוחים - לא ניתן לקבוע תור נוסף בלי לבטל אחד מהם"
            )

    # --- Layer 2: re-check בתוך אותה טרנזקציה שבה נכתב התור ---
    assignment = _assign_resources(reservation.appointment_date, reservation.appointment_time,
                                    total_duration, requires_machine)
    if assignment is None:
        raise BookingError("מצטערים, השעה הזו נתפסה בדיוק עכשיו - יש לבחור שעה אחרת")

    staff_user_id, room_id, machine_id = assignment

    is_staff_source = source == SOURCE_STAFF
    approval_status = APPROVAL_CONFIRMED if is_staff_source else APPROVAL_PENDING
    approval_expires_at = None
    if not is_staff_source:
        approval_window_hours = settings_manager.get_int("approval_window_hours", 12)
        approval_expires_at = (now_jerusalem() + timedelta(hours=approval_window_hours)).isoformat()

    appointment = Appointment(
        client_id=client_id,
        treatment_id=treatment_ids[0],
        appointment_date=reservation.appointment_date,
        appointment_time=reservation.appointment_time,
        status="pending",
        source=source,
        created_by_user_id=created_by_user_id,
        approval_status=approval_status,
        approval_expires_at=approval_expires_at,
        room_id=room_id,
        machine_id=machine_id,
        staff_user_id=staff_user_id,
        client_package_id=usable_package.client_package_id if usable_package else None,
    )
    session.add(appointment)

    try:
        # flush (לא commit) כדי לקבל appointment_id לפני שקושרים את
        # טבלת הקישור - עדיין באותה טרנזקציה פתוחה בדיוק. ה-INSERT
        # נשלח כאן, וזה הרגע שבו SQLite בפועל בודק את אינדקס
        # Layer 3 (unique index חלקי) - IntegrityError תיזרק כאן
        # אם משאב כלשהו נתפס בדיוק באותו רגע ע"י טרנזקציה אחרת
        session.flush()

        session.delete(reservation)

        # set_treatments_for_appointment מבצע commit בעצמו (ראו
        # AppointmentTreatmentManager) - זה בסדר, כי הוא אותו session
        # בדיוק (scoped_session), אז ה-commit הזה סוגר יחד את הוספת
        # התור, מחיקת השריון, וטבלת הקישור - כאילו הייתה טרנזקציה אחת
        combo_manager.set_treatments_for_appointment(appointment.appointment_id, treatment_ids)

    except IntegrityError:
        # Layer 3: רשת הביטחון הסופית - אינדקס ייחודי חלקי (staff/room/
        # machine) תפס התנגשות שחמקה מ-Layer 2 (race אמיתי בין שתי
        # בקשות בו-זמניות). לא תקלת מערכת - השעה פשוט נתפסה קודם.
        session.rollback()
        raise BookingError("מצטערים, השעה הזו נתפסה בדיוק עכשיו - יש לבחור שעה אחרת")

    audit_manager.log(
        action=ACTION_CREATE,
        entity_type="appointment",
        entity_id=appointment.appointment_id,
        details=f"תור נוצר ע\"י לקוחה #{client_id} (מקור: {source})",
    )

    return appointment
