# MFR Director

An institutional-grade AI partner for Multifamily Residential (MFR) operations,
delivered as a **Google Sheets Add-on**.

Analyzes any MFR data — from Yardi, Entrata, RealPage, AppFolio, or manual Google Sheets —
and produces a full dashboard with NOI impact calculations, red flags, and tactical directives.

---

## What It Does

1. **Reads your Google Sheets data** — select which tabs to include and optionally label each one (Rent Roll, GPR, etc.)
2. **Calls Claude AI** with an institutional-grade MFR analysis system prompt
3. **Displays an interactive HTML dashboard** inside Google Sheets with:
   - KPI header (Occupancy, Exposure, Leased %, GPR, Delinquency, Net Absorption, etc.)
   - GPR Waterfall chart
   - Vacancy drill-down with $ loss per unit
   - AR Aging table
   - Lease Expiration chart (12-month forward)
   - Loss-to-Lease by floorplan
   - Resident Activity (move velocity & retention)
   - Conversion Funnel by agent and source
   - Traffic Source ROI
   - Collections deep-dive
   - Market Context panel
   - NOI Impact Summary
   - Tactical Directives (minimum 8, with owner and deadline)
4. **Writes a formatted summary sheet** back into your Google Sheets file with KPIs, Red Flags, and Directives

---

## Setup

### Step 1 — Create the Apps Script project

1. Open your Google Sheets file
2. Go to **Extensions → Apps Script**
3. Delete any existing code in `Code.gs`
4. Create the following files (using the + button next to Files):

| File | Type |
|------|------|
| `Code.gs` | Script |
| `SystemPrompt.gs` | Script |
| `Sidebar.html` | HTML |
| `Settings.html` | HTML |

5. Copy the contents of each file from the `apps-script/` folder in this repo

### Step 2 — Update the manifest

1. In Apps Script editor, click the gear icon (Project Settings)
2. Check **"Show 'appsscript.json' manifest file in editor"**
3. Replace the contents of `appsscript.json` with the file from this repo

### Step 3 — Add your Anthropic API Key

1. In your Google Sheet, click **MFR Director → Settings (API Key)**
2. Enter your Anthropic API key (get one at `console.anthropic.com`)
3. Click Save

### Step 4 — Run your first analysis

1. Paste or import your MFR report data into separate sheets
   (one sheet per report type — e.g. "Rent Roll", "AR Aging", "Traffic")
2. Click **MFR Director → Analyze Portfolio**
3. In the sidebar:
   - Enter the **city / submarket** (e.g. "Austin, TX – South Congress")
   - Enter a **property nickname** (e.g. "Riverside")
   - Check the sheets to include
   - Optionally label each sheet with its report type (or leave "Auto-detect")
4. Click **⚡ Run Full Analysis**

---

## Data Format

MFR Director works with **any data source** — no specific format required.

Claude auto-detects the structure from column headers. Supported sources:
- Yardi exports (Rent Roll, GPR, AR, Box Score, Traffic, etc.)
- Entrata reports
- RealPage exports
- AppFolio / Buildium exports
- Manual Google Sheets maintained by your team
- CSV/Excel from any property management system

**Tips:**
- Keep each report type in its own sheet tab
- Include a header row
- The more report types you include, the more complete the analysis

---

## Cost

Each analysis calls the Claude API (`claude-opus-4-7`).
Approximate cost per analysis: **$0.50 – $2.00** depending on data volume.

The system prompt uses **prompt caching** to reduce costs on repeat runs.

---

## Project Structure

```
apps-script/
├── Code.gs           Main logic — menu, sheet reading, API orchestration
├── SystemPrompt.gs   Full MFR analysis system prompt sent to Claude
├── Sidebar.html      Analysis sidebar UI
├── Settings.html     API key configuration dialog
└── appsscript.json   Add-on manifest
mfr-skill.md          Original skill reference document
```
An institutional-grade AI partner for Multifamily Residential (MFR) operations. This agent specializes in the deep integration of Rent Roll, RESCRM, and Property Operations data. It fluently interprets unit-level classifications (CA, CB, etc.), identifies "Red Flags" across complex financial and leasing reports, and provides tactical directives to maximize NOI and asset performance.
