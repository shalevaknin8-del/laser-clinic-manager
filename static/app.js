// ============================================================
// static/app.js
// לוגיקת צד לקוח - מחברת בין templates/index.html ל-API של app.py.
//
// הקובץ מאורגן לפי סדר קריאה הגיוני:
//   1. קבועים (תוויות בעברית לסטטוסים/מקורות)
//   2. פונקציות עזר כלליות (DOM, אבטחה, פורמט)
//   3. מערכת Toast (הודעות חולפות)
//   4. מערכת מודלים + דיאלוג אישור כללי
//   5. עטיפת fetch ל-API
//   6. ניהול מצב טבלה (טעינה / נתונים / ריק)
//   7. ולידציה בצד לקוח (מקבילה ל-utils/validators.py בפייתון)
//   8. ניווט בין 6 המסכים
//   9. לוגיקת כל מסך: דשבורד, תורים, לקוחות, טיפולים, חשבוניות, לידים
//   10. אתחול (init) - מחבר הכל כשהדף נטען
//
// עקרון מרכזי: הקובץ הזה לא כותב שום SQL ולא נוגע ב-DB ישירות.
// כל בקשה עוברת fetch ל-app.py, וזה שקורא ל-Managers.
// ============================================================

'use strict';


// ============================================================
// 1. קבועים - תוויות בעברית ומיפוי צבעים לפי סטטוס
// ============================================================

// תוויות סטטוס - משותפות לתורים ולידים (המחלקות badge-* מוגדרות ב-CSS)
const STATUS_LABELS = {
    pending: 'ממתין',
    completed: 'הושלם',
    cancelled: 'בוטל',
    new: 'חדש',
    in_progress: 'בטיפול',
    converted: 'הומר ללקוח',
    rejected: 'נדחה',
};

// תוויות מקור ליד - תואם בדיוק לרשימה הקבועה ב-app.py (VALID_LEAD_SOURCES)
const SOURCE_LABELS = {
    facebook: 'פייסבוק',
    instagram: 'אינסטגרם',
    google: 'גוגל',
    referral: 'הפניה',
    walk_in: 'הליכה חופשית',
};

// מטמון מקומי - נשמר כדי לא לשלוח בקשת API בכל פעולה קטנה
// (למשל חיפוש לקוח, או מציאת פרטי טיפול לעריכה)
// מתעדכן מחדש בכל טעינה של המסך המתאים
let clientsCache = [];
let treatmentsCache = [];
let leadsCache = [];

// מזהה הפעולה שתתבצע אם המשתמש ילחץ "אישור" בדיאלוג האישור הכללי
let pendingConfirmAction = null;


// ============================================================
// 2. פונקציות עזר כלליות
// ============================================================

function qs(selector, root) {
    return (root || document).querySelector(selector);
}

function qsa(selector, root) {
    return Array.from((root || document).querySelectorAll(selector));
}

// ממיר טקסט חופשי ל-HTML בטוח - מונע החדרת קוד (XSS) כשמציגים
// שמות/הערות שהוזנו ע"י המשתמש בתוך innerHTML
function escapeHtml(value) {
    const div = document.createElement('div');
    div.textContent = value === null || value === undefined ? '' : String(value);
    return div.innerHTML;
}

// עיצוב סכום כספי אחיד לכל האתר: "250 ש"ח"
function formatCurrency(amount) {
    const number = Number(amount) || 0;
    return `${number.toLocaleString('he-IL')} ש"ח`;
}

// תאריך היום בפורמט YYYY-MM-DD - ברירת מחדל נוחה בטופס חשבונית
function todayIso() {
    const now = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

// בונה תג <span class="badge"> צבעוני לפי סטטוס
function renderStatusBadge(status) {
    const label = STATUS_LABELS[status] || status;
    return `<span class="badge badge-${escapeHtml(status)}">${escapeHtml(label)}</span>`;
}


// ============================================================
// 3. מערכת Toast - הודעות הצלחה/שגיאה שנעלמות לבד
// ============================================================

function showToast(message, type) {
    const container = qs('#toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type === 'error' ? 'error' : 'success'}`;
    toast.textContent = message;
    container.appendChild(toast);

    // אחרי 3.2 שניות - דוהה ונעלם, ואז מוסר מה-DOM
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 200);
    }, 3200);
}


// ============================================================
// 4. מערכת מודלים + דיאלוג אישור כללי
// ============================================================

function openModal(modalId) {
    qs('#' + modalId).hidden = false;
}

function closeModal(modalId) {
    qs('#' + modalId).hidden = true;
}

// מציג את דיאלוג האישור הכללי עם כותרת/הודעה מותאמות, ומריץ
// את onConfirm רק אם המשתמש באמת לחץ "אישור"
function showConfirm(title, message, onConfirm) {
    qs('#confirm-title').textContent = title;
    qs('#confirm-message').textContent = message;
    pendingConfirmAction = onConfirm;
    openModal('confirm-dialog');
}

function wireModalsAndConfirm() {
    // כל כפתור סגירה (X או "ביטול") מצביע דרך data-close-modal על ה-id שיש לסגור
    qsa('[data-close-modal]').forEach((btn) => {
        btn.addEventListener('click', () => closeModal(btn.dataset.closeModal));
    });

    // לחיצה על הרקע הכהה מחוץ לתיבה עצמה - סוגרת את המודל
    qsa('.modal-overlay').forEach((overlay) => {
        overlay.addEventListener('click', (event) => {
            if (event.target === overlay) {
                closeModal(overlay.id);
            }
        });
    });

    // מקש Escape סוגר את המודל הפתוח כרגע (אם יש)
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            const openOverlay = qs('.modal-overlay:not([hidden])');
            if (openOverlay) {
                closeModal(openOverlay.id);
            }
        }
    });

    // כפתורי דיאלוג האישור עצמו
    qs('#confirm-cancel-btn').addEventListener('click', () => {
        pendingConfirmAction = null;
        closeModal('confirm-dialog');
    });

    qs('#confirm-ok-btn').addEventListener('click', async () => {
        const action = pendingConfirmAction;
        pendingConfirmAction = null;
        closeModal('confirm-dialog');
        if (action) {
            await action();
        }
    });
}


// ============================================================
// 5. עטיפת fetch ל-API
// כל הבקשות ל-app.py עוברות דרך הפונקציה הזאת, כדי שכל הטיפול
// בשגיאות (ולידציה / התנגשות / שרת) יהיה במקום אחד
// ============================================================

