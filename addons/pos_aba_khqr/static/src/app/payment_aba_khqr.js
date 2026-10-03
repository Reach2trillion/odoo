/** @odoo-module */

import { reactive } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { PaymentInterface } from "@point_of_sale/app/payment/payment_interface";
import { register_payment_method } from "@point_of_sale/app/store/pos_store";
import { AbaKhqrDialog } from "./khqr_dialog/khqr_dialog";

const POLL_INTERVAL_MS = 3000;
const PAID_CLOSE_DELAY_MS = 1400;

/**
 * POS "terminal" for ABA KHQR.
 *
 * The server does all the bank work (PayWay QR API or local KHQR build); this
 * class only opens the KHQR popup, polls the server and resolves the payment
 * line once the request is paid.
 */
export class PaymentAbaKhqr extends PaymentInterface {
    setup() {
        super.setup(...arguments);
        this.session = null;
    }

    get paymentMethodId() {
        const method = this.payment_method_id ?? this.payment_method;
        return method && typeof method === "object" ? method.id : method;
    }

    get paymentMethodName() {
        const method = this.payment_method_id ?? this.payment_method;
        return (method && typeof method === "object" && method.name) || _t("ABA KHQR");
    }

    send_payment_request(uuid) {
        super.send_payment_request(...arguments);
        return this._payWithKhqr(uuid);
    }

    send_payment_cancel(order, uuid) {
        super.send_payment_cancel(...arguments);
        if (this.session && this.session.lineUuid === uuid) {
            this._cancel(this.session);
        }
        return Promise.resolve(true);
    }

    close() {
        if (this.session) {
            this._cancel(this.session);
        }
    }

    // ------------------------------------------------------------------
    // Flow
    // ------------------------------------------------------------------

    _payWithKhqr(uuid) {
        const order = this.pos.get_order ? this.pos.get_order() : this.pos.getOrder();
        const line = this._getLine(order, uuid);
        if (!line) {
            return Promise.resolve(false);
        }
        if (!(line.amount > 0)) {
            this._notify(_t("KHQR can only receive money. Use another method for refunds."));
            return Promise.resolve(false);
        }
        if (this.session) {
            this._finish(this.session, false);
        }

        const session = {
            lineUuid: uuid,
            order,
            amount: line.amount,
            done: false,
            timers: [],
            ui: reactive({
                state: "loading", // loading | waiting | paid | expired | cancelled | failed | error
                request: null,
                error: "",
                warning: "",
                secondsLeft: 0,
                busy: false,
                confirming: false,
                orderRef: this._orderReference(order),
            }),
        };
        this.session = session;
        const result = new Promise((resolve) => (session.resolve = resolve));
        session.closeDialog = this.env.services.dialog.add(
            AbaKhqrDialog,
            {
                ui: session.ui,
                title: this.paymentMethodName,
                onCancel: () => this._cancel(session),
                onRetry: () => this._renew(session),
                onCheck: () => this._poll(session, true),
                onAskConfirm: () => (session.ui.confirming = true),
                onBackFromConfirm: () => (session.ui.confirming = false),
                onConfirm: () => this._confirmManual(session),
            },
            { onClose: () => this._onDialogClosed(session) }
        );
        this._createRequest(session);
        return result;
    }

    async _createRequest(session) {
        const { ui } = session;
        this._stopTimers(session);
        Object.assign(ui, { state: "loading", request: null, error: "", warning: "" });
        try {
            const request = await this._call("aba_khqr_create_request", [
                this.pos.config.id,
                session.amount,
                ui.orderRef,
                session.order?.uuid || false,
            ]);
            if (session.done) {
                // The cashier closed the popup while the QR was being made.
                this._call("aba_khqr_cancel_request", [request.id]).catch(() => {});
                return;
            }
            this._applyRequest(session, request);
            if (ui.state === "waiting") {
                this._startTimers(session);
            }
        } catch (error) {
            ui.state = "error";
            ui.error = this._errorMessage(error);
        }
    }

    _applyRequest(session, request) {
        const { ui } = session;
        const previousImage = ui.request?.qr_image;
        ui.request = { ...request, qr_image: request.qr_image || previousImage };
        session.expiresAt = Date.now() + request.expires_in * 1000;
        ui.secondsLeft = request.expires_in;
        ui.warning = "";
        if (request.state === "paid") {
            this._onPaid(session, request);
        } else if (request.state === "pending") {
            ui.state = "waiting";
        } else {
            ui.state = request.state; // expired | cancelled | failed
            this._stopTimers(session);
        }
    }

