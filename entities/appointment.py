# ============================================================
# entities/appointment.py
# מחלקת ישות של תור (Appointment Entity)
# מייצגת תור בודד במערכת
# ============================================================


class Appointment:
    """
    Entity Class המייצג תור בודד בקליניקה.
    כל תור מקושר ללקוח (client_id) ולטיפול (treatment_id).
    """

    def __init__(self, client_id, treatment_id, appointment_date,
                 appointment_time, status="pending", notes=None,
                 appointment_id=None):
        # מזהה ייחודי של התור — יתקבל מ-DB אחרי הוספה
        self.appointment_id = appointment_id
        
        # מזהה הלקוח שקבע את התור (FK לטבלת clients)
        self.client_id = client_id
        
        # מזהה הטיפול שנקבע (FK לטבלת treatments)
        self.treatment_id = treatment_id
        
        # תאריך התור בפורמט YYYY-MM-DD
        self.appointment_date = appointment_date
        
        # שעת התור בפורמט HH:MM
        self.appointment_time = appointment_time
        
        # סטטוס התור: pending / completed / cancelled
        self.status = status
        
        # הערות חופשיות (שדה רשות)
        self.notes = notes

    def __str__(self):
        """
        מחזיר תצוגה קריאה של התור למשתמש.
        נקרא אוטומטית כשמדפיסים את האובייקט עם print().
        """
        return (
            f"תור #{self.appointment_id} | "
            f"לקוח: {self.client_id} | "
            f"טיפול: {self.treatment_id} | "
            f"תאריך: {self.appointment_date} {self.appointment_time} | "
            f"סטטוס: {self.status}"
        )