/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

const GEOLOCATION_OPTIONS = { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 };

/**
 * Button saving the phone's GPS position as the map location of a customer.
 *
 * <widget name="abj_location_gps" method="..." string="..." [highlight="1"] [confirm="..."]/>
 *   method     server method of the record, called with latitude, longitude, accuracy and force;
 *              it answers {status: saved | same | confirm | inaccurate | office, ...}
 *   string     button label
 *   highlight  primary (colored) button
 *   confirm    question asked before taking the position
 */
export class LocationGpsButton extends Component {
    static template = "abj_customer_location.LocationGpsButton";
    static props = {
        ...standardWidgetProps,
        method: { type: String },
        string: { type: String },
        highlight: { type: Boolean, optional: true },
        confirm: { type: String, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.state = useState({ busy: false });
    }

    async onClick() {
        if (this.state.busy) {
            return;
        }
        if (this.props.confirm && !(await this.ask(this.props.confirm, _t("Yes")))) {
            return;
        }
        this.state.busy = true;
        try {
            // a new or modified record must exist in the database before the server can use it
            if (!(await this.props.record.save())) {
                return;
            }
            const coords = await this.getPosition();
            if (coords) {
                await this.send(coords, false);
            }
        } finally {
            this.state.busy = false;
        }
    }

    ask(body, confirmLabel) {
        return new Promise((resolve) => {
            this.dialog.add(
                ConfirmationDialog,
                {
                    body,
                    confirmLabel,
                    cancelLabel: _t("Cancel"),
                    confirm: () => resolve(true),
                    cancel: () => resolve(false),
                },
                { onClose: () => resolve(false) }
            );
        });
    }

    async getPosition() {
        if (!navigator.geolocation) {
            this.warn(_t("This browser cannot read the GPS. Open Odoo in Chrome or Safari on the phone."));
            return null;
        }
        try {
            const position = await new Promise((resolve, reject) =>
                navigator.geolocation.getCurrentPosition(resolve, reject, GEOLOCATION_OPTIONS)
            );
            return position.coords;
        } catch (error) {
            const messages = {
                1: _t(
                    "Location access is blocked. Allow location for this site in the browser or phone settings, then tap the button again."
                ),
                2: _t("The GPS position is not available. Switch on Location (GPS) on the phone and try again."),
                3: _t("Getting the GPS position took too long. Go outside or near a window and try again."),
            };
            this.warn(messages[error && error.code] || _t("The GPS position could not be read. Please try again."));
            return null;
        }
    }

    async send(coords, force) {
        const { record } = this.props;
        const result = await this.orm.call(record.resModel, this.props.method, [[record.resId]], {
            latitude: coords.latitude,
            longitude: coords.longitude,
            accuracy: Number.isFinite(coords.accuracy) ? coords.accuracy : 0,
            force,
        });
        switch (result.status) {
            case "confirm": {
                const replace = await this.ask(
                    _t(
                        "You are %(distance)s from the map location saved for %(partner)s. Are you at the customer's place? Then replace the saved location with where you are now.",
                        { distance: result.distance_label, partner: result.partner }
                    ),
                    _t("Replace location")
                );
                if (replace) {
                    await this.send(coords, true);
                }
                return;
            }
            case "saved":
                this.notification.add(
                    result.replaced
                        ? _t("Map location of %(partner)s replaced (±%(accuracy)s m).", result)
                        : _t("Map location of %(partner)s saved (±%(accuracy)s m).", result),
                    { type: "success" }
                );
                break;
            case "same":
                this.notification.add(
                    _t("You are at the saved location of %(partner)s (%(distance)s away). Nothing to change.", {
                        partner: result.partner,
                        distance: result.distance_label,
                    }),
                    { type: "info" }
                );
                break;
            case "inaccurate":
                this.warn(
                    _t(
                        "The GPS is not precise enough yet (±%(accuracy)s m, %(max_accuracy)s m needed). Wait a few seconds outside, then tap again.",
                        result
                    )
                );
                return;
            case "office":
                this.warn(
                    _t(
                        "You are at %(place)s, not at the customer. The location was not saved.",
                        result
                    )
                );
                return;
        }
        await record.load();
    }

    warn(message) {
        this.notification.add(message, { type: "warning", sticky: false });
    }
}

export const locationGpsButton = {
    component: LocationGpsButton,
    extractProps: ({ attrs }) => ({
        method: attrs.method,
        string: attrs.string,
        highlight: Boolean(attrs.highlight),
        confirm: attrs.confirm,
    }),
};

registry.category("view_widgets").add("abj_location_gps", locationGpsButton);
