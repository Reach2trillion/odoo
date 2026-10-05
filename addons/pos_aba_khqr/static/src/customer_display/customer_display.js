/** @odoo-module */

import { useEffect } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { CustomerDisplay } from "@point_of_sale/customer_display/customer_display";
import { AbaKhqrCustomerDialog } from "./khqr_customer_dialog";

// Keep the green "Payment received" screen visible a moment after the cashier's
// popup has already gone, so the customer sees the confirmation.
const PAID_LINGER_MS = 2500;
const REOPEN_DELAY_MS = 400;

/**
 * Customer-facing display: show the KHQR the cashier is showing.
 *
 * The POS sends `abaKhqr` with every customer-display update while its popup
 * is open (see app/payment_aba_khqr.js), and `null` once the popup is gone.
 */
patch(CustomerDisplay.prototype, {
    setup() {
        super.setup(...arguments);
        const dialog = useService("dialog");
        let close = null;
        let closeTimer = null;
        let lastState = null;

        const open = () => {
            if (close) {
                return;
            }
            close = dialog.add(
                AbaKhqrCustomerDialog,
                { display: this.order },
                {
                    onClose: () => {
                        close = null;
                        // Closed by a tap on the screen while a QR is still due: bring it back.
                        if (this.order.abaKhqr) {
                            setTimeout(() => this.order.abaKhqr && open(), REOPEN_DELAY_MS);
                        }
                    },
                }
            );
        };

        useEffect(
            (khqr) => {
                if (khqr) {
                    lastState = khqr.state;
                    clearTimeout(closeTimer);
                    closeTimer = null;
                    open();
                } else if (close && !closeTimer) {
                    const delay = lastState === "paid" ? PAID_LINGER_MS : 0;
                    closeTimer = setTimeout(() => {
                        closeTimer = null;
                        close?.();
                    }, delay);
                }
            },
            () => [this.order.abaKhqr]
        );
    },
});
