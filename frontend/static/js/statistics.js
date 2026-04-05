let chartData = { byMaterial: [], byPrinter: [] };
let currentDays = 7;
let chartInstances = {};

document.addEventListener("DOMContentLoaded", () => {
    loadStatistics();
    loadCharts(currentDays);
    setupTimeFilter();
});

function setupTimeFilter() {
    document.querySelectorAll(".filter-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            currentDays = parseInt(btn.dataset.days);
            loadCharts(currentDays);
        });
    });
}

async function loadStatistics() {
    setStatus("Lade Daten ...");
    try {
        const [jobs, settings, byMaterial, byPrinter, heatmap] = await Promise.all([
            fetchJson("/api/jobs/stats/summary"),
            fetchJson("/api/settings"),
            fetchJson("/api/statistics/by-material"),
            fetchJson("/api/statistics/by-printer"),
            fetchJson("/api/statistics/heatmap?days=90")
        ]);
        chartData = { byMaterial, byPrinter };
        updateKpis(jobs, settings, byMaterial, byPrinter);
        updateCostBreakdown(jobs, settings);
        updatePerformance(jobs, byPrinter);
        renderHeatmap(heatmap?.data ?? []);
        renderTopMaterials(byMaterial);
        renderTopPrinters(byPrinter);
        setStatus("Aktualisiert");
        await loadCharts(currentDays);
    } catch (e) {
        console.error("Statistiken laden fehlgeschlagen", e);
        setStatus("Fehler beim Laden der Statistiken");
    }
}

async function loadCharts(days = 7) {
    try {
        const [timelineMaterial, timelineCosts] = await Promise.all([
            fetchJson(`/api/statistics/timeline-by-material?days=${days}`),
            fetchJson(`/api/statistics/timeline-costs?days=${days}`)
        ]);
        renderTimelineMaterial(timelineMaterial);
        renderCostsTimeline(timelineCosts);
        renderMaterial(chartData.byMaterial ?? []);
        renderPrinter(chartData.byPrinter ?? []);
    } catch (e) {
        console.warn("Charts laden fehlgeschlagen", e);
    }
}

async function fetchJson(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error("Request failed: " + url);
    return res.json();
}

function updateKpis(jobs, settings, byMaterial, byPrinter) {
    const totalJobs = jobs?.total_jobs ?? 0;
    const completed = jobs?.completed_jobs ?? 0;
    const filamentG = jobs?.total_filament_g ?? 0;
    const filamentKg = filamentG / 1000;
    const price = jobs?.energy_price_kwh ?? settings?.["cost.electricity_price_kwh"] ?? settings?.electricity_price_kwh ?? 0.30;
    const energyKwh = jobs?.energy_kwh_total ?? 0;
    const energyCost = jobs?.energy_cost_total;
    const energyExact = jobs?.energy_kwh_exact ?? 0;
    const energyEst = jobs?.energy_kwh_estimated ?? 0;
    const energyCostExact = energyExact * price;
    const energyCostEst = energyEst * price;
    const durationH = jobs?.total_duration_h ?? 0;
    const successRate = totalJobs > 0 ? Math.round((completed / totalJobs) * 100) : 0;

    // Längster Job aus byPrinter Daten
    let longestJobH = 0;
    if (byPrinter && Array.isArray(byPrinter)) {
        byPrinter.forEach(p => {
            if (p.duration_h > longestJobH) longestJobH = p.duration_h;
        });
    }

    // Häufigstes Material aus byMaterial Daten
    let topMaterial = "–";
    let topMaterialWeight = 0;
    if (byMaterial && Array.isArray(byMaterial)) {
        byMaterial.forEach(m => {
            const weight = m.total_weight_g ?? 0;
            if (weight > topMaterialWeight) {
                topMaterialWeight = weight;
                topMaterial = m.material_name ?? "Unbekannt";
            }
        });
    }

    // Card 1: Druckzeit
    setText("kpiDurationH", `${number(durationH, 0)}h`);
    setText("kpiLongestJob", longestJobH > 0 ? `Längster Job: ${number(longestJobH, 1)}h` : "Längster Job: –");
    
    // Card 2: Verbrauch
    setText("kpiFilamentKg", `${number(filamentKg, 2)}kg`);
    setText("kpiTopMaterial", topMaterialWeight > 0 ? `Häufigstes: ${topMaterial} (${number(topMaterialWeight/1000, 2)}kg)` : "Häufigstes Material: –");
    
    // Card 3: Kosten
    setText("kpiEnergyCost", energyCost != null ? `${number(energyCost, 2)} €` : "–");
    setText("kpiEnergyBreakdown", `Exakt: ${number(energyCostExact, 2)} € · Geschätzt: ~${number(energyCostEst, 2)} €`);
    
    // Card 4: Jobs
    setText("kpiTotalJobs", number(totalJobs));
    setText("kpiSuccessRate", `Erfolgsquote: ${successRate}%`);
    
    setStatus(`${number(durationH,0)}h Laufzeit · ${number(filamentKg,2)}kg · ${energyCost != null ? number(energyCost,0)+" €" : "–"}`);
}

