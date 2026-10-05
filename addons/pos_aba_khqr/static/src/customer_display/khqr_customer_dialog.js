/** @odoo-module */

import { Component, onMounted, onWillUnmount, useEffect, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

/**
 * Full-size KHQR for the customer-facing display.
 *
 * Pure view over `props.display.abaKhqr` (the reactive customer-display data).
 * The POS re-sends `expiresIn` with every message, so the countdown is
 * re-anchored each time and never drifts, whatever the display's own clock.
 * When the POS withdraws the data the parent keeps this dialog open a moment
 * ("paid" linger), so the last payload is kept to render that final screen.
 */
export class AbaKhqrCustomerDialog extends Component {
    static template = "pos_aba_khqr.AbaKhqrCustomerDialog";
    static components = { Dialog };
    static props = {
        display: Object,
        close: Function,
    };

    setup() {
        this.display = useState(this.props.display);
        this.ui = useState({ secondsLeft: 0 });
        this.last = this.display.abaKhqr ? { ...this.display.abaKhqr } : {};
        this.anchor = 0;

        useEffect(
            (khqr) => {
                if (khqr) {
                    this.last = { ...khqr };
                    this.anchor = Date.now() + (khqr.expiresIn || 0) * 1000;
                    this.tick();
                }
            },
            () => [this.display.abaKhqr]
        );
        onMounted(() => {
            this.timer = setInterval(() => this.tick(), 1000);
        });
        onWillUnmount(() => clearInterval(this.timer));
    }

    tick() {
        this.ui.secondsLeft = Math.max(0, Math.round((this.anchor - Date.now()) / 1000));
    }

    get khqr() {
        return this.display.abaKhqr || this.last;
    }

    get isPaid() {
        return this.khqr.state === "paid";
    }

    get isLoading() {
        return this.khqr.state === "loading" || !this.khqr.qrImage;
    }

    get isExpired() {
        return (
            !this.isPaid &&
            !this.isLoading &&
            (this.khqr.state === "expired" || this.ui.secondsLeft <= 0)
        );
    }

    get isWaiting() {
        return this.khqr.state === "waiting" && !this.isExpired && !this.isLoading;
    }

    get isUrgent() {
        return this.isWaiting && this.ui.secondsLeft <= 30;
    }

    get countdown() {
        const total = Math.max(0, Math.floor(this.ui.secondsLeft || 0));
        const minutes = Math.floor(total / 60);
        const seconds = String(total % 60).padStart(2, "0");
        return `${minutes}:${seconds}`;
    }
}
