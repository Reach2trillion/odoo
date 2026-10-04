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
            check("formatting helpers", () => {
                const f = odoo.loader.modules.get("@pos_receipt_khmer/js/kh_format");
                const eq = (got, want, what) => {
                    if (got !== want) {
                        throw new Error(`${what}: expected ${want}, got ${got}`);
                    }
                };
                // quantities in the locale they were formatted with
                eq(f.khQty("2.50"), "2.5", "khQty en");
                eq(f.khQty("1,000.00"), "1,000", "khQty en thousands");
                eq(f.khQty("1.000,00", ","), "1.000", "khQty de thousands");
                eq(f.khQty("10,00", ","), "10", "khQty de");
                // rate: KHR per unit of the POS currency, 0 when the POS sells in riel
                const usdCompany = { l10n_kh_exchange_rate: 4100, currency_id: { name: "USD" } };
                eq(f.khRate(usdCompany, {}, { name: "USD", rate: 1 }), 4100, "khRate USD POS");
                eq(f.khRate(usdCompany, {}, { name: "KHR", rate: 4100 }), 0, "khRate KHR POS");
                const khrCompany = { l10n_kh_exchange_rate: 4100, currency_id: { name: "KHR" } };
                const khrModels = { "res.currency": [{ name: "KHR", rate: 1 }] };
                eq(f.khRate(khrCompany, khrModels, { name: "USD", rate: 0.00025 }), 4000, "khRate KHR company");
                // order total on every 18.0 build (no order_sign / no taxTotals on older builds)
                eq(f.khOrderTotal({ taxTotals: { order_total: 5, order_sign: -1 } }), -5, "total");
                eq(f.khOrderTotal({ taxTotals: { order_total: 5 } }), 5, "total without order_sign");
                eq(f.khOrderTotal({ amount_total: 7 }), 7, "total without taxTotals");
                eq(f.fmtPtsSigned(-5), "-5", "negative points");
                eq(f.fmtPtsSigned(100365), "+100,365", "grouped points");
                // money: Odoo's sign order without the NBSP (core tours look for "-15.72")
                eq(f.khMoney("$\u00a06.00"), "$6.00", "khMoney positive");
                eq(f.khMoney("$\u00a0-15.72"), "$-15.72", "khMoney negative");
                eq(f.khMoney("$\u00a0-0.00"), "$0.00", "khMoney negative zero");
                eq(f.khMoney("Free"), "Free", "khMoney text");
                // paper width of a pos.config
                const p80 = f.khPaper({ kh_paper_width: "80", kh_raster_dots: 360 });
                eq(`${p80.paper}/${p80.raster_w}`, "80/0", "khPaper 80");
                const p58 = f.khPaper({ kh_paper_width: "58", kh_raster_dots: 360 });
                eq(`${p58.paper}/${p58.raster_w}`, "58/360", "khPaper 58");
                const pNone = f.khPaper(undefined);
                eq(`${pNone.paper}/${pNone.raster_w}`, "80/0", "khPaper without config");
            }),
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
                content: "80 mm (default): no 58 mm layer and no style attribute on the root",
                trigger: ".receipt-screen .pos-receipt.o_kh_receipt:not(.o_kh_w58):not([style])",
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
                content: "the core cashier line stays a visible anchor (pos_hr tours) without printing",
                trigger: `.receipt-screen .o_kh_receipt .pos-receipt-contact .cashier:contains("Served by")`,
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
            {
                content:
                    "58 mm paper: o_kh_w58 and the raster width on the receipt, the cash slip, the core " +
                    "receipt printed without the Khmer data and the Daily Sales report; the image is 360 dots",
                trigger: "body",
                run: async () => {
                    const { CashMoveReceipt } = odoo.loader.modules.get(
                        "@point_of_sale/app/navbar/cash_move_popup/cash_move_receipt/cash_move_receipt"
                    );
                    const { OrderReceipt } = odoo.loader.modules.get(
                        "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt"
                    );
                    const { PosOrder } = odoo.loader.modules.get("@point_of_sale/app/models/pos_order");
                    const { htmlToCanvas } = odoo.loader.modules.get("@point_of_sale/app/printer/render_service");
                    const { renderToElement } = odoo.loader.modules.get("@web/core/utils/render");
                    const { _t } = odoo.loader.modules.get("@web/core/l10n/translation");
                    const config = posmodel.config;
                    const saved = [config.kh_paper_width, config.kh_raster_dots];
                    const formatCurrency = posmodel.env.utils.formatCurrency;
                    // the printed image: html-to-image sizes the canvas from the root's width
                    const imageWidth = async (el) =>
                        (await htmlToCanvas(el, { addClass: "pos-receipt-print" })).width;
                    // core's Daily Sales report (printed only through an ePOS / IoT printer), with the
                    // data of an empty session: get_sale_details needs accounting read access, which the
                    // tour's POS user does not have
                    const renderSaleDetails = () =>
                        renderToElement("point_of_sale.SaleDetailsReport", {
                            products: [],
                            refund_products: [],
                            payments: [],
                            taxes: [],
                            currency: { total_paid: 0 },
                            date: "",
                            pos: posmodel,
                            formatCurrency,
                        });
                    const report80 = renderSaleDetails();
                    if (report80.classList.contains("o_kh_w58") || report80.hasAttribute("style")) {
                        throw new Error(`80 mm Daily Sales report: ${report80.outerHTML.slice(0, 120)}`);
                    }
                    // the renderer only reports a component it mounts: give it a frame to unmount
                    // the previous one (two toHtml() calls in a row patch instead, never resolve)
                    const unmounted = async () => {
                        await new Promise((r) => setTimeout(r, 100));
                        await new Promise((r) => requestAnimationFrame(() => r()));
                    };
                    // local change of the loaded record only (nothing is written to the server)
                    config.kh_paper_width = "58";
                    config.kh_raster_dots = 360;
                    try {
                        await unmounted();
                        const slip = await posmodel.printer.renderer.toHtml(CashMoveReceipt, {
                            reason: "",
                            translatedType: _t("out"),
                            formattedAmount: posmodel.env.utils.formatCurrency(-5),
                            headerData: posmodel.getReceiptHeaderData(),
                            date: "",
                        });
                        if (!slip.classList.contains("o_kh_w58") || !slip.classList.contains("o_kh_cashmove")) {
                            throw new Error(`58 mm cash slip classes: ${slip.className}`);
                        }
                        if (slip.style.getPropertyValue("--kh-raster-w") !== "360px") {
                            throw new Error(`58 mm cash slip raster width: ${slip.getAttribute("style")}`);
                        }
                        const order = posmodel.get_order(); // the paid order (still on the receipt screen)
                        await unmounted();
                        const receipt = await posmodel.printer.renderer.toHtml(OrderReceipt, {
                            data: posmodel.orderExportForPrinting(order),
                            formatCurrency,
                        });
                        if (!receipt.classList.contains("o_kh_w58") || !receipt.classList.contains("o_kh_receipt")) {
                            throw new Error(`58 mm receipt classes: ${receipt.className}`);
                        }
                        if (receipt.style.getPropertyValue("--kh-raster-w") !== "360px") {
                            throw new Error(`58 mm receipt raster width: ${receipt.getAttribute("style")}`);
                        }
                        const signOff = receipt.querySelector(".kh-again > .kh-nw")?.textContent;
                        if (!["Please come again", "Please pay at the counter"].includes(signOff)) {
                            throw new Error(`the English sign-off must be one unbreakable group: ${signOff}`);
                        }
                        const receiptWidth = await imageWidth(receipt);
                        if (receiptWidth !== 360) {
                            throw new Error(`58 mm receipt image: ${receiptWidth} dots wide, expected 360`);
                        }

                        // without the Khmer data (the data patch failed): the core receipt, still scaled
                        // to the 58 mm raster width. The patch logs a console error, which fails a tour.
                        const buildKh = PosOrder.prototype._khExportForPrinting;
                        const consoleError = console.error;
                        const logged = [];
                        let fallbackData;
                        PosOrder.prototype._khExportForPrinting = () => {
                            throw new Error("forced by the tour");
                        };
                        console.error = (...args) => logged.push(args.map(String).join(" "));
                        try {
                            fallbackData = posmodel.orderExportForPrinting(order);
                        } finally {
                            PosOrder.prototype._khExportForPrinting = buildKh;
                            console.error = consoleError;
                        }
                        if (fallbackData.kh || !logged.some((m) => m.includes("could not build the Khmer receipt data"))) {
                            throw new Error(`the forced failure did not take the fallback path: ${logged.join(" | ")}`);
                        }
                        await unmounted();
                        const fallback = await posmodel.printer.renderer.toHtml(OrderReceipt, {
                            data: fallbackData,
                            formatCurrency,
                        });
                        if (fallback.classList.contains("o_kh_receipt") || !fallback.classList.contains("o_kh_w58")) {
                            throw new Error(`58 mm fallback receipt classes: ${fallback.className}`);
                        }
                        if (fallback.style.getPropertyValue("--kh-raster-w") !== "360px") {
                            throw new Error(`58 mm fallback receipt raster width: ${fallback.getAttribute("style")}`);
                        }
                        const fallbackWidth = await imageWidth(fallback);
                        if (fallbackWidth !== 360) {
                            throw new Error(`58 mm fallback receipt image: ${fallbackWidth} dots wide, expected 360`);
                        }

                        const report = renderSaleDetails();
                        if (!report.classList.contains("o_kh_w58")) {
                            throw new Error(`58 mm Daily Sales report classes: ${report.className}`);
                        }
                        if (report.style.getPropertyValue("--kh-raster-w") !== "360px") {
                            throw new Error(`58 mm Daily Sales report raster width: ${report.getAttribute("style")}`);
                        }
                        const reportWidth = await imageWidth(report);
                        if (reportWidth !== 360) {
                            throw new Error(`58 mm Daily Sales report image: ${reportWidth} dots wide, expected 360`);
                        }
                    } finally {
                        [config.kh_paper_width, config.kh_raster_dots] = saved;
                        // htmlToCanvas leaves its copy in the render container
                        document.querySelector(".render-container")?.replaceChildren();
                    }
                },
            },
            ReceiptScreen.clickNextOrder(),
            Chrome.endTour(),
        ].flat(),
});
