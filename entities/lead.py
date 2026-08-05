# ============================================================
# entities/lead.py
# מחלקת ישות של ליד (Lead Entity)
# מייצגת לקוח פוטנציאלי שטרם הפך ללקוח בפועל
# ============================================================


class Lead:
    """
    Entity Class המייצג ליד - לקוח פוטנציאלי.
    לידים הופכים ללקוחות דרך תהליך המרה (convert_lead_to_client).
    
    סטטוסים אפשריים:
    - 'new'         : ליד חדש שעוד לא טופל
    - 'in_progress' : בטיפול (שיחה/מייל עם הלקוחה)
    - 'converted'   : הפכה ללקוחה (קבעה תור)
    - 'rejected'    : לא מעוניינת / לא מתאימה
    """

    def __init__(self, full_name, phone, source=None, status="new",
                 notes=None, lead_id=None):
        # מזהה ייחודי - יתקבל מ-DB אחרי הוספה
        self.lead_id = lead_id
        
        # שם מלא של הליד (שדה חובה)
        self.full_name = full_name
        
        # מספר טלפון (שדה חובה)
        self.phone = phone
        
        # מקור הפנייה - facebook, instagram, google, referral, walk_in
        self.source = source
        
        # סטטוס נוכחי - ברירת מחדל 'new'
        self.status = status
        
        # הערות חופשיות של דנה
        self.notes = notes

    def is_converted(self):
        """
        בודק אם הליד כבר הפך ללקוחה.
        שימושי כדי למנוע המרה כפולה של אותו ליד.
        """
        return self.status == "converted"

    def is_active(self):
        """
        בודק אם הליד עדיין פעיל (לא נדחה ולא הומר).
        לידים פעילים הם אלה שדורשים טיפול.
        """
        return self.status in ("new", "in_progress")

    def __str__(self):
        """
        מחזיר תצוגה קריאה של הליד למשתמש.
        """
        # אם אין מקור - מציגים "לא ידוע" במקום None
        source_display = self.source if self.source else "לא ידוע"
        
        return (
            f"ליד #{self.lead_id} | "
            f"שם: {self.full_name} | "
            f"טלפון: {self.phone} | "
            f"מקור: {source_display} | "
            f"סטטוס: {self.status}"
        )