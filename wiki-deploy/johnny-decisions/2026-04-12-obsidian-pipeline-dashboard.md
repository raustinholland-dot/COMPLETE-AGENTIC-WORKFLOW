# Decision: Pipeline Dashboard in Obsidian (Dataview/DataviewJS)

**Date:** April 12, 2026
**Context:** Need a live, interactive view of pipeline metrics — cost per run, cost per step, time per step, optimization targets, monthly projections — without building a custom UI. Austin already has an Obsidian vault that mirrors Johnny's wiki via the GitHub backup with ~30s sync delay.

## Decision

Use the existing Obsidian vault as the visualization layer. Add the Dataview community plugin to query frontmatter from per-run metrics files. Render everything as a single DataviewJS block with inline-styled HTML for tight layout.

## Vault Structure

```
~/Desktop/wiki-vault/                       (Austin's MBP — daily driver)
├── .obsidian/
│   ├── plugins/dataview/                    (community plugin, manually installed)
│   │   ├── manifest.json
│   │   ├── main.js
│   │   └── styles.css
│   ├── snippets/wide-dashboard.css          (overrides readable line length)
│   ├── community-plugins.json               (enables dataview)
│   └── appearance.json                      (enables wide-dashboard snippet)
├── pipeline-dashboard.md                    (the dashboard, cssclasses: wide)
├── metrics/                                 (synced from Johnny via GitHub backup)
│   └── run-YYYY-MM-DD-HHMM.md               (one file per pipeline run)
└── [wiki articles — synced from Johnny]
```

## Data Flow

```
Johnny's MBP                              GitHub Backup            Austin's Vault
─────────────────────────────────────────────────────────────────────────────
write-metrics.sh writes        ─push─→    johnny-workspace-      ─clone/pull─→  
  wiki/metrics/run-*.md                    backup repo                          metrics/run-*.md
                                                                                   ↓
                                                                              Dataview reads
                                                                                   ↓
                                                                          pipeline-dashboard.md renders
```

Sync delay: ~30 seconds end-to-end.

## Dashboard Layout

Single DataviewJS block. All HTML inline-styled (Obsidian strips `<style>` tags, so every style is on the element). Top-of-script DOM manipulation overrides Obsidian's readable line length to fill the window width.

Sections (top to bottom):
1. **Scoreboard** — horizontal flex bar, 8 metrics: Runs, Total $, Avg/Run, Avg Time, Opus $, Gemini $, Deals, Outputs
2. **3-column grid:** Cost Per Step | Optimization Targets | Monthly Projections
3. **Runs table** — full width, clickable rows linking to run detail files
4. **Footer** — L1→L3 experiment summary + pricing reference + metric definitions

## Why DataviewJS, Not Basic Dataview

Basic Dataview can only render one table per query block, with built-in headers and row counts that bloat vertical space. DataviewJS lets us:
- Render 5+ tables in a single block with no gaps
- Use a CSS grid for side-by-side layout
- Apply inline styles for tight padding
- Manipulate the DOM to override readable line length
- Compute derived metrics (averages, projections) at render time

Required toggle: Settings → Dataview → "Enable JavaScript Queries" (off by default).

## Wide-Dashboard Snippet

Obsidian's "Readable line length" constrains all notes to ~700px, which made the dashboard cramped. Two layers of override:

1. CSS snippet at `.obsidian/snippets/wide-dashboard.css` targeting `.markdown-preview-view.wide` (where `wide` is from frontmatter `cssclasses: [wide]`)
2. JavaScript inside the DataviewJS block walks up to the parent sizer element and forces `max-width: none`

The JS approach is more reliable because it bypasses CSS specificity issues entirely.

## Per-Run File Format

Each `metrics/run-*.md` file has frontmatter Dataview queries against:

```yaml
---
type: pipeline-run
date: 2026-04-12
sender: "..."
total_cost_usd: 1.19
total_seconds: 115
triage_seconds: 4
triage_input_tokens: 63931
triage_output_tokens: 2429
[... 25 more fields ...]
---
```

Plus a body with:
- Deal wikilinks (`[[trustwell-living]]`, etc.) — appear in Obsidian graph view
- Per-step detail tables ("What goes in / What comes out")

## Side Benefit: Graph View

Each run file links to the deal articles it touched. In Obsidian's graph view, run files cluster around the deals they processed. Visual representation of pipeline activity overlaid on the deal network.

## Status

Dashboard built and verified rendering April 12, 2026. Currently shows zero runs (test data was cleaned). Ready to populate once first real pipeline run completes.

## Credit

Built by Claude Code (daily driver session, Apr 12). Iterated through 5+ rounds of layout refinement based on Austin feedback ("tighter", "fill the blank space", "more condensed").
