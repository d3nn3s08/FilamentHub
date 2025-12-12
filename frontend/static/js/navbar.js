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
    const amsRadios = menu.querySelectorAll('input[name="ams_mode"][data-setting="ams_mode"]');
    const debugCheckbox = menu.querySelector('input[type="checkbox"][data-setting="debug_ws_logging"]');

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
        if (debugCheckbox) {
            debugCheckbox.checked = !!settings?.debug_ws_logging;
        }
    });

    amsRadios.forEach(radio => {
        radio.addEventListener("change", async () => {
            if (!radio.checked) return;
            await updateSetting({ ams_mode: radio.value });
        });
    });

    debugCheckbox?.addEventListener("change", async () => {
        await updateSetting({ debug_ws_logging: debugCheckbox.checked });
    });
}
