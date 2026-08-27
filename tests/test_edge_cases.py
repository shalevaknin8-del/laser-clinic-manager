# ============================================================
# tests/test_edge_cases.py
# מקרי קצה: קלט, לוגיקה עסקית, ומצב שיחה.
#
# הרצה:  python3 -m pytest tests/test_edge_cases.py -v
# ============================================================

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from conftest import create_user, login_as, create_client_with_id  # noqa: E402

from chatbot.state import ConversationState, conversation_store  # noqa: E402
from chatbot.flows import process_message  # noqa: E402
from utils.validators import (  # noqa: E402
    validate_national_id,
    normalize_national_id,
    validate_phone,
    normalize_phone,
    validate_date,
    validate_time,
)
from managers.client_manager import ClientManager  # noqa: E402
from managers.appointment_manager import AppointmentManager  # noqa: E402
from managers.appointment_treatment_manager import AppointmentTreatmentManager  # noqa: E402
from managers.invoice_manager import InvoiceManager  # noqa: E402
from entities.appointment import Appointment  # noqa: E402
from entities.invoice import Invoice  # noqa: E402


# ============================================================
# קלט: תעודת זהות
# ============================================================

def test_national_id_with_dashes_and_spaces_accepted():
    assert validate_national_id("123-456-782")[0] is True
    assert validate_national_id("123 456 782")[0] is True
    assert normalize_national_id("123-456-782") == "123456782"


def test_national_id_leading_zero_normalized():
    # ת"ז ישנה בלי אפס מוביל - 8 ספרות בפועל, המערכת משלימה ל-9
    is_valid, _ = validate_national_id("12345678")
    assert normalize_national_id("12345678") == "012345678"
    # תקינות תלויה בספרת הביקורת אחרי ההשלמה, לא תמיד תעבור -
    # מה שחשוב הוא שהנרמול לא קורס ומחזיר תמיד 9 ספרות
    assert len(normalize_national_id("12345678")) == 9


def test_national_id_letters_rejected():
    is_valid, message = validate_national_id("12345678a")
    assert is_valid is False
    assert "ספרות" in message


def test_national_id_empty_rejected():
    is_valid, message = validate_national_id("")
    assert is_valid is False
    is_valid_none, _ = validate_national_id(None)
    assert is_valid_none is False


def test_national_id_20_digits_rejected():
    is_valid, message = validate_national_id("1" * 20)
    assert is_valid is False
    assert "9 ספרות" in message


def test_verify_national_id_tolerates_formatting_differences():
    """
    לקוחה שנרשמה עם '123456782' חייבת להיות מזוהה גם כשהיא
    מקלידה את אותה תעודה עם מקפים או רווחים - זו אותה תעודה.
    """
    client_obj = create_client_with_id("לקוחת פורמט", "0500000070", "123456782")
    manager = ClientManager()

    assert manager.verify_client_national_id(client_obj.client_id, "123-456-782") is True
    assert manager.verify_client_national_id(client_obj.client_id, "123 456 782") is True
    assert manager.verify_client_national_id(client_obj.client_id, "000000000") is False


# ============================================================
# קלט: טלפון
# ============================================================

def test_phone_format_plain():
    assert validate_phone("0521234567")[0] is True


def test_phone_format_with_dash():
    assert validate_phone("052-1234567")[0] is True


def test_phone_format_with_multiple_dashes():
    assert validate_phone("052-123-4567")[0] is True


def test_phone_format_international_prefix():
    assert validate_phone("+972521234567")[0] is True


def test_phone_normalized_forms_are_equal():
    forms = ["0521234567", "052-1234567", "052-123-4567", "+972521234567", "972521234567"]
    normalized = {normalize_phone(f) for f in forms}
    assert normalized == {"0521234567"}


def test_phone_landline_shape_rejected():
    # 9 ספרות שאינן מתחילות ב-05 - לא נייד, ולכן לא יכול לקבל
    # קוד אימות ב-SMS. נדחה בכוונה (ראו TEST_REPORT.md)
    is_valid, _ = validate_phone("021234567")
    assert is_valid is False


# ============================================================
# קלט: הודעות צ'אט
# ============================================================

def test_chat_empty_message_rejected(client):
    response = client.post("/api/chat", json={"message": ""})
    assert response.status_code == 400


def test_chat_10000_char_message_rejected(client):
    response = client.post("/api/chat", json={"message": "א" * 10000})
    assert response.status_code == 400


def test_chat_emoji_only_message_does_not_crash(client):
    response = client.post("/api/chat", json={"message": "😀😀😀🎉🎊"})
    assert response.status_code == 200
    assert response.get_json()["state"] == "identifying"


