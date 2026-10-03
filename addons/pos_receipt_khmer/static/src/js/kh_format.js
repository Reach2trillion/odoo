/** Formatting helpers for the Khmer / English receipt (no Odoo dependencies, unit-testable). */

export const KH_TZ = "Asia/Phnom_Penh";
const NB = " ";

/** Round half away from zero (Math.round rounds -0.5 towards +inf). */
export const halfUp = (x) => Math.sign(x) * Math.floor(Math.abs(x) + 0.5);
/** Kill binary float noise before rounding (2.675 * 100 = 267.49999...). */
export const clean = (x) => Math.round(x * 1e6) / 1e6;
/** Whole number with Western digits and "," groups: 24,600. */
export const fmtInt = (n) => halfUp(n).toLocaleString("en-US");
/** Remove the (narrow) no-break spaces that formatCurrency puts after "$": "$ 6.00" -> "$6.00". */
export const stripNb = (s) => (typeof s === "string" ? s.replace(/[  ]/g, "") : s);
/** Receipt money string: no NBSP and the minus before the symbol ("$ -6.00" -> "-$6.00"). */
export const khMoney = (s) =>
    typeof s === "string" ? stripNb(s).replace(/^([^\d\s.,-]+)-(?=\d)/, "-$1") : s;

/**
 * KHR per USD: the company's accounting rate (l10n_kh_tax, when installed and > 0),
 * else the rate of the KHR res.currency loaded into the POS, else 0 (= no KHR on the receipt).
 */
export function khRate(company, models) {
    if (company?.l10n_kh_exchange_rate > 0) {
        return company.l10n_kh_exchange_rate;
    }
    const khr = models?.["res.currency"]?.find?.((c) => c.name === "KHR");
    return khr?.rate > 0 ? khr.rate : 0;
}
/** 4,100 | 4,055.06 */
export const fmtRate = (r) => r.toLocaleString("en-US", { maximumFractionDigits: 2 });

/** "0312663333" -> "031 266 3333"; "+855 12 345 678" -> "012 345 678". Anything else unchanged. */
export function khPhone(raw) {
    if (!raw) {
        return "";
    }
    let d = String(raw).replace(/\D/g, "");
    if (d.startsWith("855")) {
        d = "0" + d.slice(3);
    }
    if (d.length === 9 || d.length === 10) {
        return `${d.slice(0, 3)} ${d.slice(3, 6)} ${d.slice(6)}`;
    }
    return String(raw);
}
/** "https://www.abjskincare.com/" -> "abjskincare.com" */
export const khWeb = (w) =>
    (w || "").replace(/^https?:\/\//, "").replace(/^www\./, "").replace(/\/$/, "");
/** "2.00" -> "2", "1.50" -> "1.5" */
export const khQty = (s) => {
    s = s === undefined || s === null ? "" : String(s);
    return s.includes(".") ? s.replace(/0+$/, "").replace(/\.$/, "") : s;
};
/** Keep an English half on one line so a bilingual label only wraps at " / ". */
export const enNb = (s) => s.replace(/ /g, NB);

/** "yyyy-MM-dd HH:mm:ss" (UTC, as stored) or a luxon DateTime -> "dd/MM/yyyy HH:mm" in Phnom Penh. */
export function khDateTime(value) {
    const { DateTime } = luxon;
    let dt;
    if (!value) {
        dt = DateTime.now();
    } else if (typeof value === "string") {
        dt = DateTime.fromSQL(value, { zone: "utc" });
        if (!dt.isValid) {
            dt = DateTime.fromISO(value, { zone: "utc" });
        }
    } else if (value instanceof DateTime) {
        dt = value;
    } else if (value instanceof Date) {
        dt = DateTime.fromJSDate(value);
    }
    return dt && dt.isValid ? dt.setZone(KH_TZ).toFormat("dd/MM/yyyy HH:mm") : "";
}

/**
 * The receipt number without the "Order " prefix that some 18.0 builds keep in
 * pos_reference once the order is synced ("Order 00030-001-0002" -> "00030-001-0002").
 */
export function khNumber(name, prefixes = []) {
    if (typeof name !== "string") {
        return name ? String(name) : "";
    }
    for (const p of [...prefixes, "Order "]) {
        if (p && p.trim() && name.startsWith(p) && name.length > p.length) {
            return name.slice(p.length).trim();
        }
    }
    return name;
}
