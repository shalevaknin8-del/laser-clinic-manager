# ============================================================
# migrations/007_notification_log.py
# Release 2 - יומן כל הודעה שנשלחה/נכשלה. מונע שליחה כפולה של
# תזכורות (scripts/send_reminders.py בודק כאן לפני שליחה) ומאפשר
# לחקור תלונה של לקוחה שלא קיבלה הודעה.
#
# הרצה:  python3 migrations/007_notification_log.py
# בטוח להרצה חוזרת.
# ============================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import engine
from models import Base, NotificationLog


def run_migration():
    Base.metadata.create_all(engine, tables=[NotificationLog.__table__])
    print("  notification_log ready")
    return True


if __name__ == "__main__":
    print("Running migration 007 (notification_log)...")
    run_migration()
    print("Done.")
