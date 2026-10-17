import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { BasePrinter } from "@point_of_sale/app/printer/base_printer";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { htmlToCanvas } from "@point_of_sale/app/printer/render_service";
import { getFontEmbedCSS, toCanvas } from "@point_of_sale/app/utils/html-to-image";

// Android browsers print a web page through the system print dialog, which shrinks the receipt to
// the page size its print service reports (Sunmi V2 Pro: a tiny receipt). With "Print receipts
// with: RawBT app" the receipt is drawn as the printer's raster image, like the Epson / IoT path
// (1 px = 1 dot, receipt_kh.scss), and handed to the RawBT app (ru.a402d.rawbtprinter) as a
// rawbt:data:image/...;base64 link (https://rawbt.ru/start.html), which prints it as it is.

const LAUNCH_GAP_MS = 1500; // between two receipts of one print run: one RawBT job at a time
const GUARD_MS = 1000;

// Overridable by tests (the launch cannot be observed in a desktop browser).
export const khRawbt = {
    isAndroid() {
        return (
            navigator.userAgentData?.platform === "Android" || /Android/i.test(navigator.userAgent)
        );
    },
    // Chrome opens another app's link only shortly after a tap (transient user activation, ~5 s);
    // a receipt printed later (iface_print_auto after a slow sync) asks for a tap first
    hasActivation() {
        const activation = navigator.userActivation;
        return !activation || activation.isActive;
    },
    launch(url) {
        // the browser treats the link as leaving the page: point_of_sale's beforeunload handler
        // would ask "Leave site?" while offline. Clear its message for this navigation only (a
        // listener added after it runs after it).
        const guard = (event) => {
            event.returnValue = "";
        };
        window.addEventListener("beforeunload", guard);
        setTimeout(() => window.removeEventListener("beforeunload", guard), GUARD_MS);
        window.location.href = url;
    },
};

export function khUsesRawbt(config) {
    return config?.kh_print_method === "rawbt" && khRawbt.isAndroid();
}

