# ============================================================
# tests/test_portal_api.py
# api/portal_api.py - Part 9 במפרט, מקצה לקצה דרך Flask test_client.
#
# הרצה:  python3 -m pytest tests/test_portal_api.py -v
# ============================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from conftest import (  # noqa: E402
    create_client_with_id, create_user, login_as,
    future_date_str, setup_one_room_one_machine_one_staff, capture_otp_code,
)

from managers.treatment_manager import TreatmentManager  # noqa: E402


def _first_treatment_id():
    return TreatmentManager().get_all_treatments()[0].treatment_id


def _identify_and_capture_code(test_client, monkeypatch, full_name, phone):
    captured = capture_otp_code(monkeypatch)
    response = test_client.post("/api/portal/identify",
                                 json={"full_name": full_name, "phone": phone})
    return response, captured


def _verify(test_client, phone, code):
    return test_client.post("/api/portal/verify", json={"phone": phone, "code": code})


def _auth_headers(access_token):
    return {"Authorization": f"Bearer {access_token}"}


# ============================================================
# /identify - חייב תשובה זהה-בייט קיים/לא-קיים (Part 4 Step 1)
# ============================================================

def test_identify_response_shape_identical_for_existing_and_new_phone(client, monkeypatch,
                                                                        treatment_catalog):
    create_client_with_id("לקוחה קיימת", "0509990001", "123456782")

    response_existing, _ = _identify_and_capture_code(client, monkeypatch, "מישהי",
                                                        "0509990001")
    response_new, _ = _identify_and_capture_code(client, monkeypatch, "לקוחה חדשה",
                                                   "0509990002")

    assert response_existing.status_code == response_new.status_code == 200
    body_existing = response_existing.get_json()
    body_new = response_new.get_json()
    assert set(body_existing.keys()) == set(body_new.keys()) == {"success", "masked_destination"}
    assert body_existing["success"] is True and body_new["success"] is True
    # שני המספרים בני 10 ספרות - אותו אורך מיסוך בדיוק (***XXXX)
    assert body_existing["masked_destination"] == "***0001"
    assert body_new["masked_destination"] == "***0002"


def test_identify_rejects_invalid_phone_shape(client):
    response = client.post("/api/portal/identify",
                            json={"full_name": "מישהי", "phone": "abc"})
    assert response.status_code == 400


# ============================================================
# זרימה מלאה - לקוחה חדשה
# ============================================================

def test_full_new_client_flow(client, monkeypatch, treatment_catalog):
    setup_one_room_one_machine_one_staff()
    phone = "0509990010"

    _, captured = _identify_and_capture_code(client, monkeypatch, "לקוחה חדשה לגמרי", phone)
    verify_response = _verify(client, phone, captured["code"])
    assert verify_response.status_code == 200
    verify_body = verify_response.get_json()
    assert verify_body["is_new"] is True
    access_token = verify_body["access_token"]

    # לפני השלמת הרשמה - עדיין אפשר לגשת ל-treatments (לא חסום)
    treatments_response = client.get("/api/portal/treatments", headers=_auth_headers(access_token))
    assert treatments_response.status_code == 200
    treatment_id = treatments_response.get_json()["treatments"][0]["treatment_id"]

    register_response = client.post(
        "/api/portal/register",
        json={"full_name": "לקוחה חדשה לגמרי", "email": "new@example.com"},
        headers=_auth_headers(access_token),
    )
    assert register_response.status_code == 200
    assert register_response.get_json()["client"]["email"] == "new@example.com"

    # הרשמה שנייה חייבת להיכשל - כבר הושלמה
    second_register = client.post("/api/portal/register", json={},
                                   headers=_auth_headers(access_token))
    assert second_register.status_code == 400

    date_str = future_date_str()
    availability_response = client.get(
        f"/api/portal/availability?date_from={date_str}&date_to={date_str}"
        f"&treatment_ids={treatment_id}",
        headers=_auth_headers(access_token),
    )
    assert availability_response.status_code == 200
    slots = availability_response.get_json()["days"][0]["slots"]
    assert "09:00" in slots

    reserve_response = client.post(
        "/api/portal/reserve",
        json={"appointment_date": date_str, "appointment_time": "09:00",
              "treatment_ids": [treatment_id]},
        headers=_auth_headers(access_token),
    )
    assert reserve_response.status_code == 200
    reservation_id = reserve_response.get_json()["reservation_id"]

    book_response = client.post("/api/portal/book", json={"reservation_id": reservation_id},
                                 headers=_auth_headers(access_token))
    assert book_response.status_code == 200
    appointment = book_response.get_json()["appointment"]
    assert appointment["approval_status"] == "pending_approval"

    appointments_response = client.get("/api/portal/appointments",
                                        headers=_auth_headers(access_token))
    assert len(appointments_response.get_json()["appointments"]) == 1

    history_response = client.get("/api/portal/history", headers=_auth_headers(access_token))
    assert len(history_response.get_json()["appointments"]) == 1

    logout_response = client.post("/api/portal/logout", headers=_auth_headers(access_token))
    assert logout_response.status_code == 200


