# Clearwater Deal Intelligence Engine — Testing Guide

**Phases 1-5**: Ingestion, Deal Health, Output Gen, Chat Agent, AD Tracker
**Version**: 6.0
**Last Updated**: March 5, 2026
**Test Deal**: Velentium Medical (velentiummedical.com) — real active deal

---

## Full Deal Lifecycle Test — Velentium (Real Data)

**Purpose:** Test the complete deal cycle end-to-end using real Velentium artifacts in chronological order. After each ingestion + scoring event, Austin interacts with the chat agent to generate outputs (follow-up emails, pricing requests, etc.), reviews them in the Draft Editor, and approves them. This tests the full loop: ingestion -> scoring -> output generation -> approval -> next artifact.

**Test Deal:** Velentium Medical (velentiummedical.com)
**Real Data Source:** `deal-intelligence-engine/backfill/velentium/`

### Prerequisites

Run the stage-setting command to wipe Velentium and start clean:

```bash
# Wipe all Velentium data
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c "
DELETE FROM deal_workstreams WHERE deal_id = 'cw_velentiummedical_2026';
DELETE FROM approach_doc WHERE deal_id = 'cw_velentiummedical_2026';
DELETE FROM deal_stakeholders WHERE deal_id = 'cw_velentiummedical_2026';
DELETE FROM deal_health WHERE deal_id = 'cw_velentiummedical_2026';
DELETE FROM calendar_events WHERE deal_id = 'cw_velentiummedical_2026';
DELETE FROM ingestion_log WHERE deal_id = 'cw_velentiummedical_2026';
DELETE FROM outputs_log WHERE deal_id = 'cw_velentiummedical_2026';
DELETE FROM agent_traces WHERE session_id LIKE '%velentiummedical%';
DELETE FROM n8n_chat_histories WHERE session_id LIKE '%velentiummedical%';
DELETE FROM deals WHERE deal_id = 'cw_velentiummedical_2026';
"

# Wipe Qdrant vectors
curl -s -X POST http://localhost:6333/collections/deals/points/delete \
  -H "Content-Type: application/json" \
  -d '{"filter":{"must":[{"key":"deal_id","match":{"value":"cw_velentiummedical_2026"}}]}}'

# Flush Redis
docker exec clearwater-redis redis-cli -a YtieuQERpDd6DT0F780EJw FLUSHDB

# Verify clean
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c "
SELECT 'deals' as tbl, count(*) FROM deals WHERE deal_id = 'cw_velentiummedical_2026'
UNION ALL SELECT 'deal_health', count(*) FROM deal_health WHERE deal_id = 'cw_velentiummedical_2026'
UNION ALL SELECT 'ingestion_log', count(*) FROM ingestion_log WHERE deal_id = 'cw_velentiummedical_2026';
"
```

### Test Steps

Each step follows the pattern: **Ingest -> Wait -> Verify Score -> Generate Output -> Review -> Approve -> Next**

#### Step 1: Calendar Invite (Jan 21)

**Ingest:**
```bash
curl -s -X POST http://localhost:5678/webhook/calendar-event-ingest \
  -H "Content-Type: application/json" \
  -d '{
    "eventId": "velentium-clearwater-20260121-1300",
    "subject": "Velentium | Clearwater",
    "start": "2026-01-21T13:00:00-05:00",
    "end": "2026-01-21T13:30:00-05:00",
    "organizer": "Austin Holland <Austin.Holland@clearwatersecurity.com>",
    "attendees": "Austin.Holland@clearwatersecurity.com;Richmond.Donnelly@clearwatersecurity.com;david.kolb@clearwatersecurity.com;uday.rao@velentiummedical.com;travis.bird@velentiummedical.com;afelsenthal@gppfunds.com",
    "location": "Microsoft Teams Meeting",
    "bodyContent": "Microsoft Teams Meeting. Join the meeting now."
  }'
```

**Wait:** 45 seconds

**Expected:** Deal created at Discover, 1 deal_health row (calendar_only, all zeros, CAS=1A), no output generation needed for calendar-only.

#### Step 2: First Call Transcript (Jan 21)

**Ingest:**
```bash
python3 -c "
import json
from urllib.request import Request, urlopen
with open('deal-intelligence-engine/backfill/velentium/2026-01-21_transcript-05.txt') as f:
    content = f.read()
payload = {
    'messageId': 'real-velentium-call-20260121',
    'subject': 'Call Transcript - Velentium First Call 2026-01-21',
    'from': 'austin.holland@clearwatersecurity.com',
    'to': 'raustinholland+echo@gmail.com',
    'sentAt': '2026-01-21T14:30:00-05:00',
    'bodyContent': content
}
data = json.dumps(payload).encode()
req = Request('http://localhost:5678/webhook/outlook-email-ingest', data=data, headers={'Content-Type': 'application/json'})
resp = urlopen(req)
print(f'Status: {resp.status}')
"
```

**Wait:** 120 seconds

**Expected:** 2 deal_health rows, real P2V2C2 scores, CAS advanced