async function apiRequest(method, path, body) {
    const options = { method, headers: {} };

    if (body !== undefined) {
        options.headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify(body);
    }

    const response = await fetch(path, options);

    // תגובות ללא גוף (למשל DELETE שמצליח) עדיין ננסה לפרש בזהירות
    let data = null;
    try {
        data = await response.json();
    } catch (error) {
        data = null;
    }

    if (!response.ok) {
        // app.py תמיד מחזיר {"error": "...", "field": "..."} בכשלון
        const message = (data && data.error) || 'שגיאה לא צפויה בתקשורת עם השרת';
        const apiError = new Error(message);
        apiError.field = data ? data.field : undefined;
        apiError.status = response.status;
        throw apiError;
    }

    return data;
}


// ============================================================
// 6. ניהול מצב טבלה - טעינה / נתונים / ריק
// כל טבלה במערכת עוברת בין 3 מצבים אלו לפי data-table/-loading-for/-empty-for
// ============================================================

function getTableElements(name) {
    const table = qs(`[data-table="${name}"]`);
    return {
        spinner: qs(`[data-loading-for="${name}"]`),
        tableWrap: table ? table.closest('.table-wrap') : null,
        tbody: table ? table.querySelector('tbody') : null,
        empty: qs(`[data-empty-for="${name}"]`),
    };
}

function setTableLoading(name) {
    const els = getTableElements(name);
    if (els.spinner) els.spinner.hidden = false;
    if (els.tableWrap) els.tableWrap.style.display = 'none';
    if (els.empty) els.empty.hidden = true;
}

// hasRows קובע אם מציגים את הטבלה עצמה או את מצב ה"ריק" המעוצב
function setTableResult(name, hasRows) {
    const els = getTableElements(name);
    if (els.spinner) els.spinner.hidden = true;
    if (els.tableWrap) els.tableWrap.style.display = hasRows ? '' : 'none';
    if (els.empty) els.empty.hidden = hasRows;
}


// ============================================================
// 7. ולידציה בצד לקוח
// מקבילה מכוונת לפונקציות ב-utils/validators.py, כדי לתת משוב
// מיידי בלי לחכות לתשובת שרת. השרת עדיין הבודק הסופי -
// אם הוא מחזיר שגיאה, היא תוצג באותו מקום בדיוק (ראו handleFormError)
// ============================================================

function validateNameLocal(value) {
    const clean = (value || '').trim();
    if (!clean) return 'השם לא יכול להיות ריק';
    if (clean.length < 2) return 'השם קצר מדי - נדרשים לפחות 2 תווים';
    if (clean.length > 50) return 'השם ארוך מדי - עד 50 תווים';
    if (/\d/.test(clean)) return 'השם לא יכול להכיל ספרות';
    return null;
}

function validatePhoneLocal(value) {
    const clean = (value || '').trim();
    if (!clean) return 'מספר הטלפון לא יכול להיות ריק';
    if (!/^0\d{1,2}-?\d{7}$/.test(clean)) {
        return 'מספר טלפון לא תקין - נדרש פורמט כמו 0501234567';
    }
    return null;
}

function validateEmailLocal(value) {
    const clean = (value || '').trim();
    if (!clean) return null; // שדה רשות - ריק תקין

    if (!clean.includes('@')) return 'כתובת אימייל לא תקינה - חסר סימן @';

    const domainPart = clean.split('@').pop();
    if (!domainPart.includes('.')) return 'כתובת אימייל לא תקינה - חסרה סיומת (למשל .com)';

    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(clean)) return 'כתובת אימייל לא תקינה';

    return null;
}

function validatePositiveNumberLocal(value, fieldLabel) {
    if (value === '' || value === null || value === undefined) {
        return `${fieldLabel} לא יכול להיות ריק`;
    }
    const number = Number(value);
    if (Number.isNaN(number)) return `${fieldLabel} חייב להיות מספר`;
    if (number <= 0) return `${fieldLabel} חייב להיות גדול מאפס`;
    return null;
}

// מציג הודעת שגיאה מתחת לשדה נתון (span.form-error מתויג error-<fieldId>)
// ומסמן את השדה עצמו באדום דרך המחלקה has-error
function setFieldError(fieldId, message) {
    const input = document.getElementById(fieldId);
    const errorEl = document.getElementById('error-' + fieldId);
    if (input) input.classList.toggle('has-error', Boolean(message));
    if (errorEl) errorEl.textContent = message || '';
}

function clearFormErrors(formEl) {
    qsa('.form-error', formEl).forEach((el) => { el.textContent = ''; });
    // .treatment-checklist נכלל כאן כי גם הוא מסומן ב-has-error
    // (בחירת טיפולים היא checkbox-ים, לא input.form-input רגיל)
    qsa('.form-input, .treatment-checklist', formEl).forEach((el) => el.classList.remove('has-error'));
}

// ממפה שגיאת API (עם error.field מ-app.py) לשדה הנכון בטופס,
// לפי מילון ה-mapping הספציפי לאותו טופס. בלי field מתאים - מציגים toast
function handleFormError(error, fieldMap, fallbackMessage) {
    if (error.field && fieldMap[error.field]) {
        setFieldError(fieldMap[error.field], error.message);
    } else {
        showToast(error.message || fallbackMessage, 'error');
    }
}

// מונע לחיצה כפולה על "שמירה" בזמן שהבקשה ל-API עדיין בדרך -
// משבית את הכפתור ומחליף את הטקסט שלו, כדי שהמשתמש יראה שמשהו
// קורה (לא מסך קפוא) ולא ייצור בטעות שני תורים/לקוחות זהים
function setFormBusy(formId, isBusy, busyLabel) {
    const button = qs(`button[form="${formId}"]`);
    if (!button) return;

    if (isBusy) {
        button.dataset.originalLabel = button.textContent;
        button.textContent = busyLabel || 'שומר...';
        button.disabled = true;
    } else {
        button.textContent = button.dataset.originalLabel || button.textContent;
        button.disabled = false;
    }
}

// ממלא <select> באפשרויות מתוך מערך פריטים, עם escaping לתווית
function fillSelectOptions(selectEl, items, valueKey, labelFn, placeholder) {
    const options = [`<option value="" disabled selected>${escapeHtml(placeholder)}</option>`];
    items.forEach((item) => {
        options.push(`<option value="${item[valueKey]}">${escapeHtml(labelFn(item))}</option>`);
    });
    selectEl.innerHTML = options.join('');
}


