import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { PrinterService } from "@point_of_sale/app/printer/printer_service";

// The receipt is measured (htmlToCanvas) right after it is mounted; if the bundled Khmer font
// is not loaded yet, the canvas box is measured with the fallback font and rows end up clipped
// or gappy. With iface_print_auto / skip-screen the receipt is never shown on screen first.
const KH_FONTS = ['500 27px "ABJ Khmer"', '700 27px "ABJ Khmer"'];
const KH_SAMPLE = "ខ្មែរ Aa";
const MAX_WAIT_MS = 4000; // never hold a print longer than this

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

// PosPrinterService does not override print(): patching the base class covers every printer
patch(PrinterService.prototype, {
    async print() {
        await loadKhFonts();
        return super.print(...arguments);
    },
});