**Output Loop:**
1. Open Deal Room UI -> select Velentium
2. Review scores in left panel + Scoring tab
3. Ask chat: "Draft a follow-up email to Travis Bird" (or appropriate output)
4. Review draft in Draft Editor
5. Edit if needed, then approve
6. Verify in outputs_log

#### Step 3: Follow-up Email (actual email Austin sent)

**Ingest:** POST the real follow-up email Austin actually sent after the Jan 21 call. Use the email content from the backfill folder.

```bash
python3 -c "
import json
from urllib.request import Request, urlopen
with open('deal-intelligence-engine/backfill/velentium/emails-01.txt') as f:
    content = f.read()
payload = {
    'messageId': 'real-velentium-emails-01',
    'subject': 'Following up - Velentium & Clearwater Security',
    'from': 'austin.holland@clearwatersecurity.com',
    'to': 'travis.bird@velentiummedical.com',
    'sentAt': '2026-01-28T09:00:00-05:00',
    'bodyContent': content
}
data = json.dumps(payload).encode()
req = Request('http://localhost:5678/webhook/outlook-email-ingest', data=data, headers={'Content-Type': 'application/json'})
resp = urlopen(req)
print(f'Status: {resp.status}')
"
```

**Wait:** 120 seconds

**Expected:** Scores should adjust with email evidence, 3 deal_health rows

#### Step 4: Calendar Invite for Feb 5 Scope Review

**Ingest:** Send a calendar invite for the Feb 5 call.

```bash
curl -s -X POST http://localhost:5678/webhook/calendar-event-ingest \
  -H "Content-Type: application/json" \
  -d '{
    "eventId": "velentium-clearwater-20260205-1000",
    "subject": "Velentium Scope Review | Clearwater",
    "start": "2026-02-05T10:00:00-06:00",
    "end": "2026-02-05T11:00:00-06:00",
    "organizer": "uday.rao@velentiummedical.com",
    "attendees": "Austin.Holland@clearwatersecurity.com;Richmond.Donnelly@clearwatersecurity.com;steve.akers@clearwatersecurity.com;travis.bird@velentiummedical.com;uday.rao@velentiummedical.com;isabel.martinez@velentiummedical.com",
    "location": "Microsoft Teams Meeting",
    "bodyContent": "Scope review call for Clearwater security services engagement."
  }'
```

**Wait:** 45 seconds

**Expected:** 2 calendar_events rows, deal_health may or may not add a new row (depends on whether CW-02 triggers)

#### Step 5: Scope Review Call Transcript (Feb 5)

**Ingest:**
```bash
python3 -c "
import json
from urllib.request import Request, urlopen
with open('deal-intelligence-engine/backfill/velentium/2026-02-05_transcript-04.txt') as f:
    content = f.read()
payload = {
    'messageId': 'real-velentium-call-20260205',
    'subject': 'Call Transcript - Velentium Scope Review 2026-02-05',
    'from': 'austin.holland@clearwatersecurity.com',
    'to': 'raustinholland+echo@gmail.com',
    'sentAt': '2026-02-05T11:00:00-06:00',
    'bodyContent': content
}
data = json.dumps(payload).encode()
req = Request('http://localhost:5678/webhook/outlook-email-ingest', data=data, headers={'Content-Type': 'application/json'})
resp = urlopen(req)
print(f'Status: {resp.status}')
"
```

**Wait:** 120 seconds

**Expected:** Scores should increase significantly (detailed proposal-level evidence), CAS should advance, deal_stage should update

**Output Loop:**
1. Review updated scores in UI
2. Ask chat to draft appropriate outputs (pricing request, pre-call planner, internal team update, etc.)
3. Review and approve each draft
4. Verify all in outputs_log

#### Step 6: Additional Real Artifacts (as available)

Continue ingesting any additional real artifacts:
- Internal pricing request email
- Travis/Uday reply emails
- Any additional calendar invites or call transcripts

After each: verify score, generate outputs, review, approve.

### Verification Cheat Sheet

