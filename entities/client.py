# ============================================================
# entities/client.py
# מחלקת ישות של לקוח (Client Entity)
# מייצגת לקוח בודד בקליניקה
# ============================================================


class Client:
    """
    Entity Class המייצג לקוח בודד בקליניקה.
    מכיל את כל פרטי הלקוח - שם, טלפון, אימייל, כתובת.
    """

    def __init__(self, full_name, phone, email=None, address=None, client_id=None,
             national_id_hash=None):
        # מזהה ייחודי של הלקוח — יתקבל מ-DB אחרי הוספה
        self.client_id = client_id
                 # טביעת אצבע של תעודת הזהות, לא המספר עצמו. 
       
        # משמשת לאימות זהות בלבד ואינה מוחזרת בשום תגובת API
      
        self.national_id_hash = national_id_hash
        # שם מלא של הלקוח (שדה חובה)
        self.full_name = full_name
        
        # מספר טלפון (שדה חובה)
        self.phone = phone
        
        # כתובת אימייל (שדה רשות)
        self.email = email
        
        # כתובת מגורים (שדה רשות)
        self.address = address

    def __str__(self):
        """
        מחזיר תצוגה קריאה של הלקוח למשתמש.
        נקרא אוטומטית כשמדפיסים את האובייקט עם print().
        """
        # אם אין אימייל - מציגים מקף במקום
        email_display = self.email if self.email else "-"
        
        return (
            f"לקוח #{self.client_id} | "
            f"שם: {self.full_name} | "
            f"טלפון: {self.phone} | "
            f"אימייל: {email_display}"
        )