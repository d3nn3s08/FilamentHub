document.addEventListener("DOMContentLoaded", () => {
    bindSettingsControls();
});

function resolveFetchSettings() {
    if (typeof fetchSettings === "function") return fetchSettings;
    // Fallback, falls navbar.js nicht geladen wäre (sollte nicht passieren)
    return async function () {
        const res = await fetch("/api/settings");
        return res.json();
    };
}

function resolveUpdateSetting() {
    if (typeof updateSetting === "function") return updateSetting;
    return async function (partial) {
        const res = await fetch("/api/settings", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(partial),
        });
        return res.json();
    };
}

async function bindSettingsControls() {
    const amsRadios     = document.querySelectorAll('input[name="settings_ams_mode"][data-setting="ams_mode"]');
    const debugCheckbox = document.querySelector('input[type="checkbox"][data-setting="debug_ws_logging"]');
    const channelRadios = document.querySelectorAll('input[name="update_channel"][data-setting="update_channel"]');
    const debugStatus   = document.getElementById("debugStatus");

    const fetchFn = resolveFetchSettings();
    const updateFn = resolveUpdateSetting();

    try {
        const settings = await fetchFn();
        if (settings?.ams_mode) {
            amsRadios.forEach(r => r.checked = r.value === settings.ams_mode);
        }
        if (debugCheckbox) {
            debugCheckbox.checked = !!settings?.debug_ws_logging;
            if (debugStatus) {
                debugStatus.textContent = `Status: ${debugCheckbox.checked ? "aktiv" : "inaktiv"}`;
            }
        }
        if (channelRadios.length && settings?.update_channel) {
            channelRadios.forEach(r => r.checked = r.value === settings.update_channel);
        }
    } catch (e) {
        console.warn("Settings laden fehlgeschlagen", e);
        if (debugStatus) debugStatus.textContent = "Status: Fehler beim Laden";
    }

    amsRadios.forEach(radio => {
        radio.addEventListener("change", async () => {
            if (!radio.checked) return;
            await updateFn({ ams_mode: radio.value });
        });
    });

    debugCheckbox?.addEventListener("change", async () => {
        await updateFn({ debug_ws_logging: debugCheckbox.checked });
        if (debugStatus) {
            debugStatus.textContent = `Status: ${debugCheckbox.checked ? "aktiv" : "inaktiv"}`;
        }
    });

    channelRadios.forEach(radio => {
        radio.addEventListener("change", async () => {
            if (!radio.checked) return;
            await updateFn({ update_channel: radio.value });
        });
    });
}
