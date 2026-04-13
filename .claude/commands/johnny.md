# /johnny — Become Johnny-aware

When Austin types `/johnny`, you are starting (or resuming) work on the Johnny Forsyth pipeline — the OpenClaw agent system on his MBP. Before doing anything else, read the same foundation Johnny reads when he wakes from a cron. You and Johnny must share one source of truth or the system drifts.

## Session-start read (do this first, every time)

**Before the MBP reads, do these two local steps:**

0a. **Re-read the Working Principles section of `~/Desktop/sales-tools/CLAUDE.md`** (the four Karpathy principles: Think before coding, Simplicity first, Surgical changes, Verify before stopping). CLAUDE.md is auto-loaded into context at session start, but having the text in context isn't the same as operating from it. State the principles back in one line as part of your orientation summary so Austin can see they're active — that's the forcing function.

0b. **Open any memory entry in `~/.claude/projects/-Users-austinhollsnd-Desktop-sales-tools/memory/MEMORY.md` that is pinned with "START HERE"** (or similar strong-priority wording). The MEMORY.md index is in context but individual memory files are not — a pinned entry is a signal the previous session left you a specific starting point. Read the file, don't just rely on the one-line description in the index.

Then run these in parallel — they are on the MBP at `100.122.212.128` via Tailscale/SSH (ssh alias `mbp`):

1. **Core orientation** — what the system is, how it's built, where it's headed:
   ```
   ssh mbp "cat ~/.openclaw/workspace/johnny/framing.md ~/.openclaw/workspace/johnny/architecture.md ~/.openclaw/workspace/johnny/vision.md"
   ```

2. **Recent decisions** — list the last ~14 days and read any whose filename or subject matters for likely work this session:
   ```
   ssh mbp "ls -lt ~/.openclaw/workspace/johnny/decisions/ | head -15"
   ```
   Then `cat` any decision file dated within the last 3 days, plus anything whose slug matches a topic Austin is likely to bring up (pipeline, cron, metrics, compile, output, analysis, lint).

3. **Current state** — the live wiki state and recent compile log:
   ```
   ssh mbp "head -60 ~/.openclaw/workspace/wiki/log.md; echo ---; ls -lt ~/.openclaw/workspace/wiki/metrics/ | head -8"
   ```

4. **What's actually scheduled** — cron state so you know what's running:
   ```
   ssh mbp "crontab -l; echo ---; python3 -c \"import json,datetime; d=json.load(open('/Users/austinholland/.openclaw/cron/jobs.json')); [print(j['id'],j.get('enabled'),j.get('schedule',{}).get('expr',''),datetime.datetime.fromtimestamp(j.get('state',{}).get('lastRunAtMs',0)/1000) if j.get('state',{}).get('lastRunAtMs') else '') for j in d['jobs']]\""
   ```

## After reading, orient Austin briefly

Once the foundation is in context, send one short message (3–6 lines) summarizing:
- One line confirming the four Working Principles are active (proof you re-read CLAUDE.md, not just that it's loaded)
- What Johnny's doing right now (active crons, most recent compile, any pending issues visible in log.md)
- Any unresolved thread from the most recent decision file(s) + anything from a pinned "START HERE" memory entry
- Ready for Austin's direction

Do not dump the contents of the files back to him — he wrote them, he knows what they say. The summary is proof you're oriented, not a briefing.

## Core facts (shortcut — still read the files, this is just the map)

- **Johnny's MBP:** `100.122.212.128` via Tailscale, ssh alias `mbp`, user `austinholland`
- **Workspace:** `~/.openclaw/workspace/` on the MBP
- **Foundation docs:** `workspace/johnny/framing.md`, `architecture.md`, `vision.md`, `decisions/`
- **Pipeline files:** `feed-pipeline.lobster`, `compile-wiki.lobster`, `analysis-pulse.lobster`, `compile-prompt.md`, `output-prompt.md`
- **Crons:** unix crontab (analysis-pulse minute cron, daily backup 11 PM) + openclaw crons at `~/.openclaw/cron/jobs.json` (compile-trigger, output-trigger, tomorrow's briefing, SF sync, skill evolution, weekly lint)
- **Wiki:** `workspace/wiki/` — articles, index, log, metrics/
- **Metrics dashboard:** synced to `~/Desktop/wiki-vault/metrics/` via GitHub (private repo `raustinholland-dot/johnny-workspace-backup`), pulled by launchd `com.austin.vault-sync` every 60s

## Sibling command: `/johnny-testing`

When Austin says we are testing the pipeline (running a real input through Telegram and verifying the full chain), invoke `/johnny-testing` **instead of** winging it. That command pulls every file involved in end-to-end verification: the pipeline definitions, the session-jsonl walk procedure, the Obsidian dashboard definition, the metrics finalizer, and the standing rule that ground truth lives in session jsonls — not in `wiki/metrics/run-*.md`.

Both `/johnny` and `/johnny-testing` are **living commands.** When we change the pipeline, add a verification step, discover a new gotcha, or move a file, update the relevant command file in this repo (`.claude/commands/johnny.md`, `.claude/commands/johnny-testing.md`) in the same session. The cost of a stale slash command is that next session starts from the wrong map.

## What this command replaces

- `/johnny-ops` — STALE. Points to `johnny-rebuild-2026-04-06.md` and the retired Writer/Verifier sub-agent architecture. Ignore it until someone updates or removes it.
- Passive memory-pointer reading. The MEMORY.md index shows hints; this command actually pulls the authoritative docs into context.

## Standing rules (from memory, reinforced here)

- **Architectural decisions go to `~/.openclaw/workspace/johnny/decisions/` on the MBP**, not just local Claude Code memory. Filename: `YYYY-MM-DD-<slug>.md`. scp the file up, then `git add + commit + push` from inside the workspace so the nightly backup and live pushes carry it.
- **After session changes on the MBP**, prompt to commit + sync before ending (the old "never commit without asking" default doesn't apply to this workflow — that IS the standing ask).
- **If you miss an instruction**, treat it as a pointer failure, not an agent failure. Fix the pointer — the memory, the command, or this file — not yourself.
- **For destructive operations** (rm, git reset --hard, force push, dropping files): always confirm first.
- **Never use `rm`** — always `mv ~/.Trash/` (per CLAUDE.md).
