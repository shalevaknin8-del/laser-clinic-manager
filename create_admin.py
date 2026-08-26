# ============================================================
# create_admin.py
# יוצר את המנהל הראשון של המערכת.
#
# הרצה:  python3 create_admin.py
#
# הסקריפט מיועד להרצה מהטרמינל בלבד, על ידי מי שיש לו
# גישה לשרת. אין ולא יהיה דף הרשמה פתוח באינטרנט,
# כי דף כזה מאפשר לכל אחד לפתוח לעצמו חשבון.
#
# הסיסמה מוקלדת בהסתרה ואינה נשמרת בהיסטוריית הטרמינל.
# ============================================================

import sys
import getpass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from managers.user_manager import UserManager
from entities.user import ROLE_ADMIN
from utils.passwords import validate_password_strength
from utils.validators import normalize_phone


def prompt_password():
    """
    מבקש סיסמה פעמיים ומוודא התאמה.
    getpass מסתיר את ההקלדה, כך שהסיסמה לא נראית על המסך
    ולא נשמרת בהיסטוריית הפקודות.
    """
    while True:
        password = getpass.getpass("Password: ")

        is_valid, error_message = validate_password_strength(password)
        if not is_valid:
            print(f"  -> {error_message}")
            continue

        confirmation = getpass.getpass("Confirm password: ")
        if password != confirmation:
            print("  -> Passwords do not match. Try again.")
            continue

        return password


def main():
    print("=" * 55)
    print("  Create the first administrator account")
    print("=" * 55)

    user_manager = UserManager()

    existing_admins = user_manager.count_active_admins()
    if existing_admins > 0:
        print(f"\nAn active administrator already exists ({existing_admins}).")
        print("Additional users should be created from the web interface.")
        answer = input("Create another administrator anyway? (yes/no): ")
        if answer.strip().lower() not in ("yes", "y"):
            print("Cancelled.")
            return

    print()
    phone = input("Phone number (05XXXXXXXX): ").strip()
    if normalize_phone(phone) is None:
        print("Invalid Israeli mobile number. Cancelled.")
        return

    full_name = input("Full name: ").strip()
    if not full_name:
        print("Full name is required. Cancelled.")
        return

    password = prompt_password()

    user = user_manager.create_user(
        phone=phone,
        password=password,
        full_name=full_name,
        role=ROLE_ADMIN,
    )

    if user is None:
        print(f"\nFailed: {user_manager.last_error}")
        return

    print()
    print("=" * 55)
    print("  Administrator created successfully")
    print("=" * 55)
    print(f"  Phone    : {user.phone}")
    print(f"  Full name: {user.full_name}")
    print(f"  Role     : {user.role}")
    print("=" * 55)


if __name__ == "__main__":
    main()