# 🎨 DESIGN_RULES.md  
**Verbindliche UI- & Design-Regeln für FilamentHub**

Diese Datei definiert die **verbindlichen Regeln** für alle UI-Komponenten,
Tabs, Panels und Erweiterungen im Projekt.

Ziel ist:
- ein einheitliches Erscheinungsbild
- keine Design-Abweichungen
- kein Wildwuchs bei Layouts
- kein erneutes Erklären von Design-Entscheidungen

Diese Regeln gelten **projektweit**.

---

## 🧠 GRUNDPRINZIPIEN

### 1️⃣ Design-System vor Individualität
Es gibt **ein** Design-System.  
Neue Features passen sich an – nicht umgekehrt.

> ❌ Kein Feature bringt sein eigenes Layout  
> ✅ Jedes Feature nutzt bestehende Bausteine

---

### 2️⃣ Struktur ≠ Theme
- **Struktur** ist stabil und wiederverwendbar
- **Theme** ist austauschbar

Struktur wird **geteilt**, Theme wird **entkoppelt**.

---

### 3️⃣ Kein implizites Design-Wissen
Alles, was für korrektes UI nötig ist,  
muss aus diesen Regeln ableitbar sein.

---

## 🧱 VERPFLICHTENDE LAYOUT-BAUSTEINE

### ✅ Erlaubte Container

| Zweck | Pflicht-Klasse |
|---|---|
| Haupt-UI-Einheit | `.panel` |
| Card-Kopf | `.card-header` |
| Strukturierte Werte | `.info-grid` |
| Labels | `.info-label` |
| Werte | `.info-value` |

**Jede neue UI-Einheit MUSS in einer `.panel` liegen.**

---

### ❌ Verbotene Konstrukte

- Inline-Styles (`style="..."`)
- Eigene Card-Layouts
- Eigene Grid-Systeme
- Custom CSS für einzelne Features
- Kopierte CSS-Blöcke aus anderen Projekten

Wenn etwas davon nötig erscheint → **Architekturproblem, kein Featurebedarf**.

---

## 🧩 CARD-REGELN (verbindlich)

### Jede Card:
- ist eine `.panel`
- hat **optional** einen `.card-header`
- enthält **keine Logik**
- enthält **keine Styles**

### Beispiel (Referenz):

```html
<div class="panel">
  <div class="card-header">
    <h3>Titel</h3>
  </div>

  <div class="info-grid">
    <div>
      <div class="info-label">Label</div>
      <div class="info-value">Value</div>
    </div>
  </div>
</div>
🟢 STATUS & BADGES

Statusanzeigen:

IMMER über .status-badge

KEINE freien Texte im Header

Erlaubte Statusklassen:

status-ok

status-warning

status-error

💎 PRO-REGELN

PRO-Features sind keine eigenen Designs

PRO = mehr Inhalt, nicht anderes Layout

Verbindlich:

.pro-only bleibt erhalten

.pro-badge wird im .card-header verwendet

keine visuelle Abweichung zu Lite

🧭 TABS & NAVIGATION

Tabs nutzen das bestehende Tab-System

Keine neuen Tab-Layouts

Reihenfolge folgt logischer Nähe

Beispiel:
System | Performance | Printer | MQTT | JSON Inspector | Logs | Config

📂 DATEI- & ASSET-REGELN
Trennung der Welten
Bereich	Zweck
/frontend	Core UI
/app/static	Debug / Subsysteme

Assets dürfen NIEMALS gemischt werden.
CONFIG-FIRST-PRINZIP

Limits

Schutzmechanismen

Policies

gehören immer in den Config Manager, niemals in Tools.

Beispiele:

Large-JSON-Schutz

Timeouts

Max Depth

Performance Limits

🧪 FEATURE-ERWEITERUNGEN (Pflichtablauf)

Jede neue UI-Erweiterung MUSS:

Bestehende Struktur verwenden

Keine neuen Styles einführen

Keine neue Layout-Logik erfinden

Erst Design, dann Funktion

Erst Config, dann Tool

🧠 VERBINDLICHER MERKSATZ

Wenn ein Feature eigenes CSS braucht,
ist das Design-System nicht verstanden.

✅ ERFOLGSKRITERIUM

Ein Feature gilt als korrekt umgesetzt, wenn:

es optisch nicht auffällt

es sich anfühlt, als wäre es immer da gewesen

es keine Sonderregeln braucht

🔒 STATUS

Diese Regeln sind:

verbindlich

bewusst restriktiv

Grundlage für alle weiteren KI-Kommandos

Änderungen an diesem Dokument sind Architektur-Entscheidungen.
