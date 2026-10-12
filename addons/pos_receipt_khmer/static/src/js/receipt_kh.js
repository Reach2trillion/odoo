/* global luxon */
import { markup, toRaw } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { localization } from "@web/core/l10n/localization";
import { patch } from "@web/core/utils/patch";
import { floatIsZero } from "@web/core/utils/numbers";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { Orderline } from "@point_of_sale/app/generic_components/orderline/orderline";
import { CashMoveReceipt } from "@point_of_sale/app/navbar/cash_move_popup/cash_move_receipt/cash_move_receipt";
import {
    KH_TZ,
    clean,
    enNb,
    fmtInt,
    fmtPts,
    fmtPtsSigned,
    fmtRate,
    halfUp,
    hasKhmer,
    khDateTime,
    khMoney,
    khNumber,
    khOrderRounding,
    khOrderTotal,
    khPaper,
    khPhone,
    khQty,
    khRate,
    khWeb,
    khWords,
} from "./kh_format";

// Every Khmer / bilingual string below is deliberately literal (not _t()): the cashier's UI
// language must not change the receipt, and point_of_sale's km.po is stale.

const TIN_LABELS = {
    tin: "លេខអត្តសញ្ញាណកម្ម / TIN",
    vattin: "លេខអត្តសញ្ញាណកម្ម អតប / VATTIN",
};

/** Prefix of the translated "Order %s" (pos_reference of synced orders in some 18.0 builds). */
function orderPrefixes() {
    try {
        const marker = "\u0001";
        const translated = String(_t("Order %s", marker));
        const i = translated.indexOf(marker);
        return i > 0 ? [translated.slice(0, i)] : [];
    } catch {
        return [];
    }
}

// ---------------------------------------------------------------------------------------------
// Receipt-only orderline key (export_for_printing copies): the product name printed under the
// Khmer name. OrderReceipt passes the whole line to the shared Orderline, whose props are
// validated in debug mode: register the key like pos_sale registers so_reference / details.
// ---------------------------------------------------------------------------------------------
patch(Orderline, {
    props: {
        ...Orderline.props,
        line: {
            ...Orderline.props.line,
            shape: {
                ...Orderline.props.line.shape,
                kh_name_en: { type: String, optional: true },
            },
        },
    },
});

// ---------------------------------------------------------------------------------------------
// Header data (ReceiptHeader): also used by the cash in/out slip, which has no order
// ---------------------------------------------------------------------------------------------
patch(PosStore.prototype, {
    getReceiptHeaderData(order) {
        const res = super.getReceiptHeaderData(...arguments);
        try {
            const c = this.company;
            const tinLabel = TIN_LABELS[c.kh_tin_label || "tin"];
            res.kh = {
                name_km: c.kh_name || "",
                addr_km: c.kh_address_km || [c.city, c.state_id?.name].filter(Boolean).join(" "),
                addr_en: c.kh_address_en || "",
                phone: khPhone(c.phone),
                web_line: [khWeb(c.website), c.email].filter(Boolean).join(" · "),
                // WORD JOINER after each hyphen: a VATTIN such as K008-901701793 never breaks
                // inside the number (the row wraps before it instead)
                tin_line: c.vat && tinLabel ? `${tinLabel} ${c.vat.replace(/-/g, "-\u2060")}` : "",
                cashier_name: order?.getCashierName?.() || this.get_cashier?.()?.name || "",
                logo_field: c.kh_has_receipt_logo ? "kh_receipt_logo" : "logo",
                // the cash in/out slip takes its paper width from here (it has no order)
                ...khPaper(this.config),
            };
        } catch (error) {
            console.error("pos_receipt_khmer: could not build the receipt header data", error);
        }
        return res;
    },
});