function updateInventory(db, jobs) {
    // Removed - replaced by updateCostBreakdown and updatePerformance
}

function updateCostBreakdown(jobs, settings) {
    const energyCost = jobs?.energy_cost_total;
    const energyExact = jobs?.energy_kwh_exact ?? 0;
    const energyEst = jobs?.energy_kwh_estimated ?? 0;
    const price = jobs?.energy_price_kwh ?? settings?.["cost.electricity_price_kwh"] ?? 0.30;
    const costExact = energyExact * price;
    const costEst = energyEst * price;
    const totalJobs = jobs?.total_jobs ?? 0;
    const costPerJob = totalJobs > 0 && energyCost ? energyCost / totalJobs : 0;

    setText("costEnergy", energyCost != null ? `${number(energyCost, 2)} €` : "–");
    setText("costExact", `${number(costExact, 2)} €`);
    setText("costEstimated", `${number(costEst, 2)} €`);
    setText("costPerJob", costPerJob > 0 ? `${number(costPerJob, 3)} €` : "–");
    setText("electricityPrice", number(price, 2));
}

function updatePerformance(jobs, byPrinter) {
    const totalJobs = jobs?.total_jobs ?? 0;
    const completed = jobs?.completed_jobs ?? 0;
    const durationH = jobs?.total_duration_h ?? 0;
    const filamentG = jobs?.total_filament_g ?? 0;
    const avgDuration = totalJobs > 0 ? durationH / totalJobs : 0;
    const avgFilament = totalJobs > 0 ? filamentG / totalJobs : 0;
    const successRate = totalJobs > 0 ? Math.round((completed / totalJobs) * 100) : 0;

    let longestJobH = 0;
    if (byPrinter && Array.isArray(byPrinter)) {
        byPrinter.forEach(p => {
            if (p.duration_h > longestJobH) longestJobH = p.duration_h;
        });
    }

    setText("perfAvgDuration", `${number(avgDuration, 1)}h`);
    setText("perfAvgFilament", `${number(avgFilament, 1)}g`);
    setText("perfLongestJob", longestJobH > 0 ? `${number(longestJobH, 1)}h` : "–");
    setBar("barSuccess", successRate);
}

function renderHeatmap(data) {
    const container = document.getElementById("heatmapContainer");
    if (!container) return;
    
    container.innerHTML = "";
    
    // Find max jobs for scaling
    const maxJobs = Math.max(...data.map(d => d.jobs || 0), 1);
    
    data.forEach(day => {
        const cell = document.createElement("div");
        cell.className = "heatmap-cell";
        
        const jobs = day.jobs || 0;
        const level = jobs === 0 ? 0 : Math.min(4, Math.ceil((jobs / maxJobs) * 4));
        cell.classList.add(`level-${level}`);
        
        cell.dataset.date = day.date;
        cell.dataset.jobs = jobs;
        cell.dataset.filament = day.filament_g || 0;
        cell.dataset.duration = day.duration_h || 0;
        
        cell.addEventListener("mouseenter", showHeatmapTooltip);
        cell.addEventListener("mouseleave", hideHeatmapTooltip);
        
        container.appendChild(cell);
    });
}