// ============================================================
// 8. ניווט בין 6 המסכים
// ============================================================

// מפה בין שם מסך לפונקציית הטעינה שלו - מורצת בכל מעבר למסך
const SCREEN_LOADERS = {
    dashboard: loadDashboard,
    appointments: loadAppointments,
    clients: loadClients,
    treatments: loadTreatments,
    invoices: loadInvoices,
    leads: loadLeads,
};

function switchScreen(screenName) {
    qsa('.screen').forEach((section) => {
        section.classList.toggle('is-active', section.dataset.screen === screenName);
    });
    qsa('.nav-item').forEach((btn) => {
        btn.classList.toggle('is-active', btn.dataset.target === screenName);
    });

    const loader = SCREEN_LOADERS[screenName];
    if (loader) loader();
}

function wireNavigation() {
    qsa('.nav-item').forEach((btn) => {
        btn.addEventListener('click', () => switchScreen(btn.dataset.target));
    });
}


// ============================================================
// 9. לוגיקת המסכים
// ============================================================

// ---------------------------------------------------------------
// 9.1 דשבורד
// ---------------------------------------------------------------

async function loadDashboard() {
    setTableLoading('today-appointments');

    try {
        const data = await apiRequest('GET', '/api/dashboard');

        qs('[data-field="today-appointments-count"]').textContent = data.today_appointments.length;
        qs('[data-field="clients-count"]').textContent = data.clients_count;
        qs('[data-field="month-revenue"]').textContent = formatCurrency(data.month_revenue);
        qs('[data-field="open-leads-count"]').textContent = data.open_leads;

        const tbody = getTableElements('today-appointments').tbody;
        tbody.innerHTML = data.today_appointments.map((appt) => `
            <tr>
                <td>${escapeHtml(appt.appointment_time)}</td>
                <td>${escapeHtml(appt.client_name)}</td>
                <td>${escapeHtml(appt.treatment_name)}</td>
                <td>${renderStatusBadge(appt.status)}</td>
            </tr>
        `).join('');

        setTableResult('today-appointments', data.today_appointments.length > 0);
    } catch (error) {
        showToast(error.message || 'שגיאה בטעינת הדשבורד', 'error');
        setTableResult('today-appointments', false);
    }
}


// ---------------------------------------------------------------
// 9.2 תורים
// ---------------------------------------------------------------

const APPOINTMENT_FIELD_MAP = {
    client_id: 'appt-client',
    treatment_id: 'appt-treatment',
    appointment_date: 'appt-date',
    appointment_time: 'appt-time',
    status: 'appt-status',
};

async function loadAppointments() {
    setTableLoading('appointments');

    try {
        const rows = await apiRequest('GET', '/api/appointments');
        const tbody = getTableElements('appointments').tbody;

        tbody.innerHTML = rows.map((appt) => `
            <tr>
                <td>#${appt.appointment_id}</td>
                <td>${escapeHtml(appt.client_name)}</td>
                <td>${escapeHtml(appt.treatment_names.join(', '))}</td>
                <td>${formatCurrency(appt.total_price)}</td>
                <td>${appt.total_duration_minutes} דק'</td>
                <td>${escapeHtml(appt.appointment_date)}</td>
                <td>${escapeHtml(appt.appointment_time)}</td>
                <td>${renderStatusBadge(appt.status)}</td>
                <td class="table-actions">
                    <button type="button" class="btn-icon" data-action="edit-appointment"
                            data-id="${appt.appointment_id}" title="עריכה">✎</button>
                    <button type="button" class="btn-icon btn-icon-danger" data-action="delete-appointment"
                            data-id="${appt.appointment_id}" title="מחיקה">🗑</button>
                </td>
            </tr>
        `).join('');

        setTableResult('appointments', rows.length > 0);
    } catch (error) {
        showToast(error.message || 'שגיאה בטעינת תורים', 'error');
        setTableResult('appointments', false);
    }
}

// רשימת הטיפולים הזמינה לבחירה בטופס - נטענת פעם אחת בכל פתיחת
// מודל, ומשמשת גם לרינדור ה-checkbox-ים וגם לחישוב הסה"כ בזמן אמת
let appointmentModalTreatments = [];

// בונה checkbox אחד לכל טיפול בקטלוג, עם מחיר/משך לתצוגה
function renderTreatmentChecklist(selectedIds) {
    const container = qs('#appt-treatment');
    const selectedSet = new Set((selectedIds || []).map(Number));

    if (appointmentModalTreatments.length === 0) {
        container.innerHTML = '<p class="treatment-checklist-empty">הקטלוג ריק - יש להוסיף טיפולים במסך "טיפולים" קודם</p>';
        return;
    }

    container.innerHTML = appointmentModalTreatments.map((t) => `
        <label class="treatment-checklist-item">
            <input type="checkbox" name="treatment_ids" value="${t.treatment_id}"
                   data-price="${t.price}" data-duration="${t.duration_minutes}"
                   ${selectedSet.has(t.treatment_id) ? 'checked' : ''}>
            <span>${escapeHtml(t.treatment_name)}</span>
            <span class="item-price">${formatCurrency(t.price)} · ${t.duration_minutes} דק'</span>
        </label>
    `).join('');
}

// קורא את כל ה-checkbox-ים המסומנים כרגע בטופס התור
function getSelectedTreatmentIds() {
    return qsa('#appt-treatment input[type="checkbox"]:checked')
        .map((input) => Number(input.value));
}

// מחשב ומציג סה"כ מחיר ומשך לפי הטיפולים המסומנים - זהו הלב של
// "טיפול מרוכב": העלות והזמן הכוללים מחושבים מיד, לפני השמירה
function updateComboTotals() {
    const checked = qsa('#appt-treatment input[type="checkbox"]:checked');
    const totalsEl = qs('#appt-combo-totals');

    if (checked.length === 0) {
        totalsEl.hidden = true;
        return;
    }

    let totalPrice = 0;
    let totalDuration = 0;
    checked.forEach((input) => {
        totalPrice += Number(input.dataset.price);
        totalDuration += Number(input.dataset.duration);
    });

    const countLabel = checked.length === 1 ? 'טיפול אחד נבחר' : `${checked.length} טיפולים נבחרו`;
    totalsEl.textContent = `${countLabel} · סה"כ: ${formatCurrency(totalPrice)} · ${totalDuration} דקות`;
    totalsEl.hidden = false;
}

