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

const LAUNCH_GAP_MS = 1500; // between two receipts: one RawBT job at a time
const GUARD_MS = 1000;
// Android hands the link to RawBT in an Intent (Binder: about 1 MB, 2 bytes per character). A 1-bit
// receipt image takes 9,000 to 17,000 characters per 1000 dots of paper (12.5 cm): this is 2 m or more
const MAX_LINK_CHARS = 300000;

// Opening the link counts as leaving the page: point_of_sale's beforeunload handler (main.js, added
// once the POS is mounted) would ask "Leave site?" while offline. This listener is added when the
// module loads, before that one, so it runs first: while a link is being opened it stops the event
// there. (Clearing returnValue instead would itself ask on the Chrome of Android 7 handhelds.)
let khLeaveGuardUntil = 0;
window.addEventListener("beforeunload", (event) => {
    if (Date.now() < khLeaveGuardUntil) {
        event.stopImmediatePropagation();
    }
});
export function khArmLeaveGuard(ms = GUARD_MS) {
    khLeaveGuardUntil = Date.now() + ms;
}

/**
 * Chrome (or another browser) on Android. Not an Android WebView ("; wv)": the Odoo app, a vendor's
 * built-in browser): an app's WebView may show an unknown link as an error page in place of the POS.
 */
export function khIsAndroidBrowser(userAgent, platform) {
    const android = platform === "Android" || /Android/i.test(userAgent || "");
    return android && !/; wv\)/.test(userAgent || "");
}

// Overridable by tests (the launch cannot be observed in a desktop browser).
export const khRawbt = {
    isAndroid() {
        return khIsAndroidBrowser(navigator.userAgent, navigator.userAgentData?.platform);
    },
    // Chrome opens another app's link only shortly after a tap (transient user activation, ~5 s);
    // a receipt printed later (iface_print_auto after a slow sync) asks for a tap first
    hasActivation() {
        const activation = navigator.userActivation;
        return !activation || activation.isActive;
    },
    launch(url) {
        khArmLeaveGuard();
        window.location.href = url;
    },
};

export function khUsesRawbt(config) {
    return config?.kh_print_method === "rawbt" && khRawbt.isAndroid();
}

const blobToDataURL = (blob) =>
    new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(reader.error);
        reader.readAsDataURL(blob);
    });

