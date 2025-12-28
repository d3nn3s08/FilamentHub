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
    document.getElementById("notif-trigger").value = notification.trigger?.type || "manual";
    document.getElementById("notif-enabled").checked = notification.enabled !== false;
    document.getElementById("notif-persistent").checked = Boolean(notification.persistent);

    // Webhook fields
    document.getElementById("notif-webhook-url").value = notification.webhook?.url || "";
    document.getElementById("notif-webhook-type").value = notification.webhook?.type || "";
    document.getElementById("notif-webhook-username").value = notification.webhook?.username || "";

    // Update trigger section visibility
    updateTriggerSection();

    // Trigger conditions based on trigger type
    const triggerType = notification.trigger?.type;
    if (triggerType && notification.trigger?.condition) {
        const condition = notification.trigger.condition;

        if (triggerType === 'temperature') {
            document.getElementById("temp-operator").value = condition.operator || ">";
            document.getElementById("temp-value").value = condition.value || "";
        } else if (triggerType === 'humidity') {
            document.getElementById("humidity-operator").value = condition.operator || ">";
            document.getElementById("humidity-value").value = condition.value || "";
        } else if (triggerType === 'print_time') {
            document.getElementById("printtime-operator").value = condition.operator || ">";
            document.getElementById("printtime-value").value = condition.value || "";
        } else if (triggerType === 'filament_weight') {
            document.getElementById("filament-operator").value = condition.operator || "<";
            document.getElementById("filament-value").value = condition.value || "";
        } else if (triggerType === 'custom') {
            document.getElementById("custom-condition-code").value = condition.code || "";
        }
    }

    selectedNotificationId = notification.id;
}

function readForm() {
    const data = {
        id: document.getElementById("notif-id").value.trim(),
        label: document.getElementById("notif-label").value.trim(),
        message: document.getElementById("notif-message").value.trim(),
        type: document.getElementById("notif-type").value,
        persistent: document.getElementById("notif-persistent").checked,
        enabled: document.getElementById("notif-enabled").checked,
    };

    // Webhook configuration
    const webhookUrl = document.getElementById("notif-webhook-url").value.trim();
    const webhookType = document.getElementById("notif-webhook-type").value;
    if (webhookUrl && webhookType) {
        data.webhook = {
            url: webhookUrl,
            type: webhookType,
            username: document.getElementById("notif-webhook-username").value.trim() || "FilamentHub Bot"
        };
    }

    // Trigger configuration
    const triggerType = document.getElementById("notif-trigger").value;
    data.trigger = { type: triggerType };

    // Add condition based on trigger type
    if (triggerType === 'temperature') {
        data.trigger.condition = {
            type: 'temperature',
            operator: document.getElementById("temp-operator").value,
            value: parseFloat(document.getElementById("temp-value").value) || 0
        };
    } else if (triggerType === 'humidity') {
        data.trigger.condition = {
            type: 'humidity',
            operator: document.getElementById("humidity-operator").value,
            value: parseFloat(document.getElementById("humidity-value").value) || 0
        };
    } else if (triggerType === 'print_time') {
        data.trigger.condition = {
            type: 'print_time',
            operator: document.getElementById("printtime-operator").value,
            value: parseFloat(document.getElementById("printtime-value").value) || 0
        };
    } else if (triggerType === 'filament_weight') {
        data.trigger.condition = {
            type: 'filament_weight',
            operator: document.getElementById("filament-operator").value,
            value: parseFloat(document.getElementById("filament-value").value) || 0
        };
    } else if (triggerType === 'custom') {
        data.trigger.condition = {
            type: 'custom',
            code: document.getElementById("custom-condition-code").value.trim()
        };
    }

    return data;
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
    const container = document.getElementById("notification-cards-container");
    container.innerHTML = "";

    if (!notificationsConfig.length) {
        container.innerHTML = `
            <div class="notif-empty-state">
                <svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                    <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
                    <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
                </svg>
                <h3>Keine Benachrichtigungen</h3>
                <p>Erstelle deine erste Benachrichtigung mit dem Button oben</p>
            </div>
        `;
        return;
    }

    notificationsConfig.forEach((n) => {
        const card = document.createElement("div");
        card.className = `notif-card ${n.enabled === false ? 'inactive' : ''}`;

        const typeEmoji = {
            success: '✓',
            warn: '⚠️',
            error: '✕',
            info: 'ℹ️'
        }[n.type] || 'ℹ️';

        card.innerHTML = `
            <div class="notif-card-header">
                <div class="notif-card-id">${n.id}</div>
                <div class="notif-card-type-badge ${n.type || 'info'}">
                    ${typeEmoji} ${n.type || 'info'}
                </div>
            </div>
            <div class="notif-card-label">${n.label || n.id}</div>
            <div class="notif-card-message">${n.message}</div>
            <div class="notif-card-meta">
                <div class="notif-card-meta-item">
                    <span>${n.enabled !== false ? '🟢' : '⚫'}</span>
                    <span>${n.enabled !== false ? 'Aktiv' : 'Inaktiv'}</span>
                </div>
                <div class="notif-card-meta-item">
                    <span>${n.persistent ? '📌' : '⏱️'}</span>
                    <span>${n.persistent ? 'Persistent' : 'Temporär'}</span>
                </div>
            </div>
            <div class="notif-card-actions">
                <button class="notif-card-btn" onclick="editNotification('${n.id}')">✏️ Bearbeiten</button>
                <button class="notif-card-btn" onclick="triggerNotification('${n.id}')">⚡ Triggern</button>
                <button class="notif-card-btn danger" onclick="confirmDeleteNotification('${n.id}')">🗑️ Löschen</button>
            </div>
        `;

        container.appendChild(card);
    });
}