// פותח את המודל במצב "הוספה" (בלי appointmentId) או "עריכה" (עם מזהה)
async function openAppointmentModal(mode, appointmentId) {
    const form = qs('#form-appointment');
    form.reset();
    clearFormErrors(form);
    qs('#appt-id').value = '';
    qs('#appt-conflict-alert').hidden = true;
    qs('#appt-available-slots').hidden = true;
    qs('#appt-combo-totals').hidden = true;
    qs('#appt-status-group').hidden = true;

    let selectedTreatmentIds = [];

    // תמיד טוענים לקוחות וטיפולים עדכניים למילוי הטופס
    try {
        const [clients, treatments] = await Promise.all([
            apiRequest('GET', '/api/clients'),
            apiRequest('GET', '/api/treatments'),
        ]);
        fillSelectOptions(qs('#appt-client'), clients, 'client_id',
            (c) => `${c.full_name} - ${c.phone}`, 'בחר לקוח...');
        appointmentModalTreatments = treatments;
    } catch (error) {
        showToast('שגיאה בטעינת רשימת לקוחות/טיפולים', 'error');
    }

    if (mode === 'edit') {
        qs('#modal-appointment-title').textContent = 'עריכת תור';
        qs('#appt-status-group').hidden = false;

        try {
            const appt = await apiRequest('GET', `/api/appointments/${appointmentId}`);
            qs('#appt-id').value = appt.appointment_id;
            qs('#appt-client').value = appt.client_id;
            qs('#appt-date').value = appt.appointment_date;
            qs('#appt-time').value = appt.appointment_time;
            qs('#appt-status').value = appt.status;
            qs('#appt-notes').value = appt.notes || '';
            selectedTreatmentIds = appt.treatment_ids;
        } catch (error) {
            showToast(error.message || 'שגיאה בטעינת התור', 'error');
        }
    } else {
        qs('#modal-appointment-title').textContent = 'הוספת תור חדש';
    }

    renderTreatmentChecklist(selectedTreatmentIds);
    updateComboTotals();

    openModal('modal-appointment');
}

// מציג את השעות הפנויות ליום/טיפולים שנבחרו - רק במצב הוספה.
// במצב עריכה מדלגים: available-slots לא יודע להתעלם מהתור שאנחנו
// עצמו עורכים, אז השעה הנוכחית תוצג שגויה כ"תפוסה".
// בדיקת ההתנגשות האמיתית עדיין קורית בזמן השמירה (check-conflict
// עם exclude_appointment_id דרך ה-PUT), כך שהנתונים תמיד נכונים.
async function updateAvailableSlots() {
    const hint = qs('#appt-available-slots');

    if (qs('#appt-id').value) {
        hint.hidden = true;
        return;
    }

    const date = qs('#appt-date').value;
    const treatmentIds = getSelectedTreatmentIds();
    if (!date || treatmentIds.length === 0) {
        hint.hidden = true;
        return;
    }

    try {
        const params = new URLSearchParams({ date, treatment_ids: treatmentIds.join(',') });
        const data = await apiRequest('GET', `/api/appointments/available-slots?${params}`);
        renderAvailableSlots(data.available_slots);
    } catch (error) {
        hint.hidden = true;
    }
}

function renderAvailableSlots(slots) {
    const hint = qs('#appt-available-slots');

    if (slots.length === 0) {
        hint.innerHTML = '<span>אין שעות פנויות בתאריך זה</span>';
    } else {
        const shown = slots.slice(0, 16);
        const chips = shown.map((time) => (
            `<button type="button" class="slot-chip" data-action="pick-slot" data-time="${time}">${time}</button>`
        )).join('');
        const more = slots.length > shown.length ? ` ועוד ${slots.length - shown.length}...` : '';
        hint.innerHTML = `<span>שעות פנויות:</span> ${chips}${more}`;
    }

    hint.hidden = false;
}

async function handleAppointmentSubmit(event) {
    event.preventDefault();
    const form = event.target;
    clearFormErrors(form);
    qs('#appt-conflict-alert').hidden = true;

    const clientId = qs('#appt-client').value;
    const treatmentIds = getSelectedTreatmentIds();
    const date = qs('#appt-date').value;
    const time = qs('#appt-time').value;
    const notes = qs('#appt-notes').value.trim();
    const appointmentId = qs('#appt-id').value;

    let hasError = false;
    if (!clientId) { setFieldError('appt-client', 'יש לבחור לקוח'); hasError = true; }
    if (treatmentIds.length === 0) { setFieldError('appt-treatment', 'יש לבחור טיפול אחד לפחות'); hasError = true; }
    if (!date) { setFieldError('appt-date', 'התאריך לא יכול להיות ריק'); hasError = true; }
    if (!time) { setFieldError('appt-time', 'השעה לא יכולה להיות ריקה'); hasError = true; }
    if (hasError) return;

    const payload = {
        client_id: Number(clientId),
        treatment_ids: treatmentIds,
        appointment_date: date,
        appointment_time: time,
        notes: notes || null,
    };
    if (appointmentId) {
        payload.status = qs('#appt-status').value;
    }

    setFormBusy('form-appointment', true);
    try {
        if (appointmentId) {
            await apiRequest('PUT', `/api/appointments/${appointmentId}`, payload);
            showToast('התור עודכן בהצלחה', 'success');
        } else {
            await apiRequest('POST', '/api/appointments', payload);
            showToast('התור נקבע בהצלחה', 'success');
        }
        closeModal('modal-appointment');
        loadAppointments();
    } catch (error) {
        if (error.field && APPOINTMENT_FIELD_MAP[error.field]) {
            setFieldError(APPOINTMENT_FIELD_MAP[error.field], error.message);
        } else {
            // בעיקר התנגשות שעות (409 בלי field ספציפי) - מוצג בתיבת ההתראה הייעודית
            qs('#appt-conflict-alert').textContent = error.message || 'שמירת התור נכשלה';
            qs('#appt-conflict-alert').hidden = false;
        }
    } finally {
        setFormBusy('form-appointment', false);
    }
}

function wireAppointmentsScreen() {
    qs('#btn-add-appointment').addEventListener('click', () => openAppointmentModal('add'));
    qs('#appt-date').addEventListener('change', updateAvailableSlots);
    qs('#form-appointment').addEventListener('submit', handleAppointmentSubmit);

    // האזנה יחידה על מיכל ה-checkbox-ים (event delegation) - עובד
    // גם אחרי ש-renderTreatmentChecklist מחליף את התוכן הפנימי שלו
    qs('#appt-treatment').addEventListener('change', (event) => {
        if (event.target.matches('input[type="checkbox"]')) {
            updateComboTotals();
            updateAvailableSlots();
        }
    });
}


