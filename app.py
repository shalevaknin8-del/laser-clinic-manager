# ============================================================
# app.py
# נקודת הכניסה של אפליקציית הווב.
#
# תפקיד הקובץ: ליצור את האפליקציה, לחבר אליה את קבוצות
# ה-routes, ולהריץ אותה. אין כאן לוגיקה עסקית ואין routes.
#
# כל נקודות הקצה נמצאות בתיקיית api, מחולקות לפי ישות.
# החלוקה הזו מאפשרת לאכוף הרשאות ברמת הקבוצה במקום
# ברמת כל endpoint בנפרד.
#
# הרצה מקומית:  python3 app.py
# ============================================================

from flask import Flask, render_template

from database import initialize_database
from db import init_orm_tables, remove_session
from managers.treatment_manager import TreatmentManager
from managers.appointment_treatment_manager import AppointmentTreatmentManager

from api.clients_api import clients_bp
from api.appointments_api import appointments_bp
from api.treatments_api import treatments_bp
from api.invoices_api import invoices_bp
from api.leads_api import leads_bp
from api.dashboard_api import dashboard_bp
from api.verification_api import verification_bp
from api.auth_api import auth_bp
from api.users_api import users_bp
from api.chat_api import chat_bp
from api.rooms_api import rooms_bp
from api.machines_api import machines_bp
from api.staff_schedule_api import staff_schedule_bp
from api.packages_api import packages_bp
from api.portal_api import portal_bp
from security_setup import apply_security


app = Flask(__name__)

# מונע המרה של תווים עבריים לקודים בתגובות JSON,
# כך שהטקסט קריא גם בבדיקה ידנית בכלי הפיתוח של הדפדפן
app.json.ensure_ascii = False


# טעינת הגדרות האבטחה מקובץ הסביבה
from config import Config
Config.validate()

app.secret_key = Config.SECRET_KEY
app.config["SESSION_COOKIE_HTTPONLY"] = Config.SESSION_COOKIE_HTTPONLY
app.config["SESSION_COOKIE_SAMESITE"] = Config.SESSION_COOKIE_SAMESITE
app.config["SESSION_COOKIE_SECURE"] = Config.SESSION_COOKIE_SECURE

# ============================================================
# חיבור קבוצות ה-routes
# ============================================================

app.register_blueprint(clients_bp)
app.register_blueprint(appointments_bp)
app.register_blueprint(treatments_bp)
app.register_blueprint(invoices_bp)
app.register_blueprint(leads_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(verification_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(users_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(rooms_bp)
app.register_blueprint(machines_bp)
app.register_blueprint(staff_schedule_bp)
app.register_blueprint(packages_bp)
app.register_blueprint(portal_bp)

# הקשחת אבטחה. חייב לרוץ אחרי רישום כל ה-Blueprints,
# כדי שהמגבלות יחולו על ה-routes שכבר קיימים
limiter = apply_security(app)


# ============================================================
# עמוד ניהול הצוות - גרסת JWT.
#
# בשונה מהגרסה הקודמת (session cookie), השרת לא יכול לדעת מתוך
# בקשת GET רגילה אם המשתמשת מחוברת - אין כותרת Authorization על
# טעינת עמוד HTML. לכן שני ה-routes תמיד מגישים את אותו קובץ,
# וה-JS בצד הלקוח (static/app.js) הוא זה שבודק אם יש טוקן ב-
# localStorage ומפנה בהתאם (index.html -> /login אם אין טוקן,
# login.html -> / אם כבר יש). זו הדרך הרגילה לעשות את זה ב-SPA
# מגובה טוקן, ואין בה שום דליפת מידע - שני העמודים סטטיים
# לגמרי, וההרשאה עצמה עדיין נאכפת אך ורק בשרת בכל קריאת API.
# ============================================================

@app.route("/")
def index():
    """מגיש את מעטפת ממשק הניהול (SPA). הבדיקה אם מחוברים מתבצעת ב-JS."""
    return render_template("index.html")


@app.route("/login")
def login_page():
    """מגיש את מסך הכניסה. אם כבר יש טוקן שמור, ה-JS מפנה ל-/."""
    return render_template("login.html")


@app.route("/chat")
def chat_page():
    """
    מגיש את ממשק הצ'אט ללקוחות.
    העמוד פתוח בכוונה: הלקוחות אינן משתמשות במערכת
    ואין להן חשבון. האימות מתבצע בתוך השיחה עצמה.
    """
    return render_template("chat.html")

@app.after_request
def add_no_cache_headers(response):
    """
    מונע מהדפדפן לשמור תשובות בזיכרון מטמון.
    באפליקציית ניהול תמיד רוצים לראות נתונים עדכניים.
    """
    response.headers["Cache-Control"] = "no-store"
    return response


@app.teardown_appcontext
def shutdown_orm_session(exception=None):
    """
    סוגר את ה-SQLAlchemy session בסוף כל בקשה - אותו עיקרון בדיוק
    כמו סגירת חיבור SQLite גולמי ב-finally בכל מנהל. בלי זה,
    ה-session נשאר תפוס ל-thread הזה ועלול להחזיר מידע מיושן
    (stale) בבקשה הבאה שתטופל באותו thread.
    """
    remove_session(exception)


# ============================================================
# הרצה
# ============================================================

if __name__ == "__main__":
    # אתחול המסד, בטוח להרצה חוזרת
    initialize_database()

    # יצירת טבלת הקישור לטיפול מרוכב, בטוח להרצה חוזרת
    AppointmentTreatmentManager().ensure_table()

    # טבלאות ה-ORM החדשות (rooms/machines/packages/...) - ראו db.py.
    # migrations/004_orm_refactor.py הוא הדרך הרשמית להרצה חד-פעמית
    # (כולל עמודות חדשות בטבלאות קיימות); הקריאה כאן היא רשת ביטחון
    # בלבד להרצה מקומית ראשונה, בדיוק כמו initialize_database() למעלה
    init_orm_tables()

    # ללא קטלוג טיפולים אי אפשר לקבוע תורים
    treatment_manager = TreatmentManager()
    if len(treatment_manager.get_all_treatments()) == 0:
        treatment_manager.seed_catalog()

    # שרת מקומי בלבד. בפרודקשן נשתמש ב-gunicorn במקום זה.
    # פורט 5001 ולא 5000 כי ב-macOS שירות AirPlay תופס את 5000
    app.run(host="127.0.0.1", port=5001, debug=True)