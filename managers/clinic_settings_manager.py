# ============================================================
# managers/clinic_settings_manager.py
# גישה מוקלדת ל-clinic_settings (migrations/008). value תמיד TEXT
# בטבלה עצמה - כל שאר הקוד צריך int/bool/רשימה, לא מחרוזת, ולכן
# ההמרה מרוכזת כאן פעם אחת ולא ב-strip/int() מפוזר בכל קורא.
# ============================================================

from db import get_session
from models import ClinicSetting


class ClinicSettingsManager:
    def __init__(self):
        self.last_error = None

    @property
    def session(self):
        return get_session()

    def get_raw(self, key, default=None):
        row = self.session.get(ClinicSetting, key)
        return row.value if row is not None else default

    def get_int(self, key, default=None):
        value = self.get_raw(key)
        if value is None:
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def get_str(self, key, default=None):
        value = self.get_raw(key)
        return value if value is not None else default

    def get_bool(self, key, default=False):
        value = self.get_raw(key)
        if value is None:
            return default
        return str(value).strip().lower() in ("1", "true", "yes", "on")

    def get_working_days(self, default=(0, 1, 2, 3, 4)):
        """מחזיר set של ימים (0=שני...6=ראשון, ראו utils/datetime_utils.day_of_week)."""
        raw = self.get_raw("working_days")
        if not raw:
            return set(default)
        try:
            return {int(part.strip()) for part in raw.split(",") if part.strip() != ""}
        except ValueError:
            return set(default)

    def set_value(self, key, value):
        """נוצר עבור מסך ההגדרות (Release 2, שלב P1) - לא בשימוש עדיין ב-P0."""
        from utils.datetime_utils import now_jerusalem

        row = self.session.get(ClinicSetting, key)
        if row is None:
            row = ClinicSetting(key=key)
            self.session.add(row)

        row.value = str(value)
        row.updated_at = now_jerusalem().isoformat()
        self.session.commit()
        return True
