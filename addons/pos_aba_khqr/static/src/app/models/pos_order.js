/** @odoo-module */

import { toRaw } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { PosOrder } from "@point_of_sale/app/models/pos_order";

/**
 * Customer-facing display support.
 *
 * `PaymentAbaKhqr` keeps `order.abaKhqrDisplay` up to date while a KHQR popup
 * is open on the cashier screen (null otherwise). The POS already streams
 * `getCustomerDisplayData()` to the customer display whenever the order
 * changes, so the same KHQR reaches the second screen through that channel.
 *
 * The remaining lifetime is computed here, at send time, so the display can
 * re-anchor its own countdown on every message and never depends on the two
 * devices having the same clock.
 */
patch(PosOrder.prototype, {
    getCustomerDisplayData() {
        const data = super.getCustomerDisplayData(...arguments);
        const khqr = this.abaKhqrDisplay ? toRaw(this.abaKhqrDisplay) : null;
        data.abaKhqr = khqr
            ? {
                  ...khqr,
                  expiresIn: khqr.expiresAt
                      ? Math.max(0, Math.round((khqr.expiresAt - Date.now()) / 1000))
                      : 0,
              }
            : null;
        return data;
    },
});