function showHeatmapTooltip(e) {
    const tooltip = document.getElementById("heatmapTooltip");
    if (!tooltip) return;
    
    const date = e.target.dataset.date;
    const jobs = e.target.dataset.jobs;
    const filament = e.target.dataset.filament;
    const duration = e.target.dataset.duration;
    
    tooltip.innerHTML = `
        <strong>${date}</strong><br>
        ${jobs} Jobs · ${number(parseFloat(filament), 1)}g · ${number(parseFloat(duration), 1)}h
    `;
    
    const rect = e.target.getBoundingClientRect();
    tooltip.style.display = "block";
    tooltip.style.left = `${rect.left + rect.width / 2}px`;
    tooltip.style.top = `${rect.top - 60}px`;
}

function hideHeatmapTooltip() {
    const tooltip = document.getElementById("heatmapTooltip");
    if (tooltip) tooltip.style.display = "none";
}

function renderTopMaterials(data) {
    const container = document.getElementById("topMaterialsList");
    if (!container) return;
    
    // Sort by total_weight_g descending and take top 5
    const top5 = [...data]
        .sort((a, b) => (b.total_weight_g || 0) - (a.total_weight_g || 0))
        .slice(0, 5);
    
    const maxWeight = Math.max(...top5.map(m => m.total_weight_g || 0), 1);
    
    container.innerHTML = top5.map(material => {
        const weight = material.total_weight_g || 0;
        const weightKg = weight / 1000;
        const percent = Math.round((weight / maxWeight) * 100);
        const color = palette(top5.indexOf(material));
        
        return `
            <div class="ranking-item">
                <div class="ranking-label">
                    <span>${material.material_name || "Unbekannt"}</span>
                    <span>${number(weightKg, 2)}kg</span>
                </div>
                <div class="ranking-bar">
                    <div class="ranking-bar-fill" style="width: ${percent}%; background: ${color};">
                        ${percent}%
                    </div>
                </div>
            </div>
        `;
    }).join("");
}

function renderTopPrinters(data) {
    const container = document.getElementById("topPrintersList");
    if (!container) return;

    // Sort by duration_h descending and take top 5
    const top5 = [...data]
        .sort((a, b) => (b.duration_h || 0) - (a.duration_h || 0))
        .slice(0, 5);

    const maxDuration = Math.max(...top5.map(p => p.duration_h || 0), 1);

    // Moderne vertikale Card-Layout (Grid)
    container.innerHTML = `
        <div class="printer-cards-grid">
            ${top5.map((printer, idx) => {
                const duration = printer.duration_h || 0;
                const percent = Math.round((duration / maxDuration) * 100);
                const color = palette(idx + 3);
                const printerName = printer.printer_name || "Unbekannt";

                return `
                    <div class="printer-card" title="${printerName}">
                        <div class="printer-card-icon">🖨️</div>
                        <div class="printer-card-name">${printerName}</div>
                        <div class="printer-card-bar">
                            <div class="printer-card-bar-fill" style="width: ${percent}%; background: ${color};"></div>
                        </div>
                        <div class="printer-card-stats">
                            <span class="printer-card-time">${number(duration, 1)}h</span>
                            <span class="printer-card-jobs">${printer.jobs} Job${printer.jobs !== 1 ? 's' : ''}</span>
                        </div>
                    </div>
                `;
            }).join("")}
        </div>
    `;
}

function renderTimelineMaterial(data) {
    if (!window.Chart) return;
    const ctx = document.getElementById("chartTimelineMaterial");
    if (!ctx) return;
    
    // Destroy old chart if exists
    if (chartInstances.timelineMaterial) {
        chartInstances.timelineMaterial.destroy();
    }
    
    const labels = data?.dates ?? [];
    const datasets = (data?.datasets ?? []).map((ds, i) => ({
        label: ds.material,
        data: ds.data,
        borderColor: palette(i),
        backgroundColor: `${palette(i)}33`,
        tension: 0.35,
        fill: true,
        pointRadius: 2,
    }));

    chartInstances.timelineMaterial = new Chart(ctx, {
        type: "line",
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { beginAtZero: true, stacked: false, ticks: { color: "#cfd8e3" } },
                x: { ticks: { color: "#cfd8e3", maxRotation: 45 } }
            },
            plugins: {
                legend: { labels: { color: "#cfd8e3", boxWidth: 12 } },
                tooltip: { mode: "index", intersect: false },
            },
        },
    });
}

