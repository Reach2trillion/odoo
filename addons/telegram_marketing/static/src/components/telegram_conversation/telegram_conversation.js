/** @odoo-module **/

import {
    Component,
    markup,
    onMounted,
    onPatched,
    onWillUnmount,
    onWillUpdateProps,
    useRef,
    useState,
} from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

// Sent by telegram.chat._notify_bus() on the channel of the "Telegram / User" group, to which
// every member is subscribed automatically by the web client.
const NOTIFICATION_TYPE = "telegram_marketing/new_message";

/**
 * Live conversation view of a Telegram chat.
 *
 * The server renders the conversation as HTML (field ``conversation_html``);
 * this widget displays it, keeps it scrolled to the latest message, refreshes
 * itself when the bus announces a new message for this chat and marks the chat
 * as read when it is opened.
 */
export class TelegramConversationField extends Component {
    static template = "telegram_marketing.TelegramConversationField";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.busService = useService("bus_service");
        this.rootRef = useRef("root");
        this.state = useState({ html: this.getFieldValue(this.props) });
        this.onNotification = this.onNotification.bind(this);
        this.pendingRefresh = false;

        this.busService.subscribe(NOTIFICATION_TYPE, this.onNotification);

        onWillUpdateProps((nextProps) => {
            this.state.html = this.getFieldValue(nextProps);
        });
        onMounted(() => {
            this.scrollToBottom();
            this.markAsRead();
        });
        onPatched(() => this.scrollToBottom());
        onWillUnmount(() => {
            this.busService.unsubscribe(NOTIFICATION_TYPE, this.onNotification);
        });
    }

    get resId() {
        return this.props.record.resId;
    }

    get markupHtml() {
        return markup(this.state.html || "");
    }

    getFieldValue(props) {
        const value = props.record.data[props.name];
        return value ? String(value) : "";
    }

    async onNotification(payload) {
        if (!this.resId || !payload || payload.chat_id !== this.resId) {
            return;
        }
        await this.refresh();
    }

    async refresh() {
        if (this.pendingRefresh) {
            return;
        }
        this.pendingRefresh = true;
        try {
            const html = await this.orm.call("telegram.chat", "get_conversation_html", [[this.resId]]);
            this.state.html = html || "";
            await this.markAsRead();
        } catch (error) {
            console.warn("telegram_marketing: could not refresh the conversation", error);
        } finally {
            this.pendingRefresh = false;
        }
    }

    async markAsRead() {
        if (!this.resId || !this.props.record.data.unread_count) {
            return;
        }
        try {
            await this.orm.call("telegram.chat", "action_mark_read", [[this.resId]]);
            if (!this.props.record.dirty) {
                await this.props.record.load();
            }
        } catch (error) {
            console.warn("telegram_marketing: could not mark the chat as read", error);
        }
    }

    scrollToBottom() {
        const el = this.rootRef.el;
        if (el) {
            el.scrollTop = el.scrollHeight;
        }
    }
}

export const telegramConversationField = {
    component: TelegramConversationField,
    displayName: "Telegram Conversation",
    supportedTypes: ["html"],
};

registry.category("fields").add("telegram_conversation", telegramConversationField);
