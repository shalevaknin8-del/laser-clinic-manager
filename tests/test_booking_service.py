# ============================================================
# tests/test_booking_service.py
# services/availability_service.py + services/booking_service.py -
# Principle 2/3 והגנת ה-3 שכבות מפני double-booking (Part 6 במפרט).
#
# הרצה:  python3 -m pytest tests/test_booking_service.py -v
# ============================================================

import sys
import threading
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from conftest import (  # noqa: E402
    create_client_with_id, create_user,
    future_date_str as _future_date_str,
    setup_one_room_one_machine_one_staff as _setup_one_of_everything,
)

from services import availability_service  # noqa: E402
from services import booking_service  # noqa: E402
from services.booking_service import BookingError, SOURCE_PORTAL, SOURCE_STAFF  # noqa: E402
from services.availability_service import AvailabilityError  # noqa: E402

from managers.room_manager import RoomManager  # noqa: E402
from managers.machine_manager import MachineManager  # noqa: E402
from managers.staff_schedule_manager import StaffScheduleManager  # noqa: E402
from managers.treatment_manager import TreatmentManager  # noqa: E402
from managers.clinic_settings_manager import ClinicSettingsManager  # noqa: E402
from managers.package_manager import PackageManager  # noqa: E402
from managers.appointment_treatment_manager import AppointmentTreatmentManager  # noqa: E402
from models import SlotReservation, Appointment  # noqa: E402
from db import get_session  # noqa: E402
from entities.treatment import Treatment  # noqa: E402


settings_manager = ClinicSettingsManager()


def _first_treatment_id():
    return TreatmentManager().get_all_treatments()[0].treatment_id


# ============================================================
# availability_service - זמינות ציבורית
# ============================================================

def test_availability_shows_free_slot_with_resources_configured(treatment_catalog):
    _setup_one_of_everything()
    date_str = _future_date_str()
    treatment_id = _first_treatment_id()

    result = availability_service.get_public_availability(date_str, date_str, [treatment_id])

    assert result["days"][0]["date"] == date_str
    assert "09:00" in result["days"][0]["slots"]
    assert result["total_duration_minutes"] > 0
    # החוזה המדויק מהמפרט (Part 19.3) - אין שום שדה על תורים תפוסים
    assert set(result["days"][0].keys()) == {"date", "slots"}


def test_availability_empty_without_any_room():
    """בלי אף חדר פעיל אין קיבולת בכלל - גם אם יש עובדת ומכשיר."""
    MachineManager().create_machine("לייזר")
    staff = create_user("0530000002", "עובדת בדיקה", "Password123!", "employee")
    StaffScheduleManager().add_availability(staff.user_id, 0, "00:00", "23:59")
    settings_manager.set_value("working_days", "0,1,2,3,4,5,6")

    treatment_id = TreatmentManager().insert_treatment(
        Treatment(treatment_name="בדיקה", body_area="בדיקה", price=100, duration_minutes=20)
    ).treatment_id

    date_str = _future_date_str()
    result = availability_service.get_public_availability(date_str, date_str, [treatment_id])
    assert result["days"][0]["slots"] == []


def test_availability_excludes_non_working_day(treatment_catalog):
    staff = _setup_one_of_everything()
    date_str = _future_date_str()
    from utils.datetime_utils import day_of_week
    other_day = (day_of_week(date_str) + 1) % 7

    # רק יום אחר (לא זה של date_str) מוגדר כיום עבודה
    settings_manager.set_value("working_days", str(other_day))

    result = availability_service.get_public_availability(date_str, date_str,
                                                            [_first_treatment_id()])
    assert result["days"][0]["slots"] == []


def test_availability_raises_for_deleted_treatment(treatment_catalog):
    _setup_one_of_everything()
    date_str = _future_date_str()

    try:
        availability_service.get_public_availability(date_str, date_str, [999999])
        assert False, "היה צריך להיכשל - טיפול לא קיים"
    except AvailabilityError:
        pass