function renderCostsTimeline(data) {
    if (!window.Chart) return;
    const ctx = document.getElementById("chartCosts");
    if (!ctx) return;
    
    // Destroy old chart if exists
    if (chartInstances.costs) {
        chartInstances.costs.destroy();
    }
    
    const labels = data?.dates ?? [];
    const dailyCost = data?.daily_cost ?? [];
    const cumulativeCost = data?.cumulative_cost ?? [];

    chartInstances.costs = new Chart(ctx, {
        type: "bar",
        data: {
            labels,
            datasets: [
                {
                    label: "Tägliche Kosten",
                    data: dailyCost,
                    backgroundColor: "#00c6ff",
                    borderColor: "#00c6ff",
                    borderWidth: 0,
                    borderRadius: 6,
                    barPercentage: 0.75,
                    categoryPercentage: 0.6,
                    maxBarThickness: 44,
                    yAxisID: "y",
                },
                {
                    label: "Kumuliert",
                    data: cumulativeCost,
                    type: "line",
                    borderColor: "#f39c12",
                    backgroundColor: "rgba(243,156,18,0.25)",
                    tension: 0.3,
                    fill: false,
                    yAxisID: "y1",
                    pointRadius: 4,
                    pointBackgroundColor: "#f39c12",
                    spanGaps: true,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { beginAtZero: true, position: "left", ticks: { color: "#cfd8e3" } },
                y1: { beginAtZero: true, position: "right", grid: { drawOnChartArea: false }, ticks: { color: "#cfd8e3" } },
                x: { ticks: { color: "#cfd8e3", maxRotation: 45 } }
            },
            plugins: {
                legend: {
                    display: true,
                    position: "bottom",
                    align: "center",
                    labels: { color: "#cfd8e3", boxWidth: 12, padding: 8 }
                },
                tooltip: { mode: "index", intersect: false },
            },
        },
    });
}

function renderMaterial(data) {
    if (!window.Chart) return;
    const ctx = document.getElementById("chartMaterial");
    if (!ctx) return;
    
    // Destroy old chart if exists
    if (chartInstances.material) {
        chartInstances.material.destroy();
    }
    
    const labels = data.map(d => d.material_name || d.name || "Unbekannt");
    const values = data.map(d => (d.total_weight_g || 0) / 1000); // Convert to kg
    const colors = data.map((d, i) => d.color || palette(i));

    chartInstances.material = new Chart(ctx, {
        type: "doughnut",
        data: {
            labels,
            datasets: [{ data: values, backgroundColor: colors, borderWidth: 0 }]
        },
        options: {
            cutout: "60%",
            plugins: { 
                legend: { labels: { color: "#cfd8e3" } },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${ctx.label}: ${ctx.parsed.toFixed(2)} kg`
                    }
                }
            }
        }
    });
}

function renderPrinter(data) {
    if (!window.Chart) return;
    const ctx = document.getElementById("chartPrinter");
    if (!ctx) return;
    
    // Destroy old chart if exists
    if (chartInstances.printer) {
        chartInstances.printer.destroy();
    }
    
    const sorted = [...data].sort((a,b) => (b.duration_h ?? 0) - (a.duration_h ?? 0)).slice(0, 6);
    const labels = sorted.map(d => d.printer_name || "Unbekannt");
    const values = sorted.map(d => d.duration_h ?? 0);
    const colors = labels.map((_, i) => palette(i + 3));

    chartInstances.printer = new Chart(ctx, {
        type: "bar",
        data: {
            labels,
            datasets: [{
                label: "Dauer (h)",
                data: values,
                backgroundColor: colors,
                borderRadius: 8,
            }]
        },
        options: {
            indexAxis: "y",
            scales: {
                x: { beginAtZero: true, ticks: { color: "#cfd8e3" } },
                y: { ticks: { color: "#cfd8e3" } }
            },
            plugins: { legend: { display: false } }
        }
    });
}

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function setBar(id, pct) {
    const el = document.getElementById(id);
    if (el) el.style.width = `${pct}%`;
}

function setStatus(msg) {
    setText("statsInfo", msg);
}

function number(val, digits = 0) {
    const n = Number(val ?? 0);
    return n.toLocaleString("de-DE", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function palette(i) {
    const colors = ["#00c6ff", "#f39c12", "#7d5fff", "#2ecc71", "#ff6b6b", "#1abc9c", "#e84393", "#fdcb6e"];
    return colors[i % colors.length];
}
