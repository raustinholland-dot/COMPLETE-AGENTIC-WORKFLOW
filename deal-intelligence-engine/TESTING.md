# Clearwater Deal Intelligence Engine — Testing Guide

**Phases 1–5**: Ingestion, Deal Health, Output Gen, Chat Agent, AD Tracker
**Version**: 4.0
**Last Updated**: March 1, 2026
**Test Deal**: Velentium (velentium.com) — real active deal

---

## System State Going Into Testing

- Qdrant `deals` collection: **0 points** (clean slate)
- `ingestion_log`: **0 rows** (clean slate)
- `attribution_queue`: **0 rows** (clean slate)
- `deals` table: **25 rows** (real pipeline deals, Velentium NOT seeded — must be created by ingestion)
- CW-01 workflow: **Active** (bugs fixed 2026-02-27)

### Bugs Fixed Before This Test Run
1. **Qdrant payload empty** — metadata values (`deal_id`, `company_name`, `doc_type`, etc.) now use `.first().json` and include `date_created` and `message_id`
2. **Log Ingestion query** — converted from broken mixed mustache+expression syntax to proper JS template literal
3. **Check Duplicate query** — same fix applied

---

## Pre-Test Checklist

```bash
# All 5 services running
docker compose ps

# Qdrant clean and healthy
curl -s http://localhost:6333/collections/deals | jq '{points: .result.points_count, status: .result.status}'
# Expected: { "points": 0, "status": "green" }

# Postgres clean
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT COUNT(*) FROM ingestion_log; SELECT COUNT(*) FROM attribution_queue;"
# Expected: 0, 0

# Velentium NOT in deals table
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT deal_id FROM deals WHERE company_name ILIKE '%velentium%';"
# Expected: 0 rows
```

---

## Test Suite — Velentium Real Deal Flow

The tests below follow the real artifact sequence for a new Velentium deal from first touch.
Each test builds on the previous one — run them in order.

---

### Test 1: Discovery Call Calendar Invite (New Deal — First Artifact)

**Objective**: System sees Velentium for the first time via a forwarded calendar invite.
Must classify as `calendar_invite`, create a new deal record, and store vectors with correct payload.

**What to send**: Forward (or manually compose) an email to the ingestion inbox that looks like
a forwarded Google Calendar invite for a Velentium discovery call.

**Send to**: `raustinholland+echo@gmail.com`

**Sample email body**:
```
Subject: Fwd: Discovery Call — Velentium + Clearwater Security

---------- Forwarded message ---------
From: Austin Holland <Austin.Holland@clearwatersecurity.com>
Date: Thu, Feb 27, 2026 at 9:00 AM
Subject: Discovery Call — Velentium + Clearwater Security
To: Brad Brown <brad.brown@velentium.com>
Cc: Jennifer Lee <jennifer.lee@velentium.com>

Brad, Jennifer —

Looking forward to connecting Thursday. Calendar invite is below.
Agenda for our 45-minute call:

1. Overview of Velentium's current cybersecurity and compliance posture
2. Walk through any recent audit or risk assessment findings
3. Discuss Clearwater's engagement approach
4. Align on next steps

Best,
Austin Holland
Account Executive, Clearwater Security & Compliance
Austin.Holland@clearwatersecurity.com

--- Calendar Invite Details ---
Event: Discovery Call — Velentium + Clearwater Security
Date: Thursday, March 5, 2026
Time: 10:00 AM – 10:45 AM CT
Location: Zoom
Organizer: Austin Holland <Austin.Holland@clearwatersecurity.com>
Guests:
  - Brad Brown, CTO, Velentium <brad.brown@velentium.com> ✓ Accepted
  - Jennifer Lee, VP Operations, Velentium <jennifer.lee@velentium.com> ✓ Accepted
  - Austin Holland <Austin.Holland@clearwatersecurity.com>

Description:
Initial discovery call to explore how Clearwater can support Velentium's
cybersecurity and compliance program.
```

**Steps**:
1. Send to `raustinholland+echo@gmail.com`
2. Wait up to 2 minutes (trigger polls every 1 min)
3. Open n8n > Executions — click the new execution

