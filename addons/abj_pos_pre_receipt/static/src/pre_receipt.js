/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
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
        if (!order || order.is_empty()) {
            return;
        }
        // Only print: never finalize the order or change screen, so the
        // cashier stays on the order and can still edit it or take payment.
        await this.pos.printReceipt({ order, printBillActionTriggered: true });
    },
});
