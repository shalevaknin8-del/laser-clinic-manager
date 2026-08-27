# ============================================================
# tests/conftest.py
# תשתית משותפת לכל הבדיקות: בסיס נתונים מבודד וזמני,
# משתני סביבה ייעודיים לבדיקות, ופיקסצ'רים משותפים.
#
# בסיס הנתונים של הבדיקות נפרד לגמרי מ-data/clinic.db, ומאופס
# לחלוטין לפני כל בדיקה בודדת - כדי שאין דליפת מצב בין בדיקות
# ואין שום סיכון לגעת בנתוני האמת של הקליניקה.
# ============================================================

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# חייב לקרות *לפני* כל ייבוא של config/database - שני המודולים
# האלה קוראים את משתני הסביבה פעם אחת בלבד, בזמן הטעינה
TEST_DB_DIR = PROJECT_ROOT / "tests" / "_test_data"
TEST_DB_DIR.mkdir(exist_ok=True)
TEST_DB_PATH = TEST_DB_DIR / "test_clinic.db"

os.environ["SECRET_KEY"] = "test-secret-key-" + "a" * 40
os.environ.setdefault("ENVIRONMENT", "development")
os.environ["GEMINI_API_KEY"] = ""  # מכריח מסלול regex, בלי קריאות רשת אמיתיות בבדיקות
os.environ["DATABASE_PATH"] = str(TEST_DB_PATH)
os.environ["NOTIFICATION_PROVIDER"] = "console"

import pytest  # noqa: E402

from migrations.run_all import run_all as run_all_migrations  # noqa: E402
import db as db_module  # noqa: E402


def _reset_database():
    """
    מוחק את קובץ בסיס הבדיקות (כולל WAL/SHM) ובונה אותו מחדש מאפס
    ע"י הרצת אותו migrations/run_all.py בדיוק שמריצים בפרודקשן -
    כך שלבדיקות אין סכמה כפולה/נפרדת שעלולה לסטות מהאמת.

    בנוסף: מנקה את ה-session וה-connection pool של ה-ORM אחרי
    מחיקת/יצירת הקובץ. בלי זה, scoped_session (הקשור ל-thread
    שבו pytest רץ, לא לכל בדיקה בנפרד) היה ממשיך להחזיר את אותו
    Session עם identity map ישן מהבדיקה הקודמת - וגם connection
    pool שפתוח מול קובץ SQLite שכבר נמחק.
    """
    db_module.SessionLocal.remove()
    db_module.engine.dispose()

    for suffix in ("", "-wal", "-shm"):
        path = Path(str(TEST_DB_PATH) + suffix)
        if path.exists():
            path.unlink()

    run_all_migrations()


@pytest.fixture(autouse=True)
def isolated_database():
    """
    מאפס את בסיס הנתונים לפני כל בדיקה בודדת.
    כל בדיקה מתחילה ממסד ריק לגמרי - בידוד מלא, בלי תלות בסדר הרצה
    ובלי שום מגע בבסיס הנתונים האמיתי של הקליניקה.
    """
    _reset_database()

    # מנקה גם את מצב השיחות של הצ'אטבוט בזיכרון, כדי ששיחה
    # משאריות בדיקה קודמת לא תישאר תקועה בין בדיקות
    from chatbot.state import conversation_store
    conversation_store._conversations.clear()

    yield


@pytest.fixture
def treatment_catalog():
    """זורע את קטלוג הטיפולים המלא ומחזיר אותו, לשימוש בבדיקות תורים."""
    from managers.treatment_manager import TreatmentManager
    manager = TreatmentManager()
    manager.seed_catalog()
    return manager.get_all_treatments()


@pytest.fixture
def flask_app():
    """
    מחזיר את אובייקט ה-Flask האמיתי של האפליקציה, עם הגבלת הקצב מכובה.

    ההגבלה מכובה כברירת מחדל כי חלק מהבדיקות שולחות עשרות בקשות
    ברצף ואינן אמורות להיחסם ע"י ה-rate limiter - הוא נבדק בנפרד
    ובמפורש ב-test_security.py.

    שים לב: app.config["RATELIMIT_ENABLED"] לא מספיק כאן - Flask-Limiter
    קורא אותו פעם אחת בלבד ב-init_app (עם config.setdefault) ושומר
    את הערך כתכונת מופע קבועה (self.enabled). שינוי ה-config אחרי
    שהאפליקציה כבר עלתה לא משפיע. לכן מכבים ישירות על מופע ה-Limiter.
    """
    import app as app_module
    app_module.app.config["TESTING"] = True
    app_module.limiter.enabled = False
    return app_module.app


@pytest.fixture
def client(flask_app):
    """לקוח בדיקה של Flask, עם תמיכה בעוגיות session בין בקשות."""
    return flask_app.test_client()