**Expected Results**:
- All nodes green
- AI Classify output:
  ```json
  { "company_name": "Velentium", "confidence": "high", "doc_type": "calendar_invite" }
  ```
- New deal row created in `deals` table (`deal_id = cw_velentium_2026`)
- 1 row in `ingestion_log`
- Qdrant vectors written with correct payload

**Validation**:
```bash
# Check new deal record
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT deal_id, company_name, sender_domains FROM deals WHERE company_name ILIKE '%velentium%';"
# Expected: 1 row, deal_id = cw_velentium_2026

# Check ingestion log
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT message_id, deal_id, doc_type, chunk_count FROM ingestion_log ORDER BY ingested_at DESC LIMIT 1;"
# Expected: 1 row, doc_type = calendar_invite, chunk_count >= 1

# Check Qdrant payload — THIS is the key fix validation
curl -s -X POST http://localhost:6333/collections/deals/points/scroll \
  -H "Content-Type: application/json" \
  -d '{"limit": 5, "with_payload": true, "with_vector": false}' \
  | jq '.result.points[0].payload'
# Expected: { deal_id: "cw_velentium_2026", company_name: "Velentium", doc_type: "calendar_invite", ... }
# NOT: null or empty {}
```

**Pass Criteria**:
- Qdrant payload fields populated (not null/empty) — this is the primary fix being validated
- New deal row created in `deals` table
- `ingestion_log` has 1 row with correct `deal_id`

---

### Test 1a: CW-02 Shell Opportunity — Calendar-Only Zero-Score

**Objective**: Confirm CW-02 detects the calendar-only deal and inserts a zero-score placeholder rather than running the full Opus scoring pipeline. This is **correct expected behavior** for any new deal whose first (and only) artifact is a calendar invite.

**Prerequisite**: Test 1 passed. `cw_velentium_2026` exists with 1 `calendar_invite` in `ingestion_log`.

**How it works**:
- CW-01 fires CW-02 via `HTTP: Trigger Deal Health` after ingestion
- CW-02 runs `Postgres: Check Doc Types` → `total = 1`, `calendar_count = 1`
- `IF: Calendar Only?` = true → routes to `Code: Insert Placeholder Health` (skips RAG/Opus entirely)
- Zero-score row inserted with `trigger_type = 'calendar_only'`, `critical_activity_stage = '1A'`

**Validation**:
```bash
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT deal_id, pain_score, power_score, vision_score, value_score, change_score, control_score,
   trigger_type, critical_activity_stage, general_narrative, scored_at
   FROM deal_health WHERE deal_id = 'cw_velentium_2026' ORDER BY scored_at DESC LIMIT 1;"
# Expected: all scores = 0, trigger_type = 'calendar_only', CAS = '1A'
# general_narrative = 'New deal created from calendar invite. No scoring data available yet.'
```

**Pass Criteria**:
- `deal_health` row exists for the deal
- All P2V2C2 scores = 0
- `trigger_type = 'calendar_only'`
- Full Opus pipeline was NOT triggered (no RAG query executions in n8n execution log)

---

### Test 2: Deduplication — Same Invite Forwarded Again

**Objective**: Forwarding the same calendar invite a second time produces no new records.

**Steps**:
1. Forward the exact same email from Test 1 again
2. Wait 2 minutes
3. Check n8n execution

**Expected Results**:
- New execution fires
- `Postgres: Check Duplicate` finds existing `message_id`
- `Is New Email?` routes to the false branch — all downstream nodes skipped
- No new rows in `ingestion_log`
- No new vectors in Qdrant

**Validation**:
```bash
# Still only 1 ingestion_log row
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT COUNT(*) FROM ingestion_log WHERE deal_id = 'cw_velentium_2026';"
# Expected: 1

# Still same vector count as after Test 1
curl -s http://localhost:6333/collections/deals | jq '.result.points_count'
```

**Pass Criteria**: Zero duplicate records after second forward.

---

### Test 3: Discovery Call Transcript (Existing Deal, Multi-Chunk)

**Objective**: Call transcript for Velentium associates with the existing deal (no new deal row),
splits into multiple chunks, all stored with correct payload.

**Prerequisite**: Test 1 passed. `cw_velentium_2026` exists in `deals`.

**Send to**: `raustinholland+echo@gmail.com`

