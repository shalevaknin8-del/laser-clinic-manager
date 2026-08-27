# ============================================================
# models.py
# שכבת ה-ORM (SQLAlchemy) של המערכת.
#
# אסטרטגיית מעבר: "Strangler Fig", לא Big Bang.
# הטבלאות הקיימות (clients, users, treatments, appointments,
# appointment_treatments, invoices, leads, otp_codes, audit_log)
# ממופות כאן עם אותם שמות טבלה ועמודות בדיוק כמו schema.sql +
# migrations/001-003 - שום דאטה קיים לא זז ולא מתפרש מחדש.
#
# תחומים שכבר עברו ל-ORM בפועל: User, Client (שלב 2), Appointment
# + AppointmentTreatment (שלב 3, Smart Scheduling + Packages).
# תחומים שעדיין עובדים מול database.get_connection() הגולמי:
# Invoice, Lead, Treatment-CRUD (treatments_api.py עצמו) - לא
# היה צורך לגעת בהם כדי לממש זימון חכם וחבילות. שתי הגישות
# עובדות זו לצד זו על אותו קובץ SQLite בדיוק, כי מדובר באותן
# טבלאות ממש.
#
# טבלאות חדשות לגמרי (rooms/machines/staff_availability/
# staff_time_off/packages/client_packages) נוצרות ע"י
# migrations/004_orm_refactor.py, ומיוצגות כאן כבר כמודלים
# מלאים כדי שהסכמה תהיה ברורה מראש לשלב 3.
# ============================================================

from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Date, Time,
    Text, ForeignKey, UniqueConstraint, Index,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ============================================================
# Auth / Staff
# ============================================================

class User(Base):
    """
    עובדת/מנהלת מערכת. מזוהה בהתחברות לפי טלפון (כמו קודם) -
    JWT לא דורש שינוי במזהה ההתחברות, רק בדרך שבה ה-session מיוצג.
    """
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True)
    phone = Column(String, nullable=False, unique=True)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(String, nullable=False, default="employee")
    is_active = Column(Integer, nullable=False, default=1)
    failed_attempts = Column(Integer, nullable=False, default=0)
    locked_until = Column(String)
    last_login_at = Column(String)
    password_changed_at = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # מונה גרסת ה-refresh token. JWT הוא stateless - אין טבלת
    # session שאפשר למחוק ממנה כדי "לנתק" משתמשת. העלאת המספר
    # הזה (בשינוי סיסמה, או בניתוק יזום) הופכת אוטומטית כל
    # refresh token ישן ללא-תקף, בלי צורך ברשימת חסימה (blacklist).
    token_version = Column(Integer, nullable=False, default=0)

    availability_slots = relationship("StaffAvailability", back_populates="staff")
    time_off_periods = relationship("StaffTimeOff", back_populates="staff")

    def is_admin(self):
        return self.role == "admin"

    def is_locked(self):
        """נעילה זמנית עקב ניסיונות כושלים - מתפוגגת מעצמה, ראו user_manager.py."""
        if not self.locked_until:
            return False
        return datetime.now() < datetime.fromisoformat(self.locked_until)

    def can_login(self):
        return bool(self.is_active) and not self.is_locked()

    def role_label(self):
        from entities.user import ROLE_LABELS
        return ROLE_LABELS.get(self.role, self.role)


# ============================================================
# לקוחות
# ============================================================

class Client(Base):
    __tablename__ = "clients"

    client_id = Column(Integer, primary_key=True)
    full_name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    email = Column(String)
    address = Column(String)
    national_id_hash = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # הצהרת בריאות חתומה - ללא DocuSign, ללא S3.
    # הקובץ נשמר מקומית תחת תיקייה מוגנת (לא static/), ונגיש רק
    # דרך endpoint מאומת (api/clients_api.py) - לא URL ציבורי ישיר.
    has_signed_health_declaration = Column(Boolean, nullable=False, default=False)
    health_declaration_file_path = Column(String, nullable=True)

    # Release 2 - session הפורטל (migrations/012_client_token_version.py).
    # אותו עיקרון בדיוק כמו User.token_version: מאפשר לבטל refresh
    # token של לקוחה (logout יזום) בלי טבלת session נפרדת - ראו identity/tokens.py
    token_version = Column(Integer, nullable=False, default=0)

    # Release 2 - הרשמה עצמית בפורטל (migrations/013). NULL = "שלד"
    # שנוצר ע"י identity.identify_or_create_shell עבור טלפון חדש,
    # וממתין להשלמת /register (Part 4 Step 3 במפרט).
    #
    # בכוונה בלי Column(default=...): ב-SQLAlchemy default חל בכל
    # פעם שהערך הוא None בזמן ה-flush, גם אם הוא הועבר במפורש
    # (אין הבחנה אמיתית בין "לא צוין" ל"הוגדר במפורש ל-None") -
    # לכן במקום זאת, ClientManager.insert_client (מסלול היצירה
    # ה"רגיל" - טופס הצוות, בדיקות) מציין את הערך במפורש כ-"now".
    # identify_or_create_shell עוקף את ClientManager בכוונה ובונה
    # Client ישירות, כדי שהשלד יישאר NULL - ראו migrations/013 לבאקפיל
    profile_completed_at = Column(String, nullable=True)

    packages = relationship("ClientPackage", back_populates="client")


