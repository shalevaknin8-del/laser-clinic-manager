# ============================================================
# entities/invoice.py
# מחלקת ישות של חשבונית מס (Invoice Entity)
# מייצגת חשבונית בודדת שהונפקה ללקוח
# ============================================================


class Invoice:
    """
    Entity Class המייצג חשבונית מס בקליניקה.
    כל חשבונית חייבת להיות מקושרת ללקוח (client_id).
    אופציונלית, ניתן לקשר אותה גם לתור ספציפי (appointment_id).
    """

    def __init__(self, client_id, amount, invoice_date,
                 appointment_id=None, invoice_number=None, invoice_id=None,
                 is_cancelled=0, cancelled_at=None):
        # מזהה ייחודי של החשבונית ב-DB — יתקבל אחרי הוספה
        self.invoice_id = invoice_id
        
        # מספר חשבונית ייחודי בפורמט YYYY-NNN (למשל: "2026-001")
        # חובה לפי חוקי מס הכנסה בישראל
        self.invoice_number = invoice_number
        
        # מזהה הלקוח שמקבל את החשבונית (FK לטבלת clients)
        self.client_id = client_id
        
        # מזהה התור המקושר לחשבונית (אופציונלי - יכול להיות None)
        # למשל: חשבונית על מכירת מוצר לא מקושרת לתור
        self.appointment_id = appointment_id
        
        # סכום החשבונית בשקלים
        self.amount = amount
        
        # תאריך הפקת החשבונית בפורמט YYYY-MM-DD
        self.invoice_date = invoice_date

        # האם החשבונית בוטלה - 0 פעילה, 1 מבוטלת (Soft Delete)
        self.is_cancelled = is_cancelled
        
        # מתי בוטלה - None אם פעילה
        self.cancelled_at = cancelled_at

    def __str__(self):
        """
        מחזיר תצוגה קריאה של החשבונית.
        חשבונית מבוטלת מסומנת במפורש.
        """
        if self.appointment_id is not None:
            appointment_display = f"תור #{self.appointment_id}"
        else:
            appointment_display = "ללא קישור לתור"

        # סימון ברור לחשבונית מבוטלת
        if self.is_cancelled:
            status_display = " [מבוטלת]"
        else:
            status_display = ""

        return (
            f"חשבונית {self.invoice_number}{status_display} | "
            f"לקוח: {self.client_id} | "
            f"סכום: {self.amount} ש\"ח | "
            f"תאריך: {self.invoice_date} | "
            f"{appointment_display}"
        )