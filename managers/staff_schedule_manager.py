# ============================================================
# managers/staff_schedule_manager.py
# זמינות עובדות - משאב שלישי באילוץ הזימון החכם (חדר+מכשיר+עובדת).
#
# שני מנגנונים נפרדים בכוונה, כדי לא לסבך תבנית אחת:
#   1. StaffAvailability - תבנית שבועית חוזרת ("ימי ג' 09:00-17:00")
#   2. StaffTimeOff      - חופשה/מחלה בטווח תאריכים ספציפי, בלי
#                          לגעת בתבנית השבועית
#
# day_of_week עקבי עם date.weekday() של פייתון: 0=שני ... 6=ראשון.
# ============================================================

from datetime import datetime

from db import get_session
from models import StaffAvailability, StaffTimeOff, User


class StaffScheduleManager:
    def __init__(self):
        self.last_error = None

    @property
    def session(self):
        return get_session()

    # ---------- תבנית שבועית ----------

    def add_availability(self, staff_user_id, day_of_week, start_time, end_time):
        if self.session.get(User, staff_user_id) is None:
            self.last_error = "העובדת לא נמצאה"
            return None

        if not (0 <= day_of_week <= 6):
            self.last_error = "יום בשבוע לא תקין (0-6)"
            return None

        if start_time >= end_time:
            self.last_error = "שעת ההתחלה חייבת להיות לפני שעת הסיום"
            return None

        slot = StaffAvailability(
            staff_user_id=staff_user_id,
            day_of_week=day_of_week,
            start_time=start_time,
            end_time=end_time,
        )
        self.session.add(slot)
        self.session.commit()
        return slot

    def get_availability_for_staff(self, staff_user_id):
        return (
            self.session.query(StaffAvailability)
            .filter_by(staff_user_id=staff_user_id)
            .order_by(StaffAvailability.day_of_week, StaffAvailability.start_time)
            .all()
        )

    def delete_availability(self, availability_id):
        slot = self.session.get(StaffAvailability, availability_id)
        if slot is None:
            self.last_error = "משבצת הזמינות לא נמצאה"
            return False
        self.session.delete(slot)
        self.session.commit()
        return True

    # ---------- חופשה / מחלה ----------

    def add_time_off(self, staff_user_id, start_date, end_date, reason=None):
        if self.session.get(User, staff_user_id) is None:
            self.last_error = "העובדת לא נמצאה"
            return None

        if start_date > end_date:
            self.last_error = "תאריך ההתחלה חייב להיות לפני תאריך הסיום"
            return None

        time_off = StaffTimeOff(
            staff_user_id=staff_user_id,
            start_date=start_date,
            end_date=end_date,
            reason=reason,
        )
        self.session.add(time_off)
        self.session.commit()
        return time_off

    def get_time_off_for_staff(self, staff_user_id):
        return (
            self.session.query(StaffTimeOff)
            .filter_by(staff_user_id=staff_user_id)
            .order_by(StaffTimeOff.start_date)
            .all()
        )

    def delete_time_off(self, time_off_id):
        time_off = self.session.get(StaffTimeOff, time_off_id)
        if time_off is None:
            self.last_error = "רשומת החופשה לא נמצאה"
            return False
        self.session.delete(time_off)
        self.session.commit()
        return True

    # ---------- הבדיקה עצמה ----------

    def is_staff_available(self, staff_user_id, appointment_date, start_time, end_time):
        """
        בודק אם עובדת פנויה לשיבוץ בטווח נתון ביום נתון.

        מחזיר (is_available, reason). reason מנוסח לתצוגה למשתמשת -
        לא מדליף מבנה פנימי, רק "לא בשעות העבודה" / "בחופשה".
        """
        if staff_user_id is None:
            return True, None  # לא נבחרה עובדת ספציפית - אין מה לבדוק

        on_time_off = (
            self.session.query(StaffTimeOff)
            .filter(
                StaffTimeOff.staff_user_id == staff_user_id,
                StaffTimeOff.start_date <= appointment_date,
                StaffTimeOff.end_date >= appointment_date,
            )
            .first()
        )
        if on_time_off is not None:
            return False, "העובדת בחופשה בתאריך המבוקש"

        day_of_week = datetime.strptime(appointment_date, "%Y-%m-%d").weekday()

        covering_slot = (
            self.session.query(StaffAvailability)
            .filter(
                StaffAvailability.staff_user_id == staff_user_id,
                StaffAvailability.day_of_week == day_of_week,
                StaffAvailability.start_time <= start_time,
                StaffAvailability.end_time >= end_time,
            )
            .first()
        )
        if covering_slot is None:
            return False, "העובדת לא עובדת בשעות המבוקשות"

        return True, None
