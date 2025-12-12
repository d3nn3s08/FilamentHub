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
        empty.className = "panel";
        empty.textContent = "Keine Notifications vorhanden.";
        container.appendChild(empty);
        return;
    }
    notificationsConfig.forEach((n) => {
        const card = document.createElement("div");
        card.className = "panel";
        card.style.cursor = "pointer";
        card.addEventListener("click", () => fillForm(n));

        const title = document.createElement("div");
        title.className = "eyebrow";
        title.textContent = n.id;

        const label = document.createElement("h4");
        label.style.margin = "6px 0";
        label.textContent = n.label || n.id;

        const msg = document.createElement("p");
        msg.className = "subtitle";
        msg.textContent = n.message;

        const meta = document.createElement("div");
        meta.style.display = "flex";
        meta.style.gap = "8px";
        meta.style.alignItems = "center";
        const badge = document.createElement("span");
        badge.className = "btn ghost";
        badge.style.padding = "6px 10px";
        badge.textContent = n.type || "info";
        const persistent = document.createElement("span");
        persistent.className = "subtitle";
        persistent.textContent = `${n.enabled !== false ? "Aktiv" : "Inaktiv"} · ${n.persistent ? "Persistent" : "Transient"}`;
        meta.appendChild(badge);
        meta.appendChild(persistent);

        const actions = document.createElement("div");
        actions.className = "actions";
        actions.style.marginTop = "10px";

        const btnEdit = document.createElement("button");
        btnEdit.className = "btn ghost";
        btnEdit.type = "button";
        btnEdit.textContent = "Bearbeiten";
        btnEdit.addEventListener("click", (e) => {
            e.stopPropagation();
            fillForm(n);
        });

        const btnDelete = document.createElement("button");
        btnDelete.className = "btn ghost";
        btnDelete.type = "button";
        btnDelete.textContent = "Löschen";
        btnDelete.addEventListener("click", async (e) => {
            e.stopPropagation();
            await deleteNotification(n.id);
        });

        const btnTrigger = document.createElement("button");
        btnTrigger.className = "btn primary";
        btnTrigger.type = "button";
        btnTrigger.textContent = "Triggern";
        btnTrigger.addEventListener("click", async (e) => {
            e.stopPropagation();
            await triggerNotification(n.id);
        });

        actions.appendChild(btnEdit);
        actions.appendChild(btnDelete);
        actions.appendChild(btnTrigger);

        card.appendChild(title);
        card.appendChild(label);
        card.appendChild(msg);
        card.appendChild(meta);
        card.appendChild(actions);
        container.appendChild(card);
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
