/* global posmodel */
import * as Chrome from "@point_of_sale/../tests/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/tours/utils/dialog_util";
import * as ProductScreen from "@point_of_sale/../tests/tours/utils/product_screen_util";
import * as PaymentScreen from "@point_of_sale/../tests/tours/utils/payment_screen_util";
import * as ReceiptScreen from "@point_of_sale/../tests/tours/utils/receipt_screen_util";
import { registry } from "@web/core/registry";

// set by TestPosReceiptKhmerNames.test_khmer_names_tour
const DESK_PAD_KM = "បន្ទះតុ";
const LETTER_TRAY_KM = "ថាសដាក់សំបុត្រ ប្រើក្នុងការិយាល័យ សម្រាប់ឯកសារ និងសំបុត្រ";
// words longer than a 58 mm line: a transliterated brand (one Khmer word) and a Latin model code
const MAGNETIC_BOARD_KM = "អេប៊ីជេវ៉ាយធីននីងណៃរីផែរគ្រីមវិទនីយ៉ាស៊ីណាមីតអាំងវ៉េស្ទីស";
const MONITOR_STAND_KM = "ជើងទ្រអេក្រង់ SuperUltraWideMonitorStandXL2000Pro";
// a short word before a word that wraps inside itself onto 3 lines or more at 360 dots: an English
// name (Small Shelf, renamed, no Khmer name) and a Khmer word before a Latin code (Wall Shelf Unit)
const SERUM_EN = "ABJ Hyaluronic-Acid-Niacinamide-Ceramide-Serum";
const WALL_SHELF_KM = "ក្រែម ABJ-SuperUltraWideNightRepairCream-50ml";

function check(content, fn) {
    return { content, trigger: "body", run: fn };
}
function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}
const squash = (s) => (s || "").replace(/\s+/g, "");
/** Text of word boxes as printed: a space after each word that has one (kh-sp, a margin). */
const boxText = (el) =>
    [...el.querySelectorAll(".kh-words > .kh-w, .kh-words > .kh-g")]
        .map((w) => w.textContent + (w.classList.contains("kh-sp") ? " " : ""))
        .join("");
/** Receipt orderline (li.orderline) whose names contain `text` (word boxes have no spaces). */
function receiptLine(root, text) {
    return [...root.querySelectorAll(".orderline")].find((l) =>
        squash(l.querySelector(".product-name")?.textContent).includes(squash(text))
    );
}
/** Number of text lines of an element: the distinct tops (half a line apart) of its text's line boxes. */
function textLines(el) {
    const lh = parseFloat(getComputedStyle(el).lineHeight);
    const range = document.createRange();
    const tops = [];
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        range.selectNodeContents(node);
        tops.push(...[...range.getClientRects()].filter((r) => r.width > 0).map((r) => r.top));
    }
    tops.sort((a, b) => a - b);
    return tops.filter((t, i) => i === 0 || t - tops[i - 1] > lh / 2).length;
}
// the renderer only reports a component it mounts: give it a frame to unmount the previous one
const unmounted = async () => {
    await new Promise((r) => setTimeout(r, 100));
    await new Promise((r) => requestAnimationFrame(() => r()));
};

