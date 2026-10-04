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
/**
 * Receipt money string: Odoo's own sign order, without the NBSP after the symbol
 * ("$ 6.00" -> "$6.00", "$ -15.72" -> "$-15.72": what the cashier sees on the payment screen and
 * what core tours look for, "-15.72"). A negative amount that rounds to zero loses its minus
 * ("$ -0.00" -> "$0.00").
 */
export const khMoney = (s) => {
    if (typeof s !== "string") {
        return s;
    }
    s = stripNb(s);
    return /\d/.test(s) && !/[1-9]/.test(s) ? s.replace(/-(?=[\d.,])/, "") : s;
};

/**
 * KHR per unit of the POS currency, or 0 (= no KHR on the receipt).
 * - POS currency KHR (or unknown): 0, there is nothing to convert.
 * - l10n_kh_tax's company rate (KHR per unit of the *company* currency), when it is > 0 and the
 *   POS sells in the company currency (ABJ: USD company, USD POS, 4,100).
 * - else the KHR res.currency loaded into the POS: its rate and the POS currency's rate are both
 *   relative to the company currency, so KHR per POS unit = KHR.rate / posCurrency.rate.
 */
export function khRate(company, models, currency) {
    const code = currency?.name;
    if (!code || code === "KHR") {
        return 0;
    }
    const companyCode = company?.currency_id?.name;
    if (company?.l10n_kh_exchange_rate > 0 && (!companyCode || companyCode === code)) {
        return company.l10n_kh_exchange_rate;
    }
    const khr = models?.["res.currency"]?.find?.((c) => c.name === "KHR");
    const own = currency.rate > 0 ? currency.rate : companyCode === code ? 1 : 0;
    return khr?.rate > 0 && own > 0 ? khr.rate / own : 0;
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
/**
 * Quantity string without trailing decimal zeros, in the locale it was formatted with:
 * "2.00" -> "2", "1.50" -> "1.5", "1,000.00" -> "1,000"; with decimalPoint ",": "1.000,00" -> "1.000".
 */
export const khQty = (s, decimalPoint = ".") => {
    s = s === undefined || s === null ? "" : String(s);
    const i = decimalPoint ? s.lastIndexOf(decimalPoint) : -1;
    if (i < 0) {
        return s;
    }
    const frac = s.slice(i + decimalPoint.length);
    if (!/^\d+$/.test(frac)) {
        return s; // not "<int><point><digits>": leave it as formatted
    }
    const kept = frac.replace(/0+$/, "");
    return kept ? s.slice(0, i + decimalPoint.length) + kept : s.slice(0, i);
};
/** Loyalty points: "100,365", "12.5" (en-US groups like every KHR figure). */
export const fmtPts = (n) =>
    Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 2 });
/** Signed points: "+120", "-5", "0". */
export const fmtPtsSigned = (n) => (n > 0 ? "+" : n < 0 ? "-" : "") + fmtPts(Math.abs(n || 0));
/** Keep an English half on one line so a bilingual label only wraps at " / ". */
export const enNb = (s) => s.replace(/ /g, NB);

/**
 * Signed order total of the export_for_printing data, whatever the 18.0 build:
 * taxTotals.order_sign * taxTotals.order_total (order_sign only exists since Odoo 186bb06b,
 * 2024-12-16; taxTotals since 8fb7e5fd, 2024-11-29), else amount_total (every build).
 * NaN when neither is a number.
 */
export function khOrderTotal(data) {
    const t = data?.taxTotals;
    if (t && typeof t.order_total === "number") {
        return (typeof t.order_sign === "number" ? t.order_sign : 1) * t.order_total;
    }
    return typeof data?.amount_total === "number" ? data.amount_total : NaN;
}
/** Signed cash rounding of the order (taxTotals.order_rounding, or rounding_applied before 8fb7e5fd). */
export function khOrderRounding(data) {
    const t = data?.taxTotals;
    if (t && typeof t.order_rounding === "number") {
        return (typeof t.order_sign === "number" ? t.order_sign : 1) * t.order_rounding;
    }
    return typeof data?.rounding_applied === "number" ? data.rounding_applied : 0;
}

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

/**
 * Receipt paper of a pos.config: { paper: "80" | "58", raster_w: 0 on 80 mm, else the 58 mm raster
 * width in dots (pos.config.kh_raster_dots, 360-384; 384 when unset) }.
 */
export function khPaper(config) {
    const paper = config?.kh_paper_width === "58" ? "58" : "80";
    return { paper, raster_w: paper === "58" ? config.kh_raster_dots || 384 : 0 };
}