const familyKey = (family) => family.trim().replace(/^["']|["']$/g, "").toLowerCase();

// The receipt font (receipt_kh.scss), embedded by this module: html-to-image keeps a failed font
// fetch as an empty font for the rest of the session, this one is fetched again at the next print.
const KH_FAMILY = "abj khmer";
const KH_FONT_URL = "/pos_receipt_khmer/static/fonts/KantumruyPro-subset.woff2";
let khFontFace; // Promise<string>
export function khReceiptFontFace() {
    khFontFace ??= fetch(KH_FONT_URL)
        .then((response) => {
            if (!response.ok) {
                throw new Error(`${KH_FONT_URL}: HTTP ${response.status}`);
            }
            return response.blob();
        })
        .then(blobToDataURL)
        .then(
            (url) =>
                `@font-face { font-family: "ABJ Khmer"; src: url("${url}") format("woff2"); font-weight: 100 700; font-display: block; }`
        )
        .catch((error) => {
            khFontFace = undefined;
            throw error;
        });
    return khFontFace;
}

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
    const css = [];
    let fromPage = [...used];
    if (used.has(KH_FAMILY)) {
        try {
            css.push(await khReceiptFontFace());
            fromPage = fromPage.filter((family) => family !== KH_FAMILY);
        } catch (error) {
            console.warn("pos_receipt_khmer: receipt font not loaded, using the page's copy", error);
        }
    }
    let faces = new Map();
    try {
        faces = await khFontFaceMap();
    } catch (error) {
        console.warn("pos_receipt_khmer: page fonts not embedded", error);
    }
    for (const family of fromPage) {
        for (const block of faces.get(family) || []) {
            if (block.includes("url(data:") || block.includes('url("data:')) {
                css.push(block);
            } else {
                // a font html-to-image could not fetch: the printer's fallback font is used
                console.warn(`pos_receipt_khmer: font "${family}" not embedded`);
            }
        }
    }
    return css.join("\n");
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
 * uses embedded and its images inlined: half the time once warm, no 4 MB of fonts per print on a
 * handheld (so the image is ready while Chrome still counts the tap on Print), and no failed print
 * because an image could not be fetched again.
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
        // another render of a receipt (core's htmlToCanvas: the e-mail image) removes copies of the
        // same classes from the container
        if (!clone.isConnected) {
            container.appendChild(clone);
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
 * The printer dots of a receipt image (1 = black): Floyd-Steinberg on the luminance with the weights
 * and threshold of pos_epson_printer's canvasToRaster (the receipt was designed against that output),
 * so RawBT's own image settings have nothing left to change and the print matches the Epson / IoT
 * print.
 */
export function khDither(canvas) {
    const { width, height } = canvas;
    const px = canvas.getContext("2d").getImageData(0, 0, width, height).data;
    const dots = new Uint8Array(width * height);
    // error rows with one pixel of padding on each side (errors pushed past an edge are dropped)
    let row = new Float32Array(width + 2);
    let below = new Float32Array(width + 2);
    for (let y = 0; y < height; y++) {
        for (let x = 0; x < width; x++) {
            const i = y * width + x;
            let value =
                px[i * 4] * 0.299 + px[i * 4 + 1] * 0.587 + px[i * 4 + 2] * 0.114 + row[x + 1];
            value = Math.min(255, Math.max(0, value));
            const black = value < 128;
            const error = value - (black ? 0 : 255);
            dots[i] = black ? 1 : 0;
            if (error) {
                row[x + 2] += (7 / 16) * error;
                below[x] += (3 / 16) * error;
                below[x + 1] += (5 / 16) * error;
                below[x + 2] += (1 / 16) * error;
            }
        }
        [row, below] = [below, row];
        below.fill(0);
    }
    return { dots, width, height };
}

let crcTable;
function crc32(bytes) {
    crcTable ??= Array.from({ length: 256 }, (_, n) => {
        let c = n;
        for (let k = 0; k < 8; k++) {
            c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
        }
        return c >>> 0;
    });
    let crc = 0xffffffff;
    for (const byte of bytes) {
        crc = crcTable[(crc ^ byte) & 0xff] ^ (crc >>> 8);
    }
    return (crc ^ 0xffffffff) >>> 0;
}

function pngChunk(type, data) {
    const chunk = new Uint8Array(12 + data.length);
    const view = new DataView(chunk.buffer);
    view.setUint32(0, data.length);
    for (let i = 0; i < 4; i++) {
        chunk[4 + i] = type.charCodeAt(i);
    }
    chunk.set(data, 8);
    view.setUint32(8 + data.length, crc32(chunk.subarray(4, 8 + data.length)));
    return chunk;
}

/**
 * The dots as a PNG data URL: 1-bit greyscale (5 times smaller than the canvas's RGBA PNG, so the
 * link stays far below Android's Intent size limit), compressed with the browser's
 * CompressionStream (zlib, Chrome 80+); the canvas's own PNG where that is missing.
 */
export async function khDotsToPng({ dots, width, height }) {
    if (typeof CompressionStream === "function") {
        const stride = Math.ceil(width / 8);
        const raw = new Uint8Array((stride + 1) * height); // each row: filter byte 0, then the bits
        for (let y = 0; y < height; y++) {
            const offset = y * (stride + 1) + 1;
            for (let x = 0; x < width; x++) {
                if (!dots[y * width + x]) {
                    raw[offset + (x >> 3)] |= 0x80 >> (x & 7); // 1 = white
                }
            }
        }
        const header = new Uint8Array(13);
        new DataView(header.buffer).setUint32(0, width);
        new DataView(header.buffer).setUint32(4, height);
        header[8] = 1; // bit depth; colour type 0 (greyscale), deflate, no filter, no interlace
        const deflated = new Response(
            new Blob([raw]).stream().pipeThrough(new CompressionStream("deflate"))
        );
        const png = new Blob(
            [
                new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
                pngChunk("IHDR", header),
                pngChunk("IDAT", new Uint8Array(await deflated.arrayBuffer())),
                pngChunk("IEND", new Uint8Array(0)),
            ],
            { type: "image/png" }
        );
        return blobToDataURL(png);
    }
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    const image = ctx.createImageData(width, height);
    for (let i = 0; i < dots.length; i++) {
        const value = dots[i] ? 0 : 255;
        image.data.set([value, value, value, 255], i * 4);
    }
    ctx.putImageData(image, 0, 0);
    return canvas.toDataURL("image/png");
}

export class KhRawbtPrinter extends BasePrinter {
    setup({ dialog } = {}) {
        super.setup(...arguments);
        this.dialog = dialog;
        this.lastLaunch = 0;
        this.jobs = Promise.resolve();
    }

    /**
     * BasePrinter.printReceipt, one receipt at a time (an automatic print can still be drawing when
     * the cashier taps Print), with khReceiptCanvas instead of core's htmlToCanvas.
     */
    printReceipt(receipt) {
        const job = this.jobs.then(() => this.printOne(receipt));
        this.jobs = job.catch(() => {});
        return job;
    }

    async printOne(receipt) {
        if (!receipt) {
            return { successful: true };
        }
        const image = await this.processCanvas(await khReceiptCanvas(receipt));
        if (image.length + "rawbt:".length > MAX_LINK_CHARS) {
            return this.getResultsError({ tooLong: true });
        }
        let printResult;
        try {
            printResult = await this.sendPrintingJob(image);
        } catch {
            return this.getActionError();
        }
        if (!printResult || printResult.result === false) {
            return this.getResultsError(printResult);
        }
        return { successful: true };
    }

    /** @returns {Promise<string>} the image as a PNG data URL */
    processCanvas(canvas) {
        return khDotsToPng(khDither(canvas));
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

    getResultsError(printResult) {
        if (printResult?.tooLong) {
            return {
                successful: false,
                message: {
                    title: _t("Too long for RawBT"),
                    body: _t("This document is too long to send to RawBT in one piece. "),
                },
            };
        }
        return this.getActionError();
    }
}

/**
 * Use RawBT for this point of sale's receipts (setting "Print receipts with: RawBT app", Android
 * browsers only: the same point of sale opened on a computer keeps its own printing).
 */
export function khInstallRawbt(pos) {
    if (!khUsesRawbt(pos.config)) {
        return false;
    }
    if (!(pos.hardwareProxy.printer instanceof KhRawbtPrinter)) {
        pos.hardwareProxy.printer = new KhRawbtPrinter({ dialog: pos.dialog });
    }
    return true;
}

patch(PosStore.prototype, {
    async afterProcessServerData() {
        // before core's server calls (a receipt printed meanwhile goes to RawBT too) and again after
        // them: pos_epson_printer sets its ePOS printer in there, RawBT is the one chosen here
        const rawbt = khInstallRawbt(this);
        const result = await super.afterProcessServerData(...arguments);
        if (rawbt) {
            khInstallRawbt(this);
            // embed the fonts once, after the POS has loaded, so the first receipt is as quick
            setTimeout(() => {
                khReceiptFontFace().catch(() => {});
                khFontFaceMap().catch(() => {});
            }, 3000);
        }
        return result;
    },
});
