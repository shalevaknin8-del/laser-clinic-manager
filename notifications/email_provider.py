# ============================================================
# notifications/email_provider.py
# ספק התראות בדואר אלקטרוני, דרך שרת SMTP.
#
# עובד מול כל ספק שתומך ב-SMTP: Gmail, Outlook, ספק ייעודי.
# פרטי החיבור נקראים מקובץ הסביבה ולא נמצאים בקוד.
#
# הערה חשובה לגבי Gmail: יש להשתמש בסיסמת אפליקציה ייעודית
# ולא בסיסמת החשבון הרגילה. סיסמת אפליקציה ניתנת לביטול
# בנפרד בלי לשנות את סיסמת החשבון.
# ============================================================

import smtplib
from email.message import EmailMessage

from notifications.base import NotificationProvider, NotificationError


class EmailProvider(NotificationProvider):
    """שולח הודעות בדואר אלקטרוני דרך SMTP."""

    channel_name = "email"

    def __init__(self, host, port, username, password, sender):
        self.host = host
        self.port = int(port) if port else 587
        self.username = username
        self.password = password
        self.sender = sender or username

    def is_configured(self):
        """בודק שכל פרטי החיבור קיימים."""
        return all([self.host, self.username, self.password, self.sender])

    def send(self, recipient, subject, message):
        """שולח מייל ומחזיר הצלחה, או זורק חריגה בכישלון."""
        if not self.is_configured():
            raise NotificationError("Email provider is not fully configured")

        if not recipient:
            raise NotificationError("Missing recipient email address")

        email = EmailMessage()
        email["From"] = self.sender
        email["To"] = recipient
        email["Subject"] = subject or "הודעה מהקליניקה"
        email.set_content(message)

        try:
            # starttls משדרג את החיבור להצפנה לפני שליחת הסיסמה
            with smtplib.SMTP(self.host, self.port, timeout=15) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(email)

            return True

        except smtplib.SMTPAuthenticationError:
            # הודעת השגיאה לא מכילה את הסיסמה או את שם המשתמש
            raise NotificationError("Email authentication failed")

        except Exception as error:
            raise NotificationError(f"Email sending failed: {type(error).__name__}")