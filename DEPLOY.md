# DEPLOY - נוהל הרצה ועדכון

מערכת ניהול קליניקת לייזר, כולל צ'אטבוט אימות ובירור תורים.

**כתובת המערכת:** https://shalevaknin.pythonanywhere.com

| נתיב | מיועד ל | גישה |
|---|---|---|
| `/` | ממשק הניהול | דורש התחברות |
| `/login` | מסך כניסה לצוות | פתוח |
| `/chat` | צ'אטבוט הלקוחות | פתוח |

---

## חלק א - הרצה מקומית

דרישות מוקדמות: Python 3.10 ומעלה, Git.

```
git clone https://github.com/shalevaknin8-del/laser-clinic-manager.git
cd laser-clinic-manager
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python3 -c "import secrets; print(secrets.token_hex(32))"
```

לאחר הפקודה האחרונה יש לפתוח את הקובץ `.env` ולמלא שני ערכים:

- `SECRET_KEY` - המחרוזת שהודפסה בפקודה האחרונה
- `GEMINI_API_KEY` - מפתח מ-Google AI Studio

בלי מפתח Gemini המערכת עובדת, אך שכבת הבנת השפה עוברת
למסלול גיבוי מבוסס regex ומדייקת פחות.

לאחר מילוי הקובץ, ממשיכים:

```
python3 migrations/run_all.py
python3 seed_data.py
python3 create_admin.py
python3 app.py
```

המערכת תהיה זמינה בכתובת http://127.0.0.1:5001

במערכת Windows יש להחליף את `source .venv/bin/activate`
בפקודה `.venv\Scripts\activate`.

---

## חלק ב - נוהל עדכון השרת

זהו התהליך החוזר שמתבצע בכל פעם שקוד חדש נדחף לגיטהאב.

### שלב 1 - דחיפה מהמחשב המקומי

```
git add -A
git commit -m "Describe the change in English"
git push origin main
```

### שלב 2 - משיכה לשרת

נכנסים לחשבון PythonAnywhere, לוחצים **Consoles** בתפריט העליון,
ופותחים קונסולת **Bash**. שם מריצים:

```
workon clinic
cd ~/laser-clinic-manager
git pull origin main
pip install -r requirements.txt
python3 migrations/run_all.py
```

שורת התקנת הספריות נדרשת רק אם `requirements.txt` השתנה,
אך אין נזק בהרצתה בכל פעם.

הרצת המיגרציות בטוחה להרצה חוזרת. כל מיגרציה בודקת בעצמה
אם השינוי כבר בוצע, ולכן אין צורך לזכור מה כבר רץ.

### שלב 3 - הפעלה מחדש

לוחצים **Web** בתפריט העליון, ואז על הכפתור הירוק
**Reload shalevaknin.pythonanywhere.com**.

ההפעלה אורכת כ-15 שניות.

### שלב 4 - אימות

פותחים את https://shalevaknin.pythonanywhere.com/chat
ומוודאים שהעמוד נטען.

---

## חלק ג - נקודות תפעול חשובות

### מיקום מסד הנתונים

מסד הנתונים נמצא ב-`/home/shalevaknin/clinic_data/clinic.db`,
כלומר מחוץ לתיקיית הפרויקט.

הסיבה: `git pull` מעדכן את תיקיית הפרויקט. אילו המסד היה בתוכה,
עדכון קוד היה עלול לדרוס את נתוני הקליניקה.

### קובץ הסביבה

הקובץ `.env` אינו נמצא בגיט ולעולם לא יימצא בו, מכיוון שהוא מכיל
את המפתח הסודי ואת מפתח ה-API.

הקובץ נוצר ידנית על השרת. בעת מעבר לשרת חדש יש ליצור אותו מחדש
לפי המבנה שבקובץ `.env.example`.

### נתוני הדגמה בפרודקשן

הסקריפט `seed_data.py` מסרב לרוץ כאשר `ENVIRONMENT=production`.
זו הגנה מכוונת שמונעת הכנסת נתוני דמו למסד עם לקוחות אמיתיים.

להרצה מכוונת בכל זאת:

```
ENVIRONMENT=development python3 seed_data.py
```

### שחזור לגרסה קודמת

התג `v1.0-midterm` מסמן את גרסת פרויקט האמצע.

```
git checkout v1.0-midterm
```

### איתור תקלות

בעמוד **Web** של PythonAnywhere קיימים שלושה קישורים לקבצי לוג:

| הקובץ | מה מכיל |
|---|---|
| Error log | שגיאות פייתון. המקום הראשון לבדוק |
| Server log | הודעות שרת והפעלות מחדש |
| Access log | רשימת הבקשות שהתקבלו |

תקלות נפוצות:

| הסימפטום | הסיבה הסבירה |
|---|---|
| שגיאה 502 | שגיאת תחביר בקוד. יש לבדוק ב-Error log |
| `ModuleNotFoundError` | ספרייה חסרה. יש להריץ `pip install -r requirements.txt` |
| `ConfigError` | משתנה חסר בקובץ `.env` |
| שינוי בקוד לא מופיע | לא בוצעה הפעלה מחדש בכפתור Reload |