def test_chat_html_message_does_not_crash_or_execute(client):
    response = client.post("/api/chat", json={"message": "<script>alert(1)</script>"})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["reply"]
    # לא נדרש escaping ידני - JSON כשלעצמו לא "מריץ" תגית סקריפט,
    # רק מוודאים שהתוכן לא גרם לקריסה ושהתשובה חזרה כרגיל


# ============================================================
# קלט: תאריך ושעה
# ============================================================

def test_appointment_past_date_currently_allowed(client, treatment_catalog):
    """
    תיעוד התנהגות קיימת: המערכת לא חוסמת תאריך עבר בקביעת תור.
    זה מכוון (למשל תיעוד רטרואקטיבי של תור שכבר התקיים), לא באג -
    validate_date בודק רק שהפורמט תקין ושהתאריך אמיתי.
    """
    create_user("0500000040", "דנה מנהלת", "AdminPass123", "admin")
    login_as(client, "0500000040", "AdminPass123")
    target = create_client_with_id("לקוחת עבר", "0500000071", "111111118")

    response = client.post("/api/appointments", json={
        "client_id": target.client_id,
        "treatment_id": treatment_catalog[0].treatment_id,
        "appointment_date": "2020-01-01",
        "appointment_time": "10:00",
    })
    assert response.status_code == 201


def test_appointment_invalid_date_rejected(client, treatment_catalog):
    create_user("0500000041", "דנה מנהלת", "AdminPass123", "admin")
    login_as(client, "0500000041", "AdminPass123")
    target = create_client_with_id("לקוחת תאריך", "0500000072", "222222226")

    response = client.post("/api/appointments", json={
        "client_id": target.client_id,
        "treatment_id": treatment_catalog[0].treatment_id,
        "appointment_date": "2026-02-31",  # 31 בפברואר לא קיים
        "appointment_time": "10:00",
    })
    assert response.status_code == 400
    assert response.get_json()["field"] == "appointment_date"


def test_appointment_invalid_time_rejected(client, treatment_catalog):
    create_user("0500000042", "דנה מנהלת", "AdminPass123", "admin")
    login_as(client, "0500000042", "AdminPass123")
    target = create_client_with_id("לקוחת שעה", "0500000073", "333333334")

    response = client.post("/api/appointments", json={
        "client_id": target.client_id,
        "treatment_id": treatment_catalog[0].treatment_id,
        "appointment_date": "2026-06-01",
        "appointment_time": "25:00",
    })
    assert response.status_code == 400
    assert response.get_json()["field"] == "appointment_time"


def test_validate_date_and_time_directly():
    assert validate_date("2026-02-31")[0] is False
    assert validate_time("25:00")[0] is False
    assert validate_date("2026-03-15")[0] is True
    assert validate_time("14:30")[0] is True


# ============================================================
# לוגיקה עסקית: תורים
# ============================================================

def test_booking_occupied_slot_conflicts(client, treatment_catalog):
    create_user("0500000050", "דנה מנהלת", "AdminPass123", "admin")
    login_as(client, "0500000050", "AdminPass123")
    target = create_client_with_id("לקוחת תפוסה", "0500000074", "444444442")

    first = client.post("/api/appointments", json={
        "client_id": target.client_id,
        "treatment_id": treatment_catalog[0].treatment_id,
        "appointment_date": "2027-06-01",
        "appointment_time": "10:00",
    })
    assert first.status_code == 201

    second = client.post("/api/appointments", json={
        "client_id": target.client_id,
        "treatment_id": treatment_catalog[0].treatment_id,
        "appointment_date": "2027-06-01",
        "appointment_time": "10:00",
    })
    assert second.status_code == 409


def test_combo_appointment_exceeding_business_hours_rejected(client, treatment_catalog):
    """
    טיפול מרוכב שהמשך הכולל שלו חורג משעת הסגירה (18:00) חייב
    להידחות, גם אם אין תור אחר שמתנגש איתו. תוקן ב-managers/
    appointment_treatment_manager.py - ראו TEST_REPORT.md.
    """
    create_user("0500000051", "דנה מנהלת", "AdminPass123", "admin")
    login_as(client, "0500000051", "AdminPass123")
    target = create_client_with_id("לקוחת חריגה", "0500000075", "111111118")

    # "רגליים מלא" (45 דק') מתחיל ב-17:45 ומסתיים ב-18:30 - חורג
    long_treatment = next(t for t in treatment_catalog if t.duration_minutes >= 45)

    response = client.post("/api/appointments", json={
        "client_id": target.client_id,
        "treatment_id": long_treatment.treatment_id,
        "appointment_date": "2027-06-02",
        "appointment_time": "17:45",
    })
    assert response.status_code == 409
    assert "שעות הפעילות" in response.get_json()["error"]


