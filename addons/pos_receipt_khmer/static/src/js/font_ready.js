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
    let queue = Promise.resolve();
    const renderOnce = async (component, props) => {
        for (let attempt = 0; attempt < 3; attempt++) {
            const el = await rawToHtml(component, props);
            if (el && el.nodeType === Node.ELEMENT_NODE) {
                return el;
            }
            // let the renderer's own delayed hook for the stale render pass, then render again
            await new Promise((resolve) => setTimeout(resolve, 250));
        }
        return rawToHtml(component, props);
    };
    const toHtml = (component, props) => {
        const result = queue.then(
            () => renderOnce(component, props),
            () => renderOnce(component, props)
        );
        queue = result.catch(() => {});
        return result;
    };
    const toCanvas = async (component, props, options) =>
        htmlToCanvas(await toHtml(component, props), options);
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
});
