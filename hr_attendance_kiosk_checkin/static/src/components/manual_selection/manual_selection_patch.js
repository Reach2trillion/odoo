import { deserializeDateTime } from "@web/core/l10n/dates";
import { patch } from "@web/core/utils/patch";
import { KioskManualSelection } from "@hr_attendance/components/manual_selection/manual_selection";

patch(KioskManualSelection.prototype, {
    formatCheckInTime(checkIn) {
        const { DateTime } = luxon;
        const dt = deserializeDateTime(checkIn);
        return dt.hasSame(DateTime.now(), "day")
            ? dt.toLocaleString(DateTime.TIME_SIMPLE)
            : dt.toLocaleString(DateTime.DATETIME_MED);
    },
});
