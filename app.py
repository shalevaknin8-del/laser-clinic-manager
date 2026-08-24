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
from managers.treatment_manager import TreatmentManager
from managers.appointment_treatment_manager import AppointmentTreatmentManager

from api.clients_api import clients_bp
from api.appointments_api import appointments_bp
from api.treatments_api import treatments_bp
from api.invoices_api import invoices_bp
from api.leads_api import leads_bp
from api.dashboard_api import dashboard_bp


app = Flask(__name__)

# מונע המרה של תווים עבריים לקודים בתגובות JSON,
# כך שהטקסט קריא גם בבדיקה ידנית בכלי הפיתוח של הדפדפן
app.json.ensure_ascii = False


# ============================================================
# חיבור קבוצות ה-routes
# ============================================================

app.register_blueprint(clients_bp)
app.register_blueprint(appointments_bp)
app.register_blueprint(treatments_bp)
app.register_blueprint(invoices_bp)
app.register_blueprint(leads_bp)
app.register_blueprint(dashboard_bp)


# ============================================================
# עמוד הבית
# ============================================================

@app.route("/")
def index():
    """מגיש את עמוד ה-HTML הראשי מתוך תיקיית templates."""
    return render_template("index.html")


@app.after_request
def add_no_cache_headers(response):
    """
    מונע מהדפדפן לשמור תשובות בזיכרון מטמון.
    באפליקציית ניהול תמיד רוצים לראות נתונים עדכניים.
    """
    response.headers["Cache-Control"] = "no-store"
    return response


# ============================================================
# הרצה
# ============================================================

if __name__ == "__main__":
    # אתחול המסד, בטוח להרצה חוזרת
    initialize_database()

    # יצירת טבלת הקישור לטיפול מרוכב, בטוח להרצה חוזרת
    AppointmentTreatmentManager().ensure_table()

    # ללא קטלוג טיפולים אי אפשר לקבוע תורים
    treatment_manager = TreatmentManager()
    if len(treatment_manager.get_all_treatments()) == 0:
        treatment_manager.seed_catalog()

    # שרת מקומי בלבד. בפרודקשן נשתמש ב-gunicorn במקום זה.
    # פורט 5001 ולא 5000 כי ב-macOS שירות AirPlay תופס את 5000
    app.run(host="127.0.0.1", port=5001, debug=True)