def test_reservation_blocks_slot_from_other_clients(treatment_catalog):
    """Layer 1: שריון פעיל חוסם את השעה, גם בלי שום תור אמיתי."""
    _setup_one_of_everything()
    date_str = _future_date_str()
    treatment_id = _first_treatment_id()
    client_a = create_client_with_id("לקוחה א", "0501111111", "123456782")

    assert availability_service.is_slot_currently_free(date_str, "09:00", [treatment_id]) is True

    booking_service.create_reservation(client_a.client_id, date_str, "09:00", [treatment_id])

    assert availability_service.is_slot_currently_free(date_str, "09:00", [treatment_id]) is False
    result = availability_service.get_public_availability(date_str, date_str, [treatment_id])
    assert "09:00" not in result["days"][0]["slots"]


def test_expired_reservation_is_ignored(treatment_catalog):
    _setup_one_of_everything()
    date_str = _future_date_str()
    treatment_id = _first_treatment_id()
    client_a = create_client_with_id("לקוחה ב", "0501111112", "123456782")

    reservation = booking_service.create_reservation(client_a.client_id, date_str, "09:00",
                                                       [treatment_id])
    # מדמה שריון שכבר פג - נקבע ישירות ב-DB, בלי לחכות 10 דקות אמיתיות
    session = get_session()
    reservation.expires_at = "2000-01-01T00:00:00+02:00"
    session.commit()

    assert availability_service.is_slot_currently_free(date_str, "09:00", [treatment_id]) is True


# ============================================================
# booking_service - יצירת התור בפועל
# ============================================================

def test_confirm_booking_portal_source_is_pending_approval(treatment_catalog):
    _setup_one_of_everything()
    date_str = _future_date_str()
    treatment_id = _first_treatment_id()
    client_a = create_client_with_id("לקוחה ג", "0501111113", "123456782")

    reservation = booking_service.create_reservation(client_a.client_id, date_str, "09:00",
                                                       [treatment_id])
    appointment = booking_service.confirm_booking(client_a.client_id, reservation.reservation_id,
                                                    source=SOURCE_PORTAL)

    assert appointment.approval_status == "pending_approval"
    assert appointment.approval_expires_at is not None
    assert appointment.status == "pending"
    assert appointment.source == SOURCE_PORTAL
    assert appointment.staff_user_id is not None
    assert appointment.room_id is not None

    linked = AppointmentTreatmentManager().get_treatment_ids_for_appointment(
        appointment.appointment_id
    )
    assert linked == [treatment_id]


def test_confirm_booking_staff_source_is_auto_confirmed(treatment_catalog):
    _setup_one_of_everything()
    date_str = _future_date_str()
    treatment_id = _first_treatment_id()
    client_a = create_client_with_id("לקוחה ד", "0501111114", "123456782")

    reservation = booking_service.create_reservation(client_a.client_id, date_str, "09:00",
                                                       [treatment_id])
    appointment = booking_service.confirm_booking(client_a.client_id, reservation.reservation_id,
                                                    source=SOURCE_STAFF, created_by_user_id=1)

    assert appointment.approval_status == "confirmed"
    assert appointment.approval_expires_at is None


def test_confirm_booking_rejects_reservation_of_another_client(treatment_catalog):
    _setup_one_of_everything()
    date_str = _future_date_str()
    treatment_id = _first_treatment_id()
    client_a = create_client_with_id("לקוחה ה", "0501111115", "123456782")
    client_b = create_client_with_id("לקוחה ו", "0501111116", "123456782")

    reservation = booking_service.create_reservation(client_a.client_id, date_str, "09:00",
                                                       [treatment_id])
    try:
        booking_service.confirm_booking(client_b.client_id, reservation.reservation_id,
                                         source=SOURCE_PORTAL)
        assert False, "היה צריך להיכשל - השריון שייך ללקוחה אחרת"
    except BookingError:
        pass