# ============================================================
# משאבי זימון - חדשים לגמרי (שלב 3 ישתמש בהם בפועל)
# ============================================================

class Room(Base):
    __tablename__ = "rooms"

    room_id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)

    machines = relationship("Machine", back_populates="room")


class Machine(Base):
    """
    מכשיר לייזר. machine_type הוא מחרוזת חופשית ולא טבלת enum
    נפרדת בכוונה - קליניקה אחת עם כמה מכשירים לא צריכה טקסונומיה
    מלאה, רק תיוג פשוט להתאמה מול Treatment.default_machine_type.
    """
    __tablename__ = "machines"

    machine_id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    model = Column(String)
    machine_type = Column(String)
    is_active = Column(Boolean, nullable=False, default=True)
    room_id = Column(Integer, ForeignKey("rooms.room_id"), nullable=True)

    room = relationship("Room", back_populates="machines")


class StaffAvailability(Base):
    """
    תבנית שבועית חוזרת בלבד (v1) - "יום ג' 09:00-17:00".
    בכוונה בלי טבלת חריגות מורכבת: 3 עובדות בקליניקה אחת לא
    צריכות מנוע זמינות מלא, רק מסך "שעות עבודה" + חופשות בודדות
    (ראו StaffTimeOff למטה לכיסוי חופשה/מחלה בלי לסבך את התבנית).
    """
    __tablename__ = "staff_availability"

    availability_id = Column(Integer, primary_key=True)
    staff_user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    day_of_week = Column(Integer, nullable=False)  # 0=שני ... 6=ראשון, עקבי עם date.weekday()
    start_time = Column(String, nullable=False)    # "HH:MM", כמו appointment_time בשאר המערכת
    end_time = Column(String, nullable=False)

    staff = relationship("User", back_populates="availability_slots")


class StaffTimeOff(Base):
    """חופשה/מחלה של עובדת בטווח תאריכים - חוסמת שיבוץ בלי לגעת בתבנית השבועית."""
    __tablename__ = "staff_time_off"

    time_off_id = Column(Integer, primary_key=True)
    staff_user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    start_date = Column(String, nullable=False)  # "YYYY-MM-DD"
    end_date = Column(String, nullable=False)
    reason = Column(String)

    staff = relationship("User", back_populates="time_off_periods")


# ============================================================
# קטלוג טיפולים וחבילות
# ============================================================

class Treatment(Base):
    __tablename__ = "treatments"

    treatment_id = Column(Integer, primary_key=True)
    treatment_name = Column(String, nullable=False)
    body_area = Column(String)
    price = Column(Float, nullable=False)
    duration_minutes = Column(Integer, nullable=False)

    # לא כל טיפול צריך מכשיר לייזר (למשל ייעוץ) - ברירת מחדל
    # שמרנית: True, כדי שלא "נשכח" לשריין מכשיר לטיפול שכן צריך אחד
    requires_machine = Column(Boolean, nullable=False, default=True)
    default_machine_type = Column(String, nullable=True)

    packages = relationship("Package", back_populates="treatment")


class Package(Base):
    """
    חבילת טיפולים = N מפגשים של טיפול *אחד*.
    בכוונה לא חבילות מעורבות (כמה טיפולים שונים) ב-v1 - בקליניקה
    בגודל הזה חבילה כמעט תמיד "10 טיפולי רגליים", לא שילוב מוצרים.
    """
    __tablename__ = "packages"

    package_id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    treatment_id = Column(Integer, ForeignKey("treatments.treatment_id"), nullable=False)
    total_sessions = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)

    treatment = relationship("Treatment", back_populates="packages")


class ClientPackage(Base):
    """חבילה שנרכשה ע\"י לקוחה ספציפית, עם מונה מפגשים שנותרו."""
    __tablename__ = "client_packages"

    client_package_id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.client_id"), nullable=False)
    package_id = Column(Integer, ForeignKey("packages.package_id"), nullable=False)
    sessions_remaining = Column(Integer, nullable=False)
    purchased_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, nullable=False, default=True)

    client = relationship("Client", back_populates="packages")
    package = relationship("Package")


# ============================================================
# תורים - עברו ל-ORM בשלב 3, כולל אילוץ ה-3-way (חדר+מכשיר+עובדת).
# invoices/leads עדיין על database.get_connection() הגולמי -
# שום דבר בשלב 3 לא נגע בהם.
# ============================================================

