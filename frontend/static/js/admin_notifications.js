let notificationsConfig = [];
let selectedNotificationId = null;

async function loadNotifications() {
    try {
        const res = await fetch("/api/notifications-config");
        const data = await res.json();
        notificationsConfig = data.notifications || [];
        if (!selectedNotificationId && notificationsConfig.length) {
            selectedNotificationId = notificationsConfig[0].id;
        }
        renderList();
        const current = notificationsConfig.find((n) => n.id === selectedNotificationId) || notificationsConfig[0];
        if (current) fillForm(current);
    } catch (err) {
        console.error("Konnte Notifications nicht laden", err);
    }
}

function fillForm(notification) {
    document.getElementById("notif-id").value = notification.id || "";
    document.getElementById("notif-label").value = notification.label || "";
    document.getElementById("notif-message").value = notification.message || "";
    document.getElementById("notif-type").value = notification.type || "info";
    document.getElementById("notif-enabled").checked = notification.enabled !== false;
    document.getElementById("notif-persistent").checked = Boolean(notification.persistent);
    selectedNotificationId = notification.id;
}

function readForm() {
    return {
        id: document.getElementById("notif-id").value.trim(),
        label: document.getElementById("notif-label").value.trim(),
        message: document.getElementById("notif-message").value.trim(),
        type: document.getElementById("notif-type").value,
        persistent: document.getElementById("notif-persistent").checked,
        enabled: document.getElementById("notif-enabled").checked,
    };
}

async function saveNotification() {
    const data = readForm();
    if (!data.id || !data.message) {
        alert("ID und Nachricht sind Pflichtfelder.");
        return;
    }
    const idx = notificationsConfig.findIndex((n) => n.id === data.id);
    if (idx >= 0) {
        notificationsConfig[idx] = data;
    } else {
        notificationsConfig.push(data);
    }
    selectedNotificationId = data.id;
    await persistConfig();
    renderList();
    if (window.renderPersistentAlerts) {
        renderPersistentAlerts();
    }
}

async function deleteNotification(id) {
    notificationsConfig = notificationsConfig.filter((n) => n.id !== id);
    if (selectedNotificationId === id) {
        selectedNotificationId = notificationsConfig[0]?.id || null;
        if (notificationsConfig[0]) fillForm(notificationsConfig[0]);
    }
    await persistConfig();
    renderList();
}

async function persistConfig() {
    try {
        await fetch("/api/notifications-config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ notifications: notificationsConfig }),
        });
    } catch (err) {
        console.error("Konnte Notifications nicht speichern", err);
    }
}

async function triggerNotification(id) {
    const targetId = id || readForm().id;
    if (!targetId) return;
    try {
        await fetch("/api/notifications-trigger", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id: targetId }),
        });
        if (typeof window.triggerAlert === "function") {
            const notification = notificationsConfig.find((n) => n.id === targetId);
            if (notification && notification.enabled !== false) {
                window.triggerAlert(notification);
            }
        }
    } catch (err) {
        console.error("Trigger fehlgeschlagen", err);
    }
}

function testNotification() {
    const data = readForm();
    if (!data.id || !data.message) {
        alert("ID und Nachricht sind Pflichtfelder.");
        return;
    }
    if (typeof window.triggerAlert === "function") {
        window.triggerAlert({ ...data, enabled: true });
    }
}

function renderList() {
    const container = document.getElementById("notification-list");
    container.innerHTML = "";
    if (!notificationsConfig.length) {
        const empty = document.createElement("div");
        empty.style.color = "var(--text-dim)";
        empty.textContent = "Keine Notifications vorhanden.";
        container.appendChild(empty);
        return;
    }
    notificationsConfig.forEach((n) => {
        const item = document.createElement("div");
        item.className = "notif-item";
        item.addEventListener("click", () => fillForm(n));

        const header = document.createElement("div");
        header.className = "notif-item-header";
        
        const id = document.createElement("div");
        id.className = "notif-item-id";
        id.textContent = n.id;
        
        const type = document.createElement("div");
        type.className = "notif-item-type";
        type.textContent = n.type || "info";
        
        header.appendChild(id);
        header.appendChild(type);

        const label = document.createElement("div");
        label.className = "notif-item-label";
        label.textContent = n.label || n.id;

        const msg = document.createElement("div");
        msg.className = "notif-item-msg";
        msg.textContent = n.message;

        const meta = document.createElement("div");
        meta.className = "notif-item-meta";
        meta.textContent = `${n.enabled !== false ? "Aktiv" : "Inaktiv"} · ${n.persistent ? "Persistent" : "Transient"}`;

        const actions = document.createElement("div");
        actions.className = "notif-item-actions";

        const btnEdit = document.createElement("button");
        btnEdit.textContent = "✏️ Bearbeiten";
        btnEdit.addEventListener("click", (e) => {
            e.stopPropagation();
            fillForm(n);
        });

        const btnDelete = document.createElement("button");
        btnDelete.textContent = "🗑️ Löschen";
        btnDelete.addEventListener("click", async (e) => {
            e.stopPropagation();
            await deleteNotification(n.id);
        });

        const btnTrigger = document.createElement("button");
        btnTrigger.textContent = "⚡ Triggern";
        btnTrigger.addEventListener("click", async (e) => {
            e.stopPropagation();
            await triggerNotification(n.id);
        });

        actions.appendChild(btnEdit);
        actions.appendChild(btnDelete);
        actions.appendChild(btnTrigger);

        item.appendChild(header);
        item.appendChild(label);
        item.appendChild(msg);
        item.appendChild(meta);
        item.appendChild(actions);
        container.appendChild(item);
    });
}

// Neue Funktion zum Triggern mit Auswahl
async function triggerSelectedNotification() {
    const notifId = document.getElementById("notif-id").value.trim();
    const triggerType = document.getElementById("notif-trigger").value;
    if (!notifId) {
        alert("Bitte zuerst eine Notification auswählen oder anlegen.");
        return;
    }
    try {
        await fetch("/api/notifications-trigger", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id: notifId, trigger: triggerType })
        });
        if (typeof window.triggerAlert === "function") {
            const notification = notificationsConfig.find((n) => n.id === notifId);
            if (notification && notification.enabled !== false) {
                window.triggerAlert(notification);
            }
        }
    } catch (err) {
        console.error("Trigger fehlgeschlagen", err);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    loadNotifications();
    document.getElementById("btn-save").addEventListener("click", saveNotification);
    document.getElementById("btn-test").addEventListener("click", testNotification);
    document.getElementById("btn-trigger").addEventListener("click", triggerSelectedNotification);
});