def test_confirm_booking_rejects_expired_reservation(treatment_catalog):
    _setup_one_of_everything()
    date_str = _future_date_str()
    treatment_id = _first_treatment_id()
    client_a = create_client_with_id("לקוחה ז", "0501111117", "123456782")

    reservation = booking_service.create_reservation(client_a.client_id, date_str, "09:00",
                                                       [treatment_id])
    session = get_session()
    reservation.expires_at = "2000-01-01T00:00:00+02:00"
    session.commit()

    try:
        booking_service.confirm_booking(client_a.client_id, reservation.reservation_id,
                                         source=SOURCE_PORTAL)
        assert False, "היה צריך להיכשל - השריון פג"
    except BookingError:
        pass


def test_layer2_rejects_when_only_resource_taken_after_reservation(treatment_catalog):
    """
    Layer 2: לקוחה משריינת שעה (Layer 1 עובר - אין עוד שריון על
    אותה שעה). לפני שהיא מספיקה לאשר, מופיע תור אמיתי אחר שתופס
    בדיוק את אותה עובדת/חדר/מכשיר היחידים - מדמה כתיבה שלא עברה
    דרך slot_reservations בכלל (למשל מסך הצוות הקיים, שעדיין לא
    מאוחד עם booking_service - ראו סיכום שלב 3). ה-re-check בתוך
    confirm_booking (לא לפני!) חייב לתפוס את זה.
    """
    staff = _setup_one_of_everything()
    date_str = _future_date_str()
    treatment_id = _first_treatment_id()
    client_a = create_client_with_id("לקוחה ח", "0501111118", "123456782")
    client_other = create_client_with_id("לקוחה אחרת", "0501111119", "123456782")

    reservation = booking_service.create_reservation(client_a.client_id, date_str, "09:00",
                                                       [treatment_id])

    room_id = RoomManager().get_all_rooms()[0].room_id
    machine_id = MachineManager().get_all_machines()[0].machine_id

    session = get_session()
    session.add(Appointment(
        client_id=client_other.client_id,
        treatment_id=treatment_id,
        appointment_date=date_str,
        appointment_time="09:00",
        status="pending",
        source=SOURCE_STAFF,
        approval_status="confirmed",
        staff_user_id=staff.user_id,
        room_id=room_id,
        machine_id=machine_id,
    ))
    session.commit()

    try:
        booking_service.confirm_booking(client_a.client_id, reservation.reservation_id,
                                         source=SOURCE_PORTAL)
        assert False, "היה צריך להיכשל - המשאב היחיד כבר נתפס"
    except BookingError:
        pass


# ============================================================
# מגבלת תורים פתוחים וחבילות (Part 13.4)
# ============================================================

def test_max_open_appointments_limit_enforced(treatment_catalog):
    _setup_one_of_everything()
    settings_manager.set_value("max_open_appointments_per_client", "1")
    date_str = _future_date_str()
    treatment_id = _first_treatment_id()
    client_a = create_client_with_id("לקוחה ט", "0501111120", "123456782")

    first_reservation = booking_service.create_reservation(client_a.client_id, date_str, "09:00",
                                                             [treatment_id])
    booking_service.confirm_booking(client_a.client_id, first_reservation.reservation_id,
                                     source=SOURCE_PORTAL)

    second_reservation = booking_service.create_reservation(client_a.client_id, date_str, "10:00",
                                                              [treatment_id])
    try:
        booking_service.confirm_booking(client_a.client_id, second_reservation.reservation_id,
                                         source=SOURCE_PORTAL)
        assert False, "היה צריך להיכשל - חריגה ממגבלת תורים פתוחים"
    except BookingError:
        pass


