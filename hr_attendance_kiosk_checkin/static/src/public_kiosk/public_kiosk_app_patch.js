import { onWillStart } from "@odoo/owl";
import { deserializeDateTime } from "@web/core/l10n/dates";
import { rpc } from "@web/core/network/rpc";
import { patch } from "@web/core/utils/patch";
import publicKioskApp from "@hr_attendance/public_kiosk/public_kiosk_app";

patch(publicKioskApp.kioskAttendanceApp.prototype, {
    setup() {
        super.setup();
        this.state.checkedInEmployees = [];
        onWillStart(async () => {
            await this.loadCheckedInEmployees();
        });
    },

    async loadCheckedInEmployees() {
        this.state.checkedInEmployees = await rpc("/hr_attendance/checked_in_employees", {
            token: this.props.token,
        });
    },

    formatCheckInTime(checkIn) {
        const { DateTime } = luxon;
        const dt = deserializeDateTime(checkIn);
        return dt.hasSame(DateTime.now(), "day")
            ? dt.toLocaleString(DateTime.TIME_SIMPLE)
            : dt.toLocaleString(DateTime.DATETIME_MED);
    },

    switchDisplay(screen) {
        super.switchDisplay(screen);
        if (["main", "manual"].includes(this.state.active_display)) {
            this.loadCheckedInEmployees();
        }
    },
});
