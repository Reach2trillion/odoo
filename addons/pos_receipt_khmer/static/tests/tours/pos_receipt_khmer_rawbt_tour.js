/* global posmodel */
import * as Chrome from "@point_of_sale/../tests/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/tours/utils/dialog_util";
import * as ProductScreen from "@point_of_sale/../tests/tours/utils/product_screen_util";
import * as PaymentScreen from "@point_of_sale/../tests/tours/utils/payment_screen_util";
import * as ReceiptScreen from "@point_of_sale/../tests/tours/utils/receipt_screen_util";
import { registry } from "@web/core/registry";

// TestPosReceiptKhmer.test_rawbt_tour: kh_print_method = rawbt, 58 mm paper, 384 dots

function check(content, fn) {
    return { content, trigger: "body", run: fn };
}
function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}
const rawbt = () => odoo.loader.modules.get("@pos_receipt_khmer/js/rawbt_printer");
const sent = (n) => ({
    content: `RawBT received ${n} receipt(s)`,
    trigger: `body[data-kh-rawbt-sent="${n}"]`,
});
const clickPrint = {
    content: "print the receipt",
    // not while the previous print is still running (its spinner)
    trigger: ".receipt-screen .button.print:has(.fa-print):contains('Print Full Receipt')",
    run: "click",
};

registry.category("web_tour.tours").add("pos_receipt_khmer_rawbt_tour", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            check("RawBT is only used on Android", () => {
                const { khRawbt, khUsesRawbt, KhRawbtPrinter } = rawbt();
                assert(posmodel.config.kh_print_method === "rawbt", "setting loaded");
                // the test browser is not Android: the point of sale prints as before
                assert(!khRawbt.isAndroid(), "the test browser is not Android");
                assert(
                    !(posmodel.hardwareProxy.printer instanceof KhRawbtPrinter),
                    "no RawBT printer on a computer"
                );
                const isAndroid = khRawbt.isAndroid;
                khRawbt.isAndroid = () => true;
                try {
                    assert(khUsesRawbt({ kh_print_method: "rawbt" }), "rawbt on Android");
                    assert(!khUsesRawbt({ kh_print_method: "browser" }), "browser on Android");
                } finally {
                    khRawbt.isAndroid = isAndroid;
                }
                // what afterProcessServerData installs on Android, with the link recorded
                window.__khRawbtUrls = [];
                khRawbt.launch = (url) => {
                    window.__khRawbtUrls.push(url);
                    document.body.dataset.khRawbtSent = String(window.__khRawbtUrls.length);
                };
                // the tour's clicks are not user gestures: start with "the tap has expired"
                khRawbt.hasActivation = () => false;
                posmodel.hardwareProxy.printer = new KhRawbtPrinter({ dialog: posmodel.dialog });
            }),
            {
                content: "images: a real one is printed, one that cannot be loaded does not fail the print",
                trigger: "body",
                run: async () => {
                    const { khReceiptCanvas } = rawbt();
                    const make = (src) => {
                        const el = document.createElement("div");
                        el.className = "pos-receipt kh-rawbt-test";
                        el.style.cssText = "width: 384px; background: #fff";
                        el.innerHTML = `<img src="${src}" style="display: block; width: 200px; height: 120px"/><p>ABJ ខ្មែរ</p>`;
                        return el;
                    };
                    const dark = (canvas) => {
                        const px = canvas.getContext("2d").getImageData(0, 0, 200, 120).data;
                        let n = 0;
                        for (let i = 0; i < px.length; i += 4) {
                            n += px[i] < 128;
                        }
                        return n;
                    };
                    const logo = await khReceiptCanvas(make("/pos_receipt_khmer/static/img/abj_logo_print.png"));
                    assert(logo.width === 384, `width ${logo.width}`);
                    assert(dark(logo) > 500, `logo printed: ${dark(logo)} dark pixels`);
                    const missing = await khReceiptCanvas(make("/pos_receipt_khmer/static/img/no-such-image.png"));
                    assert(missing.width === 384 && dark(missing) === 0, "a missing image prints as blank space");
                    // nothing was cached as failed: the next receipt with the logo prints it
                    const again = await khReceiptCanvas(make("/pos_receipt_khmer/static/img/abj_logo_print.png"));
                    assert(dark(again) > 500, "the logo still prints");
                    assert(!document.querySelector(".render-container .kh-rawbt-test"), "copies removed");
                },
            },
            ProductScreen.addOrderline("Desk Pad", "1"),
            ProductScreen.addOrderline("Letter Tray", "2"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Cash"),
            PaymentScreen.enterPaymentLineAmount("Cash", "50"),
            PaymentScreen.clickValidate(),
            ReceiptScreen.receiptIsThere(),
            // no tap left: the cashier is asked to tap Print, the tap opens RawBT
            clickPrint,
            Dialog.is({ title: "Print receipt" }),
            Dialog.confirm("Print"),
            sent(1),
            {
                content: "RawBT gets the receipt as a 384-dot, 1-bit PNG",
                trigger: "body",
                run: async () => {
                    const url = window.__khRawbtUrls[0];
                    const prefix = "rawbt:data:image/png;base64,";
                    assert(url.startsWith(prefix), `link: ${url.slice(0, 40)}`);
                    const img = new Image();
                    img.src = url.slice("rawbt:".length);
                    await img.decode();
                    assert(img.naturalWidth === 384, `image width ${img.naturalWidth}`);
                    assert(img.naturalHeight > 600, `image height ${img.naturalHeight}`);
                    const canvas = document.createElement("canvas");
                    canvas.width = img.naturalWidth;
                    canvas.height = img.naturalHeight;
                    const ctx = canvas.getContext("2d");
                    ctx.drawImage(img, 0, 0);
                    const px = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
                    let black = 0;
                    for (let i = 0; i < px.length; i += 4) {
                        const [r, g, b, a] = [px[i], px[i + 1], px[i + 2], px[i + 3]];
                        assert(a === 255 && r === g && g === b && (r === 0 || r === 255), `pixel ${i / 4}: ${r},${g},${b},${a}`);
                        black += r === 0;
                    }
                    const share = black / (px.length / 4);
                    // printed text and rules, not an empty or solid page
                    assert(share > 0.02 && share < 0.4, `black share ${share}`);
                },
            },
            Dialog.isNot(),
            // a tap that is still fresh opens RawBT at once
            check("tap still fresh", () => {
                rawbt().khRawbt.hasActivation = () => true;
            }),
            clickPrint,
            sent(2),
            Dialog.isNot(),
            // closing the dialog prints nothing and reports no error
            check("tap expired", () => {
                rawbt().khRawbt.hasActivation = () => false;
            }),
            clickPrint,
            Dialog.is({ title: "Print receipt" }),
            Dialog.confirm("Cancel", ".btn-secondary"),
            Dialog.isNot(),
            check("nothing sent after Cancel", () => {
                assert(window.__khRawbtUrls.length === 2, `${window.__khRawbtUrls.length} sent`);
                assert(!document.querySelector(".modal"), "no error dialog");
            }),
            ReceiptScreen.clickNextOrder(),
        ].flat(),
});
