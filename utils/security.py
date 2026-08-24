# ============================================================
# utils/security.py
# פונקציות הצפנה ואימות של נתונים רגישים.
#
# העיקרון המנחה: תעודת זהות משמשת אך ורק להשוואה,
# ולכן אין שום סיבה שהיא תישמר במצב קריא.
# במקום המספר עצמו נשמרת טביעת אצבע מתמטית שלו.
#
# גם אם קובץ מסד הנתונים ידלוף, אי אפשר לשחזר ממנו
# את תעודות הזהות של הלקוחות.
# ============================================================

import hashlib
import hmac
import secrets


# מספר סיבובי החישוב. ערך גבוה מאט מתקפות ניחוש בכוח גס.
# 200,000 הוא איזון סביר בין אבטחה למהירות תגובה
HASH_ITERATIONS = 200_000

# אורך המלח באותיות הקסדצימליות
SALT_LENGTH = 16


def hash_national_id(national_id):
    """
    ממיר תעודת זהות לטביעת אצבע מאובטחת.

    לכל לקוחה נוצר מלח אקראי ייחודי. המלח מונע מצב שבו
    שתי לקוחות עם אותה תעודת זהות יקבלו את אותה טביעת אצבע,
    ומונע שימוש בטבלאות ניחוש מוכנות מראש.

    מחזיר מחרוזת בפורמט: salt$hash
    """
    if national_id is None:
        return None

    salt = secrets.token_hex(SALT_LENGTH)

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        str(national_id).encode("utf-8"),
        salt.encode("utf-8"),
        HASH_ITERATIONS,
    )

    return f"{salt}${digest.hex()}"


def verify_national_id(national_id, stored_hash):
    """
    בודק האם תעודת זהות תואמת לטביעת האצבע השמורה.

    ההשוואה מתבצעת עם compare_digest ולא עם סימן שווה רגיל.
    הסיבה: השוואה רגילה נעצרת בתו הראשון שאינו תואם, וזמן
    התגובה מסגיר כמה תווים היו נכונים. compare_digest לוקח
    תמיד את אותו זמן, ולכן חסין להתקפת תזמון.

    מחזיר True או False בלבד.
    """
    if not national_id or not stored_hash:
        return False

    if "$" not in stored_hash:
        return False

    salt, expected_hex = stored_hash.split("$", 1)

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        str(national_id).encode("utf-8"),
        salt.encode("utf-8"),
        HASH_ITERATIONS,
    )

    return hmac.compare_digest(digest.hex(), expected_hex)