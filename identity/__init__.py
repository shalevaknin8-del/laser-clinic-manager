# ============================================================
# identity/
# שכבת הזהות המאוחדת של המערכת (Release 2, Principle 1 במפרט).
#
# זהו הרכיב היחיד שעונה על השאלה "מי זאת ואיך אני יודע שזו באמת
# היא". גם הצ'אטבוט (chatbot/verification.py, שכבר קיים - עבר
# לכאן) וגם הפורטל (api/portal_api.py, בהמשך) קוראים לכאן ולא
# למנגנון אימות עצמאי משלהם.
#
# שתי שיטות כניסה, מנוע אחד:
#   שם + ת.ז. + OTP   (צ'אטבוט, קיים)
#   טלפון + OTP        (פורטל, חדש)
# שתיהן משתמשות באותה תשתית OTP בדיוק (utils/otp.py) - ההבדל
# היחיד הוא מה מוכיח "ידע" לפני שליחת הקוד.
#
# מה שלא נמצא כאן בכוונה: ייצוג ה-session אחרי אימות מוצלח.
# צ'אטבוט מייצג session כ-ConversationState בזיכרון (chatbot/state.py),
# פורטל מייצג session כ-JWT (identity/tokens.py). זה שני "צרכנים"
# שונים של אותה תוצאת אימות, לא שני מנגנוני אימות.
# ============================================================

from identity.verification import (
    RESULT_OK,
    RESULT_WRONG,
    RESULT_LOCKED,
    RESULT_NO_DATA,
    RESULT_SEND_FAILED,
    PURPOSE_PORTAL_LOGIN,
    check_national_id,
    find_client_by_phone,
    identify_or_create_shell,
    is_new_client,
    send_otp,
    confirm_otp,
)

__all__ = [
    "RESULT_OK",
    "RESULT_WRONG",
    "RESULT_LOCKED",
    "RESULT_NO_DATA",
    "RESULT_SEND_FAILED",
    "PURPOSE_PORTAL_LOGIN",
    "check_national_id",
    "find_client_by_phone",
    "identify_or_create_shell",
    "is_new_client",
    "send_otp",
    "confirm_otp",
]