**Sample email body** (or attach as `velentium-discovery-call.txt`):
```
Subject: Call Transcript — Velentium Discovery Call 2026-03-05

CALL TRANSCRIPT
Date: March 5, 2026
Duration: 45 minutes
Participants:
  - Austin Holland, Account Executive, Clearwater Security & Compliance
  - Brad Brown, CTO, Velentium
  - Jennifer Lee, VP Operations, Velentium

---

Austin: Brad, Jennifer — thanks for making time today. Can you give me a picture
of where Velentium stands from a cybersecurity and compliance standpoint?

Brad: Sure. So we're a medical device engineering firm — we build life-critical
embedded systems for clients in the MedTech space. Most of our clients are subject
to FDA 21 CFR Part 11, some have IEC 62443 requirements, and we're increasingly
seeing HIPAA come into play when our devices touch patient data. Our challenge is
that our compliance posture hasn't kept pace with how fast we've grown. We tripled
headcount in the last two years and our security program is still sized for where
we were three years ago.

Austin: That's a significant gap. Has anything specific forced the issue recently?

Brad: Yes — we just went through a SOC 2 Type II audit and it surfaced gaps in our
access control and incident response processes. We passed, but barely. Our lead
auditor told us we need to remediate before the next cycle or we're at risk of a
qualified opinion. That would be a serious problem for our enterprise clients.

Austin: How did leadership react to that?

Jennifer: Our CEO flagged it immediately. We have a board presentation in Q2 and
he wants to show the board that we've got a credible remediation plan in place.
We also have three enterprise contracts up for renewal in the fall where security
posture is an explicit evaluation criterion. So the business consequences of not
fixing this are very real.

Austin: And Jennifer, from your side — what are the biggest operational pain points?

Jennifer: Vendor risk. We work with about 40 subcontractors who have varying levels
of access to our development environment and client data. We have basically no
formal third-party risk management process. It's all informal. And our incident
response plan hasn't been tested in two years.

Austin: Those are all solvable. Let me ask about the decision-making process. When
you're ready to move forward on an engagement like this, who's in the room?

Brad: Our CEO Marcus Chen makes the final call on anything above $50K. But he won't
move without Jennifer's and my recommendation. If we're aligned, Marcus typically
follows. He trusts our judgment on the technical and operational side.

Jennifer: And I'll be honest — Marcus is very ROI-oriented. He's going to want to
see the risk quantified in business terms, not just technical language.

Austin: We can build that case. The cost of a breach for a company in your position —
regulatory exposure, client notification, potential loss of enterprise contracts —
easily exceeds $1M. Framing a $150-200K engagement against that risk profile is
a compelling story. Let me propose next steps: I'd like to put together an Approach
Document that outlines a Clearwater SRA and third-party risk program build-out
specifically for Velentium. I can target that for March 12th. Does that work?

Brad: That works. Can you include something on the SOC 2 remediation roadmap?
That's our most time-sensitive item.

Austin: Absolutely. I'll scope it as a combined SRA, TPRM, and SOC 2 remediation
program. One more question — are you talking to any other vendors right now?

Brad: We had one conversation with a firm that was too enterprise-focused for our
stage. You're the active conversation.

Austin: Good to know. I'll get the Approach Document to you by March 12th.

---
END TRANSCRIPT
```

**Expected Results**:
- AI Classify: `doc_type = "call_transcript"`, company = "Velentium", confidence = high
- Deal lookup finds `cw_velentium_2026` — NO new row in `deals`
- Text splits into 4-7 chunks
- All chunks in Qdrant under `deal_id = cw_velentium_2026`
- `ingestion_log` now has 2 rows for Velentium

**Validation**:
```bash
# Still only 1 deal record (no duplicate)
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT COUNT(*) FROM deals WHERE company_name ILIKE '%velentium%';"
# Expected: 1

# Now 2 ingestion_log entries
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT doc_type, chunk_count, ingested_at FROM ingestion_log \
   WHERE deal_id = 'cw_velentium_2026' ORDER BY ingested_at;"
# Expected: 2 rows — calendar_invite, call_transcript

# Qdrant vector count increased (transcript = multiple chunks)
curl -s http://localhost:6333/collections/deals | jq '.result.points_count'
# Expected: more than after Test 1

# Verify all vectors have deal_id payload
curl -s -X POST http://localhost:6333/collections/deals/points/scroll \
  -H "Content-Type: application/json" \
  -d '{"limit": 20, "with_payload": true, "with_vector": false}' \
  | jq '[.result.points[] | {id: .id, deal_id: .payload.deal_id, doc_type: .payload.doc_type}]'
# Expected: all entries show deal_id = "cw_velentium_2026", none null
```

