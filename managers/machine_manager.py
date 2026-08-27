# ============================================================
# managers/machine_manager.py
# ניהול מכשירי הלייזר - משאב שני מתוך שלושה באילוץ הזימון החכם.
# machine_type הוא מחרוזת חופשית (לא טבלת enum) בכוונה - ראו
# models.Machine לנימוק המלא.
# ============================================================

from db import get_session
from models import Machine, Room


class MachineManager:
    def __init__(self):
        self.last_error = None

    @property
    def session(self):
        return get_session()

    def create_machine(self, name, model=None, machine_type=None, room_id=None):
        if not name or not str(name).strip():
            self.last_error = "יש להזין שם למכשיר"
            return None

        if room_id is not None and self.session.get(Room, room_id) is None:
            self.last_error = "החדר שנבחר לא נמצא"
            return None

        machine = Machine(
            name=str(name).strip(),
            model=model,
            machine_type=machine_type,
            room_id=room_id,
            is_active=True,
        )
        self.session.add(machine)
        self.session.commit()
        return machine

    def get_machine_by_id(self, machine_id):
        return self.session.get(Machine, machine_id)

    def get_all_machines(self, include_inactive=True):
        query = self.session.query(Machine)
        if not include_inactive:
            query = query.filter_by(is_active=True)
        return query.order_by(Machine.name).all()

    def set_active(self, machine_id, is_active):
        machine = self.get_machine_by_id(machine_id)
        if machine is None:
            self.last_error = "המכשיר לא נמצא"
            return False
        machine.is_active = bool(is_active)
        self.session.commit()
        return True

    def resolve_machine_id(self, treatment, requested_machine_id):
        """
        קובע איזה מכשיר לשייך לתור, בלי לחייב את הצד הקורא (ה-frontend)
        להציג בורר מכשיר כשיש בפועל רק אחד - זה בדיוק המצב הנוכחי
        של הקליניקה. כשיתווסף מכשיר שני, הבחירה המפורשת נדרשת
        אוטומטית, בלי שום שינוי קוד.

        מחזירה (machine_id, error_message):
          - נשלח machine_id מפורש -> מוודאים שהוא קיים ומחזירים כמו שהוא
          - לא נשלח, והטיפול לא דורש מכשיר (Treatment.requires_machine) -> None
          - לא נשלח, ויש מכשיר פעיל אחד בדיוק -> נבחר אוטומטית
          - לא נשלח, ויש כמה מכשירים פעילים -> שגיאה, חובה לבחור
          - לא נשלח, ואין אף מכשיר פעיל -> None (המכשיר עוד לא הוגדר
            במערכת; לא חוסמים קביעת תורים בגלל זה)
        """
        if requested_machine_id is not None:
            if self.get_machine_by_id(requested_machine_id) is None:
                return None, "המכשיר שנבחר לא נמצא"
            return requested_machine_id, None

        # getattr עם ברירת מחדל True בכוונה: TreatmentManager (עדיין
        # SQL גולמי, לא הוחלף בשלב 3) לא קורא את עמודת requires_machine
        # בכלל - ראו TEST_REPORT/README. ברירת המחדל תואמת את עמודת
        # ה-DB עצמה (NOT NULL DEFAULT 1, ראו migrations/004_orm_refactor.py)
        requires_machine = getattr(treatment, "requires_machine", True)
        if treatment is not None and not requires_machine:
            return None, None

        active_machines = self.get_all_machines(include_inactive=False)

        if len(active_machines) == 1:
            return active_machines[0].machine_id, None

        if len(active_machines) > 1:
            return None, "יש כמה מכשירים פעילים במערכת - יש לבחור מכשיר במפורש"

        return None, None