const familyKey = (family) => family.trim().replace(/^["']|["']$/g, "").toLowerCase();

let khFontFaces; // Promise<Map<family, @font-face blocks with the font files as data URLs>>

/**
 * Every @font-face rule of the page, embedded by html-to-image (its getFontEmbedCSS), grouped by
 * family; built once per page load. Core's htmlToCanvas embeds all of them into every printed image
 * (about 4 MB in the POS); a receipt only needs the faces of its own fonts.
 */
export function khFontFaceMap() {
    khFontFaces ??= getFontEmbedCSS(document.body, { includeQueryParams: true }).then(
        (css) => {
            const faces = new Map();
            for (const block of css.split(/\n(?=@font-face)/)) {
                const family = /font-family:\s*([^;]+);/.exec(block)?.[1];
                if (family) {
                    const key = familyKey(family);
                    faces.set(key, [...(faces.get(key) || []), block]);
                }
            }
            return faces;
        },
        (error) => {
            khFontFaces = undefined; // try again at the next print
            throw error;
        }
    );
    return khFontFaces;
}

/** The embedded @font-face rules of the font families used in el (mounted), icons included. */
async function khFontEmbedCSS(el) {
    const used = new Set();
    const addFamilies = (style) => {
        for (const family of style.fontFamily.split(",")) {
            used.add(familyKey(family));
        }
    };
    for (const node of [el, ...el.querySelectorAll("*")]) {
        addFamilies(getComputedStyle(node));
        // icon fonts draw in ::before / ::after (html-to-image copies those)
        for (const pseudo of ["::before", "::after"]) {
            const style = getComputedStyle(node, pseudo);
            if (style.content && style.content !== "none" && style.content !== "normal") {
                addFamilies(style);
            }
        }
    }
    const faces = await khFontFaceMap();
    return [...used].flatMap((family) => faces.get(family) || []).join("\n");
}

// 1x1 white GIF: an image that cannot be loaded prints as blank space
const BLANK_IMAGE =
    "data:image/gif;base64,R0lGODlhAQABAIAAAP///wAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw==";
const IMAGE_WAIT_MS = 4000;

/**
 * Put the images of the receipt into the copy that is printed as data URLs, from the images the
 * browser has loaded (the receipt's own <img>, loaded by PrinterService.print). html-to-image would
 * fetch them again, and when a fetch fails (offline, a network blip) it fails the whole image and
 * caches the failure for the rest of the session: every later receipt would fail too. An image that
 * cannot be loaded at all prints as blank space instead.
 */
async function khInlineImages(el, clone) {
    const sources = [...el.querySelectorAll("img")];
    const targets = [...clone.querySelectorAll("img")];
    await Promise.all(
        targets.map(async (img, i) => {
            if (!img.getAttribute("src") || img.src.startsWith("data:")) {
                return;
            }
            const source = sources[i]?.src === img.src ? sources[i] : img;
            try {
                await Promise.race([
                    source.decode(),
                    new Promise((resolve, reject) => setTimeout(reject, IMAGE_WAIT_MS)),
                ]);
            } catch {
                console.warn(`pos_receipt_khmer: image not printed (cannot be loaded): ${img.src}`);
                img.srcset = "";
                img.src = BLANK_IMAGE;
                return;
            }
            if (!source.naturalWidth) {
                return; // no intrinsic size (some SVGs): html-to-image embeds it
            }
            try {
                const canvas = document.createElement("canvas");
                canvas.width = source.naturalWidth;
                canvas.height = source.naturalHeight;
                canvas.getContext("2d").drawImage(source, 0, 0);
                img.srcset = "";
                img.src = canvas.toDataURL("image/png");
            } catch {
                return; // cross-origin: html-to-image fetches it
            }
        })
    );
    // the printed size is measured from the copy's layout
    await Promise.all(targets.map((img) => img.decode().catch(() => {})));
}

const sanitizeNodeText = (node) => {
    if (node.nodeType === Node.TEXT_NODE) {
        node.textContent = node.textContent.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g, ""); // eslint-disable-line no-control-regex
        return;
    }
    for (const child of node.childNodes) {
        sanitizeNodeText(child);
    }
};

/**
 * Core's htmlToCanvas (render_service.js: same class, clone in the render container, same
 * html-to-image options; the image is the same, pixel for pixel), with only the fonts the receipt
 * uses embedded: half the time once warm, and no 4 MB of fonts per print on a handheld, so the
 * image is ready while Chrome still counts the tap on Print.
 */
export async function khReceiptCanvas(el) {
    const addClass = "pos-receipt-print";
    el.classList.add(addClass);
    sanitizeNodeText(el);
    const container = document.querySelector(".render-container");
    const clone = el.cloneNode(true);
    container.querySelectorAll(`.${[...el.classList].join(".")}`).forEach((node) => node.remove());
    container.appendChild(clone);
    try {
        await khInlineImages(el, clone);
        let fontEmbedCSS;
        try {
            fontEmbedCSS = await khFontEmbedCSS(clone);
        } catch (error) {
            console.warn("pos_receipt_khmer: fonts embedded the core way", error);
            return await htmlToCanvas(el, { addClass });
        }
        return await toCanvas(clone, {
            backgroundColor: "#ffffff",
            height: Math.ceil(clone.clientHeight),
            width: Math.ceil(clone.clientWidth),
            pixelRatio: 1,
            includeQueryParams: true,
            fontEmbedCSS,
        });
    } finally {
        clone.remove();
    }
}

/**
 * The receipt image as a 1-bit PNG data URL: Floyd-Steinberg on the luminance with the weights and
 * threshold of pos_epson_printer (the receipt was designed against that output), so RawBT's own
 * image settings have nothing left to change and the print matches the Epson / IoT print.
 */
export function khMonochromePng(canvas) {
    const { width, height } = canvas;
    const out = document.createElement("canvas");
    out.width = width;
    out.height = height;
    const ctx = out.getContext("2d");
    ctx.drawImage(canvas, 0, 0);
    const image = ctx.getImageData(0, 0, width, height);
    const px = image.data;
    // error rows with one pixel of padding on each side (errors pushed past an edge are dropped)
    let row = new Float32Array(width + 2);
    let below = new Float32Array(width + 2);
    for (let y = 0; y < height; y++) {
        for (let x = 0; x < width; x++) {
            const i = (y * width + x) * 4;
            let value = px[i] * 0.299 + px[i + 1] * 0.587 + px[i + 2] * 0.114 + row[x + 1];
            value = Math.min(255, Math.max(0, value));
            const dot = value < 128 ? 0 : 255;
            const error = value - dot;
            if (error) {
                row[x + 2] += (7 / 16) * error;
                below[x] += (3 / 16) * error;
                below[x + 1] += (5 / 16) * error;
                below[x + 2] += (1 / 16) * error;
            }
            px[i] = px[i + 1] = px[i + 2] = dot;
            px[i + 3] = 255;
        }
        [row, below] = [below, row];
        below.fill(0);
    }
    ctx.putImageData(image, 0, 0);
    return out.toDataURL("image/png");
}

export class KhRawbtPrinter extends BasePrinter {
    setup({ dialog } = {}) {
        super.setup(...arguments);
        this.dialog = dialog;
        this.lastLaunch = 0;
    }

    /** BasePrinter.printReceipt with khReceiptCanvas instead of core's htmlToCanvas. */
    async printReceipt(receipt) {
        if (receipt) {
            this.receiptQueue.push(receipt);
        }
        while (this.receiptQueue.length > 0) {
            receipt = this.receiptQueue.shift();
            const image = this.processCanvas(await khReceiptCanvas(receipt));
            let printResult;
            try {
                printResult = await this.sendPrintingJob(image);
            } catch {
                this.receiptQueue.length = 0;
                return this.getActionError();
            }
            if (!printResult || printResult.result === false) {
                this.receiptQueue.length = 0;
                return this.getResultsError(printResult);
            }
        }
        return { successful: true };
    }

    processCanvas(canvas) {
        return khMonochromePng(canvas);
    }

    async sendPrintingJob(dataUrl) {
        const wait = this.lastLaunch + LAUNCH_GAP_MS - Date.now();
        if (wait > 0) {
            await new Promise((resolve) => setTimeout(resolve, wait));
        }
        const url = "rawbt:" + dataUrl;
        if (khRawbt.hasActivation() || !this.dialog) {
            khRawbt.launch(url);
        } else if (!(await this.askToPrint(url))) {
            // the cashier closed the dialog: nothing to report
            return { result: true };
        }
        this.lastLaunch = Date.now();
        return { result: true };
    }

    /** Resolves true once the tap on Print has opened RawBT, false if the dialog was closed. */
    askToPrint(url) {
        return new Promise((resolve) => {
            this.dialog.add(
                ConfirmationDialog,
                {
                    title: _t("បោះពុម្ពបង្កាន់ដៃ / Print receipt"),
                    body: _t(
                        "បង្កាន់ដៃរួចរាល់ហើយ។ ចុច «បោះពុម្ព» ដើម្បីផ្ញើទៅ RawBT។\nThe receipt is ready. Tap Print to send it to RawBT."
                    ),
                    confirmLabel: _t("បោះពុម្ព / Print"),
                    cancelLabel: _t("បោះបង់ / Cancel"),
                    // open the link in the tap itself: some browsers only count the click handler
                    confirm: () => {
                        khRawbt.launch(url);
                        resolve(true);
                    },
                    cancel: () => resolve(false),
                },
                { onClose: () => resolve(false) }
            );
        });
    }

    openCashbox() {
        // RawBT receives images only; a cash drawer needs an IoT box or an ePOS printer
        console.warn("pos_receipt_khmer: the RawBT printer cannot open a cash drawer");
    }

    getActionError() {
        return {
            successful: false,
            message: {
                title: _t("RawBT could not be opened"),
                body: _t(
                    "Check that the RawBT app is installed on this device and that its printer is set up. "
                ),
            },
        };
    }

    getResultsError() {
        return this.getActionError();
    }
}

patch(PosStore.prototype, {
    async afterProcessServerData() {
        const result = await super.afterProcessServerData(...arguments);
        // only on Android: the same point of sale opened on a computer keeps its own printing
        if (khUsesRawbt(this.config)) {
            this.hardwareProxy.printer = new KhRawbtPrinter({ dialog: this.dialog });
            // embed the fonts once, after the POS has loaded, so the first receipt is as quick
            setTimeout(() => khFontFaceMap().catch(() => {}), 3000);
        }
        return result;
    },
});