// ---------------------------------------------------------------
// 9.3 לקוחות
// ---------------------------------------------------------------

const CLIENT_FIELD_MAP = {
    full_name: 'client-name',
    phone: 'client-phone',
    email: 'client-email',
};

function renderClientsTable(clients) {
    const tbody = getTableElements('clients').tbody;
    tbody.innerHTML = clients.map((client) => `
        <tr>
            <td>#${client.client_id}</td>
            <td>${escapeHtml(client.full_name)}</td>
            <td>${escapeHtml(client.phone)}</td>
            <td>${escapeHtml(client.email || '-')}</td>
            <td>${escapeHtml(client.address || '-')}</td>
            <td class="table-actions">
                <button type="button" class="btn-icon" data-action="history-client"
                        data-id="${client.client_id}" title="היסטוריה">🕒</button>
                <button type="button" class="btn-icon" data-action="edit-client"
                        data-id="${client.client_id}" title="עריכה">✎</button>
                <button type="button" class="btn-icon btn-icon-danger" data-action="delete-client"
                        data-id="${client.client_id}" title="מחיקה">🗑</button>
            </td>
        </tr>
    `).join('');
    setTableResult('clients', clients.length > 0);
}

async function loadClients() {
    setTableLoading('clients');
    try {
        clientsCache = await apiRequest('GET', '/api/clients');
        qs('#client-search').value = '';
        renderClientsTable(clientsCache);
    } catch (error) {
        showToast(error.message || 'שגיאה בטעינת לקוחות', 'error');
        setTableResult('clients', false);
    }
}

// חיפוש לקוח - סינון מקומי מיידי על המטמון, בלי לפנות שוב לשרת
function handleClientSearch(event) {
    const term = event.target.value.trim().toLowerCase();
    const filtered = clientsCache.filter((client) => (
        client.full_name.toLowerCase().includes(term) || client.phone.includes(term)
    ));
    renderClientsTable(filtered);
}

function openClientModal(mode, clientId) {
    const form = qs('#form-client');
    form.reset();
    clearFormErrors(form);
    qs('#client-id').value = '';

    if (mode === 'edit') {
        const client = clientsCache.find((c) => c.client_id === clientId);
        qs('#modal-client-title').textContent = 'עריכת לקוח';
        if (client) {
            qs('#client-id').value = client.client_id;
            qs('#client-name').value = client.full_name;
            qs('#client-phone').value = client.phone;
            qs('#client-email').value = client.email || '';
            qs('#client-address').value = client.address || '';
        }
    } else {
        qs('#modal-client-title').textContent = 'הוספת לקוח חדש';
    }

    openModal('modal-client');
}

async function openClientHistoryModal(clientId) {
    openModal('modal-client-history');
    qs('#modal-client-history-title').textContent = 'היסטוריית לקוח';

    try {
        const data = await apiRequest('GET', `/api/clients/${clientId}/history`);
        qs('#modal-client-history-title').textContent = `היסטוריה - ${data.client.full_name}`;

        const apptTbody = getTableElements('client-history-appointments').tbody;
        apptTbody.innerHTML = data.appointments.map((appt) => `
            <tr>
                <td>${escapeHtml(appt.appointment_date)}</td>
                <td>${escapeHtml(appt.appointment_time)}</td>
                <td>${escapeHtml(appt.treatment_name || '-')}</td>
                <td>${renderStatusBadge(appt.status)}</td>
            </tr>
        `).join('');
        setTableResult('client-history-appointments', data.appointments.length > 0);

        const invTbody = getTableElements('client-history-invoices').tbody;
        invTbody.innerHTML = data.invoices.map((inv) => `
            <tr>
                <td>${escapeHtml(inv.invoice_number)}</td>
                <td>${formatCurrency(inv.amount)}</td>
                <td>${escapeHtml(inv.invoice_date)}</td>
                <td>${inv.is_cancelled
                    ? '<span class="badge badge-cancelled">מבוטלת</span>'
                    : '<span class="badge badge-completed">פעילה</span>'}</td>
            </tr>
        `).join('');
        setTableResult('client-history-invoices', data.invoices.length > 0);

        qs('[data-field="client-history-total"]').textContent = formatCurrency(data.total_active_amount);
    } catch (error) {
        showToast(error.message || 'שגיאה בטעינת ההיסטוריה', 'error');
        closeModal('modal-client-history');
    }
}

async function handleClientSubmit(event) {
    event.preventDefault();
    const form = event.target;
    clearFormErrors(form);

    const fullName = qs('#client-name').value;
    const phone = qs('#client-phone').value;
    const email = qs('#client-email').value;
    const address = qs('#client-address').value.trim();
    const clientId = qs('#client-id').value;

    const nameError = validateNameLocal(fullName);
    const phoneError = validatePhoneLocal(phone);
    const emailError = validateEmailLocal(email);

    let hasError = false;
    if (nameError) { setFieldError('client-name', nameError); hasError = true; }
    if (phoneError) { setFieldError('client-phone', phoneError); hasError = true; }
    if (emailError) { setFieldError('client-email', emailError); hasError = true; }
    if (hasError) return;

    const payload = {
        full_name: fullName.trim(),
        phone: phone.trim(),
        email: email.trim() || null,
        address: address || null,
    };

    setFormBusy('form-client', true);
    try {
        if (clientId) {
            await apiRequest('PUT', `/api/clients/${clientId}`, payload);
            showToast('פרטי הלקוח עודכנו', 'success');
        } else {
            await apiRequest('POST', '/api/clients', payload);
            showToast('הלקוח נוסף בהצלחה', 'success');
        }
        closeModal('modal-client');
        loadClients();
    } catch (error) {
        handleFormError(error, CLIENT_FIELD_MAP, 'שמירת הלקוח נכשלה');
    } finally {
        setFormBusy('form-client', false);
    }
}

function wireClientsScreen() {
    qs('#btn-add-client').addEventListener('click', () => openClientModal('add'));
    qs('#client-search').addEventListener('input', handleClientSearch);
    qs('#form-client').addEventListener('submit', handleClientSubmit);
}


// ---------------------------------------------------------------
// 9.4 טיפולים
// ---------------------------------------------------------------

const TREATMENT_FIELD_MAP = {
    treatment_name: 'treatment-name',
    body_area: 'treatment-area',
    price: 'treatment-price',
    duration_minutes: 'treatment-duration',
};

