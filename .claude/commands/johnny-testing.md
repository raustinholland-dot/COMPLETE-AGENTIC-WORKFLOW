# /johnny-testing — End-to-end pipeline test protocol

When Austin says **we're testing**, we're running a real input (email / calendar / transcript / teams message) through the Telegram feed and walking the pipeline stage-by-stage against ground truth — not trusting log summaries, not trusting `wiki/metrics/run-*.md`, and not declaring anything "working" based on a single field. Every bug fix on the pipeline gets the same treatment: fix → new real input → full walk → dashboard confirmation.

Run `/johnny` first (or be sure it has already been run this session) to load the foundation docs. This command layers **testing-specific** context on top. `/johnny`'s step 0a/0b (re-read Working Principles in CLAUDE.md + open any pinned "START HERE" memory entry) applies here too — if you're invoking `/johnny-testing` without having run `/johnny` first, do those two steps now before anything else. Testing work is design work; the principles need to be actively engaged, not just loaded.

## Test-mode read (run in parallel)

All paths on the MBP (`ssh mbp`, user `austinholland`). Everything below is required context before the first real input — or before picking up a debug session mid-stream.

### 1. Pipeline definitions (the actual Lobster flows we're testing)
```
ssh mbp "cat \
  ~/.openclaw/workspace/feed-pipeline.lobster \
  ~/.openclaw/workspace/compile-wiki.lobster \
  ~/.openclaw/workspace/analysis-pulse.lobster"
```
Read these top-to-bottom. Every step's `when:` conditions, `env:` substitutions, and `command:` shells matter — pipeline bugs almost always hide in step boundaries (variable substitution, exit codes, quoting).

### 2. Agent prompts (what Johnny #1 and Johnny #2 actually receive)
```
ssh mbp "cat \
  ~/.openclaw/workspace/compile-prompt.md \
  ~/.openclaw/workspace/output-prompt.md"
```
The prompts define scope: what Johnny is told to read, what to write, what to skip. Over- and under-scoping bugs usually trace to a line in one of these.

### 3. Scripts in the verification / metrics path
```
ssh mbp "cat \
  ~/.openclaw/workspace/scripts/run-analysis-pulse.sh \
  ~/.openclaw/workspace/scripts/finalize-metrics.py"
```
`run-analysis-pulse.sh` is the unix-cron wrapper (PATH, lock, logging). `finalize-metrics.py` scans session jsonls for the real per-stage cost and writes the `wiki/metrics/run-*.md` that feeds Obsidian.

### 4. Obsidian dashboard + ingest path
```
ssh mbp "cat ~/.openclaw/workspace/johnny/decisions/2026-04-12-obsidian-pipeline-dashboard.md"
ls -lt ~/Desktop/wiki-vault/metrics/ | head -6
cat ~/Desktop/wiki-vault/pipeline-dashboard.md 2>/dev/null | head -80
```
Local side lives in `~/Desktop/wiki-vault/` on Austin's daily driver. The launchd `com.austin.vault-sync` pulls `wiki/metrics/` from GitHub every 60s. If a run doesn't appear in the dashboard within ~90s of the pipeline finishing, the failure is in (a) `finalize-metrics.py`'s git push, (b) the launchd sync, or (c) the Dataview query — check in that order.

### 5. Active hook log (the one that actually fires — not the disabled plugin)
```
ssh mbp "tail -30 ~/.openclaw/workspace/hooks-feed-lobster.log"
```
`plugin-feed-lobster.log` is the disabled-plugin file. Ignore it. See memory `reference_feed_lobster_log.md`.

### 6. State files that gate the flow
```
ssh mbp "cat ~/.openclaw/workspace/.last-analysis-ts; echo ---; \
         python3 -c \"import json,datetime; d=json.load(open('/Users/austinholland/.openclaw/cron/jobs.json')); [print(j['id'],datetime.datetime.fromtimestamp(j.get('state',{}).get('lastRunAtMs',0)/1000) if j.get('state',{}).get('lastRunAtMs') else '') for j in d['jobs'] if j['id'] in ('compile-trigger-001','output-trigger-001')]\""
```
`.last-analysis-ts` controls `check_pending`. A stale or empty file causes over-scoping or an infinite Gemini loop. `lastRunAtMs` on the two triggers lags — don't read it as "in flight" vs "not fired." Confirm firing via gateway.log, not jobs.json.

## The 7-step session-jsonl walk (MANDATORY after every test input)

This is the non-negotiable ground-truth procedure. Memory file: `feedback_scrape_telegram_on_test.md`. Expand that memory if the process changes.

1. **Anchor on the feed event** — `hooks-feed-lobster.log` `Feed message on <channel> from Austin Holland (<N> chars)` line. That timestamp anchors every downstream lookup.
2. **Find the session jsonls** — `find ~/.openclaw/agents/main/sessions -name "*.jsonl" -mmin -N`. The compile and output sessionIds also land in `~/.openclaw/cron/jobs.json` under `compile-trigger-001.state.lastRunId` and `output-trigger-001.state.lastRunId`, but fall back to mtime search if those lag.
3. **Read each session jsonl end-to-end.** Every `type: message` event has `message.role`, `message.content` (list of `text`, `toolCall`, `toolResult`), and assistant messages carry `message.usage` with real per-call token counts and `cost.total` in USD.
4. **Sum `usage.cost.total`** across all assistant messages per session for the true per-stage cost. **Do not trust `wiki/metrics/run-*.md`** — the old `write-metrics.sh` pulled session aggregates before downstream stages finished and wrote last-run numbers as if current. `finalize-metrics.py` is the replacement, but still verify it against the jsonl sum before drawing conclusions.
5. **Walk the tool calls in order** to reconstruct what Johnny actually did: every file read, every file write, every `toolCall` with `name: message` / `action: send` (the only source of what Johnny sent to Telegram, since Bot API has no history), every failed invocation and its error message.
6. **Cross-reference**:
   - `~/.openclaw/workspace/raw/YYYY-MM-DD.md` — was the capture written?
   - `~/.openclaw/workspace/clearwater/feeds/.processed-inputs.jsonl` — was the hash deduped/logged?
   - `~/.openclaw/workspace/wiki/log.md` — was a compile entry prepended? Which deals were scoped?
   - Individual `wiki/*.md` files touched by Johnny #1 — do the edits match what he narrated in log.md?
   - `~/.openclaw/cron/jobs.json` `compile-trigger-001` / `output-trigger-001` state (lagged, but confirms eventual update).
   - Gateway log `~/.openclaw/logs/gateway.log` for `run_started` / `run_completed` / `tool=edit` / errors.
7. **Telegram side** — the MCP telegram tool in this session can only **send**, not read history. Telegram's Bot API exposes no history either. The only real source of "what Johnny sent to Austin" is the session jsonl `toolCall` records from step 5.

Only after all seven: report what the run did, what it cost, and which stages succeeded. Every "it works" claim must cite a specific session jsonl line or file diff.

## Dashboard verification (after the 7-step walk)

Once the jsonl walk says the run was correct, confirm the Obsidian surface reflects it:

1. `ls -lt ~/.openclaw/workspace/wiki/metrics/` on the MBP — does the new `run-YYYY-MM-DD-HHMM.md` file exist? Frontmatter fields present?
2. `ls -lt ~/Desktop/wiki-vault/metrics/` locally — did it arrive within ~90s of the MBP write?
3. Open `~/Desktop/wiki-vault/pipeline-dashboard.md` (or have Austin refresh Obsidian) — does the scoreboard / runs table show the new run with sensible numbers?
4. If any step lags or shows wrong numbers, the fix goes in `finalize-metrics.py` (the writer), `com.austin.vault-sync` (the syncer), or the DataviewJS block in `pipeline-dashboard.md` (the renderer) — in that order.

## Living-command rule

Every time we change the pipeline, add a verification step, move a file, or discover a new testing gotcha, **update this file in the same session.** The commit goes into the sales-tools repo (`.claude/commands/johnny-testing.md`). A stale testing command is worse than no command — it tells the next session to read files that don't exist or skip checks that now matter.

## Debugging the pulse without spamming Austin

`analysis-pulse.lobster` ends in `openclaw.invoke --tool cron --action run` → `output-trigger-001` → Johnny #2 agent turn → real Telegram DMs to Austin + real Opus billing. **Do not** run `lobster run --mode tool --file ./analysis-pulse.lobster` repeatedly to test changes without first neutering the trigger path, or you will spam Austin's DM and burn Opus turns.

**Safe testing pattern:**

1. **Before any dry run, seed `.last-analysis-ts` to match the newest `## YYYY-MM-DD HH:MM` heading in `wiki/log.md`.** That forces `check_pending` to return `has_pending=false`, so steps 2–8 all skip via their `when:` guard, and only the free `finalize_metrics` step runs.
2. **For substitution / prompt / scoping experiments, run in isolation:**
   - Write a fake `.tmp-analysis-context.txt` with the exact content you want.
   - Call `gemini-json.sh` directly with that file and your new prompt.
   - Read `.tmp-analysis-result.json` and iterate — no cron fire, no Johnny #2, no Telegram traffic.
3. **Only run the full pulse end-to-end once**, from a fresh real input, after substitution + prompt changes have been verified in isolation.
4. After a test, always `grep 'output-trigger-001' ~/.openclaw/logs/gateway.log | tail` and count how many sends landed in the output session jsonl — if the count is higher than one real input should produce, something regressed.

**The 2026-04-12 incident** (the reason this section exists): substitution bug in analysis-pulse was reproduced with 3 dry runs. Each dry run fired `output-trigger-001`, Johnny #2 drafted 1–3 hallucinated messages per run, and they all landed in Austin's DM. Net damage: 7 unwanted Telegram messages and ~$1.00 in Opus cost, none of it valuable. The fix was a 1-character change (single→double quotes); the cost was testing it live instead of in isolation.

## What this command is not

- Not a substitute for `/johnny`. Run `/johnny` first to get the foundation docs (framing, architecture, vision, decisions). This command layers test-mode context on top.
- Not a replacement for actually reading the session jsonls. There is no shortcut. Metrics files are a convenience view; the jsonls are truth.
- Not for synthetic tests. Synthetic inputs can skip the hook, bypass dedup, and mask routing bugs. Testing means a real Telegram paste, real email, or real transcript into the matching feed group.