def test_cancelled_appointment_frees_the_slot(client, treatment_catalog):
    create_user("0500000052", "דנה מנהלת", "AdminPass123", "admin")
    login_as(client, "0500000052", "AdminPass123")
    target = create_client_with_id("לקוחת ביטול", "0500000076", "222222226")

    created = client.post("/api/appointments", json={
        "client_id": target.client_id,
        "treatment_id": treatment_catalog[0].treatment_id,
        "appointment_date": "2027-06-03",
        "appointment_time": "10:00",
    }).get_json()

    cancel = client.put(f"/api/appointments/{created['appointment_id']}", json={
        "status": "cancelled",
    })
    assert cancel.status_code == 200

    # אותה שעה בדיוק חייבת להיות פנויה עכשיו לתור חדש
    reused = client.post("/api/appointments", json={
        "client_id": target.client_id,
        "treatment_id": treatment_catalog[0].treatment_id,
        "appointment_date": "2027-06-03",
        "appointment_time": "10:00",
    })
    assert reused.status_code == 201


def test_cancelled_appointment_not_reported_active_by_chatbot(treatment_catalog, monkeypatch):
    client_obj = create_client_with_id("לקוחת ביטול בוט", "0500000077", "333333334")

    appointment = AppointmentManager().insert_appointment(Appointment(
        client_id=client_obj.client_id,
        treatment_id=treatment_catalog[0].treatment_id,
        appointment_date="2027-06-04",
        appointment_time="09:00",
        status="cancelled",
    ))
    AppointmentTreatmentManager().set_treatments_for_appointment(
        appointment.appointment_id, [treatment_catalog[0].treatment_id]
    )

    from utils import otp as otp_module
    captured = {}
    original = otp_module.generate_code

    def capturing(length=None):
        value = original(length)
        captured["code"] = value
        return value

    monkeypatch.setattr(otp_module, "generate_code", capturing)

    conversation = ConversationState("edge-cancelled-active")
    process_message(conversation, f"קוראים לי {client_obj.full_name}")
    process_message(conversation, "333333334")

    final_reply = process_message(conversation, captured["code"])

    assert "לא מצאתי תורים פתוחים" in final_reply


def test_client_with_multiple_future_appointments_shows_earliest(treatment_catalog):
    client_obj = create_client_with_id("לקוחת ריבוי תורים", "0500000078", "444444442")

    manager = AppointmentManager()
    combo_manager = AppointmentTreatmentManager()

    later = manager.insert_appointment(Appointment(
        client_id=client_obj.client_id,
        treatment_id=treatment_catalog[0].treatment_id,
        appointment_date="2027-08-01",
        appointment_time="10:00",
    ))
    combo_manager.set_treatments_for_appointment(
        later.appointment_id, [treatment_catalog[0].treatment_id]
    )

    earlier = manager.insert_appointment(Appointment(
        client_id=client_obj.client_id,
        treatment_id=treatment_catalog[0].treatment_id,
        appointment_date="2027-07-01",
        appointment_time="09:00",
    ))
    combo_manager.set_treatments_for_appointment(
        earlier.appointment_id, [treatment_catalog[0].treatment_id]
    )

    from utils import otp as otp_module
    captured = {}
    original = otp_module.generate_code

    def capturing(length=None):
        value = original(length)
        captured["code"] = value
        return value

    otp_module.generate_code = capturing
    try:
        conversation = ConversationState("edge-multiple-appts")
        process_message(conversation, f"קוראים לי {client_obj.full_name}")
        process_message(conversation, "444444442")
    finally:
        otp_module.generate_code = original

    final_reply = process_message(conversation, captured["code"])

    assert "01.07.2027" in final_reply
    assert "09:00" in final_reply
    assert "01.08.2027" not in final_reply


