# ============================================================
# chatbot/state.py
# ניהול מצב השיחה.
#
# הבוט חייב לזכור בין הודעה להודעה מי המועמדת הנוכחית
# ואם היא כבר אומתה. בלי זה כל הודעה נענית בבידוד
# והשיחה לא מתקדמת.
#
# הערה על אחסון: המצב נשמר בזיכרון התהליך. זה מתאים
# לשרת יחיד, שזו בדיוק הארכיטקטורה שלנו. במעבר לכמה
# שרתים יהיה צריך אחסון חיצוני, ולכן כל הגישה למצב
# מרוכזת בקובץ הזה ולא מפוזרת בקוד.
# ============================================================

import secrets
from datetime import datetime, timedelta

from config import Config


# ============================================================
# מצבי השיחה
# ============================================================

STATE_START = "start"                    # תחילת שיחה
STATE_IDENTIFYING = "identifying"        # ממתין לשם
STATE_DISAMBIGUATING = "disambiguating"  # כמה התאמות, ממתין להבהרה
STATE_AWAITING_ID = "awaiting_id"        # ממתין לתעודת זהות
STATE_AWAITING_OTP = "awaiting_otp"      # ממתין לקוד אימות
STATE_VERIFIED = "verified"              # אומת, מותר לחשוף מידע
STATE_LOCKED = "locked"                  # נחסם עקב ניסיונות כושלים


class ConversationState:
    """מצב שיחה יחידה מול לקוחה אחת."""

    def __init__(self, session_id):
        self.session_id = session_id
        self.state = STATE_START

        # המועמדת הנוכחית. מזהה בלבד, בלי פרטים אישיים
        self.candidate_client_id = None

        # רשימת המועמדות כשיש כמה התאמות לאותו שם
        self.candidates = []

        # מה שהמשתמשת טענה, לצורך השוואה בסוף
        self.claimed_date = None
        self.claimed_time = None

        # מונים נפרדים לכל שלב אימות
        self.id_attempts = 0
        self.otp_attempts = 0

        # דגלי אימות. שניהם חייבים להיות אמת כדי לחשוף מידע
        self.id_verified = False
        self.otp_verified = False

        self.created_at = datetime.now()
        self.last_activity_at = datetime.now()

    def touch(self):
        """מעדכן את זמן הפעילות האחרונה."""
        self.last_activity_at = datetime.now()

    def is_expired(self):
        """
        בודק האם השיחה פגה.
        שיחה נטושה חייבת לפוג, אחרת מחשב שנשאר פתוח
        מאפשר למישהו אחר להמשיך שיחה מאומתת.
        """
        expiry = self.last_activity_at + timedelta(
            minutes=Config.SESSION_TIMEOUT_MINUTES
        )
        return datetime.now() > expiry

    def is_fully_verified(self):
        """
        התנאי היחיד לחשיפת מידע.
        שני שלבי האימות חייבים לעבור, והשיחה לא נעולה.
        """
        return (
            self.id_verified
            and self.otp_verified
            and self.state == STATE_VERIFIED
        )

    def lock(self):
        """נועל את השיחה. אין דרך חזרה בלי להתחיל מחדש."""
        self.state = STATE_LOCKED
        self.id_verified = False
        self.otp_verified = False

    def reset_identity(self):
        """
        מנקה את זהות המועמדת ואת האימות.
        משמש כשהמשתמשת מתקנת את השם באמצע השיחה.
        """
        self.candidate_client_id = None
        self.candidates = []
        self.id_verified = False
        self.otp_verified = False
        self.id_attempts = 0
        self.otp_attempts = 0


class ConversationStore:
    """
    מאחסן את כל השיחות הפעילות.
    ניקוי השיחות שפגו מתבצע בכל גישה, כדי שהזיכרון
    לא יתמלא בשיחות נטושות.
    """

    def __init__(self):
        self._conversations = {}

    def create_session(self):
        """יוצר מזהה שיחה חדש ואקראי."""
        session_id = secrets.token_urlsafe(24)
        self._conversations[session_id] = ConversationState(session_id)
        return session_id

    def get(self, session_id):
        """
        מחזיר מצב שיחה קיים, או None אם אין כזה או שפג.
        שיחה שפגה נמחקת מיידית.
        """
        self._cleanup()

        if not session_id:
            return None

        conversation = self._conversations.get(session_id)
        if conversation is None:
            return None

        if conversation.is_expired():
            del self._conversations[session_id]
            return None

        conversation.touch()
        return conversation

    def get_or_create(self, session_id):
        """מחזיר שיחה קיימת, או פותח חדשה אם אין."""
        conversation = self.get(session_id)
        if conversation is not None:
            return conversation

        new_id = self.create_session()
        return self._conversations[new_id]

    def end(self, session_id):
        """מסיים שיחה ומוחק את המצב שלה."""
        self._conversations.pop(session_id, None)

    def _cleanup(self):
        """מוחק שיחות שפג תוקפן."""
        expired = [
            sid for sid, conv in self._conversations.items()
            if conv.is_expired()
        ]
        for sid in expired:
            del self._conversations[sid]

    def active_count(self):
        """מספר השיחות הפעילות. לצורך ניטור."""
        self._cleanup()
        return len(self._conversations)


# מופע יחיד המשותף לכל האפליקציה
conversation_store = ConversationStore()