registry.category("web_tour.tours").add("pos_receipt_khmer_names_tour", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            check("word boxes of a product name (khWords)", () => {
                const { khWords } = odoo.loader.modules.get("@pos_receipt_khmer/js/kh_format");
                const words = (s) => khWords(s).map((w) => w.t + (w.sp ? "␣" : ""));
                const eq = (got, want, what) =>
                    assert(JSON.stringify(got) === JSON.stringify(want), `${what}: ${JSON.stringify(got)}`);
                eq(words("ក្រែម BB"), ["ក្រែម␣", "BB"], "Khmer + Latin");
                eq(words("ABJ-Underarm Cream (Black, L)"), ["ABJ-Underarm␣", "Cream␣", "(Black, L)"], "Latin");
                eq(words("Desk (open"), ["Desk␣", "(open"], "unclosed bracket");
                // a no-break space keeps its two words in one box
                eq(words("ក្រែម\u00a0BB ថ្មី"), ["ក្រែម\u00a0BB␣", "ថ្មី"], "no-break space");
                eq(words("Desk\u202fPad"), ["Desk\u202fPad"], "narrow no-break space");
                eq(words("  "), [], "blank");
                // a line only breaks at spaces: a Khmer word is one unit, its dictionary parts are only
                // used when it alone is wider than the line; nothing is lost or reordered
                const sku = khWords("ក្រែមលាបយប់ឱ្យស្បែកភ្លឺថ្លា ជាមួយនីយ៉ាស៊ីណាមីត និងអង្ករ 50ml");
                eq(sku.map((w) => w.t + (w.sp ? "␣" : "")), ["ក្រែមលាបយប់ឱ្យស្បែកភ្លឺថ្លា␣", "ជាមួយនីយ៉ាស៊ីណាមីត␣", "និងអង្ករ␣", "50ml"], "words");
                const mask = khWords("ម៉ាសបិទមុខប្រចាំសប្តាហ៍");
                assert(mask.length === 1 && mask[0].parts?.length > 1, "a long Khmer word has its parts");
                eq(mask[0].parts.join(""), "ម៉ាសបិទមុខប្រចាំសប្តាហ៍", "Khmer parts");
                // zero-width spaces are the typist's word breaks (no dictionary split between them),
                // the repetition sign stays with its word
                eq(khWords("ក្រែម\u200bការពារ").map((w) => w.t).join("|"), "ក្រែម|ការពារ", "ZWSP");
                const zw = khWords("ក្រដាស\u200bគុណភាព\u200bខ្ពស់");
                eq(zw.map((w) => w.t), ["ក្រដាស", "គុណភាព", "ខ្ពស់"], "ZWSP words");
                assert(zw.every((w) => !w.sp), "no space printed at a zero-width space");
                assert(!khWords("ផ្កាៗ ស").some((w) => w.t.startsWith("ៗ")), "ៗ never starts a word box");
                assert(!khWords("ល្អ\u200bៗ").some((w) => w.t.startsWith("ៗ")), "ៗ after a zero-width space");
            }),
            ProductScreen.addOrderline("Desk Pad", "1"),
            ProductScreen.addOrderline("Letter Tray", "1"),
            ProductScreen.addOrderline("Whiteboard Pen", "1"),
            ProductScreen.addOrderline("Magnetic Board", "1"),
            ProductScreen.addOrderline("Monitor Stand", "1"),
            ProductScreen.addOrderline(SERUM_EN, "1"),
            ProductScreen.addOrderline("Wall Shelf Unit", "1"),
            check("the product screen order list is unchanged (English names, no word boxes)", () => {
                const screen = document.querySelector(".product-screen");
                assert(!screen.querySelector(".kh-words, .kh-name-en"), "Khmer receipt rows on the product screen");
                const names = [...screen.querySelectorAll(".orderline .product-name")].map((e) => e.textContent.trim());
                assert(names.includes("Desk Pad") && names.includes("Letter Tray"), `order list: ${names}`);
                const line = posmodel.get_order().lines.find((l) => l.product_id.name === "Desk Pad");
                assert(line.getDisplayData().productName === "Desk Pad", "getDisplayData must stay English");
                assert(line.product_id.kh_pos_name_km === DESK_PAD_KM, "kh_pos_name_km is loaded");
                assert(line.product_id.kh_pos_name_en === "Desk Pad", "kh_pos_name_en is loaded");
            }),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Cash"),
            PaymentScreen.enterPaymentLineAmount("Cash", "50"),
            PaymentScreen.clickValidate(),
            ReceiptScreen.receiptIsThere(),
            {
                content: "Khmer + English (default): the Khmer name is the item line",
                trigger: ".receipt-screen .pos-receipt.o_kh_receipt .orderline .product-name .kh-words",
            },
            check("both: Khmer name with the price, the product name under it", () => {
                const root = document.querySelector(".receipt-screen .pos-receipt");
                const pad = receiptLine(root, DESK_PAD_KM);
                assert(pad, "no receipt line with the Khmer name of Desk Pad");
                const words = pad.querySelector(".product-name .kh-words");
                assert(squash(words.textContent) === squash(DESK_PAD_KM), `main name: ${words.textContent}`);
                assert(
                    getComputedStyle(pad.querySelector(".product-name > .text-wrap")).display === "none",
                    "core's plain-text name must be hidden behind the word boxes"
                );
                assert(pad.querySelector(".product-price").textContent.includes("1.98"), "price on the Khmer line");
                const en = pad.querySelector(".info-list > .kh-name-en");
                assert(en && boxText(en) === "Desk Pad", `English line: ${en && boxText(en)}`);
                const qty = pad.querySelector(".info-list > .kh-qty");
                assert(en.getBoundingClientRect().top < qty.getBoundingClientRect().top, "English name before the quantity");
                assert(getComputedStyle(en).fontWeight === "500", "English line in body weight");

                const tray = receiptLine(root, LETTER_TRAY_KM);
                assert(boxText(tray.querySelector(".kh-name-en")) === "Letter Tray", "Letter Tray English line");
                assert(boxText(tray.querySelector(".product-name")) === LETTER_TRAY_KM.replace(/\s+/g, " "), "spaces kept");
                // a product without a Khmer name prints its name (as word boxes too), no English line
                const pen = receiptLine(root, "Whiteboard Pen");
                assert(pen && !pen.querySelector(".kh-name-en"), "Whiteboard Pen: no English line");
                // (the test product has a no-variant attribute: "Whiteboard Pen (add 2)")
                const penText = boxText(pen.querySelector(".product-name"));
                assert(penText.startsWith("Whiteboard Pen"), `Whiteboard Pen word boxes: "${penText}"`);
                const data = posmodel.orderExportForPrinting(posmodel.get_order());
                const exported = data.orderlines.find((l) => l.kh_name_en === "Desk Pad");
                assert(exported?.productName === DESK_PAD_KM, "receipt copy: productName swapped");
                // the order itself is untouched
                const line = posmodel.get_order().lines.find((l) => l.product_id.name === "Desk Pad");
                assert(line.get_full_product_name() === "Desk Pad", "the order line keeps its name");
            }),
            check("a Khmer-language cashier: the English line is the en_US name, not the loaded name", () => {
                // the POS loads display_name / name in the cashier's language: emulate a km_KH cashier
                const order = posmodel.get_order();
                const line = order.lines.find((l) => l.product_id.kh_pos_name_en === "Desk Pad");
                const product = line.product_id;
                const saved = [product.display_name, product.name, line.full_product_name];
                const exported = () =>
                    posmodel
                        .orderExportForPrinting(order)
                        .orderlines.find((l) => l.productName === DESK_PAD_KM);
                try {
                    // a km_KH translation different from the receipt name ("Foam": ហ្វូម / ហ្វូមលាងមុខ)
                    product.display_name = product.name = line.full_product_name = "បន្ទះ";
                    let l = exported();
                    assert(l?.kh_name_en === "Desk Pad", `km_KH name: English line ${l?.kh_name_en}`);
                    // the translation is the Khmer name itself ("SunScreen"): still both lines
                    product.display_name = product.name = line.full_product_name = DESK_PAD_KM;
                    l = exported();
                    assert(l?.kh_name_en === "Desk Pad", `same name: English line ${l?.kh_name_en}`);
                } finally {
                    [product.display_name, product.name, line.full_product_name] = saved;
                }
            }),
            {
                content: "printed image: lines frozen, same lines as the live receipt, 58 mm / 360 dots",
                trigger: "body",
                run: async () => {
                    const { OrderReceipt } = odoo.loader.modules.get(
                        "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt"
                    );
                    const { khFreezeWordLines } = odoo.loader.modules.get("@pos_receipt_khmer/js/font_ready");
                    const { htmlToCanvas } = odoo.loader.modules.get("@point_of_sale/app/printer/render_service");
                    const config = posmodel.config;
                    const saved = [config.kh_paper_width, config.kh_raster_dots];
                    config.kh_paper_width = "58";
                    config.kh_raster_dots = 360;
                    try {
                        await unmounted();
                        const el = await posmodel.printer.renderer.toHtml(OrderReceipt, {
                            data: posmodel.orderExportForPrinting(posmodel.get_order()),
                            formatCurrency: posmodel.env.utils.formatCurrency,
                        });
                        // the live layout, as the image is laid out: the text lines of every name (the
                        // tops of its text's line boxes: a word longer than the line wraps inside its box)
                        const container = document.querySelector(".render-container");
                        const live = el.cloneNode(true);
                        live.classList.add("pos-receipt-print");
                        container.appendChild(live);
                        const liveRows = [...live.querySelectorAll(".kh-words")].map((w) => ({
                            lines: textLines(w),
                            text: squash(w.textContent),
                        }));
                        live.remove();
                        const frozen = khFreezeWordLines(el);
                        assert(frozen !== el, "a receipt with Khmer names is printed from a frozen copy");
                        assert(!el.querySelector(".kh-frozen"), "the rendered receipt itself is not changed");
                        const tray = receiptLine(frozen, LETTER_TRAY_KM);
                        const lines = tray.querySelectorAll(".product-name .kh-words.kh-frozen > .kh-line");
                        assert(lines.length >= 2, `the long Khmer name must wrap at 360 dots: ${lines.length} line(s)`);
                        assert(
                            squash([...lines].map((l) => l.textContent).join("")) === squash(LETTER_TRAY_KM),
                            "every word is printed once, in order"
                        );
                        // it breaks at its spaces only: every word on one line
                        for (const word of LETTER_TRAY_KM.split(" ")) {
                            assert(
                                [...lines].some((l) => l.textContent.includes(word)),
                                `"${word}" was split over two lines`
                            );
                        }
                        // words longer than the line wrap inside the name, between their parts
                        const board = receiptLine(frozen, MAGNETIC_BOARD_KM);
                        assert(
                            board.querySelectorAll(".product-name .kh-line").length >= 2,
                            "the transliterated name must wrap at 360 dots"
                        );
                        const canvas = await htmlToCanvas(frozen, { addClass: "pos-receipt-print" });
                        assert(canvas.width === 360, `58 mm image: ${canvas.width} dots wide`);
                        // the image keeps the measured lines: each frozen line is one row
                        const copy = document.querySelector(".render-container > .pos-receipt");
                        for (const line of copy.querySelectorAll(".kh-line")) {
                            const tops = new Set(
                                [...line.children].map((w) => Math.round(w.getBoundingClientRect().top))
                            );
                            assert(tops.size === 1, `a frozen line wrapped: ${line.textContent}`);
                        }
                        // nothing runs off the paper: a word longer than the line never pushes the
                        // price out (the name's flex item may shrink below its longest word)
                        const paper = copy.getBoundingClientRect();
                        for (const el of copy.querySelectorAll(".orderline *")) {
                            const r = el.getBoundingClientRect();
                            assert(
                                !r.width || (r.right <= paper.right + 1 && r.left >= paper.left - 1),
                                `outside the 360-dot paper: ${el.className} "${el.textContent.slice(0, 30)}"`
                            );
                        }
                        // every name prints the text lines of the live layout, one frozen line each, never
                        // wrapping: a word that wraps inside itself onto 3 lines does not pull the word
                        // before it into its line (the no-wrap line squeezed that word to a column of
                        // letters: "A / B / J", "ក្ / រែ / ម"), and its own lines are frozen too
                        const rows = [...copy.querySelectorAll(".kh-words")];
                        assert(rows.length === liveRows.length, `${rows.length} names printed, ${liveRows.length} live`);
                        rows.forEach((w, i) => {
                            const want = liveRows[i];
                            const frozenLines = [...w.querySelectorAll(":scope > .kh-line")];
                            assert(
                                frozenLines.length === want.lines,
                                `"${want.text}": ${frozenLines.length} printed line(s), ${want.lines} live`
                            );
                            assert(squash(w.textContent) === want.text, `"${want.text}" printed as "${w.textContent}"`);
                            const lh = parseFloat(getComputedStyle(w).lineHeight);
                            for (const line of frozenLines) {
                                assert(
                                    line.getBoundingClientRect().height < 1.5 * lh && textLines(line) === 1,
                                    `"${want.text}": the printed line "${line.textContent}" wraps`
                                );
                            }
                        });
                        const firstLine = (text) =>
                            receiptLine(copy, text)?.querySelector(".product-name .kh-line")?.textContent;
                        assert(squash(firstLine(SERUM_EN)) === "ABJ", `${SERUM_EN}: first line "${firstLine(SERUM_EN)}"`);
                        assert(squash(firstLine(WALL_SHELF_KM)) === "ក្រែម", `Wall Shelf: first line "${firstLine(WALL_SHELF_KM)}"`);
                        const serumRow = liveRows.find((r) => r.text === squash(SERUM_EN));
                        assert(serumRow?.lines >= 4, `the test word must wrap inside itself onto 3 lines or more at 360 dots: ${serumRow?.lines}`);
                        assert(
                            receiptLine(copy, SERUM_EN).querySelectorAll(".product-name .kh-frag").length >= 3,
                            "a word longer than the line is printed as its text lines"
                        );
                        const stand = receiptLine(copy, MONITOR_STAND_KM);
                        assert(stand?.querySelector(".product-price").textContent.includes("3.19"), "Monitor Stand price");
                        // no word boxes: the element itself
                        const plain = document.createElement("div");
                        assert(khFreezeWordLines(plain) === plain, "nothing to freeze");
                    } finally {
                        [config.kh_paper_width, config.kh_raster_dots] = saved;
                        document.querySelector(".render-container")?.replaceChildren();
                    }
                },
            },
            {
                content: "English only / Khmer only (pos.config.kh_product_names, loaded record only)",
                trigger: "body",
                run: async () => {
                    const { OrderReceipt } = odoo.loader.modules.get(
                        "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt"
                    );
                    const config = posmodel.config;
                    const saved = config.kh_product_names;
                    const render = async () => {
                        await unmounted();
                        const data = posmodel.orderExportForPrinting(posmodel.get_order());
                        const el = await posmodel.printer.renderer.toHtml(OrderReceipt, {
                            data,
                            formatCurrency: posmodel.env.utils.formatCurrency,
                        });
                        return { data, el };
                    };
                    try {
                        config.kh_product_names = "en";
                        let { data, el } = await render();
                        assert(
                            data.orderlines.every((l) => !l.kh_name_en && !/[\u1780-\u17FF]/.test(l.productName)),
                            "en: English names only"
                        );
                        assert(!el.querySelector(".kh-name-en"), "en: no English line under the name");
                        assert(
                            [...el.querySelectorAll(".product-name .kh-words")].every(
                                (w) => !/[\u1780-\u17FF]/.test(w.textContent)
                            ),
                            "en: no Khmer name"
                        );
                        assert(receiptLine(el, "Desk Pad"), "en: Desk Pad printed");

                        config.kh_product_names = "km";
                        ({ data, el } = await render());
                        const pad = data.orderlines.find((l) => l.productName === DESK_PAD_KM);
                        assert(pad && !pad.kh_name_en, "km: the Khmer name only");
                        assert(
                            data.orderlines.some((l) => l.productName.startsWith("Whiteboard Pen")),
                            `km: a product without a Khmer name keeps its name: ${JSON.stringify(
                                data.orderlines.map((l) => l.productName)
                            )}`
                        );
                        assert(!el.querySelector(".kh-name-en"), "km: no English line");
                        assert(receiptLine(el, DESK_PAD_KM)?.querySelector(".kh-words"), "km: Khmer word boxes");
                    } finally {
                        config.kh_product_names = saved;
                        document.querySelector(".render-container")?.replaceChildren();
                    }
                },
            },
            ReceiptScreen.clickNextOrder(),
            Chrome.endTour(),
        ].flat(),
});
