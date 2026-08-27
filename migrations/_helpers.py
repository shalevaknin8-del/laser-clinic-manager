# ============================================================
# migrations/_helpers.py
# פונקציות עזר משותפות למיגרציות Release 2 (005 ואילך) שמוסיפות
# עמודות ל-ALTER TABLE. migrations/004_orm_refactor.py מגדיר גרסה
# זהה משלו באופן פרטי - לא נגענו בו כדי לא לשכתב עבודה קיימת,
# אבל מ-005 ואילך כמה מיגרציות שונות צריכות את אותה פעולה
# בדיוק, ולכן היא מרוכזת כאן פעם אחת.
# ============================================================


def add_column_if_missing(cursor, table, column, column_def):
    """מוסיף עמודה לטבלה קיימת רק אם היא עוד לא קיימת - בטוח להרצה חוזרת."""
    cursor.execute(f"PRAGMA table_info({table})")
    existing = [row[1] for row in cursor.fetchall()]
    if column not in existing:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_def}")
        print(f"  {table}.{column} added")
    else:
        print(f"  {table}.{column} already exists - skipped")