class Appointment(Base):
    __tablename__ = "appointments"

    appointment_id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.client_id"), nullable=False)
    treatment_id = Column(Integer, ForeignKey("treatments.treatment_id"), nullable=False)
    appointment_date = Column(String, nullable=False)
    appointment_time = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")
    notes = Column(Text)

    # 3-way constraint: חדר + מכשיר + עובדת. שלושתם nullable כי
    # לא כל תור צריך את כולם (למשל טיפול בלי מכשיר, ראו
    # Treatment.requires_machine) - האכיפה בפועל ב-appointment_manager.py
    room_id = Column(Integer, ForeignKey("rooms.room_id"), nullable=True)
    machine_id = Column(Integer, ForeignKey("machines.machine_id"), nullable=True)
    staff_user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    client_package_id = Column(Integer, ForeignKey("client_packages.client_package_id"), nullable=True)

    # Release 2 - מקור התור וסגירתו (migrations/006_extend_appointments.py).
    # staff = נקבע ע"י צוות (ברירת המחדל, גם לתורים ישנים), portal/chatbot = לקוחה עצמה
    source = Column(String, nullable=False, default="staff")
    created_by_user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    cancelled_at = Column(String, nullable=True)
    cancelled_by = Column(String, nullable=True)  # client | staff | system
    reminder_sent_at = Column(String, nullable=True)

    # Release 2 - זרימת אישור (migrations/010_approval_workflow.py).
    # נפרד לגמרי מ-status הקיים: status ממשיך לעקוב אחרי pending/completed/cancelled
    # בדיוק כמו קודם, approval_status עוקב רק אחרי שלב האישור של תורי פורטל/צ'אטבוט.
    # תור שנוצר ע"י צוות מאושר מיידית (booking_service קובע זאת בקוד, לא כברירת מחדל כאן).
    approval_status = Column(String, nullable=False, default="pending_approval")
    approved_by_user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    approved_at = Column(String, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    approval_expires_at = Column(String, nullable=True)

    __table_args__ = (
        Index("ix_appointments_approval", "approval_status", "approval_expires_at"),
        Index("ux_appt_staff_slot", "staff_user_id", "appointment_date", "appointment_time",
              unique=True, sqlite_where=(status != "cancelled")),
        Index("ux_appt_room_slot", "room_id", "appointment_date", "appointment_time",
              unique=True, sqlite_where=(status != "cancelled")),
        Index("ux_appt_machine_slot", "machine_id", "appointment_date", "appointment_time",
              unique=True, sqlite_where=(status != "cancelled")),
    )


class AppointmentTreatment(Base):
    """
    קישור many-to-many בין תור לטיפולים - "טיפול מרוכב" (למשל שפם
    + סנטר באותו ביקור). מפתח ראשי מורכב, בדיוק כמו שהטבלה
    הוגדרה במקור ב-AppointmentTreatmentManager.ensure_table().
    """
    __tablename__ = "appointment_treatments"

    appointment_id = Column(
        Integer, ForeignKey("appointments.appointment_id", ondelete="CASCADE"),
        primary_key=True,
    )
    treatment_id = Column(Integer, ForeignKey("treatments.treatment_id"), primary_key=True)


# ============================================================
# Release 2 - הזמנה עצמית (פורטל + צ'אטבוט)
# טבלאות חדשות לגמרי, נוצרות ע"י migrations/005/007/008.
# ============================================================

class SlotReservation(Base):
    """
    שריון זמני של סלוט (10 דקות) בזמן שהלקוחה בוחרת ומאשרת -
    שכבה 1 מתוך 3 של ההגנה מפני double-booking (ראו services/availability_service.py).
    לא תור אמיתי - נמחקת/מתעלמים ממנה בפקיעה, ולא משפיעה על appointments.
    """
    __tablename__ = "slot_reservations"

    reservation_id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.client_id"), nullable=False)
    appointment_date = Column(String, nullable=False)
    appointment_time = Column(String, nullable=False)
    treatment_ids = Column(Text, nullable=False)  # JSON array, למשל "[1, 4]"
    expires_at = Column(String, nullable=False)
    is_confirmed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_slot_reservations_lookup", "appointment_date", "appointment_time", "expires_at"),
    )


class NotificationLog(Base):
    """
    יומן כל הודעה שנשלחה/נכשלה - מונע שליחה כפולה (בעיקר תזכורות)
    ומאפשר חקירה כשלקוחה טוענת שלא קיבלה הודעה.
    """
    __tablename__ = "notification_log"

    log_id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.client_id"), nullable=True)
    appointment_id = Column(Integer, ForeignKey("appointments.appointment_id"), nullable=True)
    channel = Column(String, nullable=False)
    template = Column(String, nullable=False)
    status = Column(String, nullable=False)  # sent | failed
    provider_message_id = Column(String, nullable=True)
    sent_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    error_detail = Column(Text, nullable=True)


class ClinicSetting(Base):
    """
    מדיניות הקליניקה שניתנת לשינוי בלי לגעת בקוד (חלון הזמנה, שעות
    פעילות, מגבלת תורים פתוחים וכו'). value תמיד TEXT - המרת טיפוסים
    (int/bool/list) היא באחריות שכבת הגישה שקוראת מכאן, לא הטבלה עצמה.
    """
    __tablename__ = "clinic_settings"

    key = Column(String, primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(String, nullable=True)