// ---------------------------------------------------------------------------------------------
// Order data (OrderReceipt): spread super, add keys, never rename
// ---------------------------------------------------------------------------------------------
patch(PosOrder.prototype, {
    export_for_printing(baseUrl, headerData) {
        const res = super.export_for_printing(...arguments);
        // the template's change row reads these two keys on every build: normalise them first,
        // on their own, so they are right even if the Khmer data below fails
        try {
            this._khNormaliseChange(res);
        } catch (error) {
            console.error("pos_receipt_khmer: could not normalise the change", error);
        }
        try {
            this._khExportForPrinting(res);
        } catch (error) {
            // never block printing: without res.kh the root gets no o_kh_receipt class, so none of
            // the receipt CSS applies and the core receipt (header included) prints as is
            delete res.kh;
            if (res.headerData?.kh) {
                res.headerData = { ...res.headerData };
                delete res.headerData.kh;
            }
            // ...but on a 58 mm till the core receipt is still scaled to the raster width (the
            // same rule as core's Daily Sales report), so the printer gets an image it can print
            res.kh_paper = khPaper(this.config);
            console.error("pos_receipt_khmer: could not build the Khmer receipt data", error);
        }
        return res;
    },

    /**
     * Khmer names of the exported orderlines: a function (exported line, index) -> undefined (print
     * the line as is) or { main, en }: main replaces productName, en (Khmer + English only) is the
     * English name printed under it. The Khmer name is product.product.kh_pos_name_km (computed by
     * the server: "Khmer name (receipt)", else the km_KH translation of the name).
     * The POS loads product names in the cashier's language: productName is Khmer for a km_KH
     * cashier when the product has a Khmer translation. The English line is therefore the en_US name
     * the server sends with the Khmer name (kh_pos_name_en: display name with the variant values)
     * plus what productName adds to the product's display name (the values of attributes that do not
     * create variants: "Desk (Custom: Oak)").
     */
    _khProductNames() {
        const mode = ["both", "km", "en"].includes(this.config?.kh_product_names)
            ? this.config.kh_product_names
            : "both";
        if (mode === "en") {
            return () => undefined;
        }
        // the exported lines are getSortedOrderlines() in order; if another module filtered or
        // reordered them, find the order line by its full product name instead of the index
        const sorted = this.getSortedOrderlines?.() || [];
        const byName = new Map();
        for (const ol of this.lines || []) {
            const n = ol.get_full_product_name?.();
            if (n && !byName.has(n)) {
                byName.set(n, ol);
            }
        }
        /** The rest of `name` after `base` (" (Black)" -> "(Black)"), or null when it does not start with it. */
        const after = (name, base) => (base && name.startsWith(base) ? name.slice(base.length).trim() : null);
        return (l, i) => {
            const name = l?.productName;
            if (typeof name !== "string") {
                return undefined;
            }
            const ol = sorted[i]?.get_full_product_name?.() === name ? sorted[i] : byName.get(name);
            const product = ol?.product_id;
            const km = (product?.kh_pos_name_km || "").trim();
            if (!km) {
                return undefined;
            }
            if (mode === "km") {
                if (km === name.trim()) {
                    return undefined;
                }
                // keep the attribute values of the name: "Desk (Black)" -> "<Khmer> (Black)"
                const rest = after(name, product.name || "") || "";
                return { main: rest.startsWith("(") ? `${km} ${rest}` : km };
            }
            // English line: the en_US name + the extra attribute values of productName; without the
            // en_US name (older data) or when productName is not built from the product's display name
            // (a reprinted order saved in another language, a renamed product): productName if it has
            // no Khmer letters, else the en_US name alone
            const enBase = (product.kh_pos_name_en || "").trim();
            const extra = after(name, product.display_name || "");
            let en;
            if (!enBase) {
                en = name;
            } else if (extra !== null) {
                en = extra ? `${enBase} ${extra}` : enBase;
            } else {
                en = hasKhmer(name) ? enBase : name;
            }
            if (km === en.trim()) {
                return undefined;
            }
            return { main: km, en };
        };
    },

    /**
     * Khmer only: the product names of pos_sale's down-payment details (the sale order lines, saved
     * with the line as display names) are replaced with the Khmer name of the loaded product of that
     * name, when there is one. "Khmer + English" keeps them (one table cell per name: no room for a
     * second line without changing pos_sale's template). Returns a function (name) -> name.
     */
    _khDetailNames() {
        if (this.config?.kh_product_names !== "km") {
            return (n) => n;
        }
        let map;
        return (n) => {
            if (typeof n !== "string") {
                return n;
            }
            if (!map) {
                map = new Map();
                for (const p of this.models?.["product.product"]?.getAll?.() || []) {
                    const km = (p.kh_pos_name_km || "").trim();
                    if (km) {
                        for (const key of [p.display_name, p.kh_pos_name_en]) {
                            if (key && !map.has(key)) {
                                map.set(key, km);
                            }
                        }
                    }
                }
            }
            return map.get(n) || n;
        };
    },

    /**
     * order_change / show_change, whatever the 18.0 build computed (older builds have no
     * show_change, or show it on unpaid drafts as a negative "CHANGE -6.00"): only a real,
     * positive change on a paid order with at least one payment line.
     */
    _khNormaliseChange(res) {
        const digits = this.currency?.decimal_places ?? 2;
        const orderChange =
            typeof res.order_change === "number" ? res.order_change : this.get_change();
        res.order_change = orderChange;
        res.show_change =
            (res.show_change ?? true) &&
            this.finalized &&
            Number.isFinite(orderChange) &&
            orderChange > 0 &&
            !floatIsZero(orderChange, digits) &&
            (res.paymentlines?.length || 0) > 0;
    },

    _khExportForPrinting(res) {
        const currency = this.currency;
        const rate = khRate(this.company, this.models, currency);
        const unpaid = !this.finalized;
        const isReceipt = this.company.kh_doc_title === "receipt";
        // build-independent (taxTotals / order_sign do not exist on every 18.0 build)
        const total = khOrderTotal(res);
        const digits = currency?.decimal_places ?? 2;
        const pays = this.payment_ids.filter((p) => !p.is_change); // same filter and order as core
        const aligned = pays.length === res.paymentlines.length;
        const khName = this._khProductNames();
        const detailName = this._khDetailNames();

        // receipt-only USD strings without the NBSP, in Odoo's sign order ("$6.00", "$-6.00");
        // same keys, same types, so the Orderline prop shape stays valid; undefined lines
        // (pos_loyalty guard) are left alone
        res.orderlines = res.orderlines.map((l, i) => {
            if (!l) {
                return l;
            }
            const copy = { ...l };
            for (const key of ["price", "unitPrice", "price_without_discount", "oldUnitPrice"]) {
                if (typeof copy[key] === "string") {
                    copy[key] = khMoney(copy[key]);
                }
            }
            // 100 % discount: core prints the translated "Free" instead of an amount
            if (copy.discount === "100" && typeof copy.price === "string" && !/\d/.test(copy.price)) {
                copy.price = "ឥតគិតថ្លៃ / Free";
            }
            // pos_sale down-payment details ("$ 1,800.00" -> "$1,800.00"; Khmer only: Khmer names)
            if (Array.isArray(copy.details)) {
                copy.details = copy.details.map((d) =>
                    d && typeof d === "object"
                        ? {
                              ...d,
                              total: khMoney(d.total),
                              product_name: detailName(d.product_name),
                          }
                        : d
                );
            }
            // Khmer product name (pos.config.kh_product_names): the copy's productName becomes the
            // Khmer name; "both" keeps the product name in kh_name_en, printed under it
            const names = khName(l, i);
            if (names) {
                copy.productName = names.main;
                if (names.en) {
                    copy.kh_name_en = names.en;
                }
            }
            return copy;
        });
        res.paymentlines = res.paymentlines.map((pl, i) => {
            const payment = aligned ? pays[i] : undefined;
            const pm = payment?.payment_method_id;
            const name =
                pm?.kh_receipt_label ||
                (pm?.type === "cash"
                    ? "សាច់ប្រាក់ / Cash"
                    : pm?.type === "pay_later"
                    ? `គណនីអតិថិជន / ${enNb("Customer Account")}`
                    : pl.name);
            return { ...pl, name, kh_txn: payment?.transaction_id || "" };
        });

        // change: normalised by _khNormaliseChange (export_for_printing)
        const orderChange = res.order_change;

        res.label_total = markup(
            unpaid
                ? '<span class="kh-lbl-km">ប្រាក់ត្រូវបង់</span><span class="kh-lbl-en">AMOUNT DUE</span>'
                : '<span class="kh-lbl-km">សរុប</span><span class="kh-lbl-en">TOTAL</span>'
        );
        res.label_change = markup(
            '<span class="kh-lbl-km">ប្រាក់អាប់</span><span class="kh-lbl-en">CHANGE</span>'
        );
        res.label_discounts = markup("<span>បញ្ចុះតម្លៃសរុប / Total discount</span>");
        res.label_rounding = markup("<span>ការបង្គត់ / Rounding</span>");

        // KHR total: exact conversion to 1 riel (Notification 4908), never rounded to 100
        const totalKhr = rate && Number.isFinite(total) ? halfUp(clean(total * rate)) : null;
        // KHR change (cash handling): the exact riel amount rounded to the nearest 100 riel (from
        // the exact amount, so the rounding row always adds up), with an explicit rounding row;
        // nothing when it rounds to 0 riel (e.g. $0.01)
        let changeKhr = null;
        let changeRound = "";
        if (rate && res.show_change) {
            const exact = halfUp(clean(orderChange * rate));
            const cash = halfUp(exact / 100) * 100;
            if (cash > 0) {
                changeKhr = cash;
                if (cash !== exact) {
                    changeRound = (cash > exact ? "+" : "-") + fmtInt(Math.abs(cash - exact));
                }
            }
        }

        res.kh = {
            // paper: "80" | "58", raster_w: 0 on 80 mm, else the 58 mm raster width in dots
            ...khPaper(this.config),
            unpaid,
            title_km: isReceipt ? "បង្កាន់ដៃលក់" : "វិក្កយបត្រ",
            title_en: isReceipt ? "SALES RECEIPT" : "INVOICE",
            number_label: unpaid
                ? "លេខបញ្ជាទិញ / Order No."
                : isReceipt
                ? "លេខបង្កាន់ដៃ / Receipt No."
                : "លេខវិក្កយបត្រ / Invoice No.",
            number: khNumber(res.name, orderPrefixes()),
            not_doc_km: isReceipt
                ? "នេះ​មិនមែន​ជា​បង្កាន់ដៃ​ទេ"
                : "នេះ​មិនមែន​ជា​វិក្កយបត្រ​ទេ",
            not_doc_en: isReceipt ? "This is not a receipt" : "This is not an invoice",
            date: khDateTime(this.date_order),
            partner_name: this.get_partner()?.name || "",
            rate_text: rate ? fmtRate(rate) : "",
            rate_from: currency?.name || "",
            total_khr:
                totalKhr === null ? "" : (totalKhr < 0 ? "-" : "") + fmtInt(Math.abs(totalKhr)),
            change_khr: changeKhr === null ? "" : fmtInt(changeKhr),
            change_round: changeRound,
            due:
                unpaid && res.paymentlines.length && orderChange < 0 && !floatIsZero(orderChange, digits)
                    ? -orderChange
                    : 0,
            // indexed like res.orderlines (OrderReceipt.khLine finds a line by identity)
            lines: res.orderlines.map((d) => {
                if (!d) {
                    return null;
                }
                // same condition as the core discount <li> of the Orderline template
                const disc = Boolean(d.discount && d.discount !== "0");
                return {
                    // the name as word boxes (deterministic wrapping, see the stylesheet 6b), on every
                    // line (a Khmer name, a product without one, "English only"), and the English
                    // name printed under a Khmer name
                    name_words: typeof d.productName === "string" ? khWords(d.productName) : null,
                    name_km: hasKhmer(d.productName),
                    en_words: d.kh_name_en ? khWords(d.kh_name_en) : null,
                    en_latin: Boolean(d.kh_name_en) && !hasKhmer(d.kh_name_en),
                    qty: khQty(d.qty, localization.decimalPoint),
                    // "1 × $5.00" shows the unit price before the discount
                    unit_price: disc ? d.price_without_discount || d.unitPrice : d.unitPrice,
                    disc_line: disc ? `បញ្ចុះតម្លៃ ${d.discount}% / ${d.discount}% discount` : "",
                };
            }),
            // same guard as pos_loyalty's own receipt rows. Not on an unpaid pre-receipt: nothing
            // is earned or spent before payment, and the balance would not add up.
            loyalty: unpaid
                ? []
                : (res.loyaltyStats || [])
                      .filter((s) => s.program?.portal_visible && (s.points?.won || s.points?.spent))
                      .map((s) => ({
                          // block heading when there are several programs: the program's name
                          // (the points name is often the same "Points" for every program)
                          name: s.program?.name || s.points.name || "",
                          won: s.points.won ? fmtPtsSigned(s.points.won) : "",
                          // spent points print as a deduction ("-5")
                          spent: s.points.spent ? fmtPtsSigned(-s.points.spent) : "",
                          balance: s.points.balance ? fmtPts(s.points.balance) : "",
                      })),
        };
    },
});

