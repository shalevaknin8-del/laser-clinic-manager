# ============================================================
# auth/permissions.py
# מפת ההרשאות של המערכת.
#
# העיקרון: כל route מסומן ביכולת שהוא דורש, ומילון אחד
# ממפה תפקיד לאוסף היכולות שלו.
#
# הוספת תפקיד חדש בעתיד היא שורה אחת במילון שלמטה,
# בלי לגעת באף route קיים.
# ============================================================

from entities.user import ROLE_ADMIN, ROLE_EMPLOYEE


# ============================================================
# רשימת היכולות במערכת
# הפורמט: ישות.פעולה
# ============================================================

# לקוחות
CLIENT_VIEW = "client.view"
CLIENT_CREATE = "client.create"
CLIENT_EDIT = "client.edit"
CLIENT_DELETE = "client.delete"

# תורים
APPOINTMENT_VIEW = "appointment.view"
APPOINTMENT_CREATE = "appointment.create"
APPOINTMENT_EDIT = "appointment.edit"
APPOINTMENT_DELETE = "appointment.delete"

# קטלוג טיפולים
TREATMENT_VIEW = "treatment.view"
TREATMENT_EDIT = "treatment.edit"

# חשבוniות
INVOICE_VIEW = "invoice.view"
INVOICE_CREATE = "invoice.create"
INVOICE_CANCEL = "invoice.cancel"

# לידים
LEAD_VIEW = "lead.view"
LEAD_EDIT = "lead.edit"

# דוחות והכנסות
REPORT_REVENUE = "report.revenue"

# ניהול המערכת
USER_MANAGE = "user.manage"
AUDIT_VIEW = "audit.view"

# משאבי זימון (שלב 3: Smart Scheduling) - הקמת חדרים/מכשירים
# וקביעת שעות עבודה של עובדת הן החלטות ניהוליות, לא עבודה יומיומית
ROOM_MANAGE = "room.manage"
MACHINE_MANAGE = "machine.manage"
STAFF_SCHEDULE_MANAGE = "staff_schedule.manage"

# חבילות טיפולים - הגדרת הקטלוג (מחיר, מספר מפגשים) שמורה למנהלת,
# אבל מכירת חבילה קיימת ללקוחה היא פעולה יומיומית כמו הפקת חשבונית
PACKAGE_MANAGE = "package.manage"
PACKAGE_SELL = "package.sell"


# ============================================================
# מפת התפקידים
#
# ההיגיון: עובדת מבצעת את העבודה היומיומית.
# מנהלת מקבלת החלטות עסקיות ומבצעת פעולות בלתי הפיכות.
# ============================================================

EMPLOYEE_PERMISSIONS = {
    CLIENT_VIEW,
    CLIENT_CREATE,
    CLIENT_EDIT,

    APPOINTMENT_VIEW,
    APPOINTMENT_CREATE,
    # עובדת מסמנת תור כמבוטל דרך עדכון סטטוס.
    # מחיקה אמיתית שמורה למנהלת בלבד
    APPOINTMENT_EDIT,

    # עובדת רואה מחירי טיפולים כדי לתמחר ללקוחה,
    # אבל שינוי מחיר הוא החלטה עסקית של דנה
    TREATMENT_VIEW,

    INVOICE_VIEW,
    INVOICE_CREATE,
    # ביטול חשבונית הוא פעולה עם משמעות מול רשויות המס

    LEAD_VIEW,
    LEAD_EDIT,

    # מכירת חבילה קיימת ללקוחה - כמו הפקת חשבונית, לא שינוי קטלוג
    PACKAGE_SELL,
}

# למנהלת יש את כל היכולות במערכת
ADMIN_PERMISSIONS = EMPLOYEE_PERMISSIONS | {
    CLIENT_DELETE,
    APPOINTMENT_DELETE,
    TREATMENT_EDIT,
    INVOICE_CANCEL,
    REPORT_REVENUE,
    USER_MANAGE,
    AUDIT_VIEW,
    ROOM_MANAGE,
    MACHINE_MANAGE,
    STAFF_SCHEDULE_MANAGE,
    PACKAGE_MANAGE,
}


ROLE_PERMISSIONS = {
    ROLE_ADMIN: ADMIN_PERMISSIONS,
    ROLE_EMPLOYEE: EMPLOYEE_PERMISSIONS,
}


def get_permissions_for_role(role):
    """
    מחזיר את אוסף היכולות של תפקיד.
    תפקיד לא מוכר מקבל אוסף ריק, לא הרשאות מלאות.
    זו ברירת מחדל בטוחה: טעות בהגדרה חוסמת ולא פותחת.
    """
    return ROLE_PERMISSIONS.get(role, set())


def role_has_permission(role, permission):
    """בודק האם תפקיד מסוים כולל יכולת מסוימת."""
    return permission in get_permissions_for_role(role)