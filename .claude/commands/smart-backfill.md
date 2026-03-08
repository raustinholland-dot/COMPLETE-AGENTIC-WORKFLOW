---
name: smart-backfill
description: >
  Reconstruct a deal's history chronologically using calendar events as backbone,
  email thread deduplication, and milestone-based scoring. Use when Austin wants to
  backfill a deal with historical content (transcripts, emails, attachments) in
  chronological order with proper scoring progression.
argument-hint: "<deal_name> or 'all'"
---

# /smart-backfill — Intelligent Deal Timeline Reconstruction

Reconstruct a deal's history chronologically using calendar events as the backbone, email thread deduplication, and milestone-based scoring.

**Arguments:** `$ARGUMENTS`
- If a deal name (e.g. `velentium`): process only that deal
- If `all`: process all deals with backfill directories that haven't been smart-backfilled yet
- If empty: show available deals and their status

## What It Does

The smart backfill process:
1. **Calendar backbone** — Pulls calendar events from Postgres to anchor the timeline
2. **File classification** — Transcripts, voice memos, emails, PDFs, presentations
3. **Email thread dedup** — Groups by normalized subject, extracts only net-new content per reply, skips quoted-only replies (<50 chars)
4. **Milestone batching** — Groups content into scoring milestones:
   - Call transcripts → standalone milestone (always scores)
   - PDFs/PPTXs → standalone milestone (always scores)
   - Email exchanges → weekly groups (scores only if client responded)
   - Voice memos/research → bundled with nearest milestone (no scoring)
   - Same-day milestones are merged (one score per day max)
5. **Chronological ingestion** — Processes milestones in date order, scoring after each
6. **Resume support** — Progress saved to `backfill/_state/smart_progress.json`

## Steps

### 1. If no arguments: show status

Run the smart_backfill.py script with no args to show available deals:

```bash
cd "/Users/austinhollsnd/Desktop/COMPLETE AGENTIC WF/deal-intelligence-engine" && python3 scripts/smart_backfill.py 2>&1
```

Report the status and ask Austin which deal to run.

### 2. Dry run first (ALWAYS)

Before any real ingestion, ALWAYS run a dry-run first and show Austin the timeline:

```bash
cd "/Users/austinhollsnd/Desktop/COMPLETE AGENTIC WF/deal-intelligence-engine" && python3 scripts/smart_backfill.py --deal $ARGUMENTS --dry-run 2>&1
```

Present the milestone plan to Austin. Highlight:
- Number of milestones and scoring triggers
- Calendar event matches
- Email dedup stats (total → unique)
- Any transcripts without calendar matches (potential date issues)
- Estimated time

### 3. Ask for confirmation

**Always ask Austin before running the real backfill.** Show the dry-run results and ask:
- "This looks right — proceed?" or
- "Want me to adjust anything first?"

### 4. On confirmation — execute

Run the real backfill with `--clean` to wipe existing data and start fresh:

```bash
cd "/Users/austinhollsnd/Desktop/COMPLETE AGENTIC WF/deal-intelligence-engine" && python3 scripts/smart_backfill.py --deal $ARGUMENTS --clean 2>&1
```

The `--clean` flag:
- Deletes existing Qdrant chunks, ingestion_log, deal_health, deal_stakeholders, deal_notifications for the deal
- Preserves the deals row, calendar_events, and outputs_log
- Resets smart_progress so it starts from milestone 1

After each milestone scores, the `scored_at` timestamp is **backdated** to the milestone's real date — so the deal_health table shows a historically accurate score progression.

This will take 2-20 minutes depending on the deal size (each scoring milestone waits ~120s for CW-02).

After completion, report:
- Score progression (date → score → CAS)
- Total chunks ingested
- Any errors

### 4a. Verify results

After the backfill completes, run verification:

```bash
PGPASSWORD=$(grep POSTGRES_PASSWORD "/Users/austinhollsnd/Desktop/COMPLETE AGENTIC WF/deal-intelligence-engine/.env" | cut -d= -f2) psql -h localhost -p 5433 -U clearwater -d clearwater_deals -c "SELECT scored_at::date, pain_score p, power_score po, vision_score v, value_score va, change_score ch, control_score co, (pain_score+power_score+vision_score+value_score+change_score+control_score) as total, critical_activity_stage cas, trigger_type FROM deal_health WHERE deal_id='<deal_id>' ORDER BY scored_at"
```

Present the score progression table to Austin for review.

### 5. If `all` — guided deal-by-deal walkthrough

Do NOT auto-run all deals. Instead, present each deal one at a time and wait for Austin's go-ahead:

1. **List all remaining deals** — run `smart_backfill.py` with no args to show status (which deals have backfill folders, which have already been smart-backfilled, file counts per deal)

2. **For each deal**, before running the dry-run:
   - Tell Austin which deal is next
   - Show a quick preview: file count breakdown (transcripts, emails, PDFs, etc.)
   - Flag anything notable: e.g. "this deal has 0 calendar events" or "only emails, no transcripts" or "this deal is archived/internal — skip?"
   - **Wait for Austin to say "go" or "skip"** before running the dry-run

3. **After dry-run**, present the milestone plan per Step 2-3 above and wait for confirmation before executing

4. **After execution**, report results (scores, chunks, errors) before moving to the next deal

This ensures Austin stays in control of each deal and can skip, reorder, or flag issues as they come up.

## Important Notes

- **Always use `--clean` for first run on a deal** — ensures a fresh, accurate timeline
- Re-running with `--clean` is safe — it wipes and rebuilds from scratch
- Without `--clean`, dedup via `ON CONFLICT (message_id) DO NOTHING` prevents duplicates
- Progress is saved after each milestone — if interrupted, it resumes where it left off
- To reset progress for a deal: delete the entry from `backfill/_state/smart_progress.json`
- **Scores are backdated** — deal_health.scored_at reflects the milestone date, not today
- Voice memos marked "Call Type: internal excerpt" are Austin's personal notes — they ARE deal content, classified as voice_memo
- Transcripts without dates in filenames are matched to calendar events by attendee name matching
- Call transcript dates are snapped to their matching calendar event date
- **Outbound emails → outputs_log**: Emails FROM Clearwater domains are extracted and inserted into `outputs_log` as historical Prior Outputs. Classified as `follow_up_email` (external recipients), `pre_call_planner` (internal + prep/agenda keywords), or `internal_team_update` (internal default). `triggered_by=backfill_historical`. Deduped by deal+subject+date. The Ghostwriter/Concierge automatically see these as prior communication history.

## Use sub-agents

When running the actual backfill (step 4), use a sub-agent to execute the command so it doesn't block the main context. The sub-agent should run the command and report back the results.