// ---------------------------------------------------------------------------------------------
// Template helpers
// ---------------------------------------------------------------------------------------------
patch(OrderReceipt.prototype, {
    /** "$6.00", "$-20.00": receipt-only USD formatting, Odoo's sign order without the NBSP. */
    khUsd(value) {
        const v = Number(value) || 0;
        return khMoney(this.props.formatCurrency(floatIsZero(v, 6) ? 0 : v));
    },
    /** Signed order total, whatever the 18.0 build (see khOrderTotal). */
    khTotal() {
        const total = khOrderTotal(this.props.data);
        return Number.isFinite(total) ? total : 0;
    },
    /** Signed cash rounding of the order, whatever the 18.0 build. */
    khRounding() {
        return khOrderRounding(this.props.data) || 0;
    },
    /**
     * Receipt-only data of the orderline rendered in the <Orderline> slot. The slot's `line`
     * comes through OrderWidget's props, so it can be a different reactive proxy of the same
     * object than this.props.data.orderlines[i]: compare the raw objects.
     */
    khLine(line) {
        const data = this.props.data;
        const target = toRaw(line);
        const i = (data.orderlines || []).findIndex((l) => l === line || toRaw(l) === target);
        return i >= 0 ? data.kh?.lines?.[i] : undefined;
    },
});

patch(CashMoveReceipt.prototype, {
    get khMove() {
        // the popup passes _t(type) ("in" / "out")
        const isIn = String(this.props.translatedType) === String(_t("in"));
        return {
            km: isIn ? "ដាក់ប្រាក់ចូល" : "ដកប្រាក់ចេញ",
            en: isIn ? "CASH IN" : "CASH OUT",
            amount: khMoney(this.props.formattedAmount),
            // printed at the moment of the move (the popup's own date string uses the browser zone)
            date: luxon.DateTime.now().setZone(KH_TZ).toFormat("dd/MM/yyyy HH:mm"),
        };
    },
});