**Pass Criteria**:
- Only 1 deal row in `deals`
- Multiple chunks in Qdrant, all with correct payload
- `ingestion_log` has 2 rows

---

### Test 4: Low-Confidence Attribution — Unknown Sender

**Objective**: An ambiguous email from an unknown sender goes to `attribution_queue`, not Qdrant.

**Send to**: `raustinholland+echo@gmail.com`

**Sample**:
```
From: info@unknownclinic.org
Subject: Question about compliance services
Body: Hi, we're interested in learning more about your cybersecurity assessment services.
```

**Expected Results**:
- AI Classify: `confidence = "low"`
- Routes to `Postgres: Queue for Confirmation`
- Row in `attribution_queue` with `resolution = 'pending'`
- NOT in `ingestion_log`, NOT in Qdrant

**Validation**:
```bash
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT subject, ai_guess_company, ai_confidence, resolution FROM attribution_queue \
   WHERE resolution = 'pending' ORDER BY queued_at DESC LIMIT 3;"
```

---

### Test 5: Phase 2 Trigger — Deal Health Scoring (After Phase 2 Built)

**Objective**: After ingesting the discovery call transcript (Test 3), the HTTP trigger fires
and Workflow 2 scores Velentium's P2V2C2 dimensions from the RAG context.

**Prerequisite**: Workflow 2 (CW-02) built and active.

**Expected Results**:
- Webhook `POST /webhook/deal-health-trigger` returns 200
- Workflow 2 runs 15 RAG queries against Velentium namespace
- Claude Opus scores all 6 P2V2C2 dimensions (expect low scores — early Discover stage)
- New row inserted to `deal_health` table

**Expected Approximate Scores** (based on transcript content):
| Dimension | Expected | Reasoning |
|---|---|---|
| Pain | 2-3 | Pain articulated (SOC 2, TPRM), not yet validated by ES |
| Power | 1-2 | Know CEO is DM, but no direct access yet |
| Vision | 1-2 | Current/future state starting to emerge |
| Value | 1 | ROI discussed but not agreed |
| Change | 1-2 | Urgency exists (board, renewals) but no commitment |
| Control | 1 | No DAP yet |

**Validation**:
```bash
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT deal_id, pain_score, power_score, vision_score, value_score, change_score, \
   control_score, (pain_score+power_score+vision_score+value_score+change_score+control_score) AS total, \
   scored_at FROM deal_health WHERE deal_id = 'cw_velentium_2026' ORDER BY scored_at DESC LIMIT 1;"
```

---

## Validation Command Cheat Sheet

```bash
# Quick health check
curl -s http://localhost:6333/collections/deals | jq '{points: .result.points_count, status: .result.status}'

# All ingestion log entries
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT id, deal_id, doc_type, chunk_count, sender_email, ingested_at FROM ingestion_log ORDER BY ingested_at DESC;"

# All Qdrant payloads (verify no nulls)
curl -s -X POST http://localhost:6333/collections/deals/points/scroll \
  -H "Content-Type: application/json" \
  -d '{"limit": 50, "with_payload": true, "with_vector": false}' \
  | jq '[.result.points[] | {id: .id, deal_id: .payload.deal_id, doc_type: .payload.doc_type, company: .payload.company_name}]'

# All deals table
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT deal_id, company_name, deal_stage FROM deals ORDER BY created_at DESC LIMIT 5;"

# Attribution queue
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT subject, ai_guess_company, resolution FROM attribution_queue ORDER BY queued_at DESC LIMIT 5;"
```

---

## Test Execution Record

