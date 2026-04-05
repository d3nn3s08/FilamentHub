// MQTT Connection Handler - Vollständige Implementation
// Passt zu den IDs in deinem HTML: mqttBroker, mqttPort, mqttClientId, etc.


// Handler-Vereinheitlichung: Nur handleMQTTConnect(), Endpoints vereinheitlicht, IDs bereinigt, Logging und Payload exakt wie gefordert, UI-State nur über Status-GET
(function() {
    'use strict';

    // EINZIGE Connect-Funktion mit Schnellauswahl-Priorisierung
    async function handleMQTTConnect() {
        console.log('🔌 Connect geklickt!');

        const printerId = document.getElementById('mqttPrinterDropdown')?.value;
        let payload = {};
        let mode = 'manual';
        if (printerId && printerId !== '') {
            // PRIORITÄT 1: Schnellauswahl aktiv
            mode = 'printer';
            payload = {
                printer_id: printerId,
                use_printer_config: true
            };
            console.log('📦 Payload (printer):', payload);
        } else {
            // PRIORITÄT 2: Manuelle Felder
            const broker = document.getElementById('mqttBroker')?.value?.trim() || '';
            const port = document.getElementById('mqttPort')?.value?.trim() || '';
            const clientId = document.getElementById('mqttClientId')?.value?.trim() || '';
            const username = document.getElementById('mqttUsername')?.value?.trim() || '';
            const password = document.getElementById('mqttPassword')?.value?.trim() || '';
            const tls = document.getElementById('mqttTls')?.checked || false;
            const protocol = document.getElementById('mqttProtocol')?.value || '311';

            // Validierung
            if (!broker) {
                alert('Broker-Adresse fehlt!');
                return;
            }
            if (!port) {
                alert('Port fehlt!');
                return;
            }
            if (!clientId) {
                alert('Client-ID fehlt!');
                return;
            }

            payload = {
                broker: broker,
                port: Number(port),
                client_id: clientId,
                username: username ? username : null,
                password: password ? password : null,
                tls: !!tls,
                protocol: protocol === '5' ? '5' : '311'
            };
            console.log('📦 Payload (manual):', payload);
        }
        console.log('📡 POST /api/mqtt/runtime/connect');

        // POST an EINEN Endpoint
        try {
            const response = await fetch('/api/mqtt/runtime/connect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            // Nach POST IMMER Status holen
            await refreshMQTTStatus();
        } catch (error) {
            console.error('MQTT Connect Error:', error);
            alert('Fehler beim Verbindungsaufbau: ' + error.message);
        }
    }

    // Disconnect-Funktion (Endpoint vereinheitlicht)
    async function handleMQTTDisconnect() {
        try {
            await fetch('/api/mqtt/runtime/disconnect', { method: 'POST' });
            await refreshMQTTStatus();
        } catch (error) {
            console.error('MQTT Disconnect Error:', error);
            alert('Fehler beim Trennen: ' + error.message);
        }
    }

    // Status-Update Funktion (aktualisiert ALLE Status-Badges konsistent)
    function updateStatus(state, text, detail) {
        // Harte Normalisierung: nur zwei sichtbare Texte erlaubt.
        // state === 'connected' -> '🟢 Verbunden'
        // sonst -> '⚫ Nicht verbunden'
        try {
            const normalizedText = (state === 'connected') ? '🟢 Verbunden' : '⚫ Nicht verbunden';
            const normalizedClass = (state === 'connected') ? 'status-ok' : 'status-error';
            
            // Haupt-Status-Badge (System Status Tab)
            const badge = document.getElementById('mqttStatus');
            if (badge) {
                badge.textContent = normalizedText;
                badge.title = (state === 'connected') ? (detail || 'MQTT verbunden') : (detail || 'Nicht verbunden');
                badge.classList.remove('status-ok', 'status-warn', 'status-error', 'status-idle');
                badge.classList.add(normalizedClass);
            }
            
            // Pro-Mode MQTT Detail Status
            const proMqttStatus = document.getElementById('proMqttStatus');
            if (proMqttStatus) {
                proMqttStatus.textContent = (state === 'connected') ? 'connected' : 'disconnected';
            }

            // Buttons: Connect/Disconnect aktivieren/deaktivieren
            const connectBtn = document.getElementById('mqttConnectBtn');
            const disconnectBtn = document.getElementById('mqttDisconnectBtn');
            if (connectBtn) connectBtn.disabled = (state === 'connected');
            if (disconnectBtn) disconnectBtn.disabled = (state !== 'connected');
            
            console.log('🎯 Status-Badges aktualisiert:', normalizedText);
        } catch (err) {
            console.error('updateStatus error:', err);
        }
    }

    // Topics anzeigen (optional)
    function displayTopics(topics) {
        // ...existing code...
    }

    // Drucker-Dropdown Handler (Schnellauswahl)
    function handlePrinterSelect() {
        // ...existing code...
    }

    // Bambu Topics Button Handler
    async function handleBambuTopics() {
        // ...existing code...
    }

    // Event-Listener Setup
    function setupEventListeners() {
        // Connect Button
        const connectBtn = document.getElementById('mqttConnectBtn');
        if (connectBtn) {
            connectBtn.addEventListener('click', handleMQTTConnect);
        }

        // Disconnect Button
        const disconnectBtn = document.getElementById('mqttDisconnectBtn');
        if (disconnectBtn) {
            disconnectBtn.addEventListener('click', handleMQTTDisconnect);
        }

        // Drucker-Dropdown
        const printerDropdown = document.getElementById('mqttPrinterDropdown');
        if (printerDropdown) {
            printerDropdown.addEventListener('change', handlePrinterSelect);
        }

        // Bambu Topics Button
        const topicsBtn = document.getElementById('mqttTopicsBtn');
        if (topicsBtn) {
            topicsBtn.addEventListener('click', handleBambuTopics);
        }

        // Enter-Taste in Passwort-Feld = Connect
        const passwordInput = document.getElementById('mqttPassword');
        if (passwordInput) {
            passwordInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    handleMQTTConnect();
                }
            });
        }
    }

    // Initialisierung
    function init() {
        setupEventListeners();
        console.log('MQTT Connection Handler initialisiert');
        // Initial-Status setzen
        updateStatus('disconnected', 'Nicht verbunden', 'Bereit zur Verbindung');

    // 🔴 DAS WAR DER FEHLENDE TEIL
    // Status regelmäßig vom Backend holen
        refreshMQTTStatus();                 // sofort einmal
        setInterval(refreshMQTTStatus, 2000); // dann alle 2 Sekunden
    }

    // Bei DOM-Ready initialisieren
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Export für externe Nutzung
    window.MQTTConnectionHandler = {
        connect: handleMQTTConnect,
        disconnect: handleMQTTDisconnect,
        updateStatus: updateStatus,
        refresh: refreshMQTTStatus,
        updateOverview: updateOverviewFields  // NEU: Overview-Update exportieren
    };

    // --- Hilfsfunktion: Status holen und ALLE Overview-Felder aktualisieren ---
async function refreshMQTTStatus() {
    try {
        const response = await fetch('/api/mqtt/runtime/status');
        const data = await response.json();

        if (data && data.connected === true) {
            // Status-Badge aktualisieren
            updateStatus(
                'connected',
                'Verbunden',
                'MQTT verbunden'
            );
            
            // MQTT Overview Felder aktualisieren
            updateOverviewFields({
                connected: true,
                broker: data.broker,
                port: data.port,
                client_id: data.client_id,
                message_count: data.message_count,
                last_message_time: data.last_message_time,
                qos: data.qos,
                uptime: data.uptime,
                connected_since: data.connected_since,
                subscriptions_count: data.subscriptions_count || data.topics_count
            });
            
            // Setze globale Variablen für Topics-Polling
            if (typeof window._mqttLastConnected !== 'undefined') {
                window._mqttLastConnected = true;
            } else {
                window._mqttLastConnected = true; // Erstelle falls nicht vorhanden
            }
            
            // Start Topics & Messages Polling when connected
            if (typeof window._syncTopicsPolling === 'function') {
                window._syncTopicsPolling();
            }
            if (typeof window._syncMessagesPolling === 'function') {
                window._syncMessagesPolling();
            }
            if (typeof window._syncDetailsPoll === 'function') {
                window._syncDetailsPoll();
            }
            
            // Trigger Topics-Refresh wenn Tab aktiv
            if (typeof window.refreshMQTTTopics === 'function') {
                // Prüfe ob MQTT-Tab aktiv ist
                const mqttPanel = document.getElementById('panel-mqtt');
                const isMqttTabActive = mqttPanel && mqttPanel.style.display !== 'none';
                
                if (isMqttTabActive || window._mqttTabActive === true) {
                    window.refreshMQTTTopics().catch(() => {});
                }
            }
        } else {
            // Getrennt
            updateStatus(
                'disconnected',
                'Nicht verbunden',
                'Bereit zur Verbindung'
            );
            
            // Overview-Felder zurücksetzen
            updateOverviewFields({ connected: false });
            
            // Setze globale Variable
            if (typeof window._mqttLastConnected !== 'undefined') {
                window._mqttLastConnected = false;
            } else {
                window._mqttLastConnected = false;
            }
            
            // Stop Topics & Messages Polling when disconnected
            if (typeof window._syncTopicsPolling === 'function') {
                window._syncTopicsPolling();
            }
            if (typeof window._syncMessagesPolling === 'function') {
                window._syncMessagesPolling();
            }
            if (typeof window._syncDetailsPoll === 'function') {
                window._syncDetailsPoll();
            }
        }
    } catch (error) {
        console.error('Fehler beim Status-Refresh:', error);
        updateStatus(
            'disconnected',
            'Nicht verbunden',
            'Status nicht erreichbar'
        );
        updateOverviewFields({ connected: false });
        
        if (typeof window._mqttLastConnected !== 'undefined') {
            window._mqttLastConnected = false;
        } else {
            window._mqttLastConnected = false;
        }
    }
}