    _startTimers(session) {
        const { ui } = session;
        session.timers.push(
            setInterval(() => {
                ui.secondsLeft = Math.max(0, Math.round((session.expiresAt - Date.now()) / 1000));
            }, 1000)
        );
        const tick = async () => {
            if (session.done || ui.state !== "waiting") {
                return;
            }
            // Own-KHQR payments are confirmed by the cashier: only ask the
            // server again once the QR is past its expiry.
            if (ui.request?.mode === "payway" || ui.secondsLeft === 0) {
                await this._poll(session, ui.secondsLeft === 0);
            }
            if (!session.done && ui.state === "waiting") {
                session.pollTimer = setTimeout(tick, POLL_INTERVAL_MS);
            }
        };
        session.pollTimer = setTimeout(tick, POLL_INTERVAL_MS);
    }

    _stopTimers(session) {
        session.timers.forEach((timer) => clearInterval(timer));
        session.timers = [];
        clearTimeout(session.pollTimer);
    }

    async _poll(session, force = false) {
        const { ui } = session;
        if (session.polling || session.done || !ui.request) {
            return;
        }
        session.polling = true;
        try {
            const request = await this._call("aba_khqr_check_request", [ui.request.id, force]);
            if (!session.done) {
                this._applyRequest(session, request);
            }
        } catch {
            ui.warning = _t("Connection problem, still checking...");
        } finally {
            session.polling = false;
        }
    }

    _onPaid(session, request) {
        const { ui } = session;
        this._stopTimers(session);
        ui.state = "paid";
        ui.confirming = false;
        const line = this._getLine(session.order, session.lineUuid);
        if (line) {
            line.transaction_id = request.tran_id;
            line.card_type = "KHQR";
        }
        setTimeout(() => this._finish(session, true), PAID_CLOSE_DELAY_MS);
    }

    async _renew(session) {
        const { ui } = session;
        if (ui.busy) {
            return;
        }
        if (ui.request && ui.state === "waiting") {
            ui.busy = true;
            try {
                const request = await this._call("aba_khqr_cancel_request", [ui.request.id]);
                if (request.state === "paid") {
                    return this._applyRequest(session, request);
                }
            } catch {
                // the cron re-checks cancelled QR codes, nothing is lost
            } finally {
                ui.busy = false;
            }
        }
        await this._createRequest(session);
    }

    async _confirmManual(session) {
        const { ui } = session;
        if (ui.busy || !ui.request) {
            return;
        }
        ui.busy = true;
        try {
            const request = await this._call("aba_khqr_confirm_request", [ui.request.id]);
            this._applyRequest(session, request);
        } catch (error) {
            ui.warning = this._errorMessage(error);
        } finally {
            ui.busy = false;
        }
    }

    async _cancel(session) {
        const { ui } = session;
        if (session.done || session.cancelling) {
            return;
        }
        if (ui.state === "paid") {
            // Closed during the "paid" animation: the money is in, keep it.
            return this._finish(session, true);
        }
        if (!ui.request || ui.state !== "waiting") {
            return this._finish(session, false);
        }
        session.cancelling = true;
        ui.busy = true;
        this._stopTimers(session);
        try {
            const request = await this._call("aba_khqr_cancel_request", [ui.request.id]);
            if (request.state === "paid") {
                // Paid a second before the cashier gave up: keep the payment.
                return this._applyRequest(session, request);
            }
        } catch {
            // the cron re-checks cancelled QR codes, nothing is lost
        } finally {
            session.cancelling = false;
            ui.busy = false;
        }
        this._finish(session, false);
    }

    _onDialogClosed(session) {
        session.dialogClosed = true;
        if (!session.done) {
            this._cancel(session);
        }
    }

    _finish(session, paid) {
        if (session.done) {
            return;
        }
        session.done = true;
        this._stopTimers(session);
        if (this.session === session) {
            this.session = null;
        }
        if (!session.dialogClosed) {
            session.dialogClosed = true;
            session.closeDialog?.();
        }
        session.resolve(paid);
    }

    // ------------------------------------------------------------------
    // Helpers
    // ------------------------------------------------------------------

    _call(method, args) {
        const orm = this.env.services.orm;
        return (orm.silent || orm).call("pos.payment.method", method, [
            [this.paymentMethodId],
            ...args,
        ]);
    }

    _getLine(order, uuid) {
        const lines = order?.payment_ids || order?.paymentlines || [];
        return lines.find((line) => line.uuid === uuid);
    }

    _orderReference(order) {
        const candidates = [order?.pos_reference, order?.name, order?.tracking_number];
        return candidates.find((ref) => ref && ref !== "/") || "";
    }

    _errorMessage(error) {
        return error?.data?.message || error?.message || _t("Unknown error");
    }

    _notify(message) {
        this.env.services.notification.add(message, { type: "danger" });
    }
}

register_payment_method("aba_khqr", PaymentAbaKhqr);
