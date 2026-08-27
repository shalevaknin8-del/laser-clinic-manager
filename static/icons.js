// ============================================================
// static/icons.js
// ספריית אייקונים אחידה - קווי מתאר (outline) בגוון פחם עם פרט
// הדגשה אחד בזהב שמפניה בכל אייקון ("Duotone"), 24x24, קו 1.5px.
// בלי אימוג'ים, בלי אייקוני 3D - ראו README העיצוב.
//
// שימוש: ICONS.dashboard(size) מחזיר מחרוזת SVG מוכנה להטמעה.
// ============================================================

const ICON_INK = "#2C2C2C";
const ICON_GOLD = "#C9AC79";

function svgIcon(size, inner) {
    return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">${inner}</svg>`;
}

const ICONS = {
    dashboard: (size = 18) => svgIcon(size, `
        <rect x="3.5" y="3.5" width="7" height="7" rx="2" stroke="${ICON_INK}" stroke-width="1.5"/>
        <rect x="13.5" y="3.5" width="7" height="7" rx="2" stroke="${ICON_GOLD}" stroke-width="1.5"/>
        <rect x="3.5" y="13.5" width="7" height="7" rx="2" stroke="${ICON_GOLD}" stroke-width="1.5"/>
        <rect x="13.5" y="13.5" width="7" height="7" rx="2" stroke="${ICON_INK}" stroke-width="1.5"/>
    `),

    calendar: (size = 18) => svgIcon(size, `
        <rect x="3.5" y="5" width="17" height="15.5" rx="3" stroke="${ICON_INK}" stroke-width="1.5"/>
        <path d="M3.5 9.5H20.5" stroke="${ICON_INK}" stroke-width="1.5"/>
        <path d="M7.5 3V6.5" stroke="${ICON_GOLD}" stroke-width="1.5" stroke-linecap="round"/>
        <path d="M16.5 3V6.5" stroke="${ICON_GOLD}" stroke-width="1.5" stroke-linecap="round"/>
        <circle cx="8" cy="14" r="1.1" fill="${ICON_GOLD}"/>
    `),

    clients: (size = 18) => svgIcon(size, `
        <circle cx="9" cy="8" r="3.2" stroke="${ICON_INK}" stroke-width="1.5"/>
        <path d="M3.5 20c0-3.6 2.5-6 5.5-6s5.5 2.4 5.5 6" stroke="${ICON_INK}" stroke-width="1.5" stroke-linecap="round"/>
        <path d="M15.5 5.3c1.5.4 2.6 1.8 2.6 3.4 0 1.7-1.2 3.1-2.8 3.4" stroke="${ICON_GOLD}" stroke-width="1.5" stroke-linecap="round"/>
        <path d="M17 14.4c2 .5 3.5 2.5 3.5 5.1" stroke="${ICON_GOLD}" stroke-width="1.5" stroke-linecap="round"/>
    `),

    leads: (size = 18) => svgIcon(size, `
        <path d="M4 4.5H20L14 12.5V18.5L10 20.5V12.5L4 4.5Z" stroke="${ICON_INK}" stroke-width="1.5" stroke-linejoin="round"/>
        <circle cx="18.5" cy="6" r="2.2" fill="${ICON_GOLD}" stroke="#fff" stroke-width="0.5"/>
    `),

    packages: (size = 18) => svgIcon(size, `
        <path d="M12 3.5L20 7.5V16.5L12 20.5L4 16.5V7.5L12 3.5Z" stroke="${ICON_INK}" stroke-width="1.5" stroke-linejoin="round"/>
        <path d="M4 7.5L12 11.5L20 7.5" stroke="${ICON_INK}" stroke-width="1.5" stroke-linejoin="round"/>
        <path d="M12 11.5V20.5" stroke="${ICON_GOLD}" stroke-width="1.5"/>
    `),

    resources: (size = 18) => svgIcon(size, `
        <rect x="3.5" y="6.5" width="13" height="11" rx="2.5" stroke="${ICON_INK}" stroke-width="1.5"/>
        <path d="M9 12h2.2l1-2.4 1.4 4.8 1-2.4H16" stroke="${ICON_GOLD}" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M19.5 10v4" stroke="${ICON_INK}" stroke-width="1.5" stroke-linecap="round"/>
    `),

    staff: (size = 18) => svgIcon(size, `
        <circle cx="12" cy="8.2" r="3.4" stroke="${ICON_INK}" stroke-width="1.5"/>
        <path d="M5 20c0-3.9 3.1-6.5 7-6.5s7 2.6 7 6.5" stroke="${ICON_INK}" stroke-width="1.5" stroke-linecap="round"/>
        <path d="M12 15.5V18l1.6 1" stroke="${ICON_GOLD}" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
    `),

    invoices: (size = 18) => svgIcon(size, `
        <path d="M6 3.5H18V20.5L15.5 19L13 20.5L10.5 19L8 20.5L6 19V3.5Z" stroke="${ICON_INK}" stroke-width="1.5" stroke-linejoin="round"/>
        <path d="M9 8.5H15" stroke="${ICON_INK}" stroke-width="1.4" stroke-linecap="round"/>
        <path d="M9 12H13.5" stroke="${ICON_GOLD}" stroke-width="1.4" stroke-linecap="round"/>
    `),

    audit: (size = 18) => svgIcon(size, `
        <path d="M12 3.5L19.5 6.5V11C19.5 15.5 16.5 19 12 20.5C7.5 19 4.5 15.5 4.5 11V6.5L12 3.5Z" stroke="${ICON_INK}" stroke-width="1.5" stroke-linejoin="round"/>
        <path d="M9 11.5L11.2 13.7L15.5 9.3" stroke="${ICON_GOLD}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
    `),

    collapse: (size = 16) => svgIcon(size, `
        <path d="M15 5L9 12L15 19" stroke="${ICON_INK}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
    `),

    search: (size = 16) => svgIcon(size, `
        <circle cx="10.5" cy="10.5" r="6" stroke="${ICON_INK}" stroke-width="1.5"/>
        <path d="M20 20L15.2 15.2" stroke="${ICON_GOLD}" stroke-width="1.6" stroke-linecap="round"/>
    `),

    bell: (size = 17) => svgIcon(size, `
        <path d="M6 10.5C6 6.9 8.7 4.5 12 4.5C15.3 4.5 18 6.9 18 10.5C18 15 19.5 16 19.5 16H4.5C4.5 16 6 15 6 10.5Z" stroke="${ICON_INK}" stroke-width="1.5" stroke-linejoin="round"/>
        <path d="M10 19C10.4 19.7 11.1 20.1 12 20.1C12.9 20.1 13.6 19.7 14 19" stroke="${ICON_GOLD}" stroke-width="1.5" stroke-linecap="round"/>
    `),

    plus: (size = 15) => svgIcon(size, `
        <path d="M12 5V19" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
        <path d="M5 12H19" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
    `),

    chevronBack: (size = 16) => svgIcon(size, `
        <path d="M14 6L8 12L14 18" stroke="${ICON_INK}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
    `),

    contact: (size = 16) => svgIcon(size, `
        <path d="M4.5 5.5H19.5V16.5H9L4.5 20V5.5Z" stroke="${ICON_GOLD}" stroke-width="1.5" stroke-linejoin="round"/>
        <path d="M8 9.5H16" stroke="${ICON_GOLD}" stroke-width="1.3" stroke-linecap="round"/>
        <path d="M8 12.5H13" stroke="${ICON_GOLD}" stroke-width="1.3" stroke-linecap="round"/>
    `),

    empty: (size = 96) => svgIcon(size, `
        <rect x="16" y="30" width="52" height="8" rx="4" stroke="${ICON_INK}" stroke-width="1.6"/>
        <path d="M20 38V70C20 71.7 21.3 73 23 73H61C62.7 73 64 71.7 64 70V38" stroke="${ICON_INK}" stroke-width="1.6"/>
        <path d="M28 48H56" stroke="${ICON_INK}" stroke-width="1.4" stroke-linecap="round"/>
        <path d="M28 56H48" stroke="${ICON_INK}" stroke-width="1.4" stroke-linecap="round"/>
        <circle cx="70" cy="20" r="11" stroke="${ICON_GOLD}" stroke-width="1.6"/>
        <path d="M70 15V20L73.5 22.5" stroke="${ICON_GOLD}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
    `),
};
