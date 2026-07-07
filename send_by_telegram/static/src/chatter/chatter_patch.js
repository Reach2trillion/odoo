/** @odoo-module */

import { Chatter } from "@mail/chatter/web_portal/chatter";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(Chatter.prototype, {
    sendTelegram() {
        const send = async (thread) => {
            await new Promise((resolve) => {
                this.env.services.action.doAction(
                    {
                        type: "ir.actions.act_window",
                        name: _t("Send via Telegram"),
                        res_model: "telegram.message.wizard",
                        view_mode: "form",
                        views: [[false, "form"]],
                        target: "new",
                        context: {
                            default_res_model: thread.model,
                            default_res_id: thread.id,
                            from_chatter: true,
                        },
                    },
                    { onClose: resolve }
                );
            });
            this.store.Thread.insert({
                model: this.props.threadModel,
                id: this.props.threadId,
            }).fetchNewMessages();
        };
        if (this.state.thread.id) {
            send(this.state.thread);
        } else {
            this.onThreadCreated = send;
            this.props.saveRecord?.();
        }
    },
});