| Test # | Test Name | Date | Status | Notes |
|--------|-----------|------|--------|-------|
| 1 | Calendar Invite — Velentium (New Deal) | 2026-02-28 | ✅ | Qdrant payload fix validated, deal created |
| 1a | CW-02 Shell Opportunity — Calendar-Only Zero-Score | | ⬜ | Not yet run (Stallant test) |
| 2 | Deduplication — Same Invite Again | 2026-02-28 | ✅ | No duplicate records |
| 3 | Discovery Call Transcript — Existing Deal | 2026-02-28 | ✅ | Multi-chunk, no new deal row |
| 4 | Low-Confidence Attribution Queue | | ⬜ | Not yet run |
| 5 | Phase 2 Health Scoring | 2026-02-28 | ✅ | Velentium 17/30, golden record calibrated |
| 6 | Phase 3 Output Generation | 2026-02-28 | ✅ | Gmail sent, outputs_log inserted |
| 7 | Phase 4 Chat Agent smoke test | 2026-02-28 | ✅ | 28 deals returned, attribution queue surfaced |
| 8 | Phase 5 AD Tracker — end-to-end | 2026-03-01 | ✅ | See Phase 5 test results below |

---

## Phase 5 Test Results (2026-03-01)

### Agent 2 Phase 5 Fields — Velentium Verified
After CW-02 re-scored Velentium with Phase 5 additions:
- `key_objectives_strategic`: "Bifurcate security/compliance oversight from IT operations to eliminate conflict of interest" ✅
- `key_objectives_security`: Populated (SRA, TPRM, incident response) ✅
- `key_objectives_compliance`: Populated (HIPAA, SOC 2) ✅
- `inferred_workstreams`: `["mss", "siem_log_management", "mdr", "iso27001_assessment", "managed_azure_cloud", "vciso"]` ✅
- `delivery_staff_on_call`: `[{"name": "Steve Akers", "role": "delivery", "email": "steve.akers@clearwatersecurity.com"}]` ✅

### Agent 5 AD Tracker — Velentium Verified
- `approach_doc` table: 1 row created for `cw_velentium_2026` ✅
- `deal_workstreams` table: 6 rows inserted (one per inferred workstream) ✅
- Gap assessment: **correctly skipped** — Velentium is in Discover stage (gaps only fire for Qualify+) ✅
- AD Tracker fires async from CW-02 tail; CW-02 continues without waiting ✅

### Phase 5 Validation Commands
```bash
# Check approach_doc table
docker exec deal-intelligence-engine-postgres-1 psql -U clearwater -d clearwater_deals -c \
  "SELECT deal_id, pricing_requested, dc_principal_name, last_updated_at FROM approach_doc;"

# Check deal_workstreams
docker exec deal-intelligence-engine-postgres-1 psql -U clearwater -d clearwater_deals -c \
  "SELECT deal_id, service_slug, confidence, scoping_status FROM deal_workstreams WHERE deal_id = 'cw_velentium_2026';"

# Check deal_health Phase 5 fields
docker exec deal-intelligence-engine-postgres-1 psql -U clearwater -d clearwater_deals -c \
  "SELECT deal_id, key_objectives_strategic, inferred_workstreams, delivery_staff_on_call \
   FROM deal_health WHERE deal_id = 'cw_velentium_2026' ORDER BY scored_at DESC LIMIT 1;"

# Check clearwater_services seeded
docker exec deal-intelligence-engine-postgres-1 psql -U clearwater -d clearwater_deals -c \
  "SELECT COUNT(*) FROM clearwater_services;"
# Expected: 37

# Check clearwater_staff seeded
docker exec deal-intelligence-engine-postgres-1 psql -U clearwater -d clearwater_deals -c \
  "SELECT COUNT(*) FROM clearwater_staff;"
# Expected: 209

# Check clearwater_internal Qdrant collection
curl -s http://localhost:6333/collections/clearwater_internal | jq '{points: .result.points_count, status: .result.status}'
# Expected: { "points": 0, "status": "green" } — collection exists, docs not yet ingested
```

---

## Known Issues / Deferred Items (as of 2026-03-01)

