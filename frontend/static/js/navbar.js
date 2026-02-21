document.addEventListener("DOMContentLoaded", () => {
    highlightActiveNav();
    initUserMenu();
});

function highlightActiveNav() {
    const active = document.body.dataset.activePage;
    document.querySelectorAll(".sidebar__nav .nav__item").forEach(link => {
        if (!active) return;
        if (active === "dashboard" && link.getAttribute("href") === "/") {
            link.classList.add("nav__item--active");
        } else if (link.getAttribute("href")?.includes(`/${active}`)) {
            link.classList.add("nav__item--active");
        }
    });
}

async function fetchSettings() {
    try {
        const res = await fetch("/api/settings");
        if (!res.ok) throw new Error("fetch settings failed");
        return await res.json();
    } catch (e) {
        console.warn("Settings fetch failed", e);
        return { ams_mode: "single", debug_ws_logging: false };
    }
}

async function updateSetting(partial) {
    try {
        const res = await fetch("/api/settings", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(partial),
        });
        if (!res.ok) throw new Error("update failed");
        return await res.json();
    } catch (e) {
        console.warn("Settings update failed", e);
        return null;
    }
}

function initUserMenu() {
    const menu = document.querySelector(".user-menu");
    if (!menu) return;
    const trigger = menu.querySelector(".user-menu__trigger");
    const dropdown = menu.querySelector(".user-menu__dropdown");
    const themeToggle = menu.querySelector('[data-action="theme-toggle"]');
    const about = menu.querySelector('[data-action="about"]');
    const settingsBtn = menu.querySelector('[data-action="settings"]');
    const amsRadios = menu.querySelectorAll('input[name="ams_mode"][data-setting="ams_mode"]');

    const settingsModal = document.getElementById("settingsModal");
    const settingsSaveBtn = document.getElementById("settingsSaveBtn");
    const settingsElectricityPrice = document.getElementById("settingsElectricityPrice");
    const settingsClosers = document.querySelectorAll('[data-close-settings]');

    // Settings Tab Elements
    const settingsTabs = document.querySelectorAll('.settings-tab');
    const settingsTabContents = document.querySelectorAll('.settings-tab-content');
    const settingsThemeLight = document.getElementById('settingsThemeLight');
    const settingsLanguage = document.getElementById('settingsLanguage');
    const settingsBambuUsername = document.getElementById('settingsBambuUsername');
    const settingsBambuPassword = document.getElementById('settingsBambuPassword');
    const settingsBambuRegion = document.getElementById('settingsBambuRegion');
    const settingsBambuTestConnection = document.getElementById('settingsBambuTestConnection');
    const bambuConnectionStatus = document.getElementById('bambuConnectionStatus');
    const settingsDebugWsLogging = document.getElementById('settingsDebugWsLogging');
    const settingsExperimentalMode = document.getElementById('settingsExperimentalMode');
    const settingsClearCache = document.getElementById('settingsClearCache');

    // Experimental Tab Elements
    const settings3mfTitleMatching = document.getElementById('settings3mfTitleMatching');
    const settings3mfScoreThreshold = document.getElementById('settings3mfScoreThreshold');
    const settingsFileSelectionDialog = document.getElementById('settingsFileSelectionDialog');
    const settingsMultiColorTracking = document.getElementById('settingsMultiColorTracking');
    const settingsFtpGcodeDownload = document.getElementById('settingsFtpGcodeDownload');
    const experimentalDisabledWarning = document.getElementById('experimentalDisabledWarning');

    // AMS Tab Elements
    const settingsAmsConflictEnabled = document.getElementById('settingsAmsConflictEnabled');
    const settingsAmsConflictTolerance = document.getElementById('settingsAmsConflictTolerance');

    // Backup Tab Elements
    const settingsBackupCreateBtn = document.getElementById('settingsBackupCreateBtn');
    const settingsBackupStatus = document.getElementById('settingsBackupStatus');
    const settingsBackupList = document.getElementById('settingsBackupList');
    const settingsBackupRefreshBtn = document.getElementById('settingsBackupRefreshBtn');
    const settingsBackupUploadBtn = document.getElementById('settingsBackupUploadBtn');
    const settingsBackupUploadInput = document.getElementById('settingsBackupUploadInput');

    // Restore theme on load
    const stored = localStorage.getItem("fh_theme");
    if (stored === "light") {
        document.body.classList.add("theme-light");
    }

    const closeAll = () => dropdown.classList.remove("open");

    const toggleMenu = (evt) => {
        evt.stopPropagation();
        dropdown.classList.toggle("open");
        trigger.setAttribute("aria-expanded", dropdown.classList.contains("open"));
    };

    trigger?.addEventListener("click", toggleMenu);
    trigger?.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            toggleMenu(e);
        } else if (e.key === "Escape") {
            closeAll();
            trigger.focus();
        }
    });

    document.addEventListener("click", (e) => {
        if (!menu.contains(e.target)) closeAll();
    });

    about?.addEventListener("click", () => {
        alert("FilamentHub – lokale Instance. Weitere Infos folgen.");
        closeAll();
    });

    const closeSettings = () => {
        if (!settingsModal) return;
        // Move focus away before hiding (fixes aria-hidden warning)
        if (settingsModal.contains(document.activeElement)) {
            document.activeElement.blur();
        }
        settingsModal.classList.remove("show");
        settingsModal.setAttribute("aria-hidden", "true");
    };

    // Tab Switching Logic
    const switchSettingsTab = (tabName) => {
        settingsTabs.forEach(tab => {
            const isActive = tab.dataset.tab === tabName;
            tab.classList.toggle('active', isActive);
            if (isActive) {
                tab.style.background = 'rgba(46,134,222,0.2)';
                tab.style.borderColor = 'rgba(46,134,222,0.4)';
                tab.style.color = '#fff';
            } else {
                tab.style.background = 'rgba(255,255,255,0.05)';
                tab.style.borderColor = 'rgba(255,255,255,0.1)';
                tab.style.color = 'rgba(255,255,255,0.7)';
            }
        });
        settingsTabContents.forEach(content => {
            content.style.display = content.dataset.content === tabName ? 'block' : 'none';
        });
    };

    settingsTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            switchSettingsTab(tab.dataset.tab);
        });
    });

    // Update Experimental Tab based on experimental_mode
    const updateExperimentalTabState = (experimentalModeEnabled) => {
        const experimentalInputs = [
            settings3mfTitleMatching,
            settings3mfScoreThreshold,
            settingsFileSelectionDialog,
            settingsMultiColorTracking,
            settingsFtpGcodeDownload,
            settingsAmsConflictEnabled,
            settingsAmsConflictTolerance
        ];

        experimentalInputs.forEach(input => {
            if (input) {
                input.disabled = !experimentalModeEnabled;
                input.style.opacity = experimentalModeEnabled ? '1' : '0.5';
                if (input.parentElement) {
                    input.parentElement.style.cursor = experimentalModeEnabled ? 'pointer' : 'not-allowed';
                }
            }
        });

        // Show/hide warning
        if (experimentalDisabledWarning) {
            experimentalDisabledWarning.style.display = experimentalModeEnabled ? 'none' : 'block';
        }
    };

    const openSettings = async () => {
        dropdown.classList.remove("open");
        if (!settingsModal) return;
        try {
            const settings = await fetchSettings();

            // Load Electricity Price
            if (settingsElectricityPrice) {
                const price = parseFloat(settings?.["cost.electricity_price_kwh"] ?? settings?.electricity_price_kwh);
                settingsElectricityPrice.value = Number.isFinite(price) ? price : "";
            }

            // Load Theme Setting
            if (settingsThemeLight) {
                const theme = localStorage.getItem("fh_theme");
                settingsThemeLight.checked = theme === "light";
            }

            // Load Language (placeholder for now)
            if (settingsLanguage) {
                settingsLanguage.value = settings?.language || "de";
            }

            // Load Bambu Credentials
            if (settingsBambuUsername) {
                settingsBambuUsername.value = settings?.bambu_username || "";
            }
            if (settingsBambuPassword) {
                settingsBambuPassword.value = settings?.bambu_password || "";
            }
            if (settingsBambuRegion) {
                settingsBambuRegion.value = settings?.bambu_region || "global";
            }

            // Load Debug WS Logging
            if (settingsDebugWsLogging) {
                settingsDebugWsLogging.checked = !!settings?.debug_ws_logging;
            }

            // Load Experimental Mode (placeholder)
            if (settingsExperimentalMode) {
                settingsExperimentalMode.checked = settings?.experimental_mode || false;
            }

            // Load Experimental Tab Settings
            if (settings3mfTitleMatching) {
                settings3mfTitleMatching.checked = settings?.enable_3mf_title_matching ?? true; // Default: ON
            }
            if (settings3mfScoreThreshold) {
                settings3mfScoreThreshold.value = settings?.['3mf_score_threshold'] ?? 60;
            }
            if (settingsFileSelectionDialog) {
                settingsFileSelectionDialog.checked = settings?.enable_file_selection_dialog || false;
            }
            if (settingsMultiColorTracking) {
                settingsMultiColorTracking.checked = settings?.enable_multi_color_tracking ?? true; // Default: ON
            }
            if (settingsFtpGcodeDownload) {
                settingsFtpGcodeDownload.checked = settings?.enable_ftp_gcode_download ?? true; // Default: ON
            }

            // Load AMS Settings
            if (settingsAmsConflictEnabled) {
                settingsAmsConflictEnabled.checked = settings?.ams_conflict_detection_enabled ?? true; // Default: ON
            }
            if (settingsAmsConflictTolerance) {
                settingsAmsConflictTolerance.value = settings?.ams_conflict_tolerance_g ?? 5; // Default: 5g
            }

            // Update Experimental Tab State (enable/disable based on experimental_mode)
            const experimentalModeEnabled = settings?.experimental_mode || false;
            updateExperimentalTabState(experimentalModeEnabled);

        } catch (e) {
            console.warn("Settings modal load failed", e);
        }

        // Reset to first tab
        switchSettingsTab('general');

        settingsModal.classList.add("show");
        settingsModal.setAttribute("aria-hidden", "false");
    };

    settingsBtn?.addEventListener("click", (e) => {
        e.preventDefault();
        openSettings();
    });
    settingsClosers.forEach(btn => btn.addEventListener("click", closeSettings));

    // close when clicking backdrop
    settingsModal?.addEventListener("click", (e) => {
        if (e.target === settingsModal) closeSettings();
    });

    // Live-Update: Wenn experimental_mode Checkbox geändert wird
    settingsExperimentalMode?.addEventListener("change", () => {
        const isEnabled = settingsExperimentalMode.checked;
        updateExperimentalTabState(isEnabled);
    });

    settingsSaveBtn?.addEventListener("click", async () => {
        // Alle Settings in einem Objekt sammeln (statt 10+ sequentielle API-Calls)
        const allSettings = {};

        // Electricity Price
        if (settingsElectricityPrice) {
            const val = settingsElectricityPrice.value;
            allSettings["cost.electricity_price_kwh"] = val === "" ? null : Number(val);
        }

        // Theme (lokal, kein API-Call noetig)
        if (settingsThemeLight) {
            const isLight = settingsThemeLight.checked;
            document.body.classList.toggle("theme-light", isLight);
            localStorage.setItem("fh_theme", isLight ? "light" : "dark");
        }

        // Language
        if (settingsLanguage) {
            allSettings.language = settingsLanguage.value;
        }

        // Bambu Credentials
        if (settingsBambuUsername && settingsBambuPassword && settingsBambuRegion) {
            allSettings.bambu_username = settingsBambuUsername.value || null;
            allSettings.bambu_password = settingsBambuPassword.value || null;
            allSettings.bambu_region = settingsBambuRegion.value;
        }

        // Debug WS Logging
        if (settingsDebugWsLogging) {
            allSettings.debug_ws_logging = settingsDebugWsLogging.checked;
        }

        // Experimental Mode
        if (settingsExperimentalMode) {
            allSettings.experimental_mode = settingsExperimentalMode.checked;
        }

        // Experimental Tab Settings
        if (settings3mfTitleMatching) {
            allSettings.enable_3mf_title_matching = settings3mfTitleMatching.checked;
        }
        if (settings3mfScoreThreshold) {
            const threshold = parseInt(settings3mfScoreThreshold.value, 10);
            if (threshold >= 0 && threshold <= 100) {
                allSettings['3mf_score_threshold'] = threshold;
            }
        }
        if (settingsFileSelectionDialog) {
            allSettings.enable_file_selection_dialog = settingsFileSelectionDialog.checked;
        }
        if (settingsMultiColorTracking) {
            allSettings.enable_multi_color_tracking = settingsMultiColorTracking.checked;
        }
        if (settingsFtpGcodeDownload) {
            allSettings.enable_ftp_gcode_download = settingsFtpGcodeDownload.checked;
        }

        // AMS Settings
        if (settingsAmsConflictEnabled) {
            allSettings.ams_conflict_detection_enabled = settingsAmsConflictEnabled.checked;
        }
        if (settingsAmsConflictTolerance) {
            allSettings.ams_conflict_tolerance_g = parseInt(settingsAmsConflictTolerance.value, 10);
        }

        // Ein einziger API-Call statt 10+ sequentielle (spart ~2s)
        await updateSetting(allSettings);

        closeSettings();
    });

    // Clear Cache Button
    settingsClearCache?.addEventListener("click", () => {
        if (confirm("Cache wirklich leeren? Die Seite wird neu geladen.")) {
            localStorage.clear();
            sessionStorage.clear();
            location.reload();
        }
    });

    // Bambu Test Connection Button
    settingsBambuTestConnection?.addEventListener("click", async () => {
        if (!settingsBambuUsername || !settingsBambuPassword || !settingsBambuRegion) return;

        const username = settingsBambuUsername.value;
        const password = settingsBambuPassword.value;
        const region = settingsBambuRegion.value;

        if (!username || !password) {
            if (bambuConnectionStatus) {
                bambuConnectionStatus.innerHTML = '<span style="font-size: 12px; color: #ff9a8a;">Bitte E-Mail und Passwort eingeben</span>';
                bambuConnectionStatus.style.borderLeftColor = 'rgba(231,76,60,0.6)';
            }
            return;
        }

        // Show loading state
        if (bambuConnectionStatus) {
            bambuConnectionStatus.innerHTML = '<span style="font-size: 12px; color: rgba(255,255,255,0.6);">Verbindung wird getestet...</span>';
            bambuConnectionStatus.style.borderLeftColor = 'rgba(241,196,15,0.6)';
        }

        settingsBambuTestConnection.disabled = true;
        settingsBambuTestConnection.textContent = "Teste...";

        try {
            // TODO: Replace with actual API endpoint
            const response = await fetch("/api/bambu/test-connection", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, password, region })
            });

            if (response.ok) {
                const data = await response.json();
                if (bambuConnectionStatus) {
                    bambuConnectionStatus.innerHTML = '<span style="font-size: 12px; color: #8ef0b5;">✓ Verbindung erfolgreich</span>';
                    bambuConnectionStatus.style.borderLeftColor = 'rgba(46,204,113,0.6)';
                }
            } else {
                if (bambuConnectionStatus) {
                    bambuConnectionStatus.innerHTML = '<span style="font-size: 12px; color: #ff9a8a;">✗ Verbindung fehlgeschlagen</span>';
                    bambuConnectionStatus.style.borderLeftColor = 'rgba(231,76,60,0.6)';
                }
            }
        } catch (e) {
            console.error("Bambu connection test failed", e);
            if (bambuConnectionStatus) {
                bambuConnectionStatus.innerHTML = '<span style="font-size: 12px; color: #ff9a8a;">✗ Fehler beim Testen</span>';
                bambuConnectionStatus.style.borderLeftColor = 'rgba(231,76,60,0.6)';
            }
        } finally {
            settingsBambuTestConnection.disabled = false;
            settingsBambuTestConnection.textContent = "Verbindung testen";
        }
    });

    // ===== BACKUP TAB LOGIC =====
    const loadBackupList = async () => {
        if (!settingsBackupList) return;
        settingsBackupList.innerHTML = '<p style="font-size: 12px; color: rgba(255,255,255,0.4);">Lade Backups...</p>';
        try {
            const res = await fetch("/api/database/backups/list");
            const data = await res.json();
            const backups = data.backups || [];
            if (backups.length === 0) {
                settingsBackupList.innerHTML = '<p style="font-size: 12px; color: rgba(255,255,255,0.4);">Keine Backups vorhanden.</p>';
                return;
            }
            let html = '<div style="display: flex; flex-direction: column; gap: 8px;">';
            backups.forEach(b => {
                const date = new Date(b.created * 1000);
                const dateStr = date.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
                const timeStr = date.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
                html += `<div style="display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; background: rgba(0,0,0,0.2); border-radius: 6px; border: 1px solid rgba(255,255,255,0.06);">`;
                html += `<div style="flex: 1; min-width: 0;">`;
                html += `<div style="font-size: 13px; color: rgba(255,255,255,0.85);">${dateStr} ${timeStr}</div>`;
                html += `<div style="font-size: 11px; color: rgba(255,255,255,0.4);">${b.size_mb} MB</div>`;
                html += `</div>`;
                html += `<div style="display: flex; gap: 6px; flex-shrink: 0;">`;
                html += `<button type="button" onclick="window._backupDownload('${b.filename}')" style="padding: 4px 8px; background: rgba(52,152,219,0.15); border: 1px solid rgba(52,152,219,0.3); border-radius: 4px; color: #3498db; font-size: 11px; cursor: pointer;" title="Herunterladen">Download</button>`;
                html += `<button type="button" onclick="window._backupRestore('${b.filename}')" style="padding: 4px 8px; background: rgba(46,204,113,0.15); border: 1px solid rgba(46,204,113,0.3); border-radius: 4px; color: #2ecc71; font-size: 11px; cursor: pointer;" title="Wiederherstellen">Restore</button>`;
                html += `<button type="button" onclick="window._backupDelete('${b.filename}')" style="padding: 4px 8px; background: rgba(231,76,60,0.15); border: 1px solid rgba(231,76,60,0.3); border-radius: 4px; color: #e74c3c; font-size: 11px; cursor: pointer;" title="Loeschen">X</button>`;
                html += `</div></div>`;
            });
            html += '</div>';
            settingsBackupList.innerHTML = html;
        } catch (e) {
            console.error("Backup list load failed", e);
            settingsBackupList.innerHTML = '<p style="font-size: 12px; color: rgba(231,76,60,0.8);">Fehler beim Laden der Backups.</p>';
        }
    };

    // Expose backup actions globally for onclick handlers
    window._backupDownload = (filename) => {
        const a = document.createElement("a");
        a.href = `/api/database/backups/download/${encodeURIComponent(filename)}`;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    };

    window._backupRestore = async (filename) => {
        if (!confirm(`Datenbank aus "${filename}" wiederherstellen?\n\nEin Sicherheits-Backup wird vorher automatisch erstellt.\nDie Seite wird nach dem Restore neu geladen.`)) return;
        if (settingsBackupStatus) {
            settingsBackupStatus.textContent = "Restore laeuft...";
            settingsBackupStatus.style.color = "rgba(52,152,219,0.9)";
        }
        try {
            const res = await fetch(`/api/database/backups/restore/${encodeURIComponent(filename)}`, { method: "POST" });
            const data = await res.json();
            if (data.success) {
                alert("Datenbank erfolgreich wiederhergestellt!\nSicherheits-Backup: " + data.safety_backup + "\n\nDie Seite wird jetzt neu geladen.");
                location.reload();
            } else {
                if (settingsBackupStatus) {
                    settingsBackupStatus.textContent = "Restore fehlgeschlagen: " + (data.detail || "Unbekannt");
                    settingsBackupStatus.style.color = "rgba(231,76,60,0.9)";
                }
            }
        } catch (e) {
            console.error("Restore failed", e);
            if (settingsBackupStatus) {
                settingsBackupStatus.textContent = "Fehler beim Wiederherstellen";
                settingsBackupStatus.style.color = "rgba(231,76,60,0.9)";
            }
        }
    };

    window._backupDelete = async (filename) => {
        if (!confirm(`Backup "${filename}" wirklich loeschen?`)) return;
        try {
            const res = await fetch(`/api/database/backups/delete/${encodeURIComponent(filename)}`, { method: "DELETE" });
            const data = await res.json();
            if (data.success) {
                loadBackupList();
            } else {
                alert("Loeschen fehlgeschlagen: " + (data.detail || "Unbekannt"));
            }
        } catch (e) {
            console.error("Backup delete failed", e);
            alert("Fehler beim Loeschen des Backups.");
        }
    };

    settingsBackupCreateBtn?.addEventListener("click", async () => {
        if (!settingsBackupStatus) return;
        settingsBackupCreateBtn.disabled = true;
        settingsBackupCreateBtn.textContent = "Erstelle Backup...";
        settingsBackupStatus.textContent = "Backup wird erstellt...";
        settingsBackupStatus.style.color = "rgba(52,152,219,0.9)";
        try {
            const res = await fetch("/api/database/backups/create", { method: "POST" });
            const data = await res.json();
            if (data.success) {
                settingsBackupStatus.textContent = "Backup erstellt (" + data.backup_size_mb + " MB)";
                settingsBackupStatus.style.color = "rgba(46,204,113,0.9)";
                loadBackupList();
            } else {
                settingsBackupStatus.textContent = "Fehler: " + (data.detail || "Unbekannt");
                settingsBackupStatus.style.color = "rgba(231,76,60,0.9)";
            }
        } catch (e) {
            console.error("Backup creation failed", e);
            settingsBackupStatus.textContent = "Fehler beim Erstellen des Backups";
            settingsBackupStatus.style.color = "rgba(231,76,60,0.9)";
        } finally {
            settingsBackupCreateBtn.disabled = false;
            settingsBackupCreateBtn.textContent = "Backup jetzt erstellen";
        }
    });

    settingsBackupUploadBtn?.addEventListener("click", () => {
        settingsBackupUploadInput?.click();
    });

    settingsBackupUploadInput?.addEventListener("change", async (event) => {
        const file = event.target.files?.[0];
        if (!file) return;

        if (!file.name.toLowerCase().endsWith(".db")) {
            if (settingsBackupStatus) {
                settingsBackupStatus.textContent = "Nur .db-Dateien sind erlaubt";
                settingsBackupStatus.style.color = "rgba(231,76,60,0.9)";
            }
            event.target.value = "";
            return;
        }

        if (settingsBackupStatus) {
            settingsBackupStatus.textContent = "Upload laeuft...";
            settingsBackupStatus.style.color = "rgba(52,152,219,0.9)";
        }
        if (settingsBackupUploadBtn) {
            settingsBackupUploadBtn.disabled = true;
            settingsBackupUploadBtn.textContent = "Upload laeuft...";
        }

        try {
            const formData = new FormData();
            formData.append("file", file);

            const res = await fetch("/api/database/backups/upload", {
                method: "POST",
                body: formData,
            });
            const data = await res.json();

            if (!res.ok || !data.success) {
                throw new Error(data.detail || "Upload fehlgeschlagen");
            }

            if (settingsBackupStatus) {
                settingsBackupStatus.textContent = `Backup hochgeladen (${data.backup_size_mb} MB)`;
                settingsBackupStatus.style.color = "rgba(46,204,113,0.9)";
            }
            loadBackupList();
        } catch (e) {
            console.error("Backup upload failed", e);
            if (settingsBackupStatus) {
                settingsBackupStatus.textContent = "Fehler beim Upload: " + (e?.message || "Unbekannt");
                settingsBackupStatus.style.color = "rgba(231,76,60,0.9)";
            }
        } finally {
            if (settingsBackupUploadBtn) {
                settingsBackupUploadBtn.disabled = false;
                settingsBackupUploadBtn.textContent = "Backup hochladen (.db)";
            }
            event.target.value = "";
        }
    });

    settingsBackupRefreshBtn?.addEventListener("click", () => loadBackupList());

    // Load backup list when switching to backup tab
    settingsTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            if (tab.dataset.tab === 'backup') loadBackupList();
        });
    });

    themeToggle?.addEventListener("click", () => {
        const isLight = document.body.classList.toggle("theme-light");
        localStorage.setItem("fh_theme", isLight ? "light" : "dark");
        closeAll();
    });

    // Bind settings controls
    fetchSettings().then(settings => {
        if (settings?.ams_mode) {
            amsRadios.forEach(r => {
                r.checked = r.value === settings.ams_mode;
            });
        }
    });

    amsRadios.forEach(radio => {
        radio.addEventListener("change", async () => {
            if (!radio.checked) return;
            await updateSetting({ ams_mode: radio.value });
        });
    });
}

// Zentrales AMS-Status-Polling
function startAmsStatusPoll() {
    const INTERVAL_MS = 12_000; // 12 Sekunden (zwischen 10-15s)
    let lastValue = null; // unbekannter Anfangszustand

    async function fetchAndApply() {
        let value = false; // default bei Fehlern: kein AMS
        try {
            const res = await fetch("/api/printers/has_real_ams", { cache: "no-store" });
            if (res && res.ok) {
                const json = await res.json();
                // Verwende ausschließlich response.value als Wahrheit
                value = Boolean(json?.value);
            } else {
                value = false;
            }
        } catch (e) {
            // Fehlerfall: AMS als nicht vorhanden behandeln
            value = false;
        }

        // Nur bei Statusänderung UI aktualisieren
        if (lastValue !== value) {
            document.body.classList.toggle("no-ams", !value);
            window.dispatchEvent(new CustomEvent("ams-status-changed", { detail: { value } }));
            lastValue = value;
        }
    }

    // Sofort initial ausführen, dann in Intervall
    fetchAndApply();
    setInterval(fetchAndApply, INTERVAL_MS);
}

// Starte Polling sofort (kein DOMContentLoaded-Wartepunkt)
startAmsStatusPoll();
