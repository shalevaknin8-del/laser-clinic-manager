# ============================================================
# notifications/console_provider.py
# ספק התראות לסביבת פיתוח.
#
# במקום לשלוח את ההודעה, הוא מדפיס אותה לטרמינל.
# כך אפשר לבדוק את כל זרימת האימות בלי תלות בשירות חיצוני.
#
# הספק הזה חסום לשימוש בפרודקשן, כדי שלא ייווצר מצב
# שבו קודי אימות של לקוחות אמיתיים מודפסים ללוגים.
# ============================================================

from datetime import datetime

from notifications.base import NotificationProvider


class ConsoleProvider(NotificationProvider):
    """ספק שמדפיס הודעות לטרמינל במקום לשלוח אותן."""

    channel_name = "console"

    def send(self, recipient, subject, message):
        """מדפיס את ההודעה בפורמט קריא ומחזיר הצלחה."""
        timestamp = datetime.now().strftime("%H:%M:%S")

        print("")
        print("=" * 60)
        print(f"  NOTIFICATION  [{timestamp}]")
        print("=" * 60)
        print(f"  To      : {recipient}")
        if subject:
            print(f"  Subject : {subject}")
        print("-" * 60)
        print(f"  {message}")
        print("=" * 60)
        print("")

        return True