function openNotifModal(title = 'Neue Benachrichtigung') {
    document.getElementById('notif-modal-title').textContent = title;
    document.getElementById('notif-edit-modal').classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeNotifModal() {
    document.getElementById('notif-edit-modal').classList.remove('active');
    document.body.style.overflow = 'auto';
}

function editNotification(id) {
    const notification = notificationsConfig.find(n => n.id === id);
    if (notification) {
        fillForm(notification);
        openNotifModal('Benachrichtigung bearbeiten');
    }
}

function confirmDeleteNotification(id) {
    if (confirm(`Benachrichtigung "${id}" wirklich löschen?`)) {
        deleteNotification(id);
    }
}

function createNewNotification() {
    // Reset form
    document.getElementById('notif-id').value = '';
    document.getElementById('notif-label').value = '';
    document.getElementById('notif-message').value = '';
    document.getElementById('notif-type').value = 'info';
    document.getElementById('notif-trigger').value = 'manual';
    document.getElementById('notif-enabled').checked = true;
    document.getElementById('notif-persistent').checked = false;

    // Reset webhook fields
    document.getElementById('notif-webhook-url').value = '';
    document.getElementById('notif-webhook-type').value = '';
    document.getElementById('notif-webhook-username').value = '';

    // Reset all condition fields
    document.getElementById('temp-operator').value = '>';
    document.getElementById('temp-value').value = '';
    document.getElementById('humidity-operator').value = '>';
    document.getElementById('humidity-value').value = '';
    document.getElementById('printtime-operator').value = '>';
    document.getElementById('printtime-value').value = '';
    document.getElementById('filament-operator').value = '<';
    document.getElementById('filament-value').value = '';
    document.getElementById('custom-condition-code').value = '';

    // Hide trigger section
    updateTriggerSection();

    selectedNotificationId = null;
    openNotifModal('Neue Benachrichtigung');
}

// Update visibility of trigger conditions section based on trigger type
function updateTriggerSection() {
    const triggerType = document.getElementById('notif-trigger').value;
    const triggerSection = document.getElementById('trigger-conditions-section');

    // Hide all condition configs first
    document.querySelectorAll('.condition-config').forEach(el => {
        el.style.display = 'none';
    });

    // Show trigger section and relevant condition based on trigger type
    if (triggerType === 'temperature') {
        triggerSection.style.display = 'block';
        document.getElementById('condition-temperature').style.display = 'block';
    } else if (triggerType === 'humidity') {
        triggerSection.style.display = 'block';
        document.getElementById('condition-humidity').style.display = 'block';
    } else if (triggerType === 'print_time') {
        triggerSection.style.display = 'block';
        document.getElementById('condition-print_time').style.display = 'block';
    } else if (triggerType === 'filament_weight') {
        triggerSection.style.display = 'block';
        document.getElementById('condition-filament_weight').style.display = 'block';
    } else if (triggerType === 'custom') {
        triggerSection.style.display = 'block';
        document.getElementById('condition-custom').style.display = 'block';
    } else {
        // Hide trigger section for manual, print_done, error, material_low
        triggerSection.style.display = 'none';
    }
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

    // Modal buttons
    document.getElementById("btn-save").addEventListener("click", async () => {
        await saveNotification();
        closeNotifModal();
    });
    document.getElementById("btn-test").addEventListener("click", testNotification);

    // New notification button
    const btnNew = document.getElementById("btn-new-notification");
    if (btnNew) {
        btnNew.addEventListener("click", createNewNotification);
    }

    // Trigger type change handler
    const triggerSelect = document.getElementById("notif-trigger");
    if (triggerSelect) {
        triggerSelect.addEventListener("change", updateTriggerSection);
    }

    // ESC key closes modal
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeNotifModal();
        }
    });
});