def test_delete_client_with_linked_appointments_blocked(client, treatment_catalog):
    create_user("0500000053", "דנה מנהלת", "AdminPass123", "admin")
    login_as(client, "0500000053", "AdminPass123")
    target = create_client_with_id("לקוחת מחיקה", "0500000079", "111111118")
    # נשמר כמספר פשוט, לא כאובייקט ORM: קריאת ה-API הבאה עושה
    # rollback על השגיאה, ומפקיעה (expire) את האובייקט המקורי -
    # גישה חוזרת ל-target.client_id אחרי זה הייתה זורקת
    # DetachedInstanceError. ראו auth/decorators.py והתיעוד ב-db.py
    target_id = target.client_id

    manager = AppointmentManager()
    appointment = manager.insert_appointment(Appointment(
        client_id=target_id,
        treatment_id=treatment_catalog[0].treatment_id,
        appointment_date="2027-06-05",
        appointment_time="10:00",
    ))

    response = client.delete(f"/api/clients/{target_id}")
    assert response.status_code == 409
    assert "תורים" in response.get_json()["error"]

    # הלקוחה עדיין קיימת - המחיקה לא בוצעה חלקית
    assert ClientManager().get_client_by_id(target_id) is not None


def test_invoice_cancel_and_restore_roundtrip(client):
    create_user("0500000054", "דנה מנהלת", "AdminPass123", "admin")
    login_as(client, "0500000054", "AdminPass123")
    target = create_client_with_id("לקוחת חשבונית", "0500000083", "222222226")

    invoice = InvoiceManager().insert_invoice(Invoice(
        client_id=target.client_id, amount=250.0, invoice_date="2026-01-15",
    ))

    cancel = client.post(f"/api/invoices/{invoice.invoice_id}/cancel")
    assert cancel.status_code == 200

    cancelled = InvoiceManager().get_invoice_by_id(invoice.invoice_id)
    assert bool(cancelled.is_cancelled) is True
    assert cancelled.cancelled_at is not None

    double_cancel = client.post(f"/api/invoices/{invoice.invoice_id}/cancel")
    assert double_cancel.status_code == 409

    restore = client.post(f"/api/invoices/{invoice.invoice_id}/restore")
    assert restore.status_code == 200

    restored = InvoiceManager().get_invoice_by_id(invoice.invoice_id)
    assert bool(restored.is_cancelled) is False
    assert restored.cancelled_at is None

    double_restore = client.post(f"/api/invoices/{invoice.invoice_id}/restore")
    assert double_restore.status_code == 409


# ============================================================
# מצב שיחה
# ============================================================

def test_conversation_expires_mid_verification():
    conversation = ConversationState("edge-expiry")
    conversation.state = "awaiting_id"
    conversation.candidate_client_id = 1

    # מדמים חלוף זמן מעבר למגבלת ה-timeout, בלי לחכות בפועל
    from config import Config
    conversation.last_activity_at = datetime.now() - timedelta(
        minutes=Config.SESSION_TIMEOUT_MINUTES + 1
    )

    assert conversation.is_expired() is True

    conversation_store._conversations[conversation.session_id] = conversation
    fetched = conversation_store.get(conversation.session_id)

    # שיחה שפגה נמחקת ומוחזרת כ-None - לא ממשיכים מהמצב הישן
    assert fetched is None
    assert conversation.session_id not in conversation_store._conversations


def test_name_change_mid_verification_does_not_switch_identity():
    """
    כשהלקוחה כבר במצב awaiting_id, הודעה חדשה עם שם אחר לא
    אמורה לגרום להחלפת זהות שקטה - handle_awaiting_id מצפה
    לתעודת זהות בלבד, ולא "משחזר" שם מתוך הטקסט.
    """
    client_a = create_client_with_id("לקוחה א", "0500000060", "111111118")
    create_client_with_id("לקוחה ב", "0500000061", "222222226")

    conversation = ConversationState("edge-name-switch")
    process_message(conversation, "קוראים לי לקוחה א")
    assert conversation.candidate_client_id == client_a.client_id
    assert conversation.state == "awaiting_id"

    reply = process_message(conversation, "בעצם קוראים לי לקוחה ב")

    # לא זוהתה תעודת זהות בהודעה - הבוט מבקש שוב, והזהות לא הוחלפה
    assert "לא זיהיתי מספר תעודת זהות" in reply
    assert conversation.candidate_client_id == client_a.client_id
    assert conversation.state == "awaiting_id"


def test_national_id_sent_before_any_name():
    """
    הודעה ראשונה שמכילה רק ספרות (בלי שם) לא אמורה להתפרש כשם
    ולא אמורה להתאים בטעות ללקוחה כלשהי.
    """
    create_client_with_id("לקוחת בדיקה", "0500000062", "123456782")

    conversation = ConversationState("edge-id-before-name")
    reply = process_message(conversation, "123456782")

    assert conversation.state == "identifying"
    assert conversation.candidate_client_id is None
    assert "איך קוראים לך" in reply
