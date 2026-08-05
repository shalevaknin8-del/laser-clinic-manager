-- ============================================================
-- Laser Clinic Manager — Database Schema
-- קליניקת לייזר של דנה — סכמת בסיס נתונים
-- ============================================================


-- ============================================================
-- Table 1: clients (לקוחות)
-- שומרת את כל הלקוחות של הקליניקה
-- ============================================================
CREATE TABLE IF NOT EXISTS clients (
    client_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name       TEXT NOT NULL,
    phone           TEXT NOT NULL,
    email           TEXT,
    address         TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- Table 2: treatments (קטלוג טיפולים)
-- רשימת כל סוגי הטיפולים שהקליניקה מציעה
-- ============================================================
CREATE TABLE IF NOT EXISTS treatments (
    treatment_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    treatment_name      TEXT NOT NULL,
    body_area           TEXT,
    price               REAL NOT NULL,
    duration_minutes    INTEGER NOT NULL
);

-- ============================================================
-- Table 3: appointments (תורים) — הטבלה המרכזית של המערכת
-- כל תור מקושר ללקוח (client_id) ולטיפול (treatment_id)
-- ============================================================
CREATE TABLE IF NOT EXISTS appointments (
    appointment_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id           INTEGER NOT NULL,
    treatment_id        INTEGER NOT NULL,
    appointment_date    TEXT NOT NULL,
    appointment_time    TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'pending',
    notes               TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (client_id) REFERENCES clients(client_id),
    FOREIGN KEY (treatment_id) REFERENCES treatments(treatment_id)
);

-- ============================================================
-- Table 4: invoices (חשבוניות מס)
-- כל חשבונית מקושרת ללקוח, ואופציונלית גם לתור ספציפי
-- ============================================================
CREATE TABLE IF NOT EXISTS invoices (
    invoice_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number      TEXT NOT NULL UNIQUE,
    client_id           INTEGER NOT NULL,
    appointment_id      INTEGER,
    amount              REAL NOT NULL,
    invoice_date        TEXT NOT NULL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_cancelled        INTEGER NOT NULL DEFAULT 0,
    cancelled_at        TIMESTAMP,
    
    FOREIGN KEY (client_id) REFERENCES clients(client_id),
    FOREIGN KEY (appointment_id) REFERENCES appointments(appointment_id)
);

-- ============================================================
-- Table 5: leads (לידים - לקוחות פוטנציאליים)
-- מעקב אחר פניות חדשות לפני שהופכות ללקוחות
-- ============================================================
CREATE TABLE IF NOT EXISTS leads (
    lead_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name           TEXT NOT NULL,
    phone               TEXT NOT NULL,
    source              TEXT,
    status              TEXT NOT NULL DEFAULT 'new',
    notes               TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);