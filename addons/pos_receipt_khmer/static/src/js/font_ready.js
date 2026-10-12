import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { PrinterService } from "@point_of_sale/app/printer/printer_service";
import { htmlToCanvas } from "@point_of_sale/app/printer/render_service";

// The receipt is measured (htmlToCanvas) right after it is mounted; if the bundled Khmer font
// is not loaded yet, the canvas box is measured with the fallback font and rows end up clipped
// or gappy. With iface_print_auto / skip-screen the receipt is never shown on screen first.
const KH_FONTS = ['500 27px "ABJ Khmer"', '700 27px "ABJ Khmer"'];
const KH_SAMPLE = "ខ្មែរ Aa";
const MAX_WAIT_MS = 2000; // never hold a print longer than this

export function loadKhFonts() {
    if (!document.fonts?.load) {
        return Promise.resolve();
    }
    const load = Promise.all(KH_FONTS.map((f) => document.fonts.load(f, KH_SAMPLE))).catch(
        () => {}
    );
    const timeout = new Promise((resolve) => setTimeout(resolve, MAX_WAIT_MS));
    return Promise.race([load, timeout]);
}

patch(PosStore.prototype, {
    async _loadFonts() {
        // called unbound by pos_app (onWillStart(this.pos._loadFonts)): do not use `this`
        await Promise.all([super._loadFonts(...arguments), loadKhFonts()]);
    },
});

let khGraphemes;
function graphemeSegmenter() {
    if (khGraphemes === undefined) {
        try {
            khGraphemes = new Intl.Segmenter(undefined, { granularity: "grapheme" });
        } catch {
            khGraphemes = null;
        }
    }
    return khGraphemes;
}

/**
 * The text lines of a word box that wraps inside itself (a word longer than the line: the browser
 * broke it at hyphens or, overflow-wrap: break-word, between two grapheme clusters), as laid out:
 * [{ text, top }], tops in viewport px; null when it is one line or cannot be measured (no
 * Intl.Segmenter, not a plain text box).
 */
function khBoxLines(box, lineH) {
    const node = box.firstChild;
    const segmenter = graphemeSegmenter();
    if (!segmenter || box.childNodes.length !== 1 || node.nodeType !== Node.TEXT_NODE) {
        return null;
    }
    const range = document.createRange();
    const lines = [];
    let pending = ""; // clusters without a box of their own (zero-width characters) before the first line
    let lineTop = null;
    for (const { segment, index } of segmenter.segment(node.data)) {
        range.setStart(node, index);
        range.setEnd(node, index + segment.length);
        const rects = [...range.getClientRects()];
        const rect = rects.find((r) => r.width > 0) || rects[0];
        if (!rect || (!rect.width && !rect.height)) {
            lines.length ? (lines[lines.length - 1].text += segment) : (pending += segment);
            continue;
        }
        if (lineTop === null || rect.top >= lineTop + lineH / 2) {
            lines.push({ text: pending, top: rect.top });
            pending = "";
            lineTop = rect.top;
        }
        lines[lines.length - 1].text += segment;
    }
    return lines.length > 1 && lines.map((l) => l.text).join("") === node.data ? lines : null;
}

/**
 * Product names print as word boxes in a wrapping flex row (receipt_kh.scss 6b), so a line break
 * only depends on box widths, which html-to-image copies. It copies them as computed values with 6
 * significant digits, which the clone's layout snaps back to 1/64 px: a width can come back up to
 * 1/64 px smaller, so a line that fitted with less than that to spare could wrap in the image (one
 * line more than the frozen box: the word overlaps the next row), or the reverse. Before a receipt
 * is turned into an image, freeze the lines instead: lay out a copy in the render container with the
 * image's classes, group the words of every line into a no-wrap span.kh-line, and print that copy.
 * A word longer than the line wraps inside its own box: its text lines are split into boxes of
 * their own (span.kh-w.kh-frag, no-wrap), one per frozen line, so the image cannot re-wrap them
 * either (its text is redrawn slightly smaller: a last line of one or two letters would move up
 * and leave a blank line).
 * Returns el itself when it has no word boxes (or when anything fails).
 */
