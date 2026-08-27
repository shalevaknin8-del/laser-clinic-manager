# ============================================================
# tests/test_scenarios.py
# חמשת תרחישי החובה של הצ'אטבוט, מריצים מסלול שיחה מלא
# ומדפיסים תמלול קריא לכל תרחיש - הוכחת הרצה מוכנה להגשה.
#
# הרצה עם תמלול מלא על המסך:
#   python3 -m pytest tests/test_scenarios.py -s -v
# או כסקריפט עצמאי:
#   python3 tests/test_scenarios.py
# ============================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from conftest import create_client_with_id  # noqa: E402

from chatbot.state import ConversationState  # noqa: E402
from chatbot.flows import process_message  # noqa: E402
from managers.appointment_manager import AppointmentManager  # noqa: E402
from managers.appointment_treatment_manager import AppointmentTreatmentManager  # noqa: E402
from entities.appointment import Appointment  # noqa: E402
from utils import otp  # noqa: E402


def say(conversation, message):
    """שולח הודעה לבוט, מדפיס את השורה בפורמט שיחה, ומחזיר את התשובה."""
    print(f"\n  לקוחה : {message}")
    reply = process_message(conversation, message)
    for line in reply.split("\n"):
        print(f"  בוט    : {line}")
    print(f"  [state: {conversation.state}]")
    return reply


def create_appointment_for(client_obj, treatment, appointment_date, appointment_time,
                            status="pending"):
    """עוזר: קובע תור אמיתי ללקוחה נתונה, כולל רישום בטבלת הטיפול המרוכב."""
    manager = AppointmentManager()
    appointment = manager.insert_appointment(Appointment(
        client_id=client_obj.client_id,
        treatment_id=treatment.treatment_id,
        appointment_date=appointment_date,
        appointment_time=appointment_time,
        status=status,
    ))
    AppointmentTreatmentManager().set_treatments_for_appointment(
        appointment.appointment_id, [treatment.treatment_id]
    )
    return appointment


# ============================================================
# תרחיש 1: שם ייחודי + תאריך שגוי -> תיקון עם התאריך האמיתי
# ============================================================

def test_scenario_1_unique_name_wrong_date(treatment_catalog, monkeypatch):
    print("\n" + "=" * 60)
    print("  תרחיש 1: שם ייחודי, לקוחה טוענת תאריך שגוי")
    print("=" * 60)

    captured = {}
    original_generate = otp.generate_code

    def capturing_generate(length=None):
        code = original_generate(length)
        captured["code"] = code
        return code

    monkeypatch.setattr(otp, "generate_code", capturing_generate)

    rotem = create_client_with_id(
        "רותם מירון", "0521234567", "123456782",
        email="rotem.miron@example.com",
    )
    treatment = treatment_catalog[0]
    create_appointment_for(rotem, treatment, "2027-03-10", "11:30")

    conversation = ConversationState("scenario-1")

    say(conversation, "קוראים לי רותם מירון ויש לי תור בתאריך 01.01.2025 בשעה 08:00")
    assert conversation.state == "awaiting_id"
    assert conversation.candidate_client_id == rotem.client_id

    say(conversation, "123456782")
    assert conversation.state == "awaiting_otp"
    assert conversation.id_verified is True

    code = captured.get("code")
    assert code is not None, "לא נלכד קוד אימות - חייב להיווצר בשלב הקודם"

    final_reply = say(conversation, code)

    assert conversation.state == "verified"
    assert conversation.is_fully_verified() is True

    # התאריך והשעה האמיתיים חייבים להופיע בתשובה הסופית
    assert "10.03.2027" in final_reply
    assert "11:30" in final_reply
    # וגם אזכור מפורש שהתאריך שהיא טענה שגוי
    assert "01.01.2025" in final_reply
    assert "שימי לב" in final_reply

    print("\n  תוצאה: הבוט תיקן את הלקוחה עם התאריך והשעה האמיתיים. PASS")


# ============================================================
# תרחיש 2: שם לא ייחודי (שתי "רותם") -> בקשת הבהרה, לא ניחוש
# ============================================================

def test_scenario_2_ambiguous_name(treatment_catalog):
    print("\n" + "=" * 60)
    print("  תרחיש 2: שם לא ייחודי - שתי לקוחות בשם רותם")
    print("=" * 60)

    # שים לב: "987654325" (הת"ז של רותם כהן ב-seed_data.py האמיתי) לא
    # עוברת את בדיקת ספרת הביקורת של תעודת זהות ישראלית - ראו TEST_REPORT.md.
    # כאן משתמשים בת"ז תקינה כדי שתרחיש ההבהרה עצמו לא ייכשל מסיבה לא קשורה.
    rotem_cohen = create_client_with_id("רותם כהן", "0532345678", "888888880")
    create_client_with_id("רותם לוי", "0539876543", "222222226")

    conversation = ConversationState("scenario-2")

    reply = say(conversation, "קוראים לי רותם")

    # לא מותר שהבוט ינחש לקוחה - חייב לעבור למצב הבהרה
    assert conversation.state == "disambiguating"
    assert conversation.candidate_client_id is None
    assert "רותם כהן" in reply and "רותם לוי" in reply

    reply2 = say(conversation, "רותם כהן")

    # אחרי מסירת השם המלא - הבהרה הצליחה ועברנו לבקשת ת"ז
    # של המועמדת הנכונה בדיוק, לא ניחוש אקראי מבין השתיים
    assert conversation.state == "awaiting_id"
    assert conversation.candidate_client_id == rotem_cohen.client_id
    assert "תעודת הזהות" in reply2

    print("\n  תוצאה: הבוט ביקש הבהרה במקום לנחש, ואז זיהה נכון. PASS")