def test_package_holder_bypasses_open_appointment_limit(treatment_catalog):
    _setup_one_of_everything()
    settings_manager.set_value("max_open_appointments_per_client", "1")
    date_str = _future_date_str()
    treatment_id = _first_treatment_id()
    client_a = create_client_with_id("לקוחה י", "0501111121", "123456782")

    # תור ראשון "רגיל" ממלא את המגבלה
    first_reservation = booking_service.create_reservation(client_a.client_id, date_str, "09:00",
                                                             [treatment_id])
    booking_service.confirm_booking(client_a.client_id, first_reservation.reservation_id,
                                     source=SOURCE_PORTAL)

    package_manager = PackageManager()
    package = package_manager.create_package("חבילת בדיקה", treatment_id, 5, 1000)
    client_package = package_manager.purchase_package_for_client(client_a.client_id,
                                                                   package.package_id)

    second_reservation = booking_service.create_reservation(client_a.client_id, date_str, "10:00",
                                                              [treatment_id])
    appointment = booking_service.confirm_booking(client_a.client_id,
                                                    second_reservation.reservation_id,
                                                    source=SOURCE_PORTAL)

    assert appointment.client_package_id == client_package.client_package_id


# ============================================================
# מרוץ אמיתי בין שני threads - הבדיקה שהמפרט קורא לה "הסיכון
# ההנדסי המרכזי של Release 2" (Part 6)
# ============================================================

def test_concurrent_confirm_booking_only_one_wins(treatment_catalog):
    """
    שני threads אמיתיים, כל אחד עם session נפרד (scoped_session
    לפי thread - בדיוק כמו שתי בקשות HTTP מקבילות בפועל), מנסים
    לאשר בו-זמנית שני שריונים לאותה שעה בדיוק כשיש רק משאב אחד
    מכל סוג. חייב לצאת מהמרוץ הזה בדיוק תור אחד ב-DB, לא אפס
    ולא שניים, וללקוחה השנייה שגיאה נקייה - לא קריסה.
    """
    _setup_one_of_everything()
    date_str = _future_date_str()
    treatment_id = _first_treatment_id()
    client_a = create_client_with_id("לקוחה מקבילה א", "0501111130", "123456782")
    client_b = create_client_with_id("לקוחה מקבילה ב", "0501111131", "123456782")

    reservation_a = booking_service.create_reservation(client_a.client_id, date_str, "11:00",
                                                         [treatment_id])
    # שריון שני לאותה שעה בדיוק, נכנס ישירות ל-DB: מדמה את המרוץ
    # האמיתי בין שתי בקשות שהגיעו כמעט באותו רגע (create_reservation
    # עצמו לא ערוץ יחיד - בדיוק בשביל זה קיימות שכבות 2/3)
    session = get_session()
    reservation_b = SlotReservation(
        client_id=client_b.client_id, appointment_date=date_str, appointment_time="11:00",
        treatment_ids=reservation_a.treatment_ids, expires_at=reservation_a.expires_at,
    )
    session.add(reservation_b)
    session.commit()

    results = {}
    barrier = threading.Barrier(2)

    def _confirm(client_id, reservation_id, key):
        barrier.wait()
        try:
            appointment = booking_service.confirm_booking(client_id, reservation_id,
                                                            source=SOURCE_PORTAL)
            results[key] = ("ok", appointment.appointment_id)
        except BookingError as error:
            results[key] = ("error", str(error))

    thread_a = threading.Thread(target=_confirm,
                                 args=(client_a.client_id, reservation_a.reservation_id, "a"))
    thread_b = threading.Thread(target=_confirm,
                                 args=(client_b.client_id, reservation_b.reservation_id, "b"))
    thread_a.start()
    thread_b.start()
    thread_a.join()
    thread_b.join()

    outcomes = [results["a"][0], results["b"][0]]
    assert outcomes.count("ok") == 1, f"תוצאה לא צפויה: {results}"
    assert outcomes.count("error") == 1, f"תוצאה לא צפויה: {results}"

    verify_session = get_session()
    active_count = verify_session.query(Appointment).filter(
        Appointment.appointment_date == date_str,
        Appointment.appointment_time == "11:00",
        Appointment.status != "cancelled",
    ).count()
    assert active_count == 1
