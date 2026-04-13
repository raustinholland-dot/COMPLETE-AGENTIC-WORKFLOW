# Decision: Pipeline Metrics Instrumentation

**Date:** April 12, 2026
**Context:** Pipeline ran end-to-end but produced no record of token spend, time, or cost per step. Before running any optimization experiments (L1→L3, model swaps, context trimming), we need quantitative measurement of every step. "You can't optimize what you can't measure."

## Problem

Each pipeline run touches 5 LLM calls (triage, article-select, compile, gap-analysis, output) across two providers (Anthropic Opus, Google Gemini Flash). No record was kept of:
- Per-step duration
- Per-step input/output tokens
- Per-step cost
- Total run cost
- Which deals were touched

Without this, the L1→L3 experiment is unmeasurable — we'd have no baseline to compare against.

## Solution

Instrument every pipeline step. Each step writes its metrics to a temp file. A new final step (`write_metrics`) collects everything, queries OpenClaw's session/cron state for Opus token counts, calculates costs, and emits one markdown file per run with full frontmatter.

## Architecture

```
Pipeline Step          → Metrics Source                   → Captured To
─────────────────────────────────────────────────────────────────────────
init_metrics           → date +%s%3N (start time)         → .tmp-metrics-run.json
triage                 → wrapped curl + openclaw sessions → .tmp-metrics-triage.json
article_selection      → gemini-json.sh (4th arg)         → .tmp-metrics-select.json
compile (Johnny #1)    → openclaw sessions + cron list    → (queried at end)
gap_analysis           → gemini-json.sh (4th arg)         → .tmp-metrics-analysis.json
output (Johnny #2)     → openclaw sessions + cron list    → (queried at end)
write_metrics          → collects all + costs             → wiki/metrics/run-YYYY-MM-DD-HHMM.md
```

## Files Modified on MBP

| File | Change |
|------|--------|
| `gemini-json.sh` | Optional 4th arg writes `{promptTokenCount, candidatesTokenCount, durationMs, model}` to file. Stdout unchanged (backward compatible). |
| `feed-pipeline.lobster` | Added Step 0 (`init_metrics`), wrapped triage with timing, added Step 7 (`write_metrics`) before ops_log |
| `compile-wiki.lobster` | Passes `.tmp-metrics-select.json` to gemini-json.sh |
| `analysis-pulse.lobster` | Passes `.tmp-metrics-analysis.json` to gemini-json.sh |
| `write-metrics.sh` (NEW) | Collects all per-step metrics, queries `openclaw sessions --json` for Opus token counts, queries `openclaw.invoke cron list` for `lastDurationMs`, calculates costs, writes `wiki/metrics/run-*.md` |

## Cost Calculation

- **Opus (input):** `(session_tokens - output_tokens) × $15/1M`
- **Opus (output):** `output_tokens × $75/1M`
- **Gemini Flash (input):** `promptTokenCount × $0.15/1M`
- **Gemini Flash (output):** `candidatesTokenCount × $0.60/1M`
- **Total:** sum of all five steps

## Known Bugs (Tracked)

1. Triage tokens use cumulative `agent:main:main` session totals, not per-turn delta
2. Output session_tokens are stale when Johnny #2 doesn't run (script reports last session as if it ran today)
3. Triage `model` field comes back empty (jq query against llm-task response shape is wrong)
4. `deals_touched` counts historical log entries, not just this run's compile entry

These will be fixed after the first real-data run validates the architecture.

## Output Format

Each run produces a markdown file with frontmatter Dataview can query:

```yaml
---
type: pipeline-run
date: 2026-04-12
sender: "..."
total_cost_usd: 1.19
total_seconds: 115
triage_seconds: 4
triage_input_tokens: 63931
[... 25 more fields ...]
---
```

Plus a body with deal wikilinks and per-step detail tables.

## Why This Matters

The metrics file structure feeds directly into the Obsidian dashboard (separate decision: `2026-04-12-obsidian-pipeline-dashboard.md`) and provides the measurement infrastructure for the L1→L3 architectural experiment (separate decision: `2026-04-12-cost-baseline-and-l1-l3-experiment.md`).

## Status

Deployed to MBP April 12, 2026. Validated with one synthetic test run (then cleaned). Ready for first real-data run via Telegram email feed.

## Credit

Built by Claude Code (daily driver session, Apr 12). Architecture validated against real OpenClaw session/cron state queries.