// --- Neue Funktion: Overview-Felder aktualisieren ---
function updateOverviewFields({ connected, broker, port, client_id, message_count, last_message_time, qos, uptime, connected_since, subscriptions_count }) {
    // MQTT Overview Status Badge (im MQTT Tab)
    const statusBadge = document.getElementById('mqttStatusBadge');
    if (statusBadge) {
        if (connected) {
            statusBadge.textContent = 'Verbunden';
            statusBadge.className = 'status-badge status-ok';
        } else {
            statusBadge.textContent = 'Nicht verbunden';
            statusBadge.className = 'status-badge status-error';
        }
    }
    
    // Broker
    const brokerValue = document.getElementById('mqttBrokerValue');
    if (brokerValue) {
        brokerValue.textContent = connected && broker && port 
            ? `${broker}:${port}` 
            : '-';
    }
    
    // Client ID
    const clientIdValue = document.getElementById('mqttClientIdValue');
    if (clientIdValue) {
        clientIdValue.textContent = connected && client_id ? client_id : '-';
    }
    
    // Subscriptions Count (NEU)
    const subsCount = document.getElementById('mqttSubscriptionsCount');
    if (subsCount) {
        subsCount.textContent = connected && subscriptions_count !== undefined 
            ? String(subscriptions_count) 
            : '-';
    }
    
    // Nachrichten empfangen
    const msgCount = document.getElementById('mqttMsgCount');
    if (msgCount) {
        msgCount.textContent = connected && message_count !== undefined 
            ? String(message_count) 
            : '-';
    }
    
    // Letzte Nachricht
    const lastMsgTime = document.getElementById('mqttLastMsgTime');
    if (lastMsgTime) {
        lastMsgTime.textContent = connected && last_message_time 
            ? last_message_time 
            : '-';
    }
    
    // QoS Level
    const qosEl = document.getElementById('mqttQos');
    if (qosEl) {
        qosEl.textContent = connected && qos !== undefined 
            ? String(qos) 
            : '-';
    }
    
    // Verbindungsdauer
    const uptimeEl = document.getElementById('mqttUptime');
    if (uptimeEl) {
        if (connected) {
            if (uptime) {
                uptimeEl.textContent = uptime;
            } else if (connected_since) {
                uptimeEl.textContent = `seit ${connected_since}`;
            } else {
                uptimeEl.textContent = '-';
            }
        } else {
            uptimeEl.textContent = '-';
        }
    }
    
    // Pro-Mode Connection Badge
    const connBadge = document.getElementById('mqttConnBadge');
    if (connBadge) {
        if (connected) {
            connBadge.textContent = 'Verbunden';
            connBadge.className = 'status-badge status-ok';
        } else {
            connBadge.textContent = 'Nicht verbunden';
            connBadge.className = 'status-badge status-error';
        }
    }
    
    // Pro-Mode Connection Dot
    const connDot = document.getElementById('mqttConnDot');
    if (connDot) {
        connDot.classList.remove('dot-ok', 'dot-error', 'dot-idle');
        connDot.classList.add(connected ? 'dot-ok' : 'dot-idle');
    }
    
    // Pro-Mode Status Text
    const connText = document.getElementById('mqttConnText');
    if (connText) {
        if (connected && broker && port) {
            const detail = `Verbunden mit ${broker}:${port}`;
            const since = connected_since ? ` (seit ${connected_since})` : '';
            connText.textContent = detail + since;
        } else {
            connText.textContent = 'Nicht verbunden';
        }
    }
    
    console.log('📊 Overview-Felder aktualisiert:', { 
        connected, broker, port, client_id, 
        message_count, subscriptions_count, 
        last_message_time, qos 
    });
}


})();
