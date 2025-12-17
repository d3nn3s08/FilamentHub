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

    // Status-Update Funktion (wird nicht mehr direkt für Connect verwendet)
    function updateStatus(state, text, detail) {
        // Harte Normalisierung: nur zwei sichtbare Texte erlaubt.
        // state === 'connected' -> '🟢 Verbunden'
        // sonst -> '⚫ Nicht verbunden'
        try {
            const badge = document.getElementById('mqttStatus');
            const normalizedText = (state === 'connected') ? '🟢 Verbunden' : '⚫ Nicht verbunden';
            if (badge) {
                // Setze nur den normalisierten Text und Title
                badge.textContent = normalizedText;
                badge.title = (state === 'connected') ? (detail || 'MQTT verbunden') : (detail || 'Nicht verbunden');
                // Klassen: nur eine der status-* Klassen
                badge.classList.remove('status-ok', 'status-warn', 'status-error', 'status-idle');
                if (state === 'connected') {
                    badge.classList.add('status-ok');
                } else {
                    badge.classList.add('status-error');
                }
            }

            // Buttons: Connect/Disconnect aktivieren/deaktivieren
            const connectBtn = document.getElementById('mqttConnectBtn');
            const disconnectBtn = document.getElementById('mqttDisconnectBtn');
            if (connectBtn) connectBtn.disabled = (state === 'connected');
            if (disconnectBtn) disconnectBtn.disabled = (state !== 'connected');
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
        refresh: refreshMQTTStatus
    };

    // --- Hilfsfunktion: Status holen ---
async function refreshMQTTStatus() {
    try {
        const response = await fetch('/api/mqtt/runtime/status');
        const data = await response.json();

        if (data && data.connected === true) {
            updateStatus(
                'connected',
                'Verbunden',
                'MQTT verbunden'
            );
        } else {
            updateStatus(
                'disconnected',
                'Nicht verbunden',
                'Bereit zur Verbindung'
            );
        }
    } catch (error) {
        console.error('Fehler beim Status-Refresh:', error);
        updateStatus(
            'disconnected',
            'Nicht verbunden',
            'Status nicht erreichbar'
        );
    }
}


})();
