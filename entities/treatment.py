# ============================================================
# entities/treatment.py
# מחלקת ישות של טיפול (Treatment Entity)
# מייצגת טיפול בקטלוג הקליניקה
# ============================================================


class Treatment:
    """
    Entity Class המייצג טיפול בקטלוג הקליניקה.
    כל טיפול יכול לכלול איזור בודד או מספר איזורים (חבילה).
    איזורים מרובים נשמרים כמחרוזת מופרדת בפסיקים.
    """

    def __init__(self, treatment_name, body_area, price, duration_minutes,
                 treatment_id=None):
        # מזהה ייחודי של הטיפול — יתקבל מ-DB אחרי הוספה
        self.treatment_id = treatment_id
        
        # שם הטיפול בעברית (למשל: "פנים מלא", "חבילת פנים")
        self.treatment_name = treatment_name
        
        # איזור/ים - מחרוזת מופרדת בפסיקים (למשל: "פנים, שפם, סנטר")
        self.body_area = body_area
        
        # מחיר בשקלים
        self.price = price
        
        # משך הטיפול בדקות
        self.duration_minutes = duration_minutes

    def get_areas_list(self):
        """
        מחזיר רשימה של איזורי הטיפול (מפריד את המחרוזת בפסיקים).
        למשל: "פנים, שפם" -> ["פנים", "שפם"]
        שימושי כשרוצים לבדוק אם איזור מסוים נכלל בטיפול.
        """
        # split מפצל את המחרוזת לרשימה
        # strip מסיר רווחים מיותרים מסביב לכל איזור
        areas = self.body_area.split(",")
        cleaned_areas = []
        for area in areas:
            cleaned_areas.append(area.strip())
        return cleaned_areas

    def get_areas_count(self):
        """
        מחזיר את מספר האיזורים בטיפול.
        1 = טיפול בודד, 2+ = חבילה
        """
        return len(self.get_areas_list())

    def __str__(self):
        """
        מחזיר תצוגה קריאה של הטיפול למשתמש.
        מבחין בין טיפול בודד לחבילה בתצוגה.
        """
        # אם יש יותר מאיזור אחד - מדובר בחבילה
        areas_count = self.get_areas_count()
        
        if areas_count > 1:
            type_label = f"חבילה ({areas_count} איזורים)"
        else:
            type_label = "טיפול בודד"
        
        return (
            f"טיפול #{self.treatment_id} | "
            f"{self.treatment_name} ({type_label}) | "
            f"איזורים: {self.body_area} | "
            f"מחיר: {self.price} ש\"ח | "
            f"משך: {self.duration_minutes} דק'"
        )