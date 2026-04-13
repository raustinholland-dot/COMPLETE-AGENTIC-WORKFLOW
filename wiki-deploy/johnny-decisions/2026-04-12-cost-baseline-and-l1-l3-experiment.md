# Decision: Cost Baseline and L1→L3 Optimization Experiment

**Date:** April 12, 2026
**Context:** First real cost data from the metrics capture pipeline shows ~$1.19 per pipeline run. At 10 runs/day that's ~$262/month just on the feed pipeline (before scoring, briefings, syncs). Need to understand where the money goes and run experiments to drive it down.

## Cost Baseline (per pipeline run)

| Step | Model | Avg Time | Avg Cost | % of Total |
|------|-------|----------|----------|------------|
| Triage | Opus (via llm-task) | ~4s | ~$0.20 | 17% |
| Article Selection | Gemini Flash | ~3s | $0.004 | <1% |
| **Compile (Johnny #1)** | **Opus, ~28K context** | **27s** | **$0.47** | **39%** |
| Gap Analysis | Gemini Flash | ~15s | $0.005 | <1% |
| **Output (Johnny #2)** | **Opus, ~37K context** | **88s** | **$0.47** | **39%** |
| **Total** | | **~115s** | **$1.19** | **100%** |

**Headline:** Opus input is 78% of the total cost. Two big Opus turns (Compile + Output) account for 78% combined.

## Three Optimization Levers (Ranked by Risk)

### Lever 1: Move triage off Opus → Gemini Flash
- **Savings:** ~$0.20/run (99% on this step)
- **Risk:** None — triage is just classification
- **Implementation:** Change `feed-pipeline.lobster` step 4 to call `gemini-json.sh` instead of `openclaw.invoke llm-task`
- **Verdict:** Free win. Should do anyway.

### Lever 2: Trim compile context
- **Savings:** ~$0.15/run (32% on Compile)
- **Risk:** Low — Lobster already injects everything Johnny #1 needs via `.tmp-compile-articles.txt`. The always-on context (SOUL.md, FEED-RULES.md, AGENTS.md, HEARTBEAT.md) is loaded into the cron session unnecessarily.
- **Implementation:** Find a way to launch the compile-trigger cron without inheriting the full main session context, or strip files from the cron session's startup
- **Verdict:** Worth investigating after baseline data is cleaner.

### Lever 3: Move Output to Sonnet 4.6 or Gemini Flash
- **Savings:** $0.33-0.45/run (70-96% on Output)
- **Risk:** Unknown — does cheaper model preserve Austin's voice in email drafts and call prep?
- **Implementation:** Change the `output-trigger-001` cron to use a different model. Run side-by-side comparisons.
- **Verdict:** This is the L1→L3 experiment.

## Optimized Target

| Scenario | Cost/Run | Savings vs Baseline |
|----------|----------|---------------------|
| Baseline | $1.19 | — |
| Lever 1 only | $0.99 | 17% |
| Levers 1+2 | $0.84 | 29% |
| Levers 1+2+3 (Sonnet) | $0.47 | 60% |
| Levers 1+2+3 (Flash) | $0.35 | 71% |

## Monthly Projections

| Runs/day | Current | Optimized (Sonnet) | Optimized (Flash) | Saved |
|----------|---------|---------------------|-------------------|-------|
| 5 | $131/mo | $52/mo | $39/mo | $79–92 |
| 10 | $262/mo | $103/mo | $77/mo | $159–185 |
| 20 | $524/mo | $207/mo | $154/mo | $317–370 |

## The L1→L3 Experiment

**Open architectural question:** Does Output (Johnny #2) need Gemini's gap analysis to fire first, or can Compile (Johnny #1) hand off directly?

**Current architecture:** L1 → L2 → L3
```
Compile (Opus) → Gemini gap analysis → Output (Opus)
```
Gemini acts as a *gate* — it tells Output what to produce.

**Proposed architecture:** L1 → L3, with L2 as retroactive evaluator
```
Compile (Opus) → Output (Opus directly)
                       ↓
                Gemini scores the entire workflow over time
```
Gemini acts as a *judge*, not a gate. Output gets Opus's full creative judgment instead of following Gemini's checklist.

**The hypothesis:** Output quality is *higher* when Opus has full context vs. following a Gemini-defined task list. Cost is also lower (one fewer LLM call per run).

**The measurement:** Run both architectures side-by-side over 20+ real emails. The metrics dashboard captures cost and time. Quality is measured by Austin reviewing the outputs and rating them (could be as simple as 👍/👎 in Telegram).

## Why This Matters Strategically

This isn't just "optimize a pipeline." It's testing the core hypothesis behind the meta-harness paper (Stanford/MIT, arXiv:2603.28052): **the harness matters more than the model**. If we can get equal-or-better quality at 30% of the cost by changing the harness (which model handles which step, what context they get, what order they run in), that validates the entire architecture direction.

It also informs Johnny's evolution: which steps deserve Opus, which can be downgraded, and where structural changes (skipping the L2 gate) outperform model upgrades.

## Pricing Reference

| Model | Input/1M | Output/1M | Ratio |
|-------|----------|-----------|-------|
| Opus 4.6 | $15 | $75 | 5:1 |
| Sonnet 4.6 | $3 | $15 | 5:1 |
| Gemini 2.5 Flash | $0.15 | $0.60 | 4:1 |
| Gemini 2.5 Flash (thinking) | — | $3.50 | — |

## Status

Cost baseline established April 12, 2026 from one synthetic test run + historical session data. Real-data baseline pending first Telegram email through fixed hook. Once baseline is solid, run experiments in this order:

1. **Lever 1** (triage off Opus) — instant, zero risk
2. **Trim compile context** — investigate first, implement if safe
3. **L1→L3 experiment** — needs side-by-side comparison infrastructure

## Credit

Cost analysis by Claude Code (daily driver session, Apr 12). Built on metrics captured from real OpenClaw session/cron state.
