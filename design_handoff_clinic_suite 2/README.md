# Handoff: Clinic Suite — Laser Clinic Management Dashboard

## Overview
An RTL (Hebrew) internal web app for managing a laser/aesthetics clinic: daily dashboard, calendar/scheduling, client roster + profiles, and a lead pipeline (kanban). Single logged-in staff persona ("דנה כספי", clinic manager).

## About the Design Files
The bundled file (`Clinic Suite.dc.html`) is a **design reference built in HTML/CSS with a small React-like runtime** — a working prototype showing intended look, layout, and interaction, not production code to copy directly. The task is to **recreate this design in the target codebase's existing environment** (React, Vue, native, etc.) using its established component library, state management, and data layer — or, if no environment exists yet, choose the most appropriate stack and implement fresh.

## Fidelity
**High-fidelity.** Colors, typography, spacing, and copy are final. Recreate pixel-close using the codebase's own component patterns; treat exact hex values, font sizes, and radii below as source of truth.

## Global layout
- Direction: `dir="rtl"`, Hebrew UI throughout.
- Two-column app shell: fixed-height sidebar (full viewport height, sticky) + main content area that scrolls.
- Sidebar width: 248px expanded / 78px collapsed (collapses via a toggle at the bottom; labels fade out via opacity, icons stay). Animate width with `.28s cubic-bezier(.4,0,.2,1)`.
- Main content: header bar (page title + search + notification bell + primary "תור חדש" / New Appointment button) followed by a screen-specific body, padded `6px 34px 40px`.

## Design tokens

### Colors
- Background: `#FAF9F6` (warm off-white)
- Ink / primary text: `#2C2C2C`
- Muted text: `#8A8781`, `#A9A59C`, `#B4B0A8` (descending emphasis), secondary text `#6E6A63`
- Card surface: `#FFFFFF`, card shadow: `0 1px 2px rgba(44,44,44,0.03), 0 14px 34px rgba(44,44,44,0.055)`
- Borders/dividers: `rgba(44,44,44,0.045–0.07)`
- Brand accent (gold): `#C9AC79` (bar/highlight), `#A8874F` (link/ink-on-tint), `#B99A64` (progress-bar dark stop), gradient `linear-gradient(150deg, #C9AC79, #A8874F)` for the logo mark
- Links: default `#A8874F`, hover `#8A6D3B`
- Dark UI elements (primary buttons, active nav bar): `#2C2C2C`, hover `#3D3B37`
- Status/category tint system (background / dot·accent / ink), used for avatars, appointment blocks, lead source tags, calendar dots:
  - pink: bg `#F8EFF1`, dot `#C48B9F`, ink `#A9788A`
  - sage: bg `#EFF3EE`, dot `#7E9A85`, ink `#6F8A76`
  - blue: bg `#EDF1F6`, dot `#7D93AD`, ink `#6C8399`
  - gold: bg `#F5F0E6`, dot `#C9AC79`, ink `#A8874F`
- Positive delta chip: bg `#EFF3EE`, text/icon `#6F8A76`/`#7E9A85`
- Negative/soft-alert chip: bg `#F8EFF1`, text/icon `#A9788A`/`#C48B9F`
- Progress bar track: `#F1EFEA`; fill gradient `linear-gradient(90deg, #D9C49B, #B99A64)`

### Typography
- Hebrew UI font: **Assistant** (weights 200–800), Google Font, fallback `'Segoe UI', sans-serif`.
- Numeric/data font (KPIs, times, prices, table numerals): **Plus Jakarta Sans** (300–600), applied to anything showing digits — money figures, clock times, session counts.
- Scale: page title 25px/600 (letter-spacing -0.5px); card KPI figure 32px/500 (Plus Jakarta Sans, -1.2px); section heading 16–17px/600; body 13.5–14.5px; small meta/labels 11–12.5px, color muted.