async function loadTreatments() {
    setTableLoading('treatments');
    try {
        treatmentsCache = await apiRequest('GET', '/api/treatments');
        const tbody = getTableElements('treatments').tbody;

        tbody.innerHTML = treatmentsCache.map((treatment) => `
            <tr>
                <td>#${treatment.treatment_id}</td>
                <td>${escapeHtml(treatment.treatment_name)}</td>
                <td>${escapeHtml(treatment.body_area)}</td>
                <td>${formatCurrency(treatment.price)}</td>
                <td>${treatment.duration_minutes}</td>
                <td class="table-actions">
                    <button type="button" class="btn-icon" data-action="edit-treatment"
                            data-id="${treatment.treatment_id}" title="עריכה">✎</button>
                </td>
            </tr>
        `).join('');

        setTableResult('treatments', treatmentsCache.length > 0);
    } catch (error) {
        showToast(error.message || 'שגיאה בטעינת טיפולים', 'error');
        setTableResult('treatments', false);
    }
}

function openTreatmentModal(mode, treatmentId) {
    const form = qs('#form-treatment');
    form.reset();
    clearFormErrors(form);
    qs('#treatment-id').value = '';

    if (mode === 'edit') {
        const treatment = treatmentsCache.find((t) => t.treatment_id === treatmentId);
        qs('#modal-treatment-title').textContent = 'עריכת טיפול';
        if (treatment) {
            qs('#treatment-id').value = treatment.treatment_id;
            qs('#treatment-name').value = treatment.treatment_name;
            qs('#treatment-area').value = treatment.body_area;
            qs('#treatment-price').value = treatment.price;
            qs('#treatment-duration').value = treatment.duration_minutes;
        }
    } else {
        qs('#modal-treatment-title').textContent = 'הוספת טיפול';
    }

    openModal('modal-treatment');
}

async function handleTreatmentSubmit(event) {
    event.preventDefault();
    const form = event.target;
    clearFormErrors(form);

    const name = qs('#treatment-name').value;
    const area = qs('#treatment-area').value;
    const price = qs('#treatment-price').value;
    const duration = qs('#treatment-duration').value;
    const treatmentId = qs('#treatment-id').value;

    let hasError = false;
    if (!name.trim()) { setFieldError('treatment-name', 'שם הטיפול לא יכול להיות ריק'); hasError = true; }
    if (!area.trim()) { setFieldError('treatment-area', 'יש להזין לפחות איזור אחד'); hasError = true; }

    const priceError = validatePositiveNumberLocal(price, 'המחיר');
    if (priceError) { setFieldError('treatment-price', priceError); hasError = true; }

    const durationError = validatePositiveNumberLocal(duration, 'משך הטיפול');
    if (durationError) { setFieldError('treatment-duration', durationError); hasError = true; }

    if (hasError) return;

    const payload = {
        treatment_name: name.trim(),
        body_area: area.trim(),
        price: Number(price),
        duration_minutes: Number(duration),
    };

    setFormBusy('form-treatment', true);
    try {
        if (treatmentId) {
            await apiRequest('PUT', `/api/treatments/${treatmentId}`, payload);
            showToast('הטיפול עודכן', 'success');
        } else {
            await apiRequest('POST', '/api/treatments', payload);
            showToast('הטיפול נוסף לקטלוג', 'success');
        }
        closeModal('modal-treatment');
        loadTreatments();
    } catch (error) {
        handleFormError(error, TREATMENT_FIELD_MAP, 'שמירת הטיפול נכשלה');
    } finally {
        setFormBusy('form-treatment', false);
    }
}

async function handleSeedTreatments() {
    try {
        const result = await apiRequest('POST', '/api/treatments/seed');
        if (result.added_count > 0) {
            showToast(`נוספו ${result.added_count} טיפולים לקטלוג`, 'success');
        } else {
            showToast('הקטלוג כבר מכיל טיפולים - לא בוצע שינוי', 'success');
        }
        loadTreatments();
    } catch (error) {
        showToast(error.message || 'אתחול הקטלוג נכשל', 'error');
    }
}

function wireTreatmentsScreen() {
    qs('#btn-add-treatment').addEventListener('click', () => openTreatmentModal('add'));
    qs('#btn-seed-treatments').addEventListener('click', handleSeedTreatments);
    qs('#form-treatment').addEventListener('submit', handleTreatmentSubmit);
}


// ---------------------------------------------------------------
// 9.5 חשבוניות
// ---------------------------------------------------------------

const INVOICE_FIELD_MAP = {
    client_id: 'invoice-client',
    amount: 'invoice-amount',
    invoice_date: 'invoice-date',
    appointment_id: 'invoice-appointment',
};

async function loadInvoices() {
    setTableLoading('invoices');
    const includeCancelled = qs('#invoices-show-cancelled').checked;

    try {
        const [invoices, clients] = await Promise.all([
            apiRequest('GET', `/api/invoices?include_cancelled=${includeCancelled}`),
            apiRequest('GET', '/api/clients'),
        ]);

        // ל-invoice יש רק client_id - בונים מפה מהירה כדי להציג שם לקוח בטבלה
        const clientNameById = {};
        clients.forEach((client) => { clientNameById[client.client_id] = client.full_name; });

        const tbody = getTableElements('invoices').tbody;
        tbody.innerHTML = invoices.map((invoice) => {
            const clientName = clientNameById[invoice.client_id] || `#${invoice.client_id}`;
            const statusBadge = invoice.is_cancelled
                ? '<span class="badge badge-cancelled">מבוטלת</span>'
                : '<span class="badge badge-completed">פעילה</span>';
            const actionButton = invoice.is_cancelled
                ? `<button type="button" class="btn-icon" data-action="restore-invoice"
                           data-id="${invoice.invoice_id}" title="שחזור">↩</button>`
                : `<button type="button" class="btn-icon btn-icon-danger" data-action="cancel-invoice"
                           data-id="${invoice.invoice_id}" title="ביטול">✕</button>`;

            return `
                <tr>
                    <td>${escapeHtml(invoice.invoice_number)}</td>
                    <td>${escapeHtml(clientName)}</td>
                    <td>${formatCurrency(invoice.amount)}</td>
                    <td>${escapeHtml(invoice.invoice_date)}</td>
                    <td>${statusBadge}</td>
                    <td class="table-actions">${actionButton}</td>
                </tr>
            `;
        }).join('');

        setTableResult('invoices', invoices.length > 0);

        const activeTotal = invoices
            .filter((invoice) => !invoice.is_cancelled)
            .reduce((sum, invoice) => sum + invoice.amount, 0);
        qs('[data-field="invoices-total"]').textContent = formatCurrency(activeTotal);
    } catch (error) {
        showToast(error.message || 'שגיאה בטעינת חשבוניות', 'error');
        setTableResult('invoices', false);
    }
}