export function khFreezeWordLines(el, addClass = "pos-receipt-print") {
    const container = document.querySelector(".render-container");
    if (!el?.querySelector?.(".kh-words") || !container) {
        return el;
    }
    const copy = el.cloneNode(true);
    const classes = (addClass || "").split(" ").filter(Boolean);
    const added = classes.filter((c) => !copy.classList.contains(c));
    copy.classList.add(...added);
    container.appendChild(copy);
    try {
        const top = (e) => Math.round(e.getBoundingClientRect().top);
        for (const words of copy.querySelectorAll(".kh-words:not(.kh-frozen)")) {
            // the boxes in reading order; a word wider than the line wrapped between its parts
            // (span.kh-g on several lines): its parts are boxes of their own lines (the word's space
            // goes to its last part)
            const items = [];
            for (const item of [...words.children]) {
                const parts = item.classList.contains("kh-g") ? [...item.children] : [];
                if (parts.length > 1 && new Set(parts.map(top)).size > 1) {
                    if (item.classList.contains("kh-sp")) {
                        parts[parts.length - 1].classList.add("kh-sp");
                    }
                    items.push(...parts);
                } else {
                    items.push(item);
                }
            }
            // one text line of the row (px): a box that wraps inside itself is several lines high,
            // so its own height is no measure of a line (half of 3 lines is more than one line
            // pitch: it was merged into the line above, where the no-wrap line squeezed the word
            // before it to a column of letters)
            const lh = parseFloat(getComputedStyle(words).lineHeight);
            const hasLh = Number.isFinite(lh) && lh > 0;
            const boxes = [];
            for (const item of items) {
                const r = item.getBoundingClientRect();
                const lineH = hasLh ? Math.min(r.height, lh) : r.height;
                const textLines =
                    hasLh && r.height > 1.5 * lh && item.classList.contains("kh-w")
                        ? khBoxLines(item, lh)
                        : null;
                if (!textLines) {
                    boxes.push({ el: item, top: r.top, lineH });
                    continue;
                }
                // tops relative to the box: its first line starts at the box's top
                for (const line of textLines) {
                    const frag = document.createElement("span");
                    frag.className = "kh-w kh-frag";
                    frag.textContent = line.text;
                    boxes.push({ el: frag, top: r.top + line.top - textLines[0].top, lineH: lh });
                }
            }
            const lines = [];
            let lineTop = null;
            for (const { el: box, top: boxTop, lineH } of boxes) {
                // same flex line: same top (one font); a new line starts at least half a line lower
                if (lineTop === null || boxTop >= lineTop + lineH / 2) {
                    lines.push([]);
                    lineTop = boxTop;
                }
                lines[lines.length - 1].push(box);
            }
            words.replaceChildren(
                ...lines.map((items) => {
                    const line = document.createElement("span");
                    line.className = "kh-line";
                    line.append(...items);
                    return line;
                })
            );
            words.classList.add("kh-frozen");
        }
        copy.remove();
        copy.classList.remove(...added);
        return copy;
    } catch (error) {
        console.error("pos_receipt_khmer: could not freeze the product-name lines", error);
        copy.remove();
        return el;
    }
}

/**
 * Older 18.0 builds (before mid-2025) hand the printer `firstChild` of the render container from an
 * onRendered hook that also fires 100 ms after the container is flushed. When two renders overlap
 * (a double click, a print while another receipt is still rendering), a render can resolve with that
 * empty placeholder text node and the print fails with "el.classList is not iterable", or one of the
 * two renders never resolves. Guard the renderer once: run its renders one at a time, and render
 * again if the result is not an element. On current builds this only adds a cheap check.
 */
export function guardRenderer(renderer) {
    if (!renderer || renderer.__khGuarded || typeof renderer.toHtml !== "function") {
        return;
    }
    const rawToHtml = renderer.toHtml;
    const RENDER_TIMEOUT_MS = 6000;
    const STUCK = Symbol("kh-render-stuck");
    // two animation frames (plus a macrotask): lets OWL draw the renderer's emptied container after
    // the previous render, so the next render mounts afresh and reports its element
    const settle = async () => {
        await new Promise((resolve) => setTimeout(resolve, 0));
        for (let i = 0; i < 2; i++) {
            await new Promise((resolve) =>
                typeof requestAnimationFrame === "function"
                    ? requestAnimationFrame(() => resolve())
                    : setTimeout(resolve, 16)
            );
        }
    };
    const withTimeout = (promise) =>
        Promise.race([
            promise,
            new Promise((resolve) => setTimeout(() => resolve(STUCK), RENDER_TIMEOUT_MS)),
        ]);
    const renderOnce = async (component, props) => {
        for (let attempt = 0; attempt < 3; attempt++) {
            await settle();
            const el = await withTimeout(rawToHtml(component, props));
            if (el === STUCK) {
                // the renderer never reported this render: empty its container (not awaited, it
                // never reports either), let the empty state be drawn, then render again
                rawToHtml(null, {}).catch(() => {});
                await new Promise((resolve) => setTimeout(resolve, 150));
                continue;
            }
            if (el && el.nodeType === Node.ELEMENT_NODE) {
                return el;
            }
            // let the renderer's own delayed hook for the stale render pass, then render again
            await new Promise((resolve) => setTimeout(resolve, 250));
        }
        throw new Error("The receipt could not be rendered for printing. Please try again.");
    };
    let queue = Promise.resolve();
    const toHtml = (component, props) => {
        const result = queue.then(
            () => renderOnce(component, props),
            () => renderOnce(component, props)
        );
        queue = result.catch(() => {});
        return result;
    };
    // e-mail image (ReceiptScreen: renderer.toJpeg): freeze the product-name lines first
    const toCanvas = async (component, props, options) =>
        htmlToCanvas(khFreezeWordLines(await toHtml(component, props), options?.addClass), options);
    const toJpeg = async (component, props, options) => {
        const canvas = await toCanvas(component, props, options);
        return canvas.toDataURL("image/jpeg").replace("data:image/jpeg;base64,", "");
    };
    Object.assign(renderer, { toHtml, toCanvas, toJpeg, __khGuarded: true });
}

// PosPrinterService does not override print(): patching the base class covers every printer
patch(PrinterService.prototype, {
    setup() {
        super.setup(...arguments);
        guardRenderer(this.renderer);
    },
    async print() {
        guardRenderer(this.renderer);
        await loadKhFonts();
        return super.print(...arguments);
    },
    // raster printers (ePOS / IoT: BasePrinter.printReceipt -> htmlToCanvas): freeze the product-name
    // lines first. Browser printing (no device) prints the receipt as it is laid out.
    async printHtml(el, ...rest) {
        return super.printHtml(this.device ? khFreezeWordLines(el) : el, ...rest);
    },
});
