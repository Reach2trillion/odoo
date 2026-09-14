/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { getReportUrl } from "@web/webclient/actions/reports/utils";

// How long the hidden iframe stays alive after print() returns. Chrome blocks
// in print() until the dialog closes, but Safari/Firefox return immediately,
// so keep the frame around long enough for the dialog to be used.
const IFRAME_CLEANUP_DELAY_MS = 60_000;
// Small delay after the iframe "load" event so the PDF viewer plugin is ready.
const PRINT_DELAY_MS = 300;

/**
 * Loads a PDF blob in a hidden iframe and opens the browser print dialog on it.
 * With Chrome started with `--kiosk-printing` the dialog is auto-accepted,
 * which gives a fully silent print to the default printer.
 */
function printPdfBlob(blob) {
    return new Promise((resolve) => {
        const objectUrl = URL.createObjectURL(blob);
        const iframe = document.createElement("iframe");
        iframe.setAttribute("aria-hidden", "true");
        iframe.style.position = "fixed";
        iframe.style.right = "0";
        iframe.style.bottom = "0";
        iframe.style.width = "0";
        iframe.style.height = "0";
        iframe.style.border = "0";
        iframe.style.visibility = "hidden";

        const cleanup = () => {
            setTimeout(() => {
                iframe.remove();
                URL.revokeObjectURL(objectUrl);
            }, IFRAME_CLEANUP_DELAY_MS);
            resolve();
        };

        iframe.onload = () => {
            setTimeout(() => {
                try {
                    iframe.contentWindow.focus();
                    iframe.contentWindow.print();
                } catch {
                    // Browser refused printing from the frame: fall back to a tab the user can print.
                    window.open(objectUrl, "_blank");
                }
                cleanup();
            }, PRINT_DELAY_MS);
        };
        iframe.src = objectUrl;
        document.body.appendChild(iframe);
    });
}

/**
 * `ir.actions.report` handler: reports flagged with the
 * `stock_auto_print_label_browser` context key (set by
 * stock.picking._get_autoprint_report_actions) are fetched as PDF and sent to
 * the browser print dialog instead of being downloaded. Returning `false`
 * hands the action back to Odoo's default flow (download / IoT / PrintNode).
 */
async function browserPrintReportHandler(action, options, env) {
    const context = action.context || {};
    if (action.report_type !== "qweb-pdf" || !context.stock_auto_print_label_browser) {
        return false;
    }
    let blob;
    try {
        const response = await fetch(getReportUrl(action, "pdf"), { credentials: "same-origin" });
        const contentType = response.headers.get("content-type") || "";
        if (!response.ok || !contentType.includes("application/pdf")) {
            throw new Error(`${response.status} ${response.statusText}`);
        }
        blob = await response.blob();
    } catch (error) {
        env.services.notification.add(
            _t("The label could not be generated for printing (%s). Falling back to a PDF download.", error.message),
            { title: _t("Label printing"), type: "warning" }
        );
        return false;
    }
    await printPdfBlob(blob);
    return true;
}

registry
    .category("ir.actions.report handlers")
    .add("stock_auto_print_label_browser_print", browserPrintReportHandler, { sequence: 5 });