def create_user(phone, full_name, password, role):
    """עוזר: יוצר משתמש מערכת (מנהל/עובד) ישירות דרך המנהל."""
    from managers.user_manager import UserManager
    user = UserManager().create_user(
        phone=phone, password=password, full_name=full_name, role=role
    )
    assert user is not None, f"יצירת משתמש נכשלה: {UserManager().last_error}"
    return user


def login_as(test_client, phone, password):
    """
    עוזר: מתחבר עם test_client נתון ומחזיר את תשובת ה-login.

    מאז המעבר ל-JWT (שלב 2 של הריפקטור) ההתחברות לא פותחת session
    cookie אלא מחזירה access_token ב-JSON. כדי שכל שאר הבדיקות
    שכבר כתובות כ-client.get(...)/client.post(...) פשוט ימשיכו
    לעבוד בלי לצרף כותרת Authorization בכל קריאה בנפרד, ה-access
    token נרשם כאן פעם אחת כ-header קבוע על ה-test_client עצמו
    (environ_base, נתמך ע"י Werkzeug) - בדיוק כמו שהדפדפן היה שולח
    את עוגיית ה-session בעבר בכל בקשה אוטומטית.
    """
    response = test_client.post(
        "/api/auth/login", json={"phone": phone, "password": password}
    )
    if response.status_code == 200:
        access_token = response.get_json()["access_token"]
        test_client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {access_token}"
    return response


def create_client_with_id(full_name, phone, national_id,
                           email=None, address=None):
    """עוזר: יוצר לקוחה עם תעודת זהות שמורה, ומחזיר את אובייקט הלקוחה."""
    from entities.client import Client
    from managers.client_manager import ClientManager

    manager = ClientManager()
    client_obj = manager.insert_client(
        Client(full_name=full_name, phone=phone, email=email, address=address)
    )
    assert client_obj is not None, f"יצירת לקוחה נכשלה: {manager.last_error}"

    ok = manager.set_national_id(client_obj.client_id, national_id)
    assert ok, f"שמירת תעודת זהות נכשלה: {manager.last_error}"

    return client_obj


def future_date_str(days_ahead=10):
    """תאריך עתידי בפורמט YYYY-MM-DD - נשאר תקף לא משנה מתי הבדיקות רצות."""
    from datetime import timedelta
    from utils.datetime_utils import today_jerusalem, to_date_str
    return to_date_str(today_jerusalem() + timedelta(days=days_ahead))


def setup_one_room_one_machine_one_staff():
    """
    עוזר: חדר אחד, מכשיר אחד, עובדת אחת פנויה כל השבוע כל היום -
    קיבולת בדיוק 1 לכל משבצת, לבדיקות services/booking_service.py
    ו-api/portal_api.py שדורשות שיבוץ משאבים אמיתי. גם מרחיבה את
    מדיניות הקליניקה כך שיום/שעה לא יהיו משתנה שלא רלוונטי לבדיקה.
    מחזיר את אובייקט העובדת (User).
    """
    from managers.room_manager import RoomManager
    from managers.machine_manager import MachineManager
    from managers.staff_schedule_manager import StaffScheduleManager
    from managers.clinic_settings_manager import ClinicSettingsManager

    settings_manager = ClinicSettingsManager()
    settings_manager.set_value("working_days", "0,1,2,3,4,5,6")
    settings_manager.set_value("working_hours_start", "09:00")
    settings_manager.set_value("working_hours_end", "20:00")
    settings_manager.set_value("min_hours_before_booking", "0")

    RoomManager().create_room("חדר טיפולים")
    MachineManager().create_machine("לייזר ראשי")

    staff = create_user("0530000001", "עובדת בדיקה", "Password123!", "employee")
    schedule = StaffScheduleManager()
    for day in range(7):
        schedule.add_availability(staff.user_id, day, "09:00", "20:00")

    return staff


def capture_otp_code(monkeypatch):
    """מלכדת את קוד ה-OTP שנוצר, בלי לשנות את קוד הייצור."""
    from utils import otp as otp_module

    captured = {}
    original_generate = otp_module.generate_code

    def capturing_generate(length=None):
        code = original_generate(length)
        captured["code"] = code
        return code

    monkeypatch.setattr(otp_module, "generate_code", capturing_generate)
    return captured


def assert_no_sensitive_leak(payload):
    """
    בודק רקורסיבית שמבנה תגובת JSON לא מכיל שדות רגישים
    (טביעת אצבע של ת"ז או סיסמה) בשום מקום, בכל עומק.
    """
    forbidden_keys = {"national_id_hash", "password_hash", "code_hash"}

    def _walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                assert key not in forbidden_keys, f"שדה רגיש דלף בתגובה: {key}"
                _walk(value)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(payload)
