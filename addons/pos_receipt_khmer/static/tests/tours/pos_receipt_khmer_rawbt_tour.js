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
            check("RawBT is only used in an Android browser", () => {
                const { khRawbt, khUsesRawbt, khIsAndroidBrowser, khInstallRawbt, KhRawbtPrinter } = rawbt();
                assert(posmodel.config.kh_print_method === "rawbt", "setting loaded");
                // the test browser is not Android: the point of sale prints as before
                assert(!khRawbt.isAndroid(), "the test browser is not Android");
                assert(
                    !(posmodel.hardwareProxy.printer instanceof KhRawbtPrinter),
                    "no RawBT printer on a computer"
                );
                const chrome = "Mozilla/5.0 (Linux; Android 11; V2_PRO) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.6045.193 Mobile Safari/537.36";
                const webview = "Mozilla/5.0 (Linux; Android 7.1.1; V2_PRO Build/NMF26F; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/83.0.4103.106 Mobile Safari/537.36";
                const desktop = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36";
                assert(khIsAndroidBrowser(chrome), "Chrome on Android");
                const firefox = "Mozilla/5.0 (Android 11; Mobile; rv:128.0) Gecko/128.0 Firefox/128.0";
                assert(khIsAndroidBrowser(desktop.replace("X11; Linux x86_64", "Linux; Android 10; K"), "Android"), "Android by client hints");
                assert(!khIsAndroidBrowser(firefox), "not Firefox (untested)");
                assert(!khIsAndroidBrowser(webview), "not an app's WebView (the Odoo app)");
                assert(!khIsAndroidBrowser(desktop), "not a computer");
                const isAndroid = khRawbt.isAndroid;
                const previous = posmodel.hardwareProxy.printer;
                khRawbt.isAndroid = () => true;
                try {
                    assert(khUsesRawbt({ kh_print_method: "rawbt" }), "rawbt on Android");
                    assert(!khUsesRawbt({ kh_print_method: "browser" }), "browser on Android");
                    // what afterProcessServerData does on Android: install it once, keep it
                    assert(khInstallRawbt(posmodel), "installed");
                    const installed = posmodel.hardwareProxy.printer;
                    assert(installed instanceof KhRawbtPrinter, "RawBT printer installed");
                    khInstallRawbt(posmodel);
                    assert(posmodel.hardwareProxy.printer === installed, "the same printer is kept");
                } finally {
                    khRawbt.isAndroid = isAndroid;
                    posmodel.hardwareProxy.printer = previous;
                }
                // the RawBT printer, with the link recorded instead of opened
                window.__khRawbtUrls = [];
                window.__khRawbtTimes = [];
                khRawbt.launch = (url) => {
                    window.__khRawbtUrls.push(url);
                    window.__khRawbtTimes.push(Date.now());
                    document.body.dataset.khRawbtSent = String(window.__khRawbtUrls.length);
                };
                // the tour's clicks are not user gestures: start with "the tap has expired"
                khRawbt.hasActivation = () => false;
                posmodel.hardwareProxy.printer = new KhRawbtPrinter({ dialog: posmodel.dialog });
            }),
            {
                content: "opening the link stops the page's own beforeunload handlers (offline 'Leave site?')",
                trigger: "body",
                run: async () => {
                    const { khArmLeaveGuard } = rawbt();
                    let reached = 0;
                    const later = () => reached++; // added after the module's guard, like main.js's
                    window.addEventListener("beforeunload", later);
                    try {
                        khArmLeaveGuard(300);
                        window.dispatchEvent(new Event("beforeunload", { cancelable: true }));
                        assert(reached === 0, "stopped while the link is being opened");
                        await new Promise((resolve) => setTimeout(resolve, 400));
                        window.dispatchEvent(new Event("beforeunload", { cancelable: true }));
                        assert(reached === 1, "untouched otherwise");
                    } finally {
                        window.removeEventListener("beforeunload", later);
                    }
                },
            },
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
                    // IHDR: bit depth 1, colour type 0 (greyscale)
                    const head = atob(url.slice(prefix.length, prefix.length + 44));
                    assert(head.charCodeAt(24) === 1 && head.charCodeAt(25) === 0, "1-bit greyscale PNG");
                    assert(url.length < 30000, `link length ${url.length}`);
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
            {
                content: "two prints at once: one after the other, both sent, RawBT given time in between",
                trigger: "body",
                run: async () => {
                    const order = posmodel.get_order();
                    const before = window.__khRawbtUrls.length;
                    const [a, b] = await Promise.all([
                        posmodel.printReceipt({ order }),
                        posmodel.printReceipt({ order }),
                    ]);
                    assert(a && b, "both printed");
                    assert(window.__khRawbtUrls.length === before + 2, `${window.__khRawbtUrls.length - before} sent`);
                    const times = window.__khRawbtTimes.slice(-2);
                    assert(times[1] - times[0] >= 1400, `${times[1] - times[0]} ms between the two`);
                    for (const url of window.__khRawbtUrls.slice(-2)) {
                        const img = new Image();
                        img.src = url.slice("rawbt:".length);
                        await img.decode();
                        assert(img.naturalWidth === 384 && img.naturalHeight > 600, "a whole receipt");
                    }
                },
            },
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
                assert(window.__khRawbtUrls.length === 4, `${window.__khRawbtUrls.length} sent`);
                assert(!document.querySelector(".modal"), "no error dialog");
            }),
            ReceiptScreen.clickNextOrder(),
        ].flat(),
});
