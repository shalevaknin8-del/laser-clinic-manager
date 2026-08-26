# ============================================================
# tests/test_chat_flow.py
# הרצת שיחה מלאה מול הצ'אטבוט, בלי שרת ובלי דפדפן.
#
# הרצה:  python3 tests/test_chat_flow.py
#
# הבדיקה לוכדת את קוד האימות בזמן היצירה, כדי שאפשר
# יהיה להריץ את המסלול המלא באופן אוטומטי.
# ============================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chatbot.state import ConversationState
from chatbot.flows import process_message
from utils import otp


# לכידת הקוד שנוצר, בלי לשנות את קוד הייצור
captured = {}
original_generate = otp.generate_code


def capturing_generate(length=None):
    code = original_generate(length)
    captured["code"] = code
    return code


otp.generate_code = capturing_generate


def say(conversation, message):
    """שולח הודעה ומדפיס את השיחה."""
    print(f"\n  לקוחה : {message}")
    reply = process_message(conversation, message)
    for line in reply.split("\n"):
        print(f"  בוט    : {line}")
    print(f"  [state: {conversation.state}]")
    return reply


def run_main_scenario():
    """התרחיש המרכזי מהבריף: שם ייחודי עם תאריך שגוי."""
    print("=" * 60)
    print("  MAIN SCENARIO - unique name with wrong date")
    print("=" * 60)

    conversation = ConversationState("test-main")

    say(conversation, "קוראים לי רותם מירון ויש לי תור בתאריך 18.01.2027")
    say(conversation, "123456782")

    code = captured.get("code", "000000")
    say(conversation, code)


def run_ambiguous_name():
    """תרחיש 2: שם לא ייחודי, הבוט מבקש הבהרה."""
    print("\n" + "=" * 60)
    print("  SCENARIO 2 - ambiguous name")
    print("=" * 60)

    conversation = ConversationState("test-ambiguous")
    say(conversation, "קוראים לי רותם")
    say(conversation, "רותם כהן")


def run_wrong_id():
    """תרחיש 3: תעודת זהות שגויה שלוש פעמים."""
    print("\n" + "=" * 60)
    print("  SCENARIO 3 - wrong national id, three attempts")
    print("=" * 60)

    conversation = ConversationState("test-wrong-id")
    say(conversation, "קוראים לי נועה לוי")
    say(conversation, "111111111")
    say(conversation, "222222222")
    say(conversation, "333333333")


def run_no_appointments():
    """תרחיש 4: לקוחה קיימת בלי אף תור."""
    print("\n" + "=" * 60)
    print("  SCENARIO 4 - client with no appointments")
    print("=" * 60)

    conversation = ConversationState("test-no-appt")
    say(conversation, "קוראים לי שירה דהן")
    say(conversation, "444444442")

    code = captured.get("code", "000000")
    say(conversation, code)


def run_unknown_name():
    """תרחיש 5: שם שלא קיים במערכת."""
    print("\n" + "=" * 60)
    print("  SCENARIO 5 - name not in system")
    print("=" * 60)

    conversation = ConversationState("test-unknown")
    say(conversation, "קוראים לי אבישי כהן")


if __name__ == "__main__":
    run_main_scenario()
    run_ambiguous_name()
    run_wrong_id()
    run_no_appointments()
    run_unknown_name()

    print("\n" + "=" * 60)
    print("  All scenarios completed")
    print("=" * 60)

    otp.generate_code = original_generate