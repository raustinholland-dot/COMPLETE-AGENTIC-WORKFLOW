# Clearwater Deal Intelligence Engine — Testing Guide

**Phase 1 + 2**: Ingestion Pipeline & Deal Health Agent Testing
**Version**: 2.0
**Last Updated**: February 27, 2026
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
| 1 | Calendar Invite — Velentium (New Deal) | | ⬜ | Qdrant payload fix validation |
| 2 | Deduplication — Same Invite Again | | ⬜ | |
| 3 | Discovery Call Transcript — Existing Deal | | ⬜ | Multi-chunk, no new deal row |
| 4 | Low-Confidence Attribution Queue | | ⬜ | |
| 5 | Phase 2 Health Scoring (after CW-02 built) | | ⬜ | |

---

## Known Issues Going Into Testing

1. **`calendar_invite` doc_type routing** — The doc_type router sends `calendar_invite` to `Code: Extract Email Body` (email branch). This is correct behavior — calendar invites arrive as email bodies. No fix needed.
2. **HTTP Trigger Health Agent** — Returns error until Workflow 2 is built. `continueOnFail: true` is set, so the workflow completes successfully regardless.
3. **Postgres port** — External connections use port `5433` (not 5432). Docker `exec` commands connect internally and work normally.
4. **Velentium not pre-seeded** — By design. The system must create the deal record from scratch based on the calendar invite content.