async function openInvoiceModal() {
    const form = qs('#form-invoice');
    form.reset();
    clearFormErrors(form);

    try {
        const [clients, appointments] = await Promise.all([
            apiRequest('GET', '/api/clients'),
            apiRequest('GET', '/api/appointments'),
        ]);

        fillSelectOptions(qs('#invoice-client'), clients, 'client_id',
            (c) => `${c.full_name} - ${c.phone}`, 'בחר לקוח...');

        const appointmentSelect = qs('#invoice-appointment');
        const options = ['<option value="" selected>ללא קישור לתור</option>'];
        appointments.forEach((appt) => {
            const label = `#${appt.appointment_id} - ${appt.client_name} - ${appt.treatment_name} (${appt.appointment_date})`;
            options.push(`<option value="${appt.appointment_id}">${escapeHtml(label)}</option>`);
        });
        appointmentSelect.innerHTML = options.join('');
    } catch (error) {
        showToast('שגיאה בטעינת רשימת לקוחות/תורים', 'error');
    }

    qs('#invoice-date').value = todayIso();
    openModal('modal-invoice');
}

async function handleInvoiceSubmit(event) {
    event.preventDefault();
    const form = event.target;
    clearFormErrors(form);

    const clientId = qs('#invoice-client').value;
    const amount = qs('#invoice-amount').value;
    const date = qs('#invoice-date').value;
    const appointmentId = qs('#invoice-appointment').value;

    let hasError = false;
    if (!clientId) { setFieldError('invoice-client', 'יש לבחור לקוח'); hasError = true; }

    const amountError = validatePositiveNumberLocal(amount, 'הסכום');
    if (amountError) { setFieldError('invoice-amount', amountError); hasError = true; }

    if (!date) { setFieldError('invoice-date', 'התאריך לא יכול להיות ריק'); hasError = true; }
    if (hasError) return;

    const payload = {
        client_id: Number(clientId),
        amount: Number(amount),
        invoice_date: date,
        appointment_id: appointmentId ? Number(appointmentId) : null,
    };

    setFormBusy('form-invoice', true, 'מפיק...');
    try {
        const result = await apiRequest('POST', '/api/invoices', payload);
        showToast(`הופקה חשבונית ${result.invoice_number}`, 'success');
        closeModal('modal-invoice');
        loadInvoices();
    } catch (error) {
        handleFormError(error, INVOICE_FIELD_MAP, 'הפקת החשבונית נכשלה');
    } finally {
        setFormBusy('form-invoice', false);
    }
}

function wireInvoicesScreen() {
    qs('#btn-add-invoice').addEventListener('click', openInvoiceModal);
    qs('#invoices-show-cancelled').addEventListener('change', loadInvoices);
    qs('#form-invoice').addEventListener('submit', handleInvoiceSubmit);
}


// ---------------------------------------------------------------
// 9.6 לידים
// ---------------------------------------------------------------

const LEAD_FIELD_MAP = {
    full_name: 'lead-name',
    phone: 'lead-phone',
    source: 'lead-source',
    status: 'lead-status',
};

async function loadLeads() {
    setTableLoading('leads');
    try {
        leadsCache = await apiRequest('GET', '/api/leads');
        const tbody = getTableElements('leads').tbody;

        tbody.innerHTML = leadsCache.map((lead) => {
            const convertButton = lead.status === 'converted' ? '' : (
                `<button type="button" class="btn-icon" data-action="convert-lead"
                         data-id="${lead.lead_id}" title="המרה ללקוח">➜</button>`
            );

            return `
                <tr>
                    <td>#${lead.lead_id}</td>
                    <td>${escapeHtml(lead.full_name)}</td>
                    <td>${escapeHtml(lead.phone)}</td>
                    <td>${escapeHtml(SOURCE_LABELS[lead.source] || lead.source || '-')}</td>
                    <td>${renderStatusBadge(lead.status)}</td>
                    <td>${escapeHtml(lead.notes || '-')}</td>
                    <td class="table-actions">
                        ${convertButton}
                        <button type="button" class="btn-icon" data-action="edit-lead"
                                data-id="${lead.lead_id}" title="עריכה">✎</button>
                        <button type="button" class="btn-icon btn-icon-danger" data-action="delete-lead"
                                data-id="${lead.lead_id}" title="מחיקה">🗑</button>
                    </td>
                </tr>
            `;
        }).join('');

        setTableResult('leads', leadsCache.length > 0);
    } catch (error) {
        showToast(error.message || 'שגיאה בטעינת לידים', 'error');
        setTableResult('leads', false);
    }
}

function openLeadModal(mode, leadId) {
    const form = qs('#form-lead');
    form.reset();
    clearFormErrors(form);
    qs('#lead-id').value = '';
    qs('#lead-status-group').hidden = true;

    if (mode === 'edit') {
        const lead = leadsCache.find((l) => l.lead_id === leadId);
        qs('#modal-lead-title').textContent = 'עריכת ליד';
        qs('#lead-status-group').hidden = false;
        if (lead) {
            qs('#lead-id').value = lead.lead_id;
            qs('#lead-name').value = lead.full_name;
            qs('#lead-phone').value = lead.phone;
            qs('#lead-source').value = lead.source || '';
            qs('#lead-status').value = lead.status;
            qs('#lead-notes').value = lead.notes || '';
        }
    } else {
        qs('#modal-lead-title').textContent = 'הוספת ליד חדש';
    }

    openModal('modal-lead');
}

async function handleLeadSubmit(event) {
    event.preventDefault();
    const form = event.target;
    clearFormErrors(form);

    const name = qs('#lead-name').value;
    const phone = qs('#lead-phone').value;
    const source = qs('#lead-source').value;
    const notes = qs('#lead-notes').value.trim();
    const leadId = qs('#lead-id').value;

    const nameError = validateNameLocal(name);
    const phoneError = validatePhoneLocal(phone);

    let hasError = false;
    if (nameError) { setFieldError('lead-name', nameError); hasError = true; }
    if (phoneError) { setFieldError('lead-phone', phoneError); hasError = true; }
    if (hasError) return;

    const payload = {
        full_name: name.trim(),
        phone: phone.trim(),
        source: source || null,
        notes: notes || null,
    };
    if (leadId) {
        payload.status = qs('#lead-status').value;
    }

    setFormBusy('form-lead', true);
    try {
        if (leadId) {
            await apiRequest('PUT', `/api/leads/${leadId}`, payload);
            showToast('הליד עודכן', 'success');
        } else {
            await apiRequest('POST', '/api/leads', payload);
            showToast('הליד נוסף בהצלחה', 'success');
        }
        closeModal('modal-lead');
        loadLeads();
    } catch (error) {
        handleFormError(error, LEAD_FIELD_MAP, 'שמירת הליד נכשלה');
    } finally {
        setFormBusy('form-lead', false);
    }
}

function openLeadConvertModal(leadId) {
    const lead = leadsCache.find((l) => l.lead_id === leadId);
    const form = qs('#form-lead-convert');
    form.reset();
    clearFormErrors(form);
    qs('#lead-convert-id').value = leadId;
    qs('#lead-convert-summary').textContent = lead
        ? `המרת "${lead.full_name}" (${lead.phone}) ללקוח קבוע`
        : '';
    openModal('modal-lead-convert');
}

async function handleLeadConvertSubmit(event) {
    event.preventDefault();
    const form = event.target;
    clearFormErrors(form);

    const leadId = qs('#lead-convert-id').value;
    const email = qs('#lead-convert-email').value;
    const address = qs('#lead-convert-address').value.trim();

    const emailError = validateEmailLocal(email);
    if (emailError) { setFieldError('lead-convert-email', emailError); return; }

    setFormBusy('form-lead-convert', true, 'ממיר...');
    try {
        const client = await apiRequest('POST', `/api/leads/${leadId}/convert`, {
            email: email.trim() || null,
            address: address || null,
        });
        showToast(`הליד הומר ללקוח #${client.client_id} בהצלחה`, 'success');
        closeModal('modal-lead-convert');
        loadLeads();
    } catch (error) {
        if (error.field === 'email') {
            setFieldError('lead-convert-email', error.message);
        } else {
            showToast(error.message || 'ההמרה נכשלה', 'error');
        }
    } finally {
        setFormBusy('form-lead-convert', false);
    }
}

function wireLeadsScreen() {
    qs('#btn-add-lead').addEventListener('click', () => openLeadModal('add'));
    qs('#form-lead').addEventListener('submit', handleLeadSubmit);
    qs('#form-lead-convert').addEventListener('submit', handleLeadConvertSubmit);
}


// ============================================================
// פעולות טבלה דינמיות (עריכה/מחיקה/וכו') - Event Delegation
// הטבלאות נבנות מחדש בכל טעינה, אז במקום לחבר מאזין לכל כפתור
// בנפרד, מאזינים פעם אחת ברמת ה-document ובודקים data-action
// ============================================================

function wireRowActions() {
    document.addEventListener('click', (event) => {
        const button = event.target.closest('[data-action]');
        if (!button) return;

        const action = button.dataset.action;
        const id = button.dataset.id ? Number(button.dataset.id) : null;

        switch (action) {
            case 'edit-appointment':
                openAppointmentModal('edit', id);
                break;

            case 'delete-appointment':
                showConfirm('מחיקת תור', 'האם למחוק את התור? לא ניתן לשחזר פעולה זו.', async () => {
                    try {
                        await apiRequest('DELETE', `/api/appointments/${id}`);
                        showToast('התור נמחק', 'success');
                        loadAppointments();
                    } catch (error) {
                        showToast(error.message || 'המחיקה נכשלה', 'error');
                    }
                });
                break;

            case 'edit-client':
                openClientModal('edit', id);
                break;

            case 'history-client':
                openClientHistoryModal(id);
                break;

            case 'delete-client':
                showConfirm('מחיקת לקוח', 'האם למחוק את הלקוח? פעולה זו אינה הפיכה.', async () => {
                    try {
                        await apiRequest('DELETE', `/api/clients/${id}`);
                        showToast('הלקוח נמחק', 'success');
                        loadClients();
                    } catch (error) {
                        showToast(error.message || 'המחיקה נכשלה', 'error');
                    }
                });
                break;

            case 'edit-treatment':
                openTreatmentModal('edit', id);
                break;

            case 'cancel-invoice':
                showConfirm(
                    'ביטול חשבונית',
                    'לפי חוק לא ניתן למחוק חשבונית שהונפקה - רק לבטל אותה. להמשיך?',
                    async () => {
                        try {
                            await apiRequest('POST', `/api/invoices/${id}/cancel`);
                            showToast('החשבונית בוטלה', 'success');
                            loadInvoices();
                        } catch (error) {
                            showToast(error.message || 'הביטול נכשל', 'error');
                        }
                    }
                );
                break;

            case 'restore-invoice':
                (async () => {
                    try {
                        await apiRequest('POST', `/api/invoices/${id}/restore`);
                        showToast('החשבונית שוחזרה', 'success');
                        loadInvoices();
                    } catch (error) {
                        showToast(error.message || 'השחזור נכשל', 'error');
                    }
                })();
                break;

            case 'edit-lead':
                openLeadModal('edit', id);
                break;

            case 'delete-lead':
                showConfirm('מחיקת ליד', 'האם למחוק את הליד?', async () => {
                    try {
                        await apiRequest('DELETE', `/api/leads/${id}`);
                        showToast('הליד נמחק', 'success');
                        loadLeads();
                    } catch (error) {
                        showToast(error.message || 'המחיקה נכשלה', 'error');
                    }
                });
                break;

            case 'convert-lead':
                openLeadConvertModal(id);
                break;

            case 'pick-slot':
                qs('#appt-time').value = button.dataset.time;
                break;

            default:
                break;
        }
    });
}


// ============================================================
// 10. אתחול - מריץ פעם אחת כשה-DOM מוכן
// ============================================================

function init() {
    wireNavigation();
    wireModalsAndConfirm();
    wireRowActions();

    wireAppointmentsScreen();
    wireClientsScreen();
    wireTreatmentsScreen();
    wireInvoicesScreen();
    wireLeadsScreen();

    // המסך הראשון שמוצג הוא הדשבורד (מסומן is-active כברירת מחדל ב-HTML)
    loadDashboard();
}

document.addEventListener('DOMContentLoaded', init);