```bash
# Quick state check
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c "
SELECT 'deals' as tbl, count(*) FROM deals WHERE deal_id = 'cw_velentiummedical_2026'
UNION ALL SELECT 'deal_health', count(*) FROM deal_health WHERE deal_id = 'cw_velentiummedical_2026'
UNION ALL SELECT 'ingestion_log', count(*) FROM ingestion_log WHERE deal_id = 'cw_velentiummedical_2026'
UNION ALL SELECT 'outputs_log', count(*) FROM outputs_log WHERE deal_id = 'cw_velentiummedical_2026'
UNION ALL SELECT 'calendar_events', count(*) FROM calendar_events WHERE deal_id = 'cw_velentiummedical_2026';
"

# Score progression
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c "
SELECT scored_at, trigger_type, pain_score, power_score, vision_score, value_score, change_score, control_score, critical_activity_stage
FROM deal_health WHERE deal_id = 'cw_velentiummedical_2026' ORDER BY scored_at;
"

# Qdrant vector count
curl -s -X POST http://localhost:6333/collections/deals/points/count \
  -H 'Content-Type: application/json' \
  -d '{"filter":{"must":[{"key":"deal_id","match":{"value":"cw_velentiummedical_2026"}}]}}' \
  | python3 -c "import sys,json; print(f'Qdrant vectors: {json.load(sys.stdin)[\"result\"][\"count\"]}')"

# All ingestion log entries
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT id, deal_id, doc_type, chunk_count, sender_email, ingested_at FROM ingestion_log WHERE deal_id = 'cw_velentiummedical_2026' ORDER BY ingested_at;"

# Qdrant payloads (verify no nulls)
curl -s -X POST http://localhost:6333/collections/deals/points/scroll \
  -H "Content-Type: application/json" \
  -d '{"filter":{"must":[{"key":"deal_id","match":{"value":"cw_velentiummedical_2026"}}]},"limit": 20, "with_payload": true, "with_vector": false}' \
  | python3 -c "import sys,json; [print(f'{p[\"payload\"][\"doc_type\"]:20s} chunk {p[\"payload\"].get(\"chunk_index\",\"?\")}') for p in json.load(sys.stdin)['result']['points']]"
```

### Validation Checklist

- [ ] Calendar invite creates deal (CW-12 upsert working)
- [ ] Calendar-only zero-score placeholder inserted (CW-02 calendar branch)
- [ ] No feedback loop (exactly 1 deal_health row per ingestion event)
- [ ] Real transcript scores with meaningful P2V2C2 values
- [ ] deal_stage updates after scoring (CW-02 stage drift fix)
- [ ] Scoring tab shows clean timeline with score deltas
- [ ] Chat agent resolves deal_id on first iteration (no guessing)
- [ ] Output generation works (draft appears in Draft Editor)
- [ ] Draft approval works (status changes to 'sent')
- [ ] Markdown stripping working (no ###, ---, emojis in chat)
- [ ] Token usage reasonable (2-3 iterations, <20K tokens per query)

---

## Test Execution Record

| Step | Test Name | Date | Status | Notes |
|------|-----------|------|--------|-------|
| 1 | Calendar Invite (Jan 21) | 2026-03-05 | PASS | Deal created, zero-score placeholder, no loop |
| 2 | First Call Transcript (Jan 21) | 2026-03-05 | PASS | Scored 16/30, CAS=3A |
| 3 | Follow-up Email | | | |
| 4 | Calendar Invite (Feb 5) | | | |
| 5 | Scope Review Transcript (Feb 5) | | | |
| 6 | Additional Artifacts | | | |

---

## Fix Log

### 2026-03-05: CW-12 Calendar Sync — Deal-Exists Gate Removed
**Bug**: Gate blocked calendar invites from creating new deals when Velentium was wiped for testing.
**Fix**: Removed 4 gate nodes. Replaced with `Postgres: Upsert Deal` (INSERT ON CONFLICT DO UPDATE). Calendar invites now always create or update the deal.

### 2026-03-05: CW-12 Calendar Sync — Feedback Loop Disconnected
**Bug**: CW-12 re-triggered CW-02 after every calendar event, causing score thrashing (11 scoring events for Velentium).
**Fix**: `HTTP: Trigger Health Agent` node disconnected (orphaned, not deleted). Calendar events no longer trigger rescoring.

### 2026-03-05: CW-02 Deal Stage Drift Fix
**Bug**: CW-02 never updated `deals.deal_stage` after scoring. Deals stayed at "discover" regardless of CAS.
**Fix**: Added `Postgres: Update Deal Stage` node with CAS-to-stage mapping (1x->Discover, 2x->Qualify, 3x->Prove, 4x->Negotiate, 5x->Close).

### 2026-03-05: CW-03 Markdown Stripping
**Bug**: Claude responses contained markdown headers, horizontal rules, emojis, tables despite prompt rules.
**Fix**: Added post-processing in `Code: Chat Response` that strips headers->bold, removes hr/emojis, converts tables to plain text.

### 2026-03-05: CW-03 Deal ID Injection
**Bug**: Agent guessed wrong deal_id on first iteration, wasting 1-2 iterations and tokens.
**Fix**: Added `Code: Inject Deal ID` node between Chat Trigger and AI Agent. Prepends `[DEAL_SCOPE: xxx]` to chat input. System prompt references injected deal_id.

### 2026-03-05: CW-3c Scoring History Query
**Added**: `scoring_history` case in Postgres Query Webhook. Returns all deal_health rows with scores, justifications, CAS, narratives for the Scoring tab.

### 2026-03-05: UI Scoring Tab
**Added**: New Scoring tab in right panel. Timeline layout with connected dots, color-coded trigger badges, score deltas, CAS pills, expandable justifications.

### 2026-03-02: CW-05 Calendar Event Dedup
**Bug**: `Postgres: Insert Calendar Event` used `ON CONFLICT DO UPDATE`, always returned a row, always triggered CW-02 even for duplicates.
**Fix**: Added `RETURNING (xmax = 0) AS is_new_insert` + `IF: New Event?` gate. Duplicate events update the row but don't re-trigger scoring.
