# ============================================================
# managers/invoice_manager.py
# מנהל החשבוניות - אחראי על ניהול חשבוניות מס בקליניקה
# מכיל 5 מתודות CRUD + פונקציה פנימית ליצירת מספר חשבונית אוטומטי
# ============================================================

from datetime import datetime
from database import get_connection
from entities.invoice import Invoice


class InvoiceManager:
    """
    Manager Class לניהול חשבוניות מס.
    מייצר מספרי חשבונית אוטומטיים בפורמט YYYY-NNNN (למשל: 2026-0001).
    """

    def _generate_next_invoice_number(self):
        """
        מייצר את מספר החשבונית הבא בפורמט YYYY-NNNN.
        מוצא את המספר הכי גבוה בשנה הנוכחית ומוסיף 1.
        אם אין חשבוניות השנה - מתחיל מ-0001.
        
        פונקציה פנימית (מסומנת ב-_) - לשימוש רק בתוך המחלקה.
        """
        # שולפים את השנה הנוכחית מהמערכת - עדכני תמיד
        current_year = datetime.now().year
        year_prefix = f"{current_year}-"
        
        connection = get_connection()
        cursor = connection.cursor()
        
        # חשוב: השאילתה סופרת גם חשבוניות מבוטלות!
        # כך מספר של חשבונית שבוטלה לעולם לא יינתן שוב - דרישת חוק
        sql_query = "SELECT MAX(invoice_number) FROM invoices WHERE invoice_number LIKE ?"
        cursor.execute(sql_query, (f"{year_prefix}%",))
        result = cursor.fetchone()
        connection.close()
        
        # result[0] יהיה None אם אין חשבוניות השנה
        max_number = result[0]
        
        if max_number is None:
            # חשבונית ראשונה של השנה - מתחילים מ-1
            next_number = 1
        else:
            # מפצלים את המספר לפי המקף: "2026-0047" -> ["2026", "0047"]
            # לוקחים את החלק השני והופכים למספר: "0047" -> 47
            # מוסיפים 1: 47 -> 48
            sequential_part = max_number.split("-")[1]
            next_number = int(sequential_part) + 1
        
        # zfill(4) מוסיף אפסים מקדימים כדי להגיע ל-4 ספרות
        # 48 -> "0048", 1 -> "0001", 9999 -> "9999"
        formatted_sequential = str(next_number).zfill(4)
        
        # מרכיבים את המספר הסופי: "2026-0048"
        return f"{year_prefix}{formatted_sequential}"


    def insert_invoice(self, invoice):
        """
        מוסיף חשבונית חדשה לבסיס הנתונים.
        מייצר מספר חשבונית אוטומטית ומעדכן את האובייקט.
        מחזיר את האובייקט המעודכן עם invoice_number ו-invoice_id.
        """
        # מייצרים את מספר החשבונית לפני ההוספה
        invoice.invoice_number = self._generate_next_invoice_number()
        
        connection = get_connection()
        cursor = connection.cursor()
        
        sql_query = """
            INSERT INTO invoices (
                invoice_number, client_id, appointment_id, amount, invoice_date
            ) VALUES (?, ?, ?, ?, ?)
        """
        
        values = (
            invoice.invoice_number,
            invoice.client_id,
            invoice.appointment_id,
            invoice.amount,
            invoice.invoice_date
        )
        
        cursor.execute(sql_query, values)
        invoice.invoice_id = cursor.lastrowid
        
        connection.commit()
        connection.close()
        
        return invoice


    def get_invoice_by_id(self, invoice_id):
        """
        שולף חשבונית לפי מזהה טכני (invoice_id).
        מחזיר אובייקט Invoice, או None אם לא נמצא.
        """
        connection = get_connection()
        cursor = connection.cursor()
        
        sql_query = "SELECT * FROM invoices WHERE invoice_id = ?"
        cursor.execute(sql_query, (invoice_id,))
        
        row = cursor.fetchone()
        connection.close()
        
        if row is None:
            return None
        
        # סדר העמודות ב-DB:
        # 0=invoice_id, 1=invoice_number, 2=client_id, 3=appointment_id,
        # 4=amount, 5=invoice_date, 6=created_at, 7=is_cancelled, 8=cancelled_at
        invoice = Invoice(
            invoice_id=row[0],
            invoice_number=row[1],
            client_id=row[2],
            appointment_id=row[3],
            amount=row[4],
            invoice_date=row[5],
            is_cancelled=row[7],
            cancelled_at=row[8]
        )
        
        return invoice


    def get_all_invoices(self, include_cancelled=False):
        """
        שולף חשבוניות מהמערכת.
        
        include_cancelled=False (ברירת מחדל) - רק חשבוניות פעילות
        include_cancelled=True - כולל מבוטלות (לביקורת מס)
        
        ממוין לפי מספר חשבונית - מהחדש לישן.
        """
        connection = get_connection()
        cursor = connection.cursor()

        # בונים את השאילתה לפי הבקשה
        if include_cancelled:
            sql_query = "SELECT * FROM invoices ORDER BY invoice_number DESC"
        else:
            sql_query = """
                SELECT * FROM invoices
                WHERE is_cancelled = 0
                ORDER BY invoice_number DESC
            """

        cursor.execute(sql_query)
        rows = cursor.fetchall()
        connection.close()

        invoices = []
        for row in rows:
            invoice = Invoice(
                invoice_id=row[0],
                invoice_number=row[1],
                client_id=row[2],
                appointment_id=row[3],
                amount=row[4],
                invoice_date=row[5],
                is_cancelled=row[7],
                cancelled_at=row[8]
            )
            invoices.append(invoice)

        return invoices
        


    def update_invoice(self, invoice):
        """
        מעדכן חשבונית קיימת.
        שים לב: לא מאפשר לשנות את invoice_number (חוקי מס הכנסה!)
        רק סכום, תאריך, וקישור לתור ניתנים לעדכון.
        מחזיר True אם עודכן, False אם לא נמצא.
        """
        if invoice.invoice_id is None:
            return False
        
        connection = get_connection()
        cursor = connection.cursor()
        
        # שים לב - invoice_number NOT בשאילתה! לא מעדכנים אותו לעולם
        sql_query = """
            UPDATE invoices
            SET client_id = ?,
                appointment_id = ?,
                amount = ?,
                invoice_date = ?
            WHERE invoice_id = ?
        """
        
        values = (
            invoice.client_id,
            invoice.appointment_id,
            invoice.amount,
            invoice.invoice_date,
            invoice.invoice_id
        )
        
        cursor.execute(sql_query, values)
        rows_affected = cursor.rowcount
        
        connection.commit()
        connection.close()
        
        return rows_affected > 0


    def delete_invoice(self, invoice_id):
        """
        מחיקת חשבונית - חסומה בכוונה!
        
        לפי חוקי מס הכנסה בישראל, אסור למחוק חשבונית שהונפקה.
        חשבונית שגויה מבוטלת (cancel_invoice) ולא נמחקת.
        
        מחזיר תמיד False, ומדפיס הסבר למשתמש.
        """
        print("לא ניתן למחוק חשבונית - זו דרישת חוק")
        print("להפסקת תוקף החשבונית יש להשתמש בביטול (cancel_invoice)")
        return False


    def cancel_invoice(self, invoice_id):
        """
        מבטל חשבונית - Soft Delete.
        החשבונית נשארת בבסיס הנתונים ומסומנת כמבוטלת.
        
        מחזיר True אם בוטלה, False אם לא נמצאה או כבר מבוטלת.
        """
        # שולפים כדי לבדוק שקיימת ושעדיין לא מבוטלת
        invoice = self.get_invoice_by_id(invoice_id)

        if invoice is None:
            print(f"חשבונית #{invoice_id} לא נמצאה")
            return False

        if invoice.is_cancelled:
            print(f"חשבונית {invoice.invoice_number} כבר מבוטלת")
            return False

        connection = get_connection()
        cursor = connection.cursor()

        # מסמנים כמבוטלת ורושמים את זמן הביטול
        sql_query = """
            UPDATE invoices
            SET is_cancelled = 1,
                cancelled_at = CURRENT_TIMESTAMP
            WHERE invoice_id = ?
        """

        cursor.execute(sql_query, (invoice_id,))
        rows_affected = cursor.rowcount

        connection.commit()
        connection.close()

        if rows_affected > 0:
            print(f"חשבונית {invoice.invoice_number} בוטלה")
            return True

        return False


    def restore_invoice(self, invoice_id):
        """
        משחזר חשבונית שבוטלה בטעות.
        מחזיר True אם שוחזרה, False אחרת.
        """
        invoice = self.get_invoice_by_id(invoice_id)

        if invoice is None:
            print(f"חשבונית #{invoice_id} לא נמצאה")
            return False

        if not invoice.is_cancelled:
            print(f"חשבונית {invoice.invoice_number} כבר פעילה")
            return False

        connection = get_connection()
        cursor = connection.cursor()

        sql_query = """
            UPDATE invoices
            SET is_cancelled = 0,
                cancelled_at = NULL
            WHERE invoice_id = ?
        """

        cursor.execute(sql_query, (invoice_id,))
        rows_affected = cursor.rowcount

        connection.commit()
        connection.close()

        if rows_affected > 0:
            print(f"חשבונית {invoice.invoice_number} שוחזרה")
            return True

        return False