// ============================================================
// static/app.js
// לוגיקת צד הלקוח של ממשק הניהול - SPA פשוט מבוסס hash routing.
//
// אימות: JWT ולא session cookie (ראו auth/decorators.py). הטוקנים
// נשמרים ב-localStorage, ומצורפים כ-Authorization: Bearer בכל
// קריאה. apiFetch מטפל ברענון אוטומטי כשה-access token פג.
// ============================================================

const ACCESS_KEY = "clinic_access_token";
const REFRESH_KEY = "clinic_refresh_token";

const state = {
    user: null,
    route: "dashboard",
    treatments: [],
    rooms: [],
    machines: [],
    staff: [],
};

// ============================================================
// API client
// ============================================================

function getAccessToken() { return localStorage.getItem(ACCESS_KEY); }
function getRefreshToken() { return localStorage.getItem(REFRESH_KEY); }

function setTokens(access, refresh) {
    localStorage.setItem(ACCESS_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
}

function clearTokens() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
}

async function refreshAccessToken() {
    const refreshToken = getRefreshToken();
    if (!refreshToken) return false;

    const response = await fetch("/api/auth/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!response.ok) return false;
    const data = await response.json();
    setTokens(data.access_token, null);
    return true;
}

/**
 * עוטף fetch רגיל: מצרף Bearer token, ומנסה רענון פעם אחת אם
 * הבקשה חוזרת עם 401 (access token פג באמצע העבודה).
 */
async function apiFetch(path, options = {}) {
    const doFetch = () => {
        const headers = Object.assign({}, options.headers || {});
        const token = getAccessToken();
        if (token) headers["Authorization"] = "Bearer " + token;
        if (options.body && !(options.body instanceof FormData) && !headers["Content-Type"]) {
            headers["Content-Type"] = "application/json";
        }
        return fetch(path, Object.assign({}, options, { headers }));
    };

    let response = await doFetch();

    if (response.status === 401 && getRefreshToken()) {
        const refreshed = await refreshAccessToken();
        if (refreshed) {
            response = await doFetch();
        }
    }

    if (response.status === 401) {
        clearTokens();
        window.location.href = "/login";
        throw new Error("not authenticated");
    }

    return response;
}

async function apiJson(path, options = {}) {
    const response = await apiFetch(path, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        const error = new Error(data.error || "שגיאה לא צפויה");
        error.field = data.field;
        error.status = response.status;
        error.payload = data;
        throw error;
    }
    return data;
}

// ============================================================
// UI helpers: toasts, modal, confirm
// ============================================================

function toast(message, kind) {
    const stack = document.getElementById("toastStack");
    const el = document.createElement("div");
    el.className = "toast" + (kind ? " " + kind : "");
    el.textContent = message;
    stack.appendChild(el);
    setTimeout(() => el.remove(), 3600);
}

function escapeHtml(value) {
    if (value === null || value === undefined) return "";
    return String(value)
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function formatDateHe(isoDate) {
    if (!isoDate || isoDate.length !== 10) return isoDate || "";
    const [y, m, d] = isoDate.split("-");
    return `${d}.${m}.${y}`;
}

function todayIso() {
    return new Date().toISOString().slice(0, 10);
}

// ============================================================
// צביעת תורים לפי טיפול - כרונית ליזואלית בלבד, בלי קטגוריה
// אמיתית ב-DB. הגיבוב יציב (אותו טיפול תמיד מקבל אותו צבע),
// כך שהמראה עקבי בכל מקום שבו מוצג תור (יומן, לוח בקרה).
// ============================================================

const TINTS = ["pink", "sage", "blue", "gold"];
const TINT_COLORS = {
    pink: { bg: "var(--pink-bg)", dot: "var(--pink-dot)" },
    sage: { bg: "var(--sage-bg)", dot: "var(--sage-dot)" },
    blue: { bg: "var(--blue-bg)", dot: "var(--blue-dot)" },
    gold: { bg: "var(--gold-bg)", dot: "var(--gold-bar)" },
};

function tintFor(key) {
    const text = String(key || "");
    let hash = 0;
    for (let i = 0; i < text.length; i++) hash = (hash * 31 + text.charCodeAt(i)) >>> 0;
    return TINTS[hash % TINTS.length];
}

function trendBadgeHtml(current, previous) {
    if (previous === 0 && current === 0) return "";
    const delta = current - previous;
    if (delta === 0) return `<span class="badge muted">ללא שינוי</span>`;
    const up = delta > 0;
    const cls = up ? "sage" : "pink";
    const arrow = up ? "↑" : "↓";
    return `<span class="badge ${cls}">${arrow} ${Math.abs(delta)}</span>`;
}

let modalCloseHandler = null;

function openModal(titleHtml, bodyHtml, { onMount } = {}) {
    closeModal();
    const overlay = document.createElement("div");
    overlay.className = "overlay";
    overlay.id = "modalOverlay";
    overlay.innerHTML = `<div class="modal"><h2 class="modal-title">${titleHtml}</h2>${bodyHtml}</div>`;
    overlay.addEventListener("mousedown", (e) => { if (e.target === overlay) closeModal(); });
    document.body.appendChild(overlay);
    modalCloseHandler = () => overlay.remove();
    if (onMount) onMount(overlay);
    return overlay;
}

function closeModal() {
    if (modalCloseHandler) { modalCloseHandler(); modalCloseHandler = null; }
}

function confirmAction(message) {
    return new Promise((resolve) => {
        openModal("אישור פעולה", `
            <p style="font-size:14px;color:var(--muted);margin:0;">${escapeHtml(message)}</p>
            <div class="modal-actions">
                <button class="btn btn-ghost" id="confirmCancel">ביטול</button>
                <button class="btn btn-danger" id="confirmOk">אישור</button>
            </div>
        `, {
            onMount: (overlay) => {
                overlay.querySelector("#confirmCancel").onclick = () => { closeModal(); resolve(false); };
                overlay.querySelector("#confirmOk").onclick = () => { closeModal(); resolve(true); };
            },
        });
    });
}

// ============================================================
// אתחול: בדיקת התחברות, טעינת נתוני בסיס, הפעלת ניתוב
// ============================================================

async function boot() {
    if (!getAccessToken()) {
        window.location.href = "/login";
        return;
    }

    try {
        const me = await apiJson("/api/auth/me");
        state.user = me.user;
    } catch (e) {
        return; // apiFetch כבר הפנה ל-/login
    }

    renderShell();
    await loadReferenceData();

    window.addEventListener("hashchange", handleRoute);
    handleRoute();
}

async function loadReferenceData() {
    try {
        const [treatments, rooms, machines, staffList] = await Promise.all([
            apiJson("/api/treatments"),
            apiJson("/api/rooms"),
            apiJson("/api/machines"),
            apiJson("/api/users").then((r) => r.users).catch(() => []),
        ]);
        state.treatments = treatments;
        state.rooms = rooms;
        state.machines = machines;
        state.staff = staffList;
    } catch (e) {
        // נתוני עזר בלבד - כשל כאן לא אמור לחסום את שאר הממשק
    }
}

function hasPermission(permission) {
    return !!(state.user && state.user.permissions && state.user.permissions.includes(permission));
}

// ============================================================
// מעטפת האפליקציה: תפריט צד + כותרת עליונה
// ============================================================

const NAV_ITEMS = [
    { key: "dashboard", label: "לוח בקרה", icon: "dashboard" },
    { key: "calendar", label: "יומן וזימונים", icon: "calendar" },
    { key: "clients", label: "לקוחות", icon: "clients" },
    { key: "leads", label: "צינור לידים", icon: "leads" },
    { key: "packages", label: "קטלוג וחבילות", icon: "packages" },
    { key: "resources", label: "מכשירים וחדרים", icon: "resources" },
    { key: "staff", label: "צוות וזמינות", icon: "staff" },
    { key: "invoices", label: "חשבוניות", icon: "invoices" },
    { key: "audit", label: "יומן ביקורת", icon: "audit" },
];

const SIDEBAR_COLLAPSED_KEY = "clinic_sidebar_collapsed";

function renderShell() {
    const initials = (state.user.full_name || "").trim().split(/\s+/).map((w) => w[0]).slice(0, 2).join("");
    const collapsed = localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "1";

    document.getElementById("app").innerHTML = `
        <div class="app-shell">
            <aside class="sidebar${collapsed ? " collapsed" : ""}" id="sidebar">
                <div class="brand">
                    <div class="brand-mark"><span></span></div>
                    <div>
                        <div class="brand-name">קליניקת לייזר</div>
                        <div class="brand-sub">ממשק ניהול</div>
                    </div>
                </div>
                <nav class="nav" id="sideNav"></nav>
                <div class="sidebar-footer">
                    <div class="collapse-toggle" id="collapseToggle" title="כיווץ תפריט">${ICONS.collapse(16)}</div>
                    <div class="sidebar-user">
                        <div class="avatar">${escapeHtml(initials)}</div>
                        <div>
                            <div class="sidebar-user-name">${escapeHtml(state.user.full_name)}</div>
                            <div class="sidebar-user-role">${escapeHtml(state.user.role_label)}</div>
                        </div>
                        <div class="sidebar-logout" id="logoutBtn">התנתקות</div>
                    </div>
                </div>
            </aside>
            <main class="main">
                <header class="topbar">
                    <div class="flex-1">
                        <div class="crumb" id="crumb"></div>
                        <h1 class="page-title" id="pageTitle"></h1>
                    </div>
                    <div class="flex items-center gap-8" id="topbarActions"></div>
                </header>
                <div class="page-body" id="pageBody"></div>
            </main>
        </div>
        <div class="toast-stack" id="toastStack"></div>
    `;

    document.getElementById("sideNav").innerHTML = NAV_ITEMS.map((item) => (
        `<div class="nav-item" data-route="${item.key}" title="${escapeHtml(item.label)}">
            <span class="nav-item-icon">${ICONS[item.icon] ? ICONS[item.icon](18) : ""}</span>
            <span class="nav-item-label">${escapeHtml(item.label)}</span>
        </div>`
    )).join("");

    document.querySelectorAll(".nav-item").forEach((el) => {
        el.addEventListener("click", () => { window.location.hash = "#" + el.dataset.route; });
    });

    document.getElementById("collapseToggle").addEventListener("click", () => {
        const sidebar = document.getElementById("sidebar");
        const isCollapsed = sidebar.classList.toggle("collapsed");
        localStorage.setItem(SIDEBAR_COLLAPSED_KEY, isCollapsed ? "1" : "0");
    });

    document.getElementById("logoutBtn").addEventListener("click", async () => {
        try { await apiJson("/api/auth/logout", { method: "POST" }); } catch (e) { /* ignore */ }
        clearTokens();
        window.location.href = "/login";
    });
}

function setActiveNav(routeKey) {
    document.querySelectorAll(".nav-item").forEach((el) => {
        el.classList.toggle("active", el.dataset.route === routeKey);
    });
}

function setPageHeader(crumb, title, actionsHtml) {
    document.getElementById("crumb").textContent = crumb;
    document.getElementById("pageTitle").textContent = title;
    document.getElementById("topbarActions").innerHTML = actionsHtml || "";
}

// ============================================================
// ניתוב
// ============================================================

const ROUTES = {
    dashboard: renderDashboard,
    calendar: renderCalendar,
    clients: renderClientsList,
    leads: renderLeads,
    packages: renderPackages,
    resources: renderResources,
    staff: renderStaff,
    invoices: renderInvoices,
    audit: renderAudit,
};

function handleRoute() {
    const hash = (window.location.hash || "#dashboard").slice(1);
    const [routeKey, param] = hash.split("/");
    const handler = ROUTES[routeKey] || renderDashboard;
    setActiveNav(routeKey);
    document.getElementById("pageBody").innerHTML = `<div class="loading-row">טוען...</div>`;
    handler(param);
}

// ============================================================
// לוח בקרה
// ============================================================

async function renderDashboard() {
    setPageHeader("לוח בקרה", `שלום, ${state.user.full_name.split(" ")[0]}`, "");
    const body = document.getElementById("pageBody");

    let data;
    try {
        data = await apiJson("/api/dashboard");
    } catch (e) {
        body.innerHTML = `<div class="loading-row">שגיאה בטעינת הנתונים</div>`;
        return;
    }

    const revenueTrend = data.revenue_trend || { this_month: data.month_revenue, previous_month: 0 };
    const leadsTrend = data.leads_trend || { this_month: data.open_leads, previous_month: 0, by_source: {} };
    const apptTrend = data.appointments_trend || { today_count: data.today_appointments.length, same_weekday_last_week_count: 0 };
    const sourceLabels = { facebook: "פייסבוק", instagram: "אינסטגרם", google: "גוגל", referral: "הפניות", walk_in: "מהרחוב", "אחר": "אחר" };
    const sourceSummary = Object.entries(leadsTrend.by_source)
        .map(([src, count]) => `${count} מ${sourceLabels[src] || src}`)
        .join(", ");

    body.innerHTML = `
        <div class="stack">
            <div class="grid-3">
                <div class="card stat-card">
                    ${sparklineSvg([apptTrend.same_weekday_last_week_count, apptTrend.today_count])}
                    <div class="stat-label">תורי היום</div>
                    <div class="flex items-center gap-8 mt-8">
                        <div class="stat-value num">${apptTrend.today_count}</div>
                        ${trendBadgeHtml(apptTrend.today_count, apptTrend.same_weekday_last_week_count)}
                    </div>
                    <div class="stat-sub">לעומת ${apptTrend.same_weekday_last_week_count} באותו יום שעבר</div>
                </div>
                <div class="card stat-card">
                    ${sparklineSvg([leadsTrend.previous_month, leadsTrend.this_month])}
                    <div class="stat-label">לידים חדשים החודש</div>
                    <div class="flex items-center gap-8 mt-8">
                        <div class="stat-value num">${leadsTrend.this_month}</div>
                        ${trendBadgeHtml(leadsTrend.this_month, leadsTrend.previous_month)}
                    </div>
                    <div class="stat-sub">${sourceSummary || "אין עדיין לידים החודש"}</div>
                </div>
                <div class="card stat-card">
                    ${sparklineSvg([revenueTrend.previous_month, revenueTrend.this_month])}
                    <div class="stat-label">הכנסות החודש</div>
                    <div class="flex items-center gap-8 mt-8">
                        <div class="stat-value num">₪ ${Number(revenueTrend.this_month || 0).toLocaleString("he-IL")}</div>
                        ${trendBadgeHtml(revenueTrend.this_month, revenueTrend.previous_month)}
                    </div>
                    <div class="stat-sub">מול ₪ ${Number(revenueTrend.previous_month || 0).toLocaleString("he-IL")} בחודש שעבר</div>
                </div>
            </div>
            <div class="grid-2" style="grid-template-columns: minmax(0,1.7fr) minmax(0,1fr);">
                <div class="card">
                    <h2 class="card-title">ציר היום</h2>
                    <div id="todayList"></div>
                </div>
                <div class="card">
                    <div class="flex items-center" style="margin-bottom:16px;">
                        <h2 class="card-title" style="margin:0;">דורש מעקב</h2>
                        <span class="text-sm text-muted" style="margin-inline-start:auto;">${data.needs_follow_up.length} מתוך ${data.open_leads}</span>
                    </div>
                    <div id="followUpList"></div>
                </div>
            </div>
        </div>
    `;

    const list = document.getElementById("todayList");
    if (!data.today_appointments.length) {
        list.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">${ICONS.empty(88)}</div>
                <div class="empty-state-title">היומן פנוי היום</div>
                <div class="text-sm">אפשר להתחיל את היום עם תור ראשון</div>
                <button class="btn btn-primary btn-sm" id="emptyStateNewAppt">${ICONS.plus(13)} תור חדש</button>
            </div>`;
        document.getElementById("emptyStateNewAppt").addEventListener("click", () => openAppointmentModal());
    } else {
        list.innerHTML = data.today_appointments.map((a) => {
            const tint = tintFor(a.treatment_name);
            const colors = TINT_COLORS[tint];
            return `
                <div class="flex items-center gap-12" style="padding:10px 6px;border-top:1px solid var(--border-soft);">
                    <div class="num" style="width:52px;font-weight:600;">${escapeHtml(a.appointment_time)}</div>
                    <div class="flex items-center gap-12" style="flex:1;min-width:0;padding:11px 14px;border-radius:14px;background:${colors.bg};">
                        <div style="width:3px;align-self:stretch;border-radius:3px;background:${colors.dot};"></div>
                        <div class="flex-1">
                            <div style="font-weight:600;">${escapeHtml(a.client_name)}</div>
                            <div class="text-sm text-muted">${escapeHtml(a.treatment_name || "")}</div>
                        </div>
                        <span class="text-sm text-muted">${statusLabel(a.status)}</span>
                    </div>
                </div>
            `;
        }).join("");
    }

    const followUp = document.getElementById("followUpList");
    if (!data.needs_follow_up.length) {
        followUp.innerHTML = `<div class="text-sm text-muted">אין לידים שממתינים למעקב</div>`;
    } else {
        followUp.innerHTML = data.needs_follow_up.map((lead) => {
            const initials = (lead.full_name || "").trim().split(/\s+/).map((w) => w[0]).slice(0, 2).join("");
            const tint = tintFor(lead.full_name);
            const colors = TINT_COLORS[tint];
            return `
                <div class="flex items-center gap-12 clickable" data-open-lead="${lead.lead_id}" style="padding:10px 6px;border-radius:12px;">
                    <div class="avatar" style="background:${colors.bg};color:${colors.dot};">${escapeHtml(initials)}</div>
                    <div class="flex-1">
                        <div style="font-weight:600;font-size:13.5px;">${escapeHtml(lead.full_name)}</div>
                        <div class="text-sm text-muted">${escapeHtml(lead.source || "")}</div>
                    </div>
                </div>
            `;
        }).join("");
        followUp.querySelectorAll("[data-open-lead]").forEach((el) => {
            el.addEventListener("click", () => { window.location.hash = "#leads"; });
        });
    }
}

function sparklineSvg(values) {
    // קו מגמה עדין ברקע הכרטיס, לפי שני ערכים אמיתיים בלבד (חודש
    // קודם מול נוכחי, או אותו יום שעבר מול היום) - לא נתונים מומצאים,
    // ראו DESIGN_NOTES.md על העיקרון של 0 אמיתי במקום דמו
    const width = 220, height = 44, padding = 6;
    const safeValues = values.map((v) => Number(v) || 0);
    const maxValue = Math.max(...safeValues, 1);
    const points = safeValues.map((v, i) => {
        const x = padding + (i * (width - padding * 2)) / (safeValues.length - 1 || 1);
        const y = height - padding - (v / maxValue) * (height - padding * 2);
        return `${x},${y}`;
    }).join(" ");
    return `
        <svg class="stat-sparkline" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
            <polyline points="${points}" fill="none" stroke="#DCD8D0" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>`;
}

function statusLabel(status) {
    return { pending: "ממתין", completed: "הושלם", cancelled: "בוטל" }[status] || status;
}
function statusBadgeClass(status) {
    return { pending: "gold", completed: "sage", cancelled: "muted" }[status] || "muted";
}

// ============================================================
// יומן ותורים
// ============================================================

let calendarDate = todayIso();
let calendarView = "week"; // "day" | "week" | "month"
let calendarWeekOffset = 0; // 0 = השבוע הנוכחי
let calendarMonthOffset = 0; // 0 = החודש הנוכחי
let calendarAppointmentsById = {}; // נבנה מחדש בכל renderCalendar - tooltip הריחוף קורא ממנו לפי מזהה, לא מ-JSON בתוך attribute

const CAL_WORK_START_HOUR = 9;
const CAL_WORK_END_HOUR = 19;
const CAL_PX_PER_HOUR = 56;
const CAL_HOURS = Array.from(
    { length: CAL_WORK_END_HOUR - CAL_WORK_START_HOUR },
    (_, i) => `${String(CAL_WORK_START_HOUR + i).padStart(2, "0")}:00`
);
// יום עבודה ישראלי: ראשון עד שישי (6 ימים, בלי שבת) - כמו בעיצוב המקור
const CAL_DAY_NAMES = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי"];

function weekStartFor(isoDate) {
    const d = new Date(isoDate + "T00:00:00");
    d.setDate(d.getDate() - d.getDay()); // getDay(): 0=ראשון, כבר מתאים
    return d;
}

function minutesFromWorkStart(hhmm) {
    const [h, m] = hhmm.split(":").map(Number);
    return (h - CAL_WORK_START_HOUR) * 60 + m;
}

const CAL_VIEWS = [
    { key: "day", label: "יום" },
    { key: "week", label: "שבוע" },
    { key: "month", label: "חודש" },
];

async function renderCalendar() {
    setPageHeader("יומן הקליניקה", "ניהול זימונים", `
        <button class="btn btn-primary" id="newApptBtn">${ICONS.plus(13)} תור חדש</button>
    `);

    document.getElementById("pageBody").innerHTML = `
        <div class="card">
            <div class="cal-toolbar">
                <div class="cal-nav-btn" id="calPrev">${ICONS.chevronBack(15)}</div>
                <div class="cal-nav-btn" id="calNext" style="transform:scaleX(-1);">${ICONS.chevronBack(15)}</div>
                <span class="cal-range-label" id="calLabel"></span>
                <div class="cal-segmented" id="calSegmented">
                    ${CAL_VIEWS.map((v) => `<div class="cal-segment" data-view="${v.key}">${v.label}</div>`).join("")}
                </div>
            </div>
            <div id="calendarBody" style="overflow-x:auto;position:relative;"></div>
        </div>
    `;

    document.getElementById("calPrev").addEventListener("click", () => shiftCalendar(-1));
    document.getElementById("calNext").addEventListener("click", () => shiftCalendar(1));
    document.getElementById("newApptBtn").addEventListener("click", () => openAppointmentModal());

    document.querySelectorAll("#calSegmented .cal-segment").forEach((el) => {
        el.classList.toggle("active", el.dataset.view === calendarView);
        el.addEventListener("click", () => { calendarView = el.dataset.view; renderCalendar(); });
    });

    let appointments;
    try {
        appointments = await apiJson("/api/appointments");
    } catch (e) {
        document.getElementById("calendarBody").innerHTML = `<div class="loading-row">שגיאה בטעינה</div>`;
        return;
    }

    calendarAppointmentsById = {};

    if (calendarView === "week") {
        renderWeekGrid(appointments);
    } else if (calendarView === "month") {
        renderMonthGrid(appointments);
    } else {
        renderDayGrid(appointments);
    }
}

function shiftCalendar(direction) {
    if (calendarView === "week") {
        calendarWeekOffset += direction;
    } else if (calendarView === "month") {
        calendarMonthOffset += direction;
    } else {
        const d = new Date(calendarDate + "T00:00:00");
        d.setDate(d.getDate() + direction);
        calendarDate = d.toISOString().slice(0, 10);
    }
    renderCalendar();
}

function renderDayGrid(appointments) {
    document.getElementById("calLabel").textContent = formatDateHe(calendarDate);
    renderTimeGrid([{ date: calendarDate, name: null }], appointments, true);
}

function renderWeekGrid(appointments) {
    const start = weekStartFor(todayIso());
    start.setDate(start.getDate() + calendarWeekOffset * 7);

    const days = CAL_DAY_NAMES.map((name, i) => {
        const d = new Date(start);
        d.setDate(d.getDate() + i);
        return { date: d.toISOString().slice(0, 10), name };
    });

    const label = `${formatDateHe(days[0].date)} – ${formatDateHe(days[days.length - 1].date)}`;
    document.getElementById("calLabel").textContent = label;
    renderTimeGrid(days, appointments, false);
}

/** מצייר גריד שעות משותף ליום/שבוע - יום הוא גריד עם עמודה אחת. */
function renderTimeGrid(days, appointments, isSingleDay) {
    const container = document.getElementById("calendarBody");
    const gridCols = `54px repeat(${days.length}, minmax(${isSingleDay ? "280px" : "150px"}, 1fr))`;

    const headerHtml = days.map((day) => {
        const isToday = day.date === todayIso();
        return `
            <div style="padding:10px 0 12px;text-align:center;border-inline-start:1px solid var(--border-soft);">
                ${day.name ? `<div class="text-sm text-muted">${day.name}</div>` : ""}
                <div class="num" style="margin-top:2px;font-size:15px;font-weight:500;color:${isToday ? "var(--gold-ink)" : "var(--ink)"};">
                    ${day.date.slice(8, 10)}.${day.date.slice(5, 7)}
                </div>
            </div>
        `;
    }).join("");

    const hourLabelsHtml = CAL_HOURS.map((h) => (
        `<div class="num text-sm text-muted" style="height:${CAL_PX_PER_HOUR}px;padding-top:1px;">${h}</div>`
    )).join("");

    const dayColumnsHtml = days.map((day) => {
        const dayAppointments = appointments.filter((a) => a.appointment_date === day.date);
        const gridLinesHtml = CAL_HOURS.map(() => (
            `<div style="height:${CAL_PX_PER_HOUR}px;border-top:1px solid var(--border-soft);"></div>`
        )).join("");

        const blocksHtml = dayAppointments.map((a) => {
            const tint = tintFor(a.treatment_name);
            const colors = TINT_COLORS[tint];
            const top = (minutesFromWorkStart(a.appointment_time) / 60) * CAL_PX_PER_HOUR;
            const height = Math.max(30, ((a.total_duration_minutes || 30) / 60) * CAL_PX_PER_HOUR - 4);
            if (top < 0 || top > (CAL_WORK_END_HOUR - CAL_WORK_START_HOUR) * CAL_PX_PER_HOUR) return "";
            calendarAppointmentsById[a.appointment_id] = a;
            return `
                <div class="clickable cal-appt-block" data-appt-id="${a.appointment_id}"
                     style="position:absolute;inset-inline:3px;top:${top}px;height:${height}px;border-radius:10px;padding:6px 8px;
                            background:${colors.bg};overflow:hidden;cursor:pointer;">
                    <div style="display:flex;gap:6px;height:100%;">
                        <div style="width:2.5px;border-radius:3px;background:${colors.dot};flex:0 0 auto;"></div>
                        <div style="min-width:0;">
                            <div style="font-size:12.5px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escapeHtml(a.client_name)}</div>
                            <div style="font-size:11px;color:var(--muted);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escapeHtml(a.treatment_name || "")} · ${escapeHtml(a.appointment_time)}</div>
                        </div>
                    </div>
                </div>
            `;
        }).join("");

        return `
            <div style="position:relative;border-inline-start:1px solid var(--border-soft);">
                ${gridLinesHtml}
                ${blocksHtml}
            </div>
        `;
    }).join("");

    container.innerHTML = `
        <div style="display:grid;grid-template-columns:${gridCols};border-top:1px solid var(--border);min-width:${days.length > 1 ? "700px" : "auto"};">
            <div></div>
            ${headerHtml}
        </div>
        <div style="display:grid;grid-template-columns:${gridCols};min-width:${days.length > 1 ? "700px" : "auto"};">
            <div style="display:flex;flex-direction:column;">${hourLabelsHtml}</div>
            ${dayColumnsHtml}
        </div>
    `;

    container.querySelectorAll("[data-appt-id]").forEach((el) => {
        el.addEventListener("click", () => openAppointmentModal(el.dataset.apptId));
        attachApptTooltip(el);
    });

    if (!appointments.some((a) => days.some((d) => d.date === a.appointment_date))) {
        container.insertAdjacentHTML("beforeend", `
            <div class="empty-state"><div class="empty-state-title">אין תורים בטווח הזה</div>
            <div class="text-sm">אפשר להוסיף תור חדש עם הכפתור למעלה</div></div>
        `);
    }
}

/**
 * Part 19 בעיצוב: ריחוף מעל בלוק תור פותח כרטיס צף (246px) עם פרטי
 * התור, ממוקם לפי ה-bounding rect של הבלוק עצמו. נסגר ב-mouseleave.
 */
function attachApptTooltip(el) {
    let tooltipEl = null;

    el.addEventListener("mouseenter", () => {
        const appointment = calendarAppointmentsById[el.dataset.apptId];
        if (!appointment) return;

        const rect = el.getBoundingClientRect();
        tooltipEl = document.createElement("div");
        tooltipEl.className = "cal-tooltip";
        tooltipEl.innerHTML = `
            <div class="cal-tooltip-title">${escapeHtml(appointment.client_name)}</div>
            <div class="cal-tooltip-row">${escapeHtml(appointment.treatment_name || "")}</div>
            <div class="cal-tooltip-row num ltr">${escapeHtml(appointment.appointment_time)} · ${escapeHtml(formatDateHe(appointment.appointment_date))}</div>
            ${appointment.package_progress ? `<div class="cal-tooltip-row">חבילה: ${escapeHtml(appointment.package_progress)}</div>` : ""}
            <div class="cal-tooltip-row">${ICONS.contact(14)} יצירת קשר</div>
        `;
        document.body.appendChild(tooltipEl);

        const tooltipWidth = 246;
        let left = rect.left - tooltipWidth - 10;
        if (left < 8) left = rect.right + 10;
        let top = Math.min(rect.top, window.innerHeight - tooltipEl.offsetHeight - 12);
        tooltipEl.style.left = `${left}px`;
        tooltipEl.style.top = `${Math.max(8, top)}px`;
    });

    el.addEventListener("mouseleave", () => {
        if (tooltipEl) { tooltipEl.remove(); tooltipEl = null; }
    });
}

// ---------- תצוגת חודש ----------

function renderMonthGrid(appointments) {
    const base = new Date(todayIso() + "T00:00:00");
    base.setDate(1);
    base.setMonth(base.getMonth() + calendarMonthOffset);

    document.getElementById("calLabel").textContent = base.toLocaleDateString("he-IL", { month: "long", year: "numeric" });

    // ראשון עד שבת - 42 תאים (6 שבועות), מתחיל מהראשון שלפני/בתחילת החודש
    const firstOfMonth = new Date(base);
    const gridStart = new Date(firstOfMonth);
    gridStart.setDate(gridStart.getDate() - gridStart.getDay());

    const monthIndex = firstOfMonth.getMonth();
    const today = todayIso();

    const appointmentsByDate = {};
    appointments.forEach((a) => {
        (appointmentsByDate[a.appointment_date] = appointmentsByDate[a.appointment_date] || []).push(a);
    });

    const headHtml = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"]
        .map((name) => `<div class="cal-month-head">${name}</div>`).join("");

    const cellsHtml = Array.from({ length: 42 }, (_, i) => {
        const d = new Date(gridStart);
        d.setDate(d.getDate() + i);
        const dateStr = d.toISOString().slice(0, 10);
        const isOutside = d.getMonth() !== monthIndex;
        const isToday = dateStr === today;
        const dayAppointments = appointmentsByDate[dateStr] || [];
        const dotsHtml = dayAppointments.slice(0, 5).map((a) => {
            const colors = TINT_COLORS[tintFor(a.treatment_name)];
            return `<span class="cal-month-dot" style="background:${colors.dot};"></span>`;
        }).join("");

        return `
            <div class="cal-month-cell${isOutside ? " outside" : ""}" data-month-date="${dateStr}">
                <div class="cal-month-date num${isToday ? " today" : ""}">${d.getDate()}</div>
                <div class="cal-month-dots">${dotsHtml}</div>
            </div>
        `;
    }).join("");

    document.getElementById("calendarBody").innerHTML = `
        <div class="cal-month-grid">${headHtml}${cellsHtml}</div>
    `;

    document.querySelectorAll("[data-month-date]").forEach((el) => {
        el.addEventListener("click", () => {
            calendarDate = el.dataset.monthDate;
            calendarView = "day";
            renderCalendar();
        });
    });
}

function treatmentOptionsHtml(selectedIds) {
    return state.treatments.map((t) => (
        `<option value="${t.treatment_id}" ${selectedIds && selectedIds.includes(t.treatment_id) ? "selected" : ""}>${escapeHtml(t.treatment_name)} (${t.duration_minutes} דק')</option>`
    )).join("");
}

async function openAppointmentModal(appointmentId) {
    let existing = null;
    let clients = [];
    try {
        clients = await apiJson("/api/clients");
        if (appointmentId) existing = await apiJson(`/api/appointments/${appointmentId}`);
    } catch (e) {
        toast("שגיאה בטעינת נתונים", "error");
        return;
    }

    const clientOptions = clients.map((c) => (
        `<option value="${c.client_id}" ${existing && existing.client_id === c.client_id ? "selected" : ""}>${escapeHtml(c.full_name)}</option>`
    )).join("");

    const staffOptions = state.staff.map((u) => (
        `<option value="${u.user_id}" ${existing && existing.staff_user_id === u.user_id ? "selected" : ""}>${escapeHtml(u.full_name)}</option>`
    )).join("");
    const roomOptions = state.rooms.map((r) => (
        `<option value="${r.room_id}" ${existing && existing.room_id === r.room_id ? "selected" : ""}>${escapeHtml(r.name)}</option>`
    )).join("");

    openModal(existing ? "עריכת תור" : "תור חדש", `
        <div class="field"><label>לקוחה</label><select id="apptClient">${clientOptions}</select></div>
        <div class="field"><label>טיפולים (אפשר לבחור כמה)</label>
            <select id="apptTreatments" multiple size="4">${treatmentOptionsHtml(existing ? existing.treatment_ids : [])}</select>
        </div>
        <div class="field-row">
            <div class="field"><label>תאריך</label><input type="date" id="apptDate" value="${existing ? existing.appointment_date : calendarDate}"></div>
            <div class="field"><label>שעה</label><input type="time" id="apptTime" value="${existing ? existing.appointment_time : ""}"></div>
        </div>
        <div class="field-row">
            <div class="field"><label>חדר (רשות)</label><select id="apptRoom"><option value="">ללא</option>${roomOptions}</select></div>
            <div class="field"><label>עובדת (רשות)</label><select id="apptStaff"><option value="">ללא</option>${staffOptions}</select></div>
        </div>
        ${existing ? `
        <div class="field"><label>סטטוס</label>
            <select id="apptStatus">
                <option value="pending" ${existing.status === "pending" ? "selected" : ""}>ממתין</option>
                <option value="completed" ${existing.status === "completed" ? "selected" : ""}>הושלם</option>
                <option value="cancelled" ${existing.status === "cancelled" ? "selected" : ""}>בוטל</option>
            </select>
        </div>` : ""}
        <div class="field"><label>הערות</label><textarea id="apptNotes" rows="2">${existing ? escapeHtml(existing.notes || "") : ""}</textarea></div>
        <div id="apptError" class="field-error"></div>
        <div class="modal-actions">
            ${existing && hasPermission("appointment.delete") ? '<button class="btn btn-danger" id="apptDelete" style="margin-inline-end:auto;">מחיקת תור</button>' : ""}
            <button class="btn btn-ghost" id="apptCancel">ביטול</button>
            <button class="btn btn-primary" id="apptSave">${existing ? "שמירה" : "קביעת תור"}</button>
        </div>
    `, {
        onMount: (overlay) => {
            overlay.querySelector("#apptCancel").onclick = closeModal;
            if (existing && overlay.querySelector("#apptDelete")) {
                overlay.querySelector("#apptDelete").onclick = async () => {
                    const ok = await confirmAction("למחוק את התור? פעולה זו סופית.");
                    if (!ok) return;
                    try {
                        await apiJson(`/api/appointments/${appointmentId}`, { method: "DELETE" });
                        closeModal();
                        toast("התור נמחק", "success");
                        loadCalendarList();
                    } catch (e) { toast(e.message, "error"); }
                };
            }
            overlay.querySelector("#apptSave").onclick = () => saveAppointment(appointmentId);
        },
    });
}

async function saveAppointment(appointmentId) {
    const treatmentSelect = document.getElementById("apptTreatments");
    const treatmentIds = Array.from(treatmentSelect.selectedOptions).map((o) => parseInt(o.value, 10));
    const errorEl = document.getElementById("apptError");
    errorEl.textContent = "";

    if (!treatmentIds.length) {
        errorEl.textContent = "יש לבחור טיפול אחד לפחות";
        return;
    }

    const payload = {
        client_id: parseInt(document.getElementById("apptClient").value, 10),
        treatment_ids: treatmentIds,
        appointment_date: document.getElementById("apptDate").value,
        appointment_time: document.getElementById("apptTime").value,
        notes: document.getElementById("apptNotes").value || null,
        room_id: document.getElementById("apptRoom").value ? parseInt(document.getElementById("apptRoom").value, 10) : null,
        staff_user_id: document.getElementById("apptStaff").value ? parseInt(document.getElementById("apptStaff").value, 10) : null,
    };
    const statusField = document.getElementById("apptStatus");
    if (statusField) payload.status = statusField.value;

    try {
        if (appointmentId) {
            await apiJson(`/api/appointments/${appointmentId}`, { method: "PUT", body: JSON.stringify(payload) });
            toast("התור עודכן", "success");
        } else {
            await apiJson("/api/appointments", { method: "POST", body: JSON.stringify(payload) });
            toast("התור נקבע", "success");
        }
        closeModal();
        loadCalendarList();
    } catch (e) {
        errorEl.textContent = e.message;
    }
}

// ============================================================
// לקוחות
// ============================================================

async function renderClientsList() {
    setPageHeader("לקוחות", "מרכז לקוחות", `
        <button class="btn btn-primary" id="newClientBtn">${ICONS.plus(13)} לקוחה חדשה</button>
    `);
    document.getElementById("pageBody").innerHTML = `<div class="card" style="padding:6px;"><table id="clientsTable">
        <thead><tr><th>לקוחה</th><th>טלפון</th><th>חבילה פעילה</th><th>הכנסה</th><th></th></tr></thead>
        <tbody><tr><td colspan="5" class="loading-row">טוען...</td></tr></tbody>
    </table></div>`;

    document.getElementById("newClientBtn").addEventListener("click", () => openClientModal());

    let clients;
    try {
        clients = await apiJson("/api/clients");
    } catch (e) {
        document.querySelector("#clientsTable tbody").innerHTML = `<tr><td colspan="5" class="loading-row">שגיאה בטעינה</td></tr>`;
        return;
    }

    const tbody = document.querySelector("#clientsTable tbody");
    if (!clients.length) {
        tbody.innerHTML = `<tr><td colspan="5" class="loading-row">אין עדיין לקוחות במערכת</td></tr>`;
        return;
    }

    tbody.innerHTML = clients.map((c) => {
        const initials = (c.full_name || "").trim().split(/\s+/).map((w) => w[0]).slice(0, 2).join("");
        const tint = tintFor(c.full_name);
        const colors = TINT_COLORS[tint];
        const sinceYear = c.created_at ? new Date(c.created_at).getFullYear() : null;
        const pkg = c.active_package;
        const progressPct = pkg ? Math.round(((pkg.total_sessions - pkg.sessions_remaining) / pkg.total_sessions) * 100) : 0;

        return `
        <tr class="clickable" data-client-id="${c.client_id}">
            <td>
                <div class="flex items-center gap-12">
                    <div class="avatar" style="background:${colors.bg};color:${colors.dot};">${escapeHtml(initials)}</div>
                    <div>
                        <div style="font-weight:600;">${escapeHtml(c.full_name)}</div>
                        <div class="text-sm text-muted">${sinceYear ? `לקוחה מ-${sinceYear}` : ""}</div>
                    </div>
                </div>
            </td>
            <td class="num ltr">${escapeHtml(c.phone)}</td>
            <td>
                ${pkg ? `
                    <div class="text-sm">${escapeHtml(pkg.name)} · ${pkg.sessions_remaining}/${pkg.total_sessions}</div>
                    <div class="progress-track mt-8" style="width:100px;"><div class="progress-fill" style="width:${progressPct}%;"></div></div>
                ` : `<span class="text-sm text-muted">ללא חבילה פעילה</span>`}
            </td>
            <td class="num" style="font-weight:500;">₪ ${Number(c.total_revenue || 0).toLocaleString("he-IL")}</td>
            <td><svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M14 6l-6 6 6 6" stroke="#C7C3BB" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" transform="scale(-1,1) translate(-24,0)"></path></svg></td>
        </tr>
    `;
    }).join("");

    tbody.querySelectorAll("[data-client-id]").forEach((el) => {
        el.addEventListener("click", () => { window.location.hash = "#clients/" + el.dataset.clientId; });
    });
}

function openClientModal(existing) {
    openModal(existing ? "עריכת לקוחה" : "לקוחה חדשה", `
        <div class="field"><label>שם מלא</label><input id="clientName" value="${existing ? escapeHtml(existing.full_name) : ""}"></div>
        <div class="field"><label>טלפון</label><input id="clientPhone" class="ltr" value="${existing ? escapeHtml(existing.phone) : ""}"></div>
        <div class="field"><label>אימייל (רשות)</label><input id="clientEmail" class="ltr" value="${existing ? escapeHtml(existing.email || "") : ""}"></div>
        <div class="field"><label>כתובת (רשות)</label><input id="clientAddress" value="${existing ? escapeHtml(existing.address || "") : ""}"></div>
        <div id="clientError" class="field-error"></div>
        <div class="modal-actions">
            <button class="btn btn-ghost" id="clientCancel">ביטול</button>
            <button class="btn btn-primary" id="clientSave">שמירה</button>
        </div>
    `, {
        onMount: (overlay) => {
            overlay.querySelector("#clientCancel").onclick = closeModal;
            overlay.querySelector("#clientSave").onclick = async () => {
                const payload = {
                    full_name: document.getElementById("clientName").value,
                    phone: document.getElementById("clientPhone").value,
                    email: document.getElementById("clientEmail").value || null,
                    address: document.getElementById("clientAddress").value || null,
                };
                try {
                    if (existing) {
                        await apiJson(`/api/clients/${existing.client_id}`, { method: "PUT", body: JSON.stringify(payload) });
                    } else {
                        await apiJson("/api/clients", { method: "POST", body: JSON.stringify(payload) });
                    }
                    closeModal();
                    toast("הלקוחה נשמרה", "success");
                    handleRoute();
                } catch (e) {
                    document.getElementById("clientError").textContent = e.message;
                }
            };
        },
    });
}

async function renderClientProfile(clientIdRaw) {
    const clientId = parseInt(clientIdRaw, 10);
    setPageHeader("לקוחות", "פרופיל לקוחה", "");
    const body = document.getElementById("pageBody");
    body.innerHTML = `<div class="loading-row">טוען...</div>`;

    let data;
    try {
        data = await apiJson(`/api/clients/${clientId}/history`);
    } catch (e) {
        body.innerHTML = `<div class="loading-row">שגיאה בטעינה</div>`;
        return;
    }

    const client = data.client;
    const initials = (client.full_name || "").trim().split(/\s+/).map((w) => w[0]).slice(0, 2).join("");

    let clientPackages = [];
    let packageCatalog = [];
    try {
        [clientPackages, packageCatalog] = await Promise.all([
            apiJson(`/api/packages/client/${clientId}`),
            apiJson("/api/packages"),
        ]);
    } catch (e) { /* ignore - הכרטיס עדיין יוצג בלי חבילה */ }
    const packageById = Object.fromEntries(packageCatalog.map((p) => [p.package_id, p]));
    const activeClientPackage = clientPackages.find((cp) => cp.is_active && cp.sessions_remaining > 0) || null;
    const activePackage = activeClientPackage && packageById[activeClientPackage.package_id]
        ? { ...activeClientPackage, package: packageById[activeClientPackage.package_id] }
        : null;

    const lastVisit = data.appointments
        .filter((a) => a.status === "completed")
        .sort((a, b) => (a.appointment_date < b.appointment_date ? 1 : -1))[0];
    const openInvoicesCount = data.invoices.filter((inv) => !inv.is_cancelled).length;

    body.innerHTML = `
        <div class="stack">
            <div class="card">
                <div class="text-sm text-muted" style="cursor:pointer;margin-bottom:14px;" id="backToList">${ICONS.chevronBack(13)} חזרה לרשימת הלקוחות</div>
                <div class="flex items-center gap-12">
                    <div class="avatar lg">${escapeHtml(initials)}</div>
                    <div class="flex-1">
                        <div class="flex items-center gap-8">
                            <h2 style="margin:0;font-size:22px;font-weight:600;">${escapeHtml(client.full_name)}</h2>
                            ${activePackage ? '<span class="badge gold">לקוחת חבילה</span>' : ""}
                        </div>
                        <div class="flex items-center gap-12 text-sm text-muted mt-8">
                            <span class="num ltr">${escapeHtml(client.phone)}</span>
                            <span>${escapeHtml(client.email || "")}</span>
                        </div>
                    </div>
                    <button class="btn btn-secondary" id="editClientBtn">עריכת פרטים</button>
                    <button class="btn btn-primary" id="newApptForClient">קביעת תור</button>
                </div>
            </div>

            <div class="grid-2" style="grid-template-columns: minmax(0,1.6fr) minmax(0,1fr);align-items:start;">
                <div class="card">
                    <div class="tabs" id="profileTabs">
                        <div class="tab active" data-tab="details">פרטים</div>
                        <div class="tab" data-tab="history">היסטוריית טיפולים</div>
                        <div class="tab" data-tab="docs">מסמכים</div>
                    </div>
                    <div id="profileTabBody"></div>
                </div>

                <div class="stack">
                    <div class="card">
                        <h2 class="card-title">חבילה פעילה</h2>
                        ${activePackage ? `
                            <div class="flex items-center gap-8">
                                <span class="stat-value num" style="font-size:26px;">${activePackage.package.total_sessions - activePackage.sessions_remaining}/${activePackage.package.total_sessions}</span>
                            </div>
                            <div class="progress-track mt-8"><div class="progress-fill" style="width:${Math.round(((activePackage.package.total_sessions - activePackage.sessions_remaining) / activePackage.package.total_sessions) * 100)}%;"></div></div>
                            <div class="text-sm text-muted mt-8">${escapeHtml(activePackage.package.name)} · נותרו ${activePackage.sessions_remaining} מפגשים</div>
                        ` : `<div class="text-sm text-muted">אין חבילה פעילה. אפשר למכור חבילה מעמוד "קטלוג וחבילות".</div>`}
                    </div>
                    <div class="card">
                        <h2 class="card-title">סיכום כספי</h2>
                        <div class="stack" style="gap:12px;">
                            <div class="flex items-center"><span class="text-sm text-muted">הכנסה מצטברת</span><span class="num" style="margin-inline-start:auto;font-weight:600;">₪ ${Number(data.total_active_amount || 0).toLocaleString("he-IL")}</span></div>
                            <div class="flex items-center"><span class="text-sm text-muted">חשבוניות פתוחות</span><span class="num" style="margin-inline-start:auto;font-weight:600;">${openInvoicesCount}</span></div>
                            <div class="flex items-center"><span class="text-sm text-muted">ביקור אחרון</span><span class="num" style="margin-inline-start:auto;font-weight:600;">${lastVisit ? formatDateHe(lastVisit.appointment_date) : "—"}</span></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

    document.getElementById("backToList").addEventListener("click", () => { window.location.hash = "#clients"; });
    document.getElementById("editClientBtn").addEventListener("click", () => openClientModal(client));
    document.getElementById("newApptForClient").addEventListener("click", () => openAppointmentModal());

    function renderDetailsTab() {
        return `
            <div class="field-row">
                <div><div class="text-sm text-muted">כתובת</div><div class="mt-8">${escapeHtml(client.address || "—")}</div></div>
                <div><div class="text-sm text-muted">לקוחה מאז</div><div class="mt-8 num">${client.created_at ? formatDateHe(client.created_at.slice(0, 10)) : "—"}</div></div>
            </div>
            <div class="field-row mt-16">
                <div><div class="text-sm text-muted">חשבוניות</div><div class="mt-8">${data.invoices.length ? `${data.invoices.length} חשבוניות` : "אין חשבוניות"}</div></div>
                <div>
                    <div class="text-sm text-muted">הצהרת בריאות</div>
                    <div class="mt-8">
                        ${client.has_signed_health_declaration
                            ? '<span class="badge sage">חתומה</span>'
                            : `<div class="flex items-center gap-8">
                                 <span class="badge muted">לא חתומה</span>
                                 <label class="btn btn-secondary btn-sm" style="cursor:pointer;">
                                     העלאת מסמך<input type="file" id="healthDeclFile" accept=".pdf,.jpg,.jpeg,.png" style="display:none;">
                                 </label>
                               </div>`}
                    </div>
                </div>
            </div>
        `;
    }

    function renderHistoryTab() {
        if (!data.appointments.length) return `<div class="text-sm text-muted">אין עדיין תורים</div>`;
        return data.appointments.map((a) => `
            <div class="flex items-center gap-12" style="padding:11px 6px;border-top:1px solid var(--border-soft);">
                <div class="text-sm text-muted num" style="width:90px;">${formatDateHe(a.appointment_date)}</div>
                <div class="flex-1">${escapeHtml(a.treatment_name || "")}</div>
                <span class="badge ${statusBadgeClass(a.status)}">${statusLabel(a.status)}</span>
            </div>
        `).join("");
    }

    function renderDocsTab() {
        if (!client.has_signed_health_declaration) {
            return `<div class="text-sm text-muted">אין מסמכים עדיין</div>`;
        }
        return `
            <div class="grid-3">
                <div class="card" style="box-shadow:none;border:1px solid var(--border);padding:16px;">
                    ${ICONS.invoices(22)}
                    <div style="font-weight:600;margin-top:10px;">הצהרת בריאות</div>
                    <div class="text-sm text-muted mt-8">PDF/תמונה</div>
                </div>
            </div>
        `;
    }

    const TAB_RENDERERS = { details: renderDetailsTab, history: renderHistoryTab, docs: renderDocsTab };

    function activateTab(tabKey) {
        document.querySelectorAll("#profileTabs .tab").forEach((el) => el.classList.toggle("active", el.dataset.tab === tabKey));
        document.getElementById("profileTabBody").innerHTML = TAB_RENDERERS[tabKey]();

        const fileInput = document.getElementById("healthDeclFile");
        if (fileInput) {
            fileInput.addEventListener("change", async () => {
                if (!fileInput.files.length) return;
                const formData = new FormData();
                formData.append("file", fileInput.files[0]);
                try {
                    await apiFetch(`/api/clients/${clientId}/health-declaration`, { method: "POST", body: formData })
                        .then((r) => { if (!r.ok) throw new Error("upload failed"); });
                    toast("המסמך הועלה", "success");
                    renderClientProfile(clientIdRaw);
                } catch (e) {
                    toast("העלאת המסמך נכשלה", "error");
                }
            });
        }
    }

    document.querySelectorAll("#profileTabs .tab").forEach((el) => {
        el.addEventListener("click", () => activateTab(el.dataset.tab));
    });
    activateTab("details");
}

// עדכון הראוטר: כתובת clients/<id> מציגה פרופיל, אחרת רשימה
ROUTES.clients = (param) => (param ? renderClientProfile(param) : renderClientsList());

// ============================================================
// לידים
// ============================================================

const LEAD_STAGES = [
    { key: "new", label: "ליד חדש", dot: "var(--blue-dot)" },
    { key: "in_progress", label: "בטיפול", dot: "var(--gold-bar)" },
    { key: "converted", label: "הומר ללקוחה", dot: "var(--sage-dot)" },
    { key: "rejected", label: "לא רלוונטי", dot: "var(--pink-dot)" },
];

async function renderLeads() {
    setPageHeader("צינור לידים", "ניהול לידים", `<button class="btn btn-primary" id="newLeadBtn">${ICONS.plus(13)} ליד חדש</button>`);
    document.getElementById("pageBody").innerHTML = `<div class="kanban" id="kanbanBoard"></div>`;
    document.getElementById("newLeadBtn").addEventListener("click", () => openLeadModal());

    let leads;
    try {
        leads = await apiJson("/api/leads");
    } catch (e) {
        document.getElementById("kanbanBoard").innerHTML = `<div class="loading-row">שגיאה בטעינה</div>`;
        return;
    }

    renderKanbanBoard(leads);
}

/**
 * מצייר את לוח הלידים ומחבר גרירה-ושחרור אמיתית (HTML5 DnD) בין
 * העמודות - גרירת כרטיס לעמודה אחרת שולחת PUT עם הסטטוס החדש.
 */
function renderKanbanBoard(leads) {
    const board = document.getElementById("kanbanBoard");
    board.innerHTML = LEAD_STAGES.map((stage) => {
        const stageLeads = leads.filter((l) => l.status === stage.key);
        return `
            <div class="kanban-col" data-stage="${stage.key}">
                <div class="kanban-col-head"><span class="kanban-dot" style="background:${stage.dot};"></span>${stage.label}<span class="kanban-count">${stageLeads.length}</span></div>
                <div class="kanban-drop-zone" data-stage="${stage.key}">${stageLeads.map((l) => leadCardHtml(l)).join("")}</div>
            </div>
        `;
    }).join("");

    board.querySelectorAll("[data-lead-id]").forEach((card) => {
        card.addEventListener("click", () => openLeadModal(leads.find((l) => l.lead_id == card.dataset.leadId)));

        card.addEventListener("dragstart", (e) => {
            e.dataTransfer.setData("text/plain", card.dataset.leadId);
            e.dataTransfer.effectAllowed = "move";
            setTimeout(() => card.classList.add("dragging"), 0);
        });
        card.addEventListener("dragend", () => card.classList.remove("dragging"));
    });

    board.querySelectorAll(".kanban-col").forEach((col) => {
        col.addEventListener("dragover", (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = "move";
            col.style.background = "var(--gold-bg)";
        });
        col.addEventListener("dragleave", () => { col.style.background = ""; });
        col.addEventListener("drop", async (e) => {
            e.preventDefault();
            col.style.background = "";
            const leadId = e.dataTransfer.getData("text/plain");
            const newStage = col.dataset.stage;
            const lead = leads.find((l) => String(l.lead_id) === leadId);
            if (!lead || lead.status === newStage) return;

            try {
                await apiJson(`/api/leads/${leadId}`, {
                    method: "PUT",
                    body: JSON.stringify({
                        full_name: lead.full_name, phone: lead.phone,
                        source: lead.source, status: newStage, notes: lead.notes,
                    }),
                });
                lead.status = newStage;
                renderKanbanBoard(leads);
                toast("הליד הועבר ל-‏" + LEAD_STAGES.find((s) => s.key === newStage).label, "success");
            } catch (err) {
                toast(err.message, "error");
            }
        });
    });
}

function leadCardHtml(lead) {
    const initials = (lead.full_name || "").trim().split(/\s+/).map((w) => w[0]).slice(0, 2).join("");
    const colors = TINT_COLORS[tintFor(lead.full_name)];
    return `
        <div class="kanban-card clickable" data-lead-id="${lead.lead_id}" draggable="true">
            <div class="flex items-center gap-8">
                <div class="avatar" style="width:24px;height:24px;font-size:10.5px;background:${colors.bg};color:${colors.dot};">${escapeHtml(initials)}</div>
                <div style="font-weight:600;flex:1;min-width:0;">${escapeHtml(lead.full_name)}</div>
                <span style="color:var(--muted-3);">${ICONS.contact(14)}</span>
            </div>
            <div class="text-sm text-muted num ltr mt-8">${escapeHtml(lead.phone)}</div>
            ${lead.notes ? `<div class="text-sm mt-8">${escapeHtml(lead.notes)}</div>` : ""}
            <span class="badge gold mt-8">${escapeHtml(lead.source || "")}</span>
        </div>
    `;
}

function openLeadModal(existing) {
    const sourceOptions = ["facebook", "instagram", "google", "referral", "walk_in"];
    const sourceLabels = { facebook: "פייסבוק", instagram: "אינסטגרם", google: "גוגל", referral: "הפניה", walk_in: "מהרחוב" };
    const statusOptions = LEAD_STAGES;

    openModal(existing ? "עריכת ליד" : "ליד חדש", `
        <div class="field"><label>שם מלא</label><input id="leadName" value="${existing ? escapeHtml(existing.full_name) : ""}"></div>
        <div class="field"><label>טלפון</label><input id="leadPhone" class="ltr" value="${existing ? escapeHtml(existing.phone) : ""}"></div>
        <div class="field"><label>מקור</label><select id="leadSource">
            ${sourceOptions.map((s) => `<option value="${s}" ${existing && existing.source === s ? "selected" : ""}>${sourceLabels[s]}</option>`).join("")}
        </select></div>
        ${existing ? `<div class="field"><label>סטטוס</label><select id="leadStatus">
            ${statusOptions.map((s) => `<option value="${s.key}" ${existing.status === s.key ? "selected" : ""}>${s.label}</option>`).join("")}
        </select></div>` : ""}
        <div class="field"><label>הערות</label><textarea id="leadNotes" rows="2">${existing ? escapeHtml(existing.notes || "") : ""}</textarea></div>
        <div id="leadError" class="field-error"></div>
        <div class="modal-actions">
            ${existing ? '<button class="btn btn-danger" id="leadDelete" style="margin-inline-end:auto;">מחיקה</button>' : ""}
            ${existing && existing.status !== "converted" ? '<button class="btn btn-secondary" id="leadConvert">המרה ללקוחה</button>' : ""}
            <button class="btn btn-ghost" id="leadCancel">ביטול</button>
            <button class="btn btn-primary" id="leadSave">שמירה</button>
        </div>
    `, {
        onMount: (overlay) => {
            overlay.querySelector("#leadCancel").onclick = closeModal;
            if (existing && overlay.querySelector("#leadDelete")) {
                overlay.querySelector("#leadDelete").onclick = async () => {
                    const ok = await confirmAction("למחוק את הליד?");
                    if (!ok) return;
                    await apiJson(`/api/leads/${existing.lead_id}`, { method: "DELETE" });
                    closeModal(); toast("הליד נמחק", "success"); renderLeads();
                };
            }
            if (existing && overlay.querySelector("#leadConvert")) {
                overlay.querySelector("#leadConvert").onclick = async () => {
                    try {
                        await apiJson(`/api/leads/${existing.lead_id}/convert`, { method: "POST", body: JSON.stringify({}) });
                        closeModal(); toast("הליד הומר ללקוחה", "success"); renderLeads();
                    } catch (e) { document.getElementById("leadError").textContent = e.message; }
                };
            }
            overlay.querySelector("#leadSave").onclick = async () => {
                const payload = {
                    full_name: document.getElementById("leadName").value,
                    phone: document.getElementById("leadPhone").value,
                    source: document.getElementById("leadSource").value,
                    notes: document.getElementById("leadNotes").value || null,
                };
                const statusField = document.getElementById("leadStatus");
                if (statusField) payload.status = statusField.value;
                try {
                    if (existing) {
                        await apiJson(`/api/leads/${existing.lead_id}`, { method: "PUT", body: JSON.stringify(payload) });
                    } else {
                        await apiJson("/api/leads", { method: "POST", body: JSON.stringify(payload) });
                    }
                    closeModal(); toast("הליד נשמר", "success"); renderLeads();
                } catch (e) {
                    document.getElementById("leadError").textContent = e.message;
                }
            };
        },
    });
}

// ============================================================
// קטלוג וחבילות
// ============================================================

async function renderPackages() {
    setPageHeader("קטלוג וחבילות", "חבילות טיפולים", hasPermission("package.manage")
        ? `<button class="btn btn-primary" id="newPackageBtn">+ חבילה חדשה</button>` : "");

    document.getElementById("pageBody").innerHTML = `<div class="card" style="padding:6px;"><table id="packagesTable">
        <thead><tr><th>שם</th><th>טיפול</th><th>מפגשים</th><th>מחיר</th><th>סטטוס</th></tr></thead>
        <tbody><tr><td colspan="5" class="loading-row">טוען...</td></tr></tbody>
    </table></div>`;

    if (document.getElementById("newPackageBtn")) {
        document.getElementById("newPackageBtn").addEventListener("click", () => openPackageModal());
    }

    let packages;
    try {
        packages = await apiJson("/api/packages");
    } catch (e) {
        document.querySelector("#packagesTable tbody").innerHTML = `<tr><td colspan="5" class="loading-row">שגיאה בטעינה</td></tr>`;
        return;
    }

    const treatmentName = (id) => (state.treatments.find((t) => t.treatment_id === id) || {}).treatment_name || "-";

    document.querySelector("#packagesTable tbody").innerHTML = packages.length ? packages.map((p) => `
        <tr>
            <td style="font-weight:600;">${escapeHtml(p.name)}</td>
            <td>${escapeHtml(treatmentName(p.treatment_id))}</td>
            <td class="num">${p.total_sessions}</td>
            <td class="num">₪ ${p.price}</td>
            <td>${p.is_active ? '<span class="badge sage">פעילה</span>' : '<span class="badge muted">מושבתת</span>'}</td>
        </tr>
    `).join("") : `<tr><td colspan="5" class="loading-row">אין עדיין חבילות בקטלוג</td></tr>`;
}

function openPackageModal() {
    openModal("חבילה חדשה", `
        <div class="field"><label>שם החבילה</label><input id="pkgName"></div>
        <div class="field"><label>טיפול</label><select id="pkgTreatment">${treatmentOptionsHtml()}</select></div>
        <div class="field-row">
            <div class="field"><label>מספר מפגשים</label><input type="number" id="pkgSessions" min="1"></div>
            <div class="field"><label>מחיר</label><input type="number" id="pkgPrice" min="1"></div>
        </div>
        <div id="pkgError" class="field-error"></div>
        <div class="modal-actions">
            <button class="btn btn-ghost" id="pkgCancel">ביטול</button>
            <button class="btn btn-primary" id="pkgSave">שמירה</button>
        </div>
    `, {
        onMount: (overlay) => {
            overlay.querySelector("#pkgCancel").onclick = closeModal;
            overlay.querySelector("#pkgSave").onclick = async () => {
                const payload = {
                    name: document.getElementById("pkgName").value,
                    treatment_id: parseInt(document.getElementById("pkgTreatment").value, 10),
                    total_sessions: parseInt(document.getElementById("pkgSessions").value, 10),
                    price: parseFloat(document.getElementById("pkgPrice").value),
                };
                try {
                    await apiJson("/api/packages", { method: "POST", body: JSON.stringify(payload) });
                    closeModal(); toast("החבילה נוספה", "success"); renderPackages();
                } catch (e) { document.getElementById("pkgError").textContent = e.message; }
            };
        },
    });
}

// ============================================================
// מכשירים וחדרים
// ============================================================

async function renderResources() {
    setPageHeader("מכשירים וחדרים", "משאבי הקליניקה", "");
    document.getElementById("pageBody").innerHTML = `
        <div class="grid-2">
            <div class="card">
                <div class="flex items-center" style="margin-bottom:16px;">
                    <h2 class="card-title" style="margin:0;">חדרים</h2>
                    ${hasPermission("room.manage") ? '<button class="btn btn-secondary btn-sm" id="newRoomBtn" style="margin-inline-start:auto;">+ חדר</button>' : ""}
                </div>
                <div id="roomsList"></div>
            </div>
            <div class="card">
                <div class="flex items-center" style="margin-bottom:16px;">
                    <h2 class="card-title" style="margin:0;">מכשירים</h2>
                    ${hasPermission("machine.manage") ? '<button class="btn btn-secondary btn-sm" id="newMachineBtn" style="margin-inline-start:auto;">+ מכשיר</button>' : ""}
                </div>
                <div id="machinesList"></div>
            </div>
        </div>
    `;

    if (document.getElementById("newRoomBtn")) document.getElementById("newRoomBtn").onclick = () => openRoomModal();
    if (document.getElementById("newMachineBtn")) document.getElementById("newMachineBtn").onclick = () => openMachineModal();

    await loadReferenceData();

    document.getElementById("roomsList").innerHTML = state.rooms.length ? state.rooms.map((r) => `
        <div class="flex items-center gap-8" style="padding:10px 4px;border-top:1px solid var(--border-soft);">
            <span>${escapeHtml(r.name)}</span>
            <span class="badge ${r.is_active ? "sage" : "muted"}" style="margin-inline-start:auto;">${r.is_active ? "פעיל" : "מושבת"}</span>
        </div>
    `).join("") : `<div class="text-sm text-muted">לא הוגדרו חדרים</div>`;

    document.getElementById("machinesList").innerHTML = state.machines.length ? state.machines.map((m) => `
        <div class="flex items-center gap-8" style="padding:10px 4px;border-top:1px solid var(--border-soft);">
            <span>${escapeHtml(m.name)}</span>
            <span class="text-sm text-muted">${escapeHtml(m.machine_type || "")}</span>
            <span class="badge ${m.is_active ? "sage" : "muted"}" style="margin-inline-start:auto;">${m.is_active ? "פעיל" : "מושבת"}</span>
        </div>
    `).join("") : `<div class="text-sm text-muted">לא הוגדרו מכשירים</div>`;
}

function openRoomModal() {
    openModal("חדר חדש", `
        <div class="field"><label>שם החדר</label><input id="roomName"></div>
        <div id="roomError" class="field-error"></div>
        <div class="modal-actions">
            <button class="btn btn-ghost" id="roomCancel">ביטול</button>
            <button class="btn btn-primary" id="roomSave">שמירה</button>
        </div>
    `, {
        onMount: (overlay) => {
            overlay.querySelector("#roomCancel").onclick = closeModal;
            overlay.querySelector("#roomSave").onclick = async () => {
                try {
                    await apiJson("/api/rooms", { method: "POST", body: JSON.stringify({ name: document.getElementById("roomName").value }) });
                    closeModal(); toast("החדר נוסף", "success"); renderResources();
                } catch (e) { document.getElementById("roomError").textContent = e.message; }
            };
        },
    });
}

function openMachineModal() {
    openModal("מכשיר חדש", `
        <div class="field"><label>שם המכשיר</label><input id="machineName"></div>
        <div class="field"><label>סוג (רשות)</label><input id="machineType" placeholder="למשל: דיודה, אלכסנדריט"></div>
        <div id="machineError" class="field-error"></div>
        <div class="modal-actions">
            <button class="btn btn-ghost" id="machineCancel">ביטול</button>
            <button class="btn btn-primary" id="machineSave">שמירה</button>
        </div>
    `, {
        onMount: (overlay) => {
            overlay.querySelector("#machineCancel").onclick = closeModal;
            overlay.querySelector("#machineSave").onclick = async () => {
                try {
                    await apiJson("/api/machines", {
                        method: "POST",
                        body: JSON.stringify({ name: document.getElementById("machineName").value, machine_type: document.getElementById("machineType").value || null }),
                    });
                    closeModal(); toast("המכשיר נוסף", "success"); renderResources();
                } catch (e) { document.getElementById("machineError").textContent = e.message; }
            };
        },
    });
}

// ============================================================
// צוות וזמינות
// ============================================================

const DAY_OF_WEEK_LABELS = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"];

async function renderStaff() {
    setPageHeader("צוות וזמינות", "עובדות הקליניקה", hasPermission("user.manage")
        ? `<button class="btn btn-primary" id="newStaffBtn">+ עובדת חדשה</button>` : "");

    document.getElementById("pageBody").innerHTML = `<div id="staffCards" class="stack"></div>`;
    if (document.getElementById("newStaffBtn")) document.getElementById("newStaffBtn").onclick = () => openStaffModal();

    let users;
    try { users = await apiJson("/api/users").then((r) => r.users); }
    catch (e) { document.getElementById("staffCards").innerHTML = `<div class="loading-row">אין הרשאה לצפות בעמוד זה</div>`; return; }

    const cards = document.getElementById("staffCards");
    cards.innerHTML = "";
    for (const user of users) {
        const card = document.createElement("div");
        card.className = "card";
        card.innerHTML = `
            <div class="flex items-center gap-12">
                <div class="flex-1">
                    <div style="font-weight:600;">${escapeHtml(user.full_name)}</div>
                    <div class="text-sm text-muted">${escapeHtml(user.role_label)} · <span class="num ltr">${escapeHtml(user.phone)}</span></div>
                </div>
                <span class="badge ${user.is_active ? "sage" : "muted"}">${user.is_active ? "פעילה" : "מושבתת"}</span>
                ${hasPermission("staff_schedule.manage") ? `<button class="btn btn-secondary btn-sm" data-avail-for="${user.user_id}">שעות עבודה</button>` : ""}
            </div>
            <div id="avail-${user.user_id}" class="mt-16"></div>
        `;
        cards.appendChild(card);
    }

    cards.querySelectorAll("[data-avail-for]").forEach((btn) => {
        btn.addEventListener("click", async () => {
            const userId = btn.dataset.availFor;
            const box = document.getElementById("avail-" + userId);
            if (box.dataset.loaded === "1") { box.innerHTML = ""; box.dataset.loaded = ""; return; }
            const slots = await apiJson(`/api/staff/${userId}/availability`);
            box.dataset.loaded = "1";
            box.innerHTML = `
                <div style="border-top:1px solid var(--border-soft);padding-top:12px;">
                    ${slots.map((s) => `<div class="text-sm">${DAY_OF_WEEK_LABELS[s.day_of_week]}: ${s.start_time}–${s.end_time}</div>`).join("") || '<div class="text-sm text-muted">לא הוגדרו שעות עבודה</div>'}
                    <button class="btn btn-ghost btn-sm mt-8" data-add-avail="${userId}">+ הוספת משבצת</button>
                </div>
            `;
            box.querySelector("[data-add-avail]").addEventListener("click", () => openAvailabilityModal(userId));
        });
    });
}

function openAvailabilityModal(userId) {
    openModal("הוספת שעות עבודה", `
        <div class="field"><label>יום בשבוע</label><select id="availDay">
            ${DAY_OF_WEEK_LABELS.map((label, idx) => `<option value="${idx}">${label}</option>`).join("")}
        </select></div>
        <div class="field-row">
            <div class="field"><label>משעה</label><input type="time" id="availStart" value="09:00"></div>
            <div class="field"><label>עד שעה</label><input type="time" id="availEnd" value="18:00"></div>
        </div>
        <div id="availError" class="field-error"></div>
        <div class="modal-actions">
            <button class="btn btn-ghost" id="availCancel">ביטול</button>
            <button class="btn btn-primary" id="availSave">שמירה</button>
        </div>
    `, {
        onMount: (overlay) => {
            overlay.querySelector("#availCancel").onclick = closeModal;
            overlay.querySelector("#availSave").onclick = async () => {
                try {
                    await apiJson(`/api/staff/${userId}/availability`, {
                        method: "POST",
                        body: JSON.stringify({
                            day_of_week: parseInt(document.getElementById("availDay").value, 10),
                            start_time: document.getElementById("availStart").value,
                            end_time: document.getElementById("availEnd").value,
                        }),
                    });
                    closeModal(); toast("הזמינות נוספה", "success"); renderStaff();
                } catch (e) { document.getElementById("availError").textContent = e.message; }
            };
        },
    });
}

function openStaffModal() {
    openModal("עובדת חדשה", `
        <div class="field"><label>שם מלא</label><input id="staffName"></div>
        <div class="field"><label>טלפון (משמש להתחברות)</label><input id="staffPhone" class="ltr"></div>
        <div class="field"><label>סיסמה זמנית</label><input type="password" id="staffPassword"></div>
        <div class="field"><label>תפקיד</label><select id="staffRole"><option value="employee">עובדת</option><option value="admin">מנהלת</option></select></div>
        <div id="staffError" class="field-error"></div>
        <div class="modal-actions">
            <button class="btn btn-ghost" id="staffCancel">ביטול</button>
            <button class="btn btn-primary" id="staffSave">יצירה</button>
        </div>
    `, {
        onMount: (overlay) => {
            overlay.querySelector("#staffCancel").onclick = closeModal;
            overlay.querySelector("#staffSave").onclick = async () => {
                try {
                    await apiJson("/api/users", {
                        method: "POST",
                        body: JSON.stringify({
                            full_name: document.getElementById("staffName").value,
                            phone: document.getElementById("staffPhone").value,
                            password: document.getElementById("staffPassword").value,
                            role: document.getElementById("staffRole").value,
                        }),
                    });
                    closeModal(); toast("העובדת נוצרה", "success"); renderStaff();
                } catch (e) { document.getElementById("staffError").textContent = e.message; }
            };
        },
    });
}

// ============================================================
// חשבוניות
// ============================================================

async function renderInvoices() {
    setPageHeader("חשבוניות", "חשבוניות מס", "");
    document.getElementById("pageBody").innerHTML = `<div class="card" style="padding:6px;"><table id="invoicesTable">
        <thead><tr><th>מספר</th><th>תאריך</th><th>סכום</th><th>סטטוס</th><th></th></tr></thead>
        <tbody><tr><td colspan="5" class="loading-row">טוען...</td></tr></tbody>
    </table></div>`;

    let invoices;
    try { invoices = await apiJson("/api/invoices?include_cancelled=true"); }
    catch (e) { document.querySelector("#invoicesTable tbody").innerHTML = `<tr><td colspan="5" class="loading-row">שגיאה בטעינה</td></tr>`; return; }

    document.querySelector("#invoicesTable tbody").innerHTML = invoices.length ? invoices.map((inv) => `
        <tr>
            <td class="num" style="font-weight:600;">${inv.invoice_number}</td>
            <td>${formatDateHe(inv.invoice_date)}</td>
            <td class="num">₪ ${inv.amount}</td>
            <td>${inv.is_cancelled ? '<span class="badge muted">מבוטלת</span>' : '<span class="badge sage">פעילה</span>'}</td>
            <td>
                ${hasPermission("invoice.cancel") ? (inv.is_cancelled
                    ? `<button class="btn btn-ghost btn-sm" data-restore="${inv.invoice_id}">שחזור</button>`
                    : `<button class="btn btn-ghost btn-sm" data-cancel="${inv.invoice_id}">ביטול</button>`) : ""}
            </td>
        </tr>
    `).join("") : `<tr><td colspan="5" class="loading-row">אין עדיין חשבוניות</td></tr>`;

    document.querySelectorAll("[data-cancel]").forEach((btn) => btn.addEventListener("click", async () => {
        await apiJson(`/api/invoices/${btn.dataset.cancel}/cancel`, { method: "POST" });
        toast("החשבונית בוטלה", "success"); renderInvoices();
    }));
    document.querySelectorAll("[data-restore]").forEach((btn) => btn.addEventListener("click", async () => {
        await apiJson(`/api/invoices/${btn.dataset.restore}/restore`, { method: "POST" });
        toast("החשבונית שוחזרה", "success"); renderInvoices();
    }));
}

// ============================================================
// יומן ביקורת
// ============================================================

async function renderAudit() {
    setPageHeader("יומן ביקורת", "פעולות אחרונות במערכת", "");
    document.getElementById("pageBody").innerHTML = `<div class="card" style="padding:6px;"><table id="auditTable">
        <thead><tr><th>מתי</th><th>מי</th><th>פעולה</th><th>פרטים</th></tr></thead>
        <tbody><tr><td colspan="4" class="loading-row">טוען...</td></tr></tbody>
    </table></div>`;

    let entries;
    try { entries = await apiJson("/api/users/audit?limit=100").then((r) => r.entries); }
    catch (e) { document.querySelector("#auditTable tbody").innerHTML = `<tr><td colspan="4" class="loading-row">אין הרשאה לצפות בעמוד זה</td></tr>`; return; }

    document.querySelector("#auditTable tbody").innerHTML = entries.length ? entries.map((e) => `
        <tr>
            <td class="text-sm text-muted num">${escapeHtml(e.created_at || "")}</td>
            <td>${escapeHtml(e.user_name || "מערכת")}</td>
            <td>${escapeHtml(e.action)}</td>
            <td class="text-sm text-muted">${escapeHtml(e.details || "")}</td>
        </tr>
    `).join("") : `<tr><td colspan="4" class="loading-row">אין עדיין רשומות</td></tr>`;
}

boot();