# ============================================================
# זרימה מלאה - לקוחה קיימת (בלי /register)
# ============================================================

def test_full_existing_client_flow_skips_registration(client, monkeypatch, treatment_catalog):
    setup_one_room_one_machine_one_staff()
    existing = create_client_with_id("לקוחה ותיקה", "0509990020", "123456782")

    _, captured = _identify_and_capture_code(client, monkeypatch, "לקוחה ותיקה", "0509990020")
    verify_response = _verify(client, "0509990020", captured["code"])
    verify_body = verify_response.get_json()
    assert verify_body["is_new"] is False
    access_token = verify_body["access_token"]

    me_response = client.get("/api/portal/me", headers=_auth_headers(access_token))
    assert me_response.get_json()["client"]["client_id"] == existing.client_id

    # מנסה להירשם בכל זאת - חייב להיכשל, הפרופיל כבר מלא
    register_response = client.post("/api/portal/register", json={},
                                     headers=_auth_headers(access_token))
    assert register_response.status_code == 400


def test_verify_wrong_code_and_unknown_phone_get_same_generic_error(client, monkeypatch,
                                                                      treatment_catalog):
    create_client_with_id("לקוחה", "0509990030", "123456782")
    _identify_and_capture_code(client, monkeypatch, "לקוחה", "0509990030")

    wrong_code_response = _verify(client, "0509990030", "000000")
    unknown_phone_response = _verify(client, "0509999999", "000000")

    assert wrong_code_response.status_code == unknown_phone_response.status_code == 401
    assert wrong_code_response.get_json()["error"] == unknown_phone_response.get_json()["error"]


# ============================================================
# הגנה - client_id תמיד מהטוקן, לעולם לא מ-URL (Part 8 סעיף 1)
# ============================================================

def test_protected_endpoints_reject_missing_token(client):
    for path, method in [
        ("/api/portal/me", "get"),
        ("/api/portal/history", "get"),
        ("/api/portal/treatments", "get"),
        ("/api/portal/appointments", "get"),
        ("/api/portal/logout", "post"),
        ("/api/portal/register", "post"),
        ("/api/portal/reserve", "post"),
        ("/api/portal/book", "post"),
    ]:
        response = getattr(client, method)(path, json={})
        assert response.status_code == 401, f"{path} היה צריך לדרוש אימות"


def test_staff_token_rejected_by_portal_endpoint(client):
    """טוקן צוות (auth/jwt_utils) לא נותן גישה לפורטל - סוגי טוקן שונים לגמרי."""
    create_user("0530009999", "עובדת", "Password123!", "admin")
    login_response = login_as(client, "0530009999", "Password123!")
    assert login_response.status_code == 200
    staff_access_token = login_response.get_json()["access_token"]

    response = client.get("/api/portal/me", headers=_auth_headers(staff_access_token))
    assert response.status_code == 401


def test_portal_token_rejected_by_staff_endpoint(client, monkeypatch, treatment_catalog):
    """ולהפך - טוקן פורטל לא נותן גישה לממשק הצוות."""
    create_client_with_id("לקוחה", "0509990040", "123456782")
    _, captured = _identify_and_capture_code(client, monkeypatch, "לקוחה", "0509990040")
    verify_body = _verify(client, "0509990040", captured["code"]).get_json()

    response = client.get("/api/auth/me", headers=_auth_headers(verify_body["access_token"]))
    assert response.status_code == 401


def test_availability_requires_all_params(client, monkeypatch, treatment_catalog):
    create_client_with_id("לקוחה", "0509990050", "123456782")
    _, captured = _identify_and_capture_code(client, monkeypatch, "לקוחה", "0509990050")
    access_token = _verify(client, "0509990050", captured["code"]).get_json()["access_token"]

    response = client.get("/api/portal/availability", headers=_auth_headers(access_token))
    assert response.status_code == 400
