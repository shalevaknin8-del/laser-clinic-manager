# ============================================================
# managers/room_manager.py
# ניהול חדרי הטיפול - משאב ראשון מתוך שלושה באילוץ הזימון החכם
# (חדר + מכשיר + עובדת). קטלוג קטן ופשוט בכוונה - קליניקה בגודל
# הזה לא צריכה יותר מכמה חדרים, אין צורך בטקסונומיה מורכבת.
# ============================================================

from db import get_session
from models import Room


class RoomManager:
    def __init__(self):
        self.last_error = None

    @property
    def session(self):
        return get_session()

    def create_room(self, name):
        if not name or not str(name).strip():
            self.last_error = "יש להזין שם לחדר"
            return None

        room = Room(name=str(name).strip(), is_active=True)
        self.session.add(room)
        self.session.commit()
        return room

    def get_room_by_id(self, room_id):
        return self.session.get(Room, room_id)

    def get_all_rooms(self, include_inactive=True):
        query = self.session.query(Room)
        if not include_inactive:
            query = query.filter_by(is_active=True)
        return query.order_by(Room.name).all()

    def set_active(self, room_id, is_active):
        room = self.get_room_by_id(room_id)
        if room is None:
            self.last_error = "החדר לא נמצא"
            return False
        room.is_active = bool(is_active)
        self.session.commit()
        return True
