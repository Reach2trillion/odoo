/** @odoo-module */

import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { Dialog } from "@web/core/dialog/dialog";

/**
 * KHQR popup shown to the customer at the POS.
 * Pure view: the flow lives in PaymentAbaKhqr, which shares `ui` (reactive).
 */
export class AbaKhqrDialog extends Component {
    static template = "pos_aba_khqr.AbaKhqrDialog";
    static components = { Dialog };
    static props = {
        ui: Object,
        title: { type: String, optional: true },
        onCancel: Function,
        onRetry: Function,
        onCheck: Function,
        onAskConfirm: Function,
        onBackFromConfirm: Function,
        onConfirm: Function,
        close: Function,
    };

    setup() {
        this.ui = useState(this.props.ui);
    }

    get request() {
        return this.ui.request || {};
    }

    get isOwnKhqr() {
        return this.request.mode === "bakong";
    }

    get isExpired() {
        return (
            this.ui.state === "expired" ||
            (this.ui.state === "waiting" && Boolean(this.ui.request) && this.ui.secondsLeft <= 0)
        );
    }

    get merchantName() {
        return this.request.merchant_name || this.props.title || "";
    }

    get amountText() {
        return this.request.amount_text || "";
    }

    get currency() {
        return this.request.currency || "";
    }

    get currencySymbol() {
        return this.request.currency_symbol || "$";
    }

    get amountLabel() {
        return `${this.amountText} ${this.currency}`.trim();
    }

    get showTimer() {
        return this.ui.state === "waiting" && !this.isExpired;
    }

    get countdown() {
        const total = Math.max(0, Math.floor(this.ui.secondsLeft || 0));
        const hours = Math.floor(total / 3600);
        const minutes = Math.floor((total % 3600) / 60);
        const seconds = String(total % 60).padStart(2, "0");
        return hours
            ? `${hours}:${String(minutes).padStart(2, "0")}:${seconds}`
            : `${minutes}:${seconds}`;
    }

    get statusText() {
        switch (this.ui.state) {
            case "loading":
                return _t("Creating the KHQR...");
            case "waiting":
                if (this.isExpired) {
                    return _t("QR expired");
                }
                return this.isOwnKhqr
                    ? _t("Waiting - check your ABA app")
                    : _t("Waiting for payment");
            case "paid":
                return this.request.apv
                    ? _t("Paid - APV %s", this.request.apv)
                    : _t("Paid");
            case "expired":
                return _t("QR expired");
            case "cancelled":
                return _t("Cancelled");
            case "failed":
                return _t("Payment failed");
            default:
                return _t("Could not create the QR");
        }
    }

    get statusClass() {
        return {
            "is-paid": this.ui.state === "paid",
            "is-urgent": this.showTimer && this.ui.secondsLeft <= 30,
            "is-error": ["error", "failed", "cancelled"].includes(this.ui.state) || this.isExpired,
        };
    }

    get errorText() {
        return this.ui.error || this.request.message || this.statusText;
    }
}