### Radii & shadows
- Cards/panels: 18px radius.
- Nested rows/pills/buttons: 10–14px.
- Avatars: full circle.
- Standard card shadow: `0 1px 2px rgba(44,44,44,0.03), 0 14px 34px rgba(44,44,44,0.055)` (lighter `0 8px 22px rgba(44,44,44,0.05)` on kanban cards).

### Icons
Custom 24×24 outline SVGs (stroke `#2C2C2C` with one gold `#C9AC79` accent stroke/fill per icon), ~19px rendered size in nav, 15–17px in header/actions. No icon library — recreate as a small in-house icon set or swap for the codebase's icon system matching the two-tone (neutral + gold accent) style.

## Screens / Views

### 1. Sidebar navigation (persistent)
- Logo mark (30×30 gradient gold rounded square with a ring glyph) + clinic name "לומין אסתטיקס" / subtitle "קליניקת לייזר · תל אביב".
- Nav items: לוח בקרה (Dashboard), יומן וזימונים (Calendar), לקוחות (Clients), צינור לידים (Leads pipeline) — each with icon + label; active item gets tint bg `#F5F0E6`, a 2px gold vertical bar floating just outside the item's edge, bold dark text.
- Secondary nav (non-interactive in this prototype): קטלוג וחבילות (Catalog/Packages), מכשירים וחדרים (Devices/Rooms).
- Footer: collapse toggle (chevron flips on collapse) + a user card (avatar initials "ד״כ", name, role "מנהלת קליניקה").

### 2. Dashboard (default screen)
Title "לוח בקרה", crumb "ברוכה הבאה, דנה".
- **3 KPI cards** (grid, equal width): הכנסות החודש (Monthly revenue) with ₪ figure + up/down % chip + comparison line + faint sparkline background; לידים חדשים (New leads) same pattern; תורים היום (Today's appointments) same pattern with occupancy note. Sparkline: thin `#DCD8D0` polyline, 50% opacity, absolutely positioned along the card's bottom edge.
- **Today's timeline** (left, ~65% width): "ציר היום" header + date + "כל היומן" link. Vertical timeline: time+duration column, a dot-on-line rail (7px dot in the tint's dot color), and an appointment row (colored tint background, colored left bar, client name + treatment + resource/room/staff line, optional package-progress pill, status text colored by state: מאושר=sage green text, ממתין=muted). Includes an **empty state** (illustrative outline SVG + "היומן פנוי היום" message + CTA) toggled by an `emptyToday` flag — build both.
- **Right column**: "דורש מעקב" (Needs follow-up) list — avatar-initial rows with name, source + time-since, WhatsApp icon action. "חבילות בסיום" (Packages nearing completion) — name + treatment + fraction with a gradient progress bar per client.

### 3. Calendar
Title "יומן הקליניקה", crumb "ניהול זימונים".
- Toolbar: prev/next chevrons, a date-range label, a 3-way segmented control (יום/שבוע/חודש — day/week/month) with sliding white pill + shadow on the active segment, and a legend (3 colored dots: לייזר=pink, פנים=sage, ייעוץ=blue).
- **Week/Day view**: CSS-grid time grid — fixed 54px hour-label column + one column per visible day (1 for day view, 6 for week, Sun–Fri). Hour rows at 56px/hour from 09:00–19:00. Appointment blocks are absolutely positioned (`top`/`height` computed from start time & duration in minutes), rounded 10px, tinted background, colored left bar, client + treatment truncated with ellipsis. Hover shows a fixed-position tooltip card (246px wide) with client, treatment, time, package, and a WhatsApp icon — positioned near the cursor via mouse-enter bounding-rect math, dismissed on mouse-leave.
- **Month view**: 7-column grid, day-name header row, 42 day cells (6 weeks), each cell showing the date number (today = white numeral on gold-filled circle), dimmed opacity for days outside the current month, and up to a few small colored dots representing that day's appointment tints.

### 4. Clients — list
Title "לקוחות", crumb "מרכז לקוחות".
- Single card containing a header row (לקוחה/טלפון/טיפול אחרון/חבילה פעילה/הכנסה) and one row per client: avatar-initials (tinted), name + "customer since" line, phone (LTR, Plus Jakarta Sans), last treatment + date, active package name + slim progress bar, total revenue (bold, Plus Jakarta Sans), chevron. Row click opens the profile.

