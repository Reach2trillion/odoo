/* global luxon */
import { markup, toRaw } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { floatIsZero } from "@web/core/utils/numbers";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { CashMoveReceipt } from "@point_of_sale/app/navbar/cash_move_popup/cash_move_receipt/cash_move_receipt";
import {
    KH_TZ,
    clean,
    enNb,
    fmtInt,
    fmtRate,
    halfUp,
    khDateTime,
    khMoney,
    khNumber,
    khPhone,
    khQty,
    khRate,
    khWeb,
    stripNb,
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
                tin_line: c.vat && tinLabel ? `${tinLabel} ${c.vat}` : "",
                cashier_name: order?.getCashierName?.() || this.get_cashier?.()?.name || "",
                logo_field: c.kh_has_receipt_logo ? "kh_receipt_logo" : "logo",
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
        try {
            this._khExportForPrinting(res);
        } catch (error) {
            // never block printing: the receipt falls back to the core content
            delete res.kh;
            console.error("pos_receipt_khmer: could not build the Khmer receipt data", error);
        }
        return res;
    },

    _khExportForPrinting(res) {
        const rate = khRate(this.company, this.models);
        const unpaid = !this.finalized;
        const isReceipt = this.company.kh_doc_title === "receipt";
        const taxTotals = res.taxTotals || this.taxTotals;
        const total = taxTotals.order_sign * taxTotals.order_total;
        const digits = this.currency?.decimal_places ?? 2;
        const pays = this.payment_ids.filter((p) => !p.is_change); // same filter and order as core
        const aligned = pays.length === res.paymentlines.length;

        // receipt-only USD strings without the NBSP and with the minus first ("-$6.00"); same
        // keys, same types, so the Orderline prop shape stays valid; undefined lines (pos_loyalty
        // guard) are left alone
        res.orderlines = res.orderlines.map((l) => {
            if (!l) {
                return l;
            }
            const copy = { ...l };
            for (const key of ["price", "unitPrice", "price_without_discount", "oldUnitPrice"]) {
                if (typeof copy[key] === "string") {
                    copy[key] = khMoney(copy[key]);
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

        // change: normalised here, whatever the 18.0 build computed (older builds have no
        // show_change, or show it on unpaid drafts as a negative "CHANGE -6.00").
        // Only a real, positive change on a paid order with at least one payment line.
        const orderChange =
            typeof res.order_change === "number" ? res.order_change : this.get_change();
        res.order_change = orderChange;
        res.show_change =
            (res.show_change ?? true) &&
            !unpaid &&
            orderChange > 0 &&
            !floatIsZero(orderChange, digits) &&
            res.paymentlines.length > 0;

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
        const totalKhr = rate ? halfUp(clean(total * rate)) : null;
        // KHR change (cash handling): nearest 100 riel, with an explicit rounding row
        let changeKhr = null;
        let changeRound = "";
        if (rate && res.show_change) {
            const exact = halfUp(clean(orderChange * rate));
            changeKhr = halfUp(clean((orderChange * rate) / 100)) * 100;
            if (changeKhr !== exact) {
                changeRound = (changeKhr > exact ? "+" : "-") + fmtInt(Math.abs(changeKhr - exact));
            }
        }

        res.kh = {
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
                    qty: khQty(d.qty),
                    // "1 × $5.00" shows the unit price before the discount
                    unit_price: disc ? d.price_without_discount || d.unitPrice : d.unitPrice,
                    disc_line: disc ? `បញ្ចុះតម្លៃ ${d.discount}% / ${d.discount}% discount` : "",
                };
            }),
            // same guard as pos_loyalty's own receipt rows
            loyalty: (res.loyaltyStats || [])
                .filter((s) => s.program?.portal_visible && (s.points?.won || s.points?.spent))
                .map((s) => ({
                    name: s.points.name || "Points",
                    won: s.points.won,
                    spent: s.points.spent,
                    balance: s.points.balance,
                })),
        };
    },
});

// ---------------------------------------------------------------------------------------------
// Template helpers
// ---------------------------------------------------------------------------------------------
patch(OrderReceipt.prototype, {
    /** "$6.00", "-$20.00": receipt-only USD formatting, no NBSP after the symbol. */
    khUsd(value) {
        const v = Number(value) || 0;
        const s = stripNb(this.props.formatCurrency(Math.abs(v)));
        return v < 0 && !floatIsZero(v, 6) ? "-" + s : s;
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
