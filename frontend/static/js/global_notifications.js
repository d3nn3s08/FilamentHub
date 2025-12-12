(function () {
    const state = {
        config: [],
        socket: null,
        reconnectTimer: null,
        alertRoot: null,
    };

    function getAlertRoot() {
        if (!state.alertRoot) {
            state.alertRoot = document.getElementById("alert-root");
        }
        return state.alertRoot;
    }

    async function loadNotifications() {
        try {
            const res = await fetch("/api/notifications-config");
            if (!res.ok) throw new Error("Config Load failed");
            const data = await res.json();
            state.config = data.notifications || [];
            // KEIN automatisches Anzeigen persistenter Alerts mehr!
        } catch (err) {
            console.error("Notifications konnten nicht geladen werden:", err);
        }
    }

    function findNotificationById(id) {
        return state.config.find((n) => n.id === id);
    }

    function createAlertElement(notification) {
        const root = getAlertRoot();
        if (!root) return null;

        const wrapper = document.createElement("div");
        wrapper.className = `alert alert--${notification.type || "info"}`;
        wrapper.dataset.id = notification.id || "";
        if (notification.persistent) wrapper.dataset.persistent = "true";

        const content = document.createElement("div");
        content.className = "alert__content";

        const title = document.createElement("div");
        title.className = "alert__title";
        title.textContent = notification.label || notification.id || "Notification";

        const message = document.createElement("div");
        message.className = "alert__message";
        message.textContent = notification.message || "";

        const closeBtn = document.createElement("button");
        closeBtn.className = "alert__close";
        closeBtn.type = "button";
        closeBtn.innerText = "×";
        closeBtn.addEventListener("click", () => closeAlert(wrapper));

        content.appendChild(title);
        content.appendChild(message);
        wrapper.appendChild(content);
        wrapper.appendChild(closeBtn);
        return wrapper;
    }

    function triggerAlert(notification) {
        const root = getAlertRoot();
        if (!root) return;

        let resolved = notification;
        if (typeof notification === "string") {
            resolved = findNotificationById(notification);
        }
        if (!resolved) return;
        if (resolved.enabled === false) return;

        const existing = root.querySelector(`.alert[data-id="${resolved.id}"]`);
        if (existing && resolved.persistent) {
            return;
        }

        const alertEl = createAlertElement(resolved);
        if (!alertEl) return;
        root.appendChild(alertEl);

        if (!resolved.persistent) {
            setTimeout(() => closeAlert(alertEl), 6500);
        }
    }

    function renderPersistentAlerts() {
        const root = getAlertRoot();
        if (!root) return;
        root.querySelectorAll('.alert[data-persistent="true"]').forEach((el) => el.remove());
        state.config
            .filter((n) => n.enabled !== false && n.persistent)
            .forEach((n) => triggerAlert(n));
    }

    function closeAlert(element) {
        if (!element) return;
        element.classList.add("alert--closing");
        setTimeout(() => element.remove(), 180);
    }

    function handleSocketMessage(event) {
        try {
            const data = JSON.parse(event.data);
            if (data && data.event === "notification_trigger" && data.payload) {
                triggerAlert(data.payload);
            }
        } catch (err) {
            console.error("WebSocket payload ungültig:", err);
        }
    }

    function connectSocket() {
        const protocol = window.location.protocol === "https:" ? "wss" : "ws";
        const wsUrl = `${protocol}://${window.location.host}/api/notifications/ws`;
        try {
            state.socket = new WebSocket(wsUrl);
            state.socket.onmessage = handleSocketMessage;
            state.socket.onclose = () => {
                if (state.reconnectTimer) clearTimeout(state.reconnectTimer);
                state.reconnectTimer = setTimeout(connectSocket, 2000);
            };
            state.socket.onerror = () => {
                try {
                    state.socket.close();
                } catch (e) {
                    console.error("WebSocket close error", e);
                }
            };
        } catch (err) {
            console.error("WebSocket konnte nicht geöffnet werden:", err);
            if (state.reconnectTimer) clearTimeout(state.reconnectTimer);
            state.reconnectTimer = setTimeout(connectSocket, 3000);
        }
    }


    document.addEventListener("DOMContentLoaded", () => {
        loadNotifications();
        // WebSocket nur im Admin-Panel verbinden
        if (window.location.pathname.startsWith("/admin/notifications")) {
            connectSocket();
        }
    });

    window.loadNotifications = loadNotifications;
    window.triggerAlert = triggerAlert;
    window.renderPersistentAlerts = renderPersistentAlerts;
    window.closeAlert = closeAlert;
})();
