# ============================================================
# tests/test_datetime_utils.py
# utils/datetime_utils.py - נורמליזציית זמן עם אזור זמן מפורש.
#
# הרצה:  python3 -m pytest tests/test_datetime_utils.py -v
# ============================================================

import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils.datetime_utils import (  # noqa: E402
    combine_local,
    to_date_str,
    to_time_str,
    parse_date_str,
    parse_time_str,
    day_of_week,
    is_in_past,
    hours_until,
    add_minutes,
    expires_at_iso,
    has_expired,
    now_jerusalem,
)


# ============================================================
# המרות בסיסיות
# ============================================================

def test_combine_local_is_timezone_aware():
    result = combine_local("2026-01-19", "14:00")
    assert result.tzinfo is not None
    assert result.hour == 14 and result.minute == 0


def test_to_date_str_and_to_time_str_round_trip():
    combined = combine_local("2026-01-19", "14:30")
    assert to_date_str(combined) == "2026-01-19"
    assert to_time_str(combined) == "14:30"


def test_parse_date_and_time_str():
    assert parse_date_str("2026-01-19").isoformat() == "2026-01-19"
    assert parse_time_str("14:30").strftime("%H:%M") == "14:30"


# ============================================================
# יום בשבוע - עקבי עם המוסכמה הקיימת (StaffAvailability): 0=שני...6=ראשון
# ============================================================

def test_day_of_week_matches_existing_convention():
    # 2026-01-19 הוא יום שני
    assert day_of_week("2026-01-19") == 0
    # 2026-01-25 הוא יום ראשון
    assert day_of_week("2026-01-25") == 6


# ============================================================
# עבר/עתיד ו-hours_until
# ============================================================

def test_is_in_past_for_past_date():
    assert is_in_past("2020-01-01", "09:00") is True


def test_is_in_past_for_far_future_date():
    assert is_in_past("2099-01-01", "09:00") is False


def test_hours_until_is_positive_for_future():
    assert hours_until("2099-01-01", "09:00") > 0


def test_hours_until_is_negative_for_past():
    assert hours_until("2020-01-01", "09:00") < 0


def test_hours_until_roughly_correct_magnitude():
    future = now_jerusalem() + timedelta(hours=5)
    hours = hours_until(to_date_str(future), to_time_str(future))
    # מדויק לדקה, לא לשנייה (to_time_str מאבד שניות) - לכן טווח סבילות קטן
    assert 4.98 <= hours <= 5.02


# ============================================================
# חשבון תאריך/שעה
# ============================================================

def test_add_minutes_within_same_day():
    date_str, time_str = add_minutes("2026-01-19", "13:50", 10)
    assert (date_str, time_str) == ("2026-01-19", "14:00")


def test_add_minutes_crosses_midnight():
    date_str, time_str = add_minutes("2026-01-19", "23:50", 20)
    assert (date_str, time_str) == ("2026-01-20", "00:10")


# ============================================================
# תפוגה (slot_reservations, otp_codes)
# ============================================================

def test_expires_at_iso_not_yet_expired():
    future_iso = expires_at_iso(10)
    assert has_expired(future_iso) is False


def test_has_expired_for_past_timestamp():
    past_iso = expires_at_iso(-10)
    assert has_expired(past_iso) is True


def test_has_expired_tolerates_naive_iso_string():
    """
    חותמות תפוגה ישנות (לפני המעבר למודול הזה) עשויות להישמר בלי
    אזור זמן. מפורשות כזמן מקומי ישראלי כדי לא לשבור אותן.
    """
    naive_future = (now_jerusalem().replace(tzinfo=None) + timedelta(minutes=10)).isoformat()
    assert has_expired(naive_future) is False

    naive_past = (now_jerusalem().replace(tzinfo=None) - timedelta(minutes=10)).isoformat()
    assert has_expired(naive_past) is True


# ============================================================
# מודעות לאזור זמן - הסיבה שהמודול הזה קיים בכלל (Migration 008/009 במפרט)
# ============================================================

def test_utc_offset_differs_between_summer_and_winter():
    """
    ישראל: שעון קיץ (IDT, UTC+3) מול שעון חורף (IST, UTC+2).
    זו בדיוק הבדיקה שהייתה חסרה לפני המודול הזה - חישוב זמן נאיבי
    (בלי אזור זמן) לא היה מבחין בין השניים בכלל.
    """
    summer = combine_local("2026-07-01", "12:00")
    winter = combine_local("2026-01-01", "12:00")

    assert summer.utcoffset() == timedelta(hours=3)
    assert winter.utcoffset() == timedelta(hours=2)
