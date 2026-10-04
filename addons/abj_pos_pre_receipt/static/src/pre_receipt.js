/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { mountComponent } from "@web/env";
import { loadAllImages } from "@point_of_sale/utils";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";

patch(PosOrder.prototype, {
    export_for_printing(baseUrl, headerData) {
        const result = super.export_for_printing(...arguments);
        // Unpaid order printed from the product screen: flag it so the
        // receipt clearly says it is not a proof of payment.
        result.is_pre_receipt = !this.finalized;
        return result;
    },
});

patch(ControlButtons.prototype, {
    async clickPrintPreReceipt() {
        const order = this.pos.get_order();
        if (!order || order.is_empty() || this.printingPreReceipt) {
            return;
        }
        // Only print: never finalize the order or change screen, so the
        // cashier stays on the order and can still edit it or take payment.
        this.printingPreReceipt = true;
        // Render the receipt in our own off-screen container instead of the
        // shared renderer service (renderer.toHtml), whose single shared slot
        // can hand back a wrong element when prints overlap.
        const container = document.createElement("div");
        container.className = "abj-pre-receipt-render";
        container.style.cssText = "position: fixed; left: -10000px; top: 0; width: 512px;";
        document.body.appendChild(container);
        let app;
        try {
            app = await mountComponent(OrderReceipt, container, {
                env: this.env,
                props: {
                    data: this.pos.orderExportForPrinting(order),
                    formatCurrency: this.env.utils.formatCurrency,
                },
            });
            const el = container.querySelector(".pos-receipt");
            if (!el) {
                throw new Error("The receipt could not be rendered.");
            }
            try {
                await loadAllImages(el);
            } catch (error) {
                console.error("Images could not be loaded correctly", error);
            }
            await this.pos.printer.printHtml(el, { webPrintFallback: true });
        } catch (error) {
            console.error("abj_pos_pre_receipt: printing the bill failed", error);
            this.notification.add(_t("The bill could not be printed: %s", error.message || error), {
                type: "danger",
            });
        } finally {
            app?.destroy();
            container.remove();
            this.printingPreReceipt = false;
        }
    },
});
