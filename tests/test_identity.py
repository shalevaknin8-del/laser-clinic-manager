# ============================================================
# tests/test_identity.py
# identity/ - שכבת הזהות המאוחדת (Release 2, Principle 1).
#
# הרצה:  python3 -m pytest tests/test_identity.py -v
# ============================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from conftest import create_client_with_id  # noqa: E402

from identity.verification import (  # noqa: E402
    RESULT_OK,
    RESULT_WRONG,
    RESULT_NO_DATA,
    PURPOSE_CHATBOT_IDENTITY,
    PURPOSE_PORTAL_LOGIN,
    check_national_id,
    find_client_by_phone,
    send_otp,
    confirm_otp,
)
from identity.tokens import (  # noqa: E402
    create_portal_token_pair,
    decode_portal_token,
    bump_client_token_version,
    TOKEN_TYPE_PORTAL_ACCESS,
    TOKEN_TYPE_PORTAL_REFRESH,
)
from auth.jwt_utils import create_access_token, TokenError  # noqa: E402
from db import get_session  # noqa: E402
from utils import otp as otp_module  # noqa: E402


def _capture_otp_code(monkeypatch):
    """מלכדת את קוד ה-OTP שנוצר, בלי לשנות את קוד הייצור - כמו tests/test_chat_flow.py."""
    captured = {}
    original_generate = otp_module.generate_code

    def capturing_generate(length=None):
        code = original_generate(length)
        captured["code"] = code
        return code

    monkeypatch.setattr(otp_module, "generate_code", capturing_generate)
    return captured


# ============================================================
# find_client_by_phone - זיהוי הפורטל
# ============================================================

def test_find_client_by_phone_matches_normalized_number():
    client_obj = create_client_with_id("לקוחת פורטל", "0501234567", "123456782")
    found = find_client_by_phone("0501234567")
    assert found is not None
    assert found.client_id == client_obj.client_id


def test_find_client_by_phone_matches_alternate_formatting():
    """
    לקוחה קיימת חייבת להימצא גם כשהיא מקלידה את הטלפון שלה
    בפורמט שונה מזה שנשמר - זה בדיוק מה שמיגרציית הנרמול (005) פתרה.
    """
    create_client_with_id("לקוחת פורמט", "0507654321", "123456782")
    found = find_client_by_phone("050-765-4321")
    assert found is not None
    assert found.phone == "0507654321"


def test_find_client_by_phone_returns_none_for_unknown_number():
    assert find_client_by_phone("0509999999") is None


def test_find_client_by_phone_returns_none_for_garbage_input():
    assert find_client_by_phone("not-a-phone") is None


# ============================================================
# check_national_id - שלב אימות א' של הצ'אטבוט
# ============================================================

def test_check_national_id_correct():
    client_obj = create_client_with_id("לקוחת תז", "0500000001", "123456782")
    assert check_national_id(client_obj.client_id, "123456782") is True


def test_check_national_id_wrong():
    client_obj = create_client_with_id("לקוחת תז", "0500000002", "123456782")
    assert check_national_id(client_obj.client_id, "000000000") is False


def test_check_national_id_none_client_id():
    assert check_national_id(None, "123456782") is False


# ============================================================
# send_otp / confirm_otp - משותף לשתי שיטות הכניסה
# ============================================================

def test_send_and_confirm_otp_round_trip(monkeypatch):
    client_obj = create_client_with_id("לקוחת אוטפי", "0500000003", "123456782")
    captured = _capture_otp_code(monkeypatch)

    result, masked = send_otp(client_obj.client_id, purpose=PURPOSE_PORTAL_LOGIN)
    assert result == RESULT_OK
    assert masked == "***0003"

    confirm_result, reason = confirm_otp(client_obj.client_id, captured["code"],
                                          purpose=PURPOSE_PORTAL_LOGIN)
    assert confirm_result == RESULT_OK
    assert reason == "ok"


def test_confirm_otp_wrong_code(monkeypatch):
    client_obj = create_client_with_id("לקוחת אוטפי", "0500000004", "123456782")
    _capture_otp_code(monkeypatch)

    send_otp(client_obj.client_id, purpose=PURPOSE_PORTAL_LOGIN)
    result, _reason = confirm_otp(client_obj.client_id, "000000", purpose=PURPOSE_PORTAL_LOGIN)
    assert result == RESULT_WRONG


def test_otp_purpose_is_isolated_between_chatbot_and_portal(monkeypatch):
    """
    קוד שנשלח לזרימת הפורטל לא יכול להתממש בזרימת הצ'אטבוט, גם עם
    אותה לקוחה בדיוק ובאותו רגע - שתי הזרימות משתמשות ב-purpose שונה.
    """
    client_obj = create_client_with_id("לקוחת פרפוז", "0500000005", "123456782")
    captured = _capture_otp_code(monkeypatch)

    send_otp(client_obj.client_id, purpose=PURPOSE_PORTAL_LOGIN)
    result, _reason = confirm_otp(client_obj.client_id, captured["code"],
                                   purpose=PURPOSE_CHATBOT_IDENTITY)
    assert result == RESULT_WRONG


def test_send_otp_no_data_for_unknown_client():
    result, masked = send_otp(999999, purpose=PURPOSE_PORTAL_LOGIN)
    assert result == RESULT_NO_DATA
    assert masked is None


# ============================================================
# identity/tokens.py - JWT נפרד לגמרי מהצוות
# ============================================================

def test_portal_token_round_trip():
    client_obj = create_client_with_id("לקוחת טוקן", "0500000006", "123456782")

    access_token, refresh_token = create_portal_token_pair(client_obj)

    access_payload = decode_portal_token(access_token, expected_type=TOKEN_TYPE_PORTAL_ACCESS)
    assert access_payload["sub"] == str(client_obj.client_id)

    refresh_payload = decode_portal_token(refresh_token, expected_type=TOKEN_TYPE_PORTAL_REFRESH)
    assert refresh_payload["token_version"] == 0


def test_staff_token_rejected_by_portal_decoder():
    """
    הבדיקה הקריטית: טוקן שהונפק למשתמשת צוות (auth/jwt_utils) לעולם
    לא יתקבל כטוקן פורטל, גם אם מישהו ינסה להעביר אותו בכוונה -
    ה-'type' שונה לגמרי (access מול portal_access).
    """
    class _FakeUser:
        user_id = 1
        role = "employee"

    staff_token = create_access_token(_FakeUser())

    try:
        decode_portal_token(staff_token, expected_type=TOKEN_TYPE_PORTAL_ACCESS)
        assert False, "צריך היה להיכשל - זה טוקן צוות, לא טוקן פורטל"
    except TokenError:
        pass


def test_bump_client_token_version_invalidates_and_persists():
    client_obj = create_client_with_id("לקוחת ניתוק", "0500000007", "123456782")
    session = get_session()

    bump_client_token_version(client_obj, session)
    assert client_obj.token_version == 1

    reloaded = session.get(type(client_obj), client_obj.client_id)
    assert reloaded.token_version == 1