# ============================================================
# תרחיש 3: ת"ז שגויה שלוש פעמים -> נעילה מנומסת בלי חשיפת פרטים
# ============================================================

def test_scenario_3_wrong_id_three_times_locks(treatment_catalog):
    print("\n" + "=" * 60)
    print("  תרחיש 3: תעודת זהות שגויה שלוש פעמים - נעילה")
    print("=" * 60)

    noa = create_client_with_id("נועה לוי", "0543456789", "111111118")

    conversation = ConversationState("scenario-3")

    say(conversation, "קוראים לי נועה לוי")
    assert conversation.state == "awaiting_id"
    assert conversation.candidate_client_id == noa.client_id

    reply1 = say(conversation, "111111111")
    assert conversation.state == "awaiting_id"
    assert conversation.id_attempts == 1
    assert "נותרו 2 ניסיונות" in reply1

    reply2 = say(conversation, "222222222")
    assert conversation.state == "awaiting_id"
    assert conversation.id_attempts == 2
    assert "נותרו 1 ניסיונות" in reply2

    reply3 = say(conversation, "333333333")
    assert conversation.state == "locked"
    assert conversation.id_attempts == 3

    # הודעת הנעילה מנומסת ולא חושפת שום פרט אישי של הלקוחה
    assert "נועה" not in reply3
    assert noa.phone not in reply3
    assert "חרגת ממספר הניסיונות" in reply3

    # השיחה נשארת נעולה - אין דרך חזרה בלי להתחיל מחדש
    reply4 = say(conversation, "111111118")  # אפילו הת"ז הנכונה עכשיו לא עוזרת
    assert conversation.state == "locked"
    assert "נועה" not in reply4

    print("\n  תוצאה: נעילה אחרי 3 ניסיונות כושלים, בלי דליפת פרטים. PASS")


# ============================================================
# תרחיש 4: לקוחה קיימת בלי אף תור
# ============================================================

def test_scenario_4_existing_client_no_appointments(treatment_catalog, monkeypatch):
    print("\n" + "=" * 60)
    print("  תרחיש 4: לקוחה קיימת שאין לה אף תור")
    print("=" * 60)

    captured = {}
    original_generate = otp.generate_code

    def capturing_generate(length=None):
        code = original_generate(length)
        captured["code"] = code
        return code

    monkeypatch.setattr(otp, "generate_code", capturing_generate)

    shira = create_client_with_id("שירה דהן", "0546789012", "444444442")

    conversation = ConversationState("scenario-4")

    say(conversation, "קוראים לי שירה דהן")
    say(conversation, "444444442")
    assert conversation.state == "awaiting_otp"

    code = captured.get("code")
    final_reply = say(conversation, code)

    assert conversation.state == "verified"
    assert "לא מצאתי תורים פתוחים" in final_reply
    assert shira.full_name in final_reply

    print("\n  תוצאה: הבוט דיווח נכון שאין תורים פתוחים. PASS")


# ============================================================
# תרחיש 5: שם שלא קיים במערכת
# ============================================================

def test_scenario_5_unknown_name():
    print("\n" + "=" * 60)
    print("  תרחיש 5: שם שלא קיים במערכת")
    print("=" * 60)

    conversation = ConversationState("scenario-5")

    reply = say(conversation, "קוראים לי אבישי כהן")

    assert conversation.state == "identifying"
    assert conversation.candidate_client_id is None
    assert "לא מצאתי" in reply
    assert "אבישי כהן" in reply

    print("\n  תוצאה: הבוט דיווח שלא נמצאה לקוחה בשם הזה. PASS")


if __name__ == "__main__":
    # מאפשר הרצה כסקריפט עצמאי, בדיוק כמו tests/test_chat_flow.py הקיים.
    # משתמש בפיקסצ'רים מ-conftest.py ישירות, בלי pytest.
    import conftest

    def _run(test_function, needs_treatments=False, needs_monkeypatch=False):
        conftest._reset_database()
        from chatbot.state import conversation_store
        conversation_store._conversations.clear()

        kwargs = {}
        if needs_treatments:
            from managers.treatment_manager import TreatmentManager
            manager = TreatmentManager()
            manager.seed_catalog()
            kwargs["treatment_catalog"] = manager.get_all_treatments()

        if needs_monkeypatch:
            import pytest as _pytest
            with _pytest.MonkeyPatch.context() as mp:
                kwargs["monkeypatch"] = mp
                test_function(**kwargs)
        else:
            test_function(**kwargs)

    _run(test_scenario_1_unique_name_wrong_date, needs_treatments=True, needs_monkeypatch=True)
    _run(test_scenario_2_ambiguous_name, needs_treatments=True)
    _run(test_scenario_3_wrong_id_three_times_locks, needs_treatments=True)
    _run(test_scenario_4_existing_client_no_appointments, needs_treatments=True, needs_monkeypatch=True)
    _run(test_scenario_5_unknown_name)

    print("\n" + "=" * 60)
    print("  כל חמשת התרחישים עברו בהצלחה")
    print("=" * 60)
