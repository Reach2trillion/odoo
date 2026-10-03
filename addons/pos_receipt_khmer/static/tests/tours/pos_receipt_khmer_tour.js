/* global posmodel */
import * as Chrome from "@point_of_sale/../tests/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/tours/utils/dialog_util";
import * as ProductScreen from "@point_of_sale/../tests/tours/utils/product_screen_util";
import * as PaymentScreen from "@point_of_sale/../tests/tours/utils/payment_screen_util";
import * as ReceiptScreen from "@point_of_sale/../tests/tours/utils/receipt_screen_util";
import { registry } from "@web/core/registry";

function check(content, fn) {
    return { content, trigger: "body", run: fn };
}

registry.category("web_tour.tours").add("pos_receipt_khmer_tour", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.addOrderline("Desk Pad", "1"),
            // unpaid draft (what a pre-receipt prints): AMOUNT DUE, never a change row
            check("draft order exports an unpaid pre-receipt", () => {
                const data = posmodel.orderExportForPrinting(posmodel.get_order());
                if (!data.kh || !data.kh.unpaid) {
                    throw new Error("a draft order must be exported as unpaid");
                }
                if (data.show_change) {
                    throw new Error("an unpaid pre-receipt must not print a change row");
                }
                if (!String(data.label_total).includes("AMOUNT DUE")) {
                    throw new Error("an unpaid pre-receipt must say AMOUNT DUE");
                }
                if (data.kh.total_khr !== "8,118") {
                    throw new Error(`KHR total of $1.98 at 4,100 should be 8,118, got ${data.kh.total_khr}`);
                }
            }),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Cash"),
            PaymentScreen.enterPaymentLineAmount("Cash", "20"),
            PaymentScreen.clickValidate(),
            ReceiptScreen.receiptIsThere(),
            {
                content: "the receipt is the Khmer receipt",
                trigger: ".receipt-screen .pos-receipt.o_kh_receipt:not(.o_kh_unpaid)",
            },
            {
                content: "paid title band",
                trigger: `.receipt-screen .o_kh_receipt .kh-band .kh-band-en:contains("INVOICE")`,
            },
            {
                content: "bilingual TOTAL (Khmer)",
                trigger: `.receipt-screen .o_kh_receipt .receipt-total .kh-lbl-km:contains("សរុប")`,
            },
            {
                content: "bilingual TOTAL (English)",
                trigger: `.receipt-screen .o_kh_receipt .receipt-total .kh-lbl-en:contains("TOTAL")`,
            },
            {
                content: "USD total without the space after the symbol",
                trigger: `.receipt-screen .o_kh_receipt .receipt-total .pos-receipt-right-align:contains("$1.98")`,
            },
            {
                content: "exact KHR total",
                trigger: `.receipt-screen .o_kh_receipt .receipt-total .kh-amt-khr:contains("8,118")`,
            },
            {
                content: "rate row",
                trigger: `.receipt-screen .o_kh_receipt .kh-rate:contains("4,100")`,
            },
            {
                content: "cash payment row",
                trigger: `.receipt-screen .o_kh_receipt .paymentlines:contains("Cash"):contains("$20.00")`,
            },
            {
                content: "change in USD and riel, cash riel rounded to 100",
                trigger: `.receipt-screen .o_kh_receipt .receipt-change .kh-amt-khr:contains("73,900")`,
            },
            {
                content: "KHR change rounding row ($18.02 x 4,100 = 73,882)",
                trigger: `.receipt-screen .o_kh_receipt .receipt-change .kh-round:contains("+18")`,
            },
            {
                content: "thank-you sign-off",
                trigger: `.receipt-screen .o_kh_receipt .kh-signoff .kh-thanks-en:contains("THANK YOU")`,
            },
            check("receipt number has no 'Order ' prefix", () => {
                const rows = [...document.querySelectorAll(".receipt-screen .kh-meta .kh-row b")];
                if (!rows.length || rows[0].textContent.startsWith("Order")) {
                    throw new Error(`unexpected receipt number: ${rows[0]?.textContent}`);
                }
            }),
            {
                content: "cash in/out slip is bilingual",
                trigger: "body",
                run: async () => {
                    const { CashMoveReceipt } = odoo.loader.modules.get(
                        "@point_of_sale/app/navbar/cash_move_popup/cash_move_receipt/cash_move_receipt"
                    );
                    const { _t } = odoo.loader.modules.get("@web/core/l10n/translation");
                    const el = await posmodel.printer.renderer.toHtml(CashMoveReceipt, {
                        reason: "float",
                        translatedType: _t("in"),
                        formattedAmount: posmodel.env.utils.formatCurrency(50),
                        headerData: posmodel.getReceiptHeaderData(),
                        date: "",
                    });
                    const band = el.querySelector(".kh-band");
                    if (!el.classList.contains("o_kh_cashmove") || !band?.textContent.includes("CASH IN")) {
                        throw new Error("cash in slip without the bilingual band");
                    }
                    if (!el.querySelector(".kh-row--big b")?.textContent.includes("$50.00")) {
                        throw new Error("cash in slip without the amount");
                    }
                },
            },
            ReceiptScreen.clickNextOrder(),
            Chrome.endTour(),
        ].flat(),
});