1. **Test 4 (attribution queue)** — Not yet run. Low priority.
2. **`HTTP: Draft Declining Alert` in CW-02** — FIXED this session. Malformed JSON body (mixed mustache+expression syntax) replaced with `={{ JSON.stringify({...}) }}` pattern.
3. **`pricing_request` output type (CW-03)** — Not yet implemented. Agent 5 queues this gap type but CW-03 doesn't know how to generate it. Deferred pending Austin confirming Carter/Steve Teams message format.
4. **`clearwater_internal` Qdrant collection** — FIXED this session. 57 vectors ingested: security_engineering (5), managed_security_healthcare (6), bia_bcp (2), privacy_compliance_audit (42), managed_azure_cloud (2 inline). Script: `scripts/ingest-clearwater-internal.py`.
5. **`set_deal_hold` chat tool** — Not built. Austin sets `hold_until` via Metabase SQL runner for now.

## This Session — What Was Built (2026-03-01)

1. **Metabase dashboards** — 3 dashboards built via API:
   - Dashboard 1 (Command Center): http://localhost:3000/dashboard/2 — KPIs + bubble chart + pipeline bar + deal health matrix (conditional formatting)
   - Dashboard 2 (Deal Deep Dive): http://localhost:3000/dashboard/3 — P2V2C2 bars + trend line + stakeholders + activity feed, filtered by company name
   - Dashboard 3 (Scoring Audit Log): http://localhost:3000/dashboard/4 — full scoring history per deal
   - Command Center set as Metabase homepage

2. **Calendar invite ingestion (CW-01)** — 4 new nodes added, 31 total:
   - `Code: Parse ICS` — parses .ics attachment or inline VCALENDAR, extracts all fields
   - `Code: Build Calendar SQL` — builds safe SQL using sq() helper
   - `Postgres: Insert Calendar Event` — inserts into calendar_events table
   - `Code: Merge ICS Text` — packages event text for embed pipeline
   - `Route by Document Type` now has calendar as first output (5 total)
   - AI classifier updated to detect calendar_invite doc_type
   - Deployed and active

## Next Session — End-to-End Test Plan

**Goal**: Run a complete deal lifecycle from first calendar invite through health scoring.

**Pre-test: Clean Velentium from system** (since Velentium already exists from prior testing):
```bash
# Remove existing Velentium data to simulate fresh deal
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "DELETE FROM deal_health WHERE deal_id = 'cw_velentium_2026';
   DELETE FROM deal_stakeholders WHERE deal_id = 'cw_velentium_2026';
   DELETE FROM ingestion_log WHERE deal_id = 'cw_velentium_2026';
   DELETE FROM calendar_events WHERE deal_id = 'cw_velentium_2026';
   DELETE FROM approach_doc WHERE deal_id = 'cw_velentium_2026';
   DELETE FROM deal_workstreams WHERE deal_id = 'cw_velentium_2026';
   DELETE FROM deals WHERE deal_id = 'cw_velentium_2026';"

# Clear Qdrant vectors for this deal
curl -s -X POST http://localhost:6333/collections/deals/points/delete \
  -H "Content-Type: application/json" \
  -d '{"filter": {"must": [{"key": "deal_id", "match": {"value": "cw_velentium_2026"}}]}}'
```

**Test sequence** (run Tests 1-3 in TESTING.md in order, then verify health score + dashboards):

1. **Test 1**: Forward calendar invite → verify `calendar_events` row, deal created, vectors in Qdrant
2. **Test 2**: Dedup check
3. **Test 3**: Forward call transcript → verify multi-chunk ingestion
4. **Verify CW-02 fired**: Check `deal_health` table for new scoring row
5. **Verify CW-05 fired**: Check `approach_doc` and `deal_workstreams` tables
6. **Open Metabase**: Verify Velentium appears in Command Center matrix, Deep Dive shows scores
7. **Open chat widget**: Ask "What is the Velentium P2V2C2 score?" — verify correct answer
8. **Test output generation**: Ask chat agent to draft a follow-up email to Brad Brown, preview it, approve it

**New Test: Calendar Invite Creates Deal**
Verify the new ICS branch by checking:
```bash
# calendar_events table has the event
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT deal_id, title, start_time, meeting_type, attendees FROM calendar_events \
   WHERE deal_id = 'cw_velentium_2026';"

# Deal was created at Discover stage
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT deal_id, company_name, deal_stage, created_at FROM deals \
   WHERE deal_id = 'cw_velentium_2026';"
```