### 5. Clients — profile
Crumb "מרכז לקוחות", title "כרטיס לקוחה". Back link at top of the main card returns to the list.
- Header block: large avatar-initials circle, name + tier pill (e.g. "לקוחת חבילה", gold tint), phone + email, WhatsApp + "זימון תור" (Book appointment) action buttons.
- **Tabs**: פרטים (Details) / היסטוריית טיפולים (History) / מסמכים (Docs) — active tab bold + 2px gold underline (`inset 0 -2px 0 0`).
  - Details: 2-column key/value grid — address, join date, Fitzpatrick skin type, health declaration (sage-colored "signed" text), preferred machine, sensitivities/notes.
  - History: table rows — date (Plus Jakarta Sans), treatment, staff, price (right-aligned, Plus Jakarta Sans).
  - Docs: 3-column card grid — file icon, doc name, meta (type/date/count).
- **Right rail**: "חבילה פעילה" card — big done/total counter + gradient progress bar + next-session note. "סיכום כספי" card — cumulative revenue, open invoices, last visit, as label/value rows.

### 6. Leads (kanban)
Title "צינור לידים", crumb "ניהול לידים".
- 4 columns (equal width) representing pipeline stages: ליד חדש (new), נוצר קשר (contacted), ייעוץ נקבע (booked), הומר ללקוחה (converted) — each with a colored dot, title, and count.
- Cards are HTML5-draggable (`draggable`, `dragstart`/`dragend`/`dragover`/`drop`) between columns; dragged card dims to 45% opacity, target column background darkens slightly on drag-over. Card: avatar-initials, name, phone (LTR), free-text note, source tag (tinted pill), relative age, WhatsApp icon.

## Interactions & Behavior
- All navigation is client-side state (`screen` value: dashboard/calendar/clients/leads); no real routing/URLs in the prototype — implement real routes in production.
- Sidebar collapse is local UI state, persists only in-session in the prototype.
- Calendar view (day/week/month) and week/month offset are local state; "today" is hardcoded to **Wed, Aug 26, 2026** for the mock data — replace with real current date and live data.
- Calendar hover tooltip: attach on mouseenter with the hovered element's bounding rect to position a fixed tooltip; clear on mouseleave.
- Client profile tab and selected client are local state; opening a client resets to the Details tab.
- Leads drag-and-drop mutates the lead's `stage` field on drop; no persistence beyond in-memory state in the prototype.
- No loading/error states are designed — mock data renders instantly. Design these states before shipping.
- No responsive/mobile layout is designed — this is a desktop-oriented internal tool. Confirm target breakpoints before implementing.

## State Management
Suggested state shape for a real implementation:
- `currentScreen`: 'dashboard' | 'calendar' | 'clients' | 'leads'
- `sidebarCollapsed`: boolean
- Calendar: `view` ('day'|'week'|'month'), `weekOffset`/`monthOffset` (or a real selected date)
- Clients: `selectedClientId`, `activeProfileTab`
- Leads: `leads[]` with a `stage` field per lead, updated via drag/drop (or explicit move action)
- Server data needed: clinic KPIs (revenue, leads, appointments/occupancy), today's/period appointments, client roster + profiles + treatment history + documents, lead pipeline records, staff/room/device catalog (referenced but not yet screens).

## Assets
No external images. All icons are hand-drawn inline SVGs (see Icons above). Sparkline charts are static inline SVG polylines (mock data — wire to real revenue/lead/appointment time series). Fonts loaded from Google Fonts: Assistant, Plus Jakarta Sans.

## Files
- `Clinic Suite.html` — the full design prototype (all 6 screens + interactions), included in this folder for reference.
- `screenshots/01-dashboard.png`, `02-calendar.png`, `03-clients-list.png`, `04-client-profile.png`, `05-leads.png` — static reference captures of each screen.
