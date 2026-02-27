# Clearwater Deal Intelligence Engine - Testing Guide

**Phase 1**: Ingestion Pipeline Testing
**Version**: 1.0
**Last Updated**: February 26, 2026

---

## Testing Overview

This guide covers comprehensive testing scenarios for the Gmail → Qdrant ingestion pipeline. All tests assume you've completed the deployment steps in `DEPLOYMENT.md`.

---

## Pre-Test Checklist

Before running tests, verify:

```bash
cd deal-intelligence-engine

# ✅ All 5 services running
docker compose ps | grep -E "Up|healthy" | wc -l  # Should be 5

# ✅ n8n workflow active
# Manual check: http://localhost:5678 > Workflows > "Ingestion Pipeline" shows "Active"

# ✅ Credentials configured
# Manual check: http://localhost:5678 > Settings > Credentials shows 7 credentials

# ✅ Qdrant collection ready
curl -s http://localhost:6333/collections/deals | jq '.result.status'  # Should be "green"
```

---

## Test Suite

### Test 1: Happy Path - Forwarded Calendar Invite (New Deal)

**Objective**: Verify complete end-to-end flow from Gmail to Qdrant using the true first artifact for a new deal — a forwarded Google Calendar invite. This is what Austin sends to prospects when scheduling the initial discovery call, forwarding a copy to the ingestion inbox at the same time.

**How to send**: Forward (or manually compose) a calendar invite email to the ingestion inbox, mimicking what Gmail sends when you forward a Google Calendar event.

**Test Data**:
```
To: raustinholland+echo@gmail.com
Subject: Fwd: Discovery Call - Acme Hospital + Clearwater Security
From: Your regular Gmail account (raustinholland@gmail.com)
Body:

---------- Forwarded message ---------
From: Austin Hollins <raustinholland@gmail.com>
Date: Thu, Feb 26, 2026 at 9:14 AM
Subject: Discovery Call - Acme Hospital + Clearwater Security
To: Dr. Sarah Johnson <sjohnson@acmehospital.org>
Cc: Tom Wilson <twilson@acmehospital.org>

Sarah, Tom —

Looking forward to connecting on Thursday. I've sent the calendar invite below.
Agenda for our 45-minute call:

1. Overview of Acme Hospital's current security and compliance posture
2. Walk through your recent HIPAA SRA findings
3. Discuss Clearwater's engagement approach and methodology
4. Align on next steps

Please let me know if the time doesn't work and we can find an alternative.

Best,
Austin Hollins
Account Executive, Clearwater Security & Compliance
austin.hollins@clearwatercompliance.com | (615) 555-0142

--- Calendar Invite Details ---
Event: Discovery Call - Acme Hospital + Clearwater Security
Date: Thursday, March 5, 2026
Time: 10:00 AM – 10:45 AM CT
Location: Zoom (link: https://zoom.us/j/123456789)
Organizer: Austin Hollins <raustinholland@gmail.com>
Guests:
  - Dr. Sarah Johnson, CIO, Acme Hospital <sjohnson@acmehospital.org> ✓ Accepted
  - Tom Wilson, CISO, Acme Hospital <twilson@acmehospital.org> ✓ Accepted
  - Austin Hollins <raustinholland@gmail.com>

Description:
Initial discovery call to explore how Clearwater can support Acme Hospital's
cybersecurity and HIPAA compliance program. Acme is a 400-bed regional health
system in Nashville, TN that recently completed an external SRA with 23 open
findings. Key contacts are Dr. Sarah Johnson (CIO) and Tom Wilson (CISO).
CFO Jane Doe has approved budget exploration for 2026.

Test ID: test-001-happy-path-2026-02-26
```

**Steps**:
1. Send email to ingestion inbox
2. Wait up to 2 minutes (Gmail Trigger polls every 1 minute)
3. Navigate to n8n > Executions
4. Click latest execution

**Expected Results**:
- ✅ Execution status: Success (all nodes green)
- ✅ Gmail Trigger: Captured email with correct subject
- ✅ AI Classify node output:
  ```json
  {
    "company_name": "Acme Hospital",
    "confidence": "high",
    "confidence_score": 0.90+,
    "doc_type": "calendar_invite"
  }
  ```
- ✅ Deduplication Check: Empty result (new email, no prior `message_id`)
- ✅ New deal created: `deal_id` = `cw_acmehospital_2026` inserted to `deals` table
- ✅ Contextual Enrichment: Chunk(s) prepended with `[DEAL CONTEXT]` header
- ✅ OpenAI Embeddings: Vectors generated successfully
- ✅ Qdrant Insert: Success
- ✅ Postgres Log: 1 row in `ingestion_log`

**Validation Queries**:
```bash
# Check ingestion_log
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT message_id, deal_id, doc_type, chunk_count, sender_email \
   FROM ingestion_log \
   WHERE subject LIKE '%Acme Hospital%' \
   ORDER BY ingested_at DESC LIMIT 1;"

# Expected: 1 row, doc_type = 'calendar_invite', chunk_count >= 1

# Check new deal record was created
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT deal_id, company_name, sender_domains, is_active \
   FROM deals WHERE company_name LIKE '%Acme%';"

# Expected: 1 row with deal_id = "cw_acmehospital_2026", is_active = true

# Check Qdrant vectors
curl -X POST http://localhost:6333/collections/deals/points/scroll \
  -H "Content-Type: application/json" \
  -d '{"limit": 10, "with_payload": true, "with_vector": false, "filter": {"must": [{"key": "company_name", "match": {"value": "Acme Hospital"}}]}}' \
  | jq '.result.points | length'

# Inspect a chunk payload to verify contextual enrichment and doc_type
curl -X POST http://localhost:6333/collections/deals/points/scroll \
  -H "Content-Type: application/json" \
  -d '{"limit": 1, "with_payload": true, "with_vector": false, "filter": {"must": [{"key": "company_name", "match": {"value": "Acme Hospital"}}]}}' \
  | jq '.result.points[0].payload'

# Expected payload fields: deal_id, company_name, doc_type="calendar_invite",
# sender_domain, chunk_index, date_created, attribution_confidence
```

**Pass Criteria**:
- All nodes executed successfully
- New deal row created in `deals` table (first artifact = new deal)
- Vectors queryable in Qdrant
- `doc_type` correctly identified as `calendar_invite`

---

### Test 2a: Happy Path - Follow-up Call Transcript (Existing Deal)

**Objective**: Verify that a call transcript sent after the calendar invite correctly associates with the existing deal rather than creating a duplicate deal record. Tests the existing-deal lookup path and multi-chunk splitting.

**Prerequisite**: Test 1 must have passed (Acme Hospital deal exists in `deals` table).

**How to send**: Email the transcript as a `.txt` attachment OR paste it directly in the email body.

**Test Data**:
```
To: raustinholland+echo@gmail.com
Subject: Call Transcript - Acme Hospital Discovery Call 2026-03-05
From: Your regular Gmail account
Body (or attach as acme-hospital-discovery-call.txt):

CALL TRANSCRIPT
Date: March 5, 2026
Duration: 47 minutes
Participants:
  - Austin Hollins, Account Executive, Clearwater Security & Compliance
  - Dr. Sarah Johnson, Chief Information Officer, Acme Hospital
  - Tom Wilson, CISO, Acme Hospital

---

Austin: Sarah, Tom — thanks for making time today. I know you're both busy.
Before we dive in, can you give me a quick picture of Acme Hospital's current
situation from a security and compliance standpoint?

Sarah: Sure. So Acme is a 400-bed regional health system here in Nashville.
We've been growing pretty fast — we acquired two smaller clinics in 2024 —
and honestly our security program hasn't kept up. We had an external HIPAA
security risk assessment done last fall and the results were not great.
We came out with 23 open findings, several of them high severity.

Austin: That's a significant number. What was the reaction from leadership
when those results came back?

Sarah: Our CFO, Jane Doe, was alarmed. She brought it straight to the board.
We've had a couple of incidents in the past 18 months — nothing public, but
enough to make everyone nervous. Jane has made this a 2026 priority and
she's allocated budget. We're looking at somewhere in the $150,000 to
$200,000 range depending on scope.

Austin: And Tom, from your side — what are the biggest gaps you're seeing
day to day?

Tom: Honestly, it's a few things. One is we don't have a mature third-party
risk management program. We've got 60-plus vendors with access to PHI and
we're basically doing nothing to vet them. Two is our incident response plan
hasn't been updated since 2021 and it's never been tested. And three —
and this is the one that keeps me up at night — our security awareness
training is basically a checkbox exercise. People are still clicking phishing
links in our simulations.

Austin: Those are all addressable. Clearwater has done a lot of work in
exactly these areas. Can I ask — how did you hear about us?

Sarah: A colleague of mine, the CIO at St. Thomas Health, recommended you.
She said you did a full SRA for them last year and it was one of the
most practical, actionable assessments she'd ever seen. That's what we
want — something we can actually execute on, not a 200-page report that
sits on a shelf.

Austin: That's exactly how we approach it. Let me ask about your timeline.
Jane has flagged this as a 2026 priority — is there a specific deadline
driving that? Board meeting, renewal cycle, anything like that?

Sarah: We have a board presentation in June where Jane wants to show
meaningful progress. And we have a cyber insurance renewal in August —
our broker has told us we need to show significant improvement or we're
looking at a 30% premium increase. So the pressure is real.

Austin: Understood. That gives us a clear window. Tom, in terms of internal
resources — if we ran a full Security Risk Assessment and a third-party
risk program build-out, what would your team be able to contribute?

Tom: We have two security analysts I can dedicate part-time. And I can
personally commit probably 8 to 10 hours a week during the engagement.
We've tried to do some of this ourselves but we just don't have the
specialized expertise.

Austin: That's actually a good setup — our model works best when we have
a real internal counterpart, not just a handoff. One thing I want to
understand better — when it comes to the final decision on a contract
like this, who's in the room? Is it you, Sarah, Jane, or all three?

Sarah: Jane makes the final call on anything above $100K. But she won't
move without Tom's and my recommendation. So if Tom and I are aligned,
Jane typically follows. She trusts our judgment on the technical side.

Austin: Got it. So the real audience for an approach document or proposal
would be the two of you first, and then you'd present to Jane. Is that
right?

Sarah: Exactly. And I'll be honest — Jane is very numbers-oriented. If
we come to her with a clear ROI story — cost of a breach versus cost of
the engagement, potential fine exposure — that will land well with her.

Austin: We can absolutely build that case. We have benchmarking data from
healthcare systems your size. The average cost of a HIPAA breach for a
hospital like Acme is north of $2 million when you factor in OCR fines,
remediation, and reputational damage. Framing your $180K investment against
that risk profile is a strong story.

Tom: That's exactly the kind of language Jane responds to.

Austin: Let me propose next steps. I'd like to put together a brief
Approach Document that outlines what a Clearwater SRA engagement looks
like for Acme specifically — scope, methodology, timeline, and a rough
investment range. I'd target getting that to you by March 12th. Does that
work?

Sarah: That works. Can you include something on the third-party risk
program? That's Tom's biggest pain point and if we can address both in
one engagement, it's a much easier sell.

Austin: Absolutely. I'll scope it as a combined SRA plus TPRM program
build. One more question — do you have any other vendors you're evaluating
for this, or are you talking to Clearwater exclusively right now?

Sarah: We had a conversation with one other firm last month but honestly
they weren't a fit — too enterprise-focused, not enough healthcare expertise.
You're the only active conversation at this point.

Austin: Good to know. I'll get that Approach Document to you by March 12th.
Tom, Sarah — really appreciate your time today. This sounds like a great fit.

Sarah: Thanks Austin. Looking forward to seeing what you put together.

Tom: Same here. Talk soon.

---
END TRANSCRIPT

Test ID: test-002a-transcript-2026-03-05
```

**Expected Results**:
- ✅ AI Classify: `doc_type = "call_transcript"`, company = "Acme Hospital", confidence = high
- ✅ Deal lookup finds existing `cw_acmehospital_2026` — NO new row created in `deals`
- ✅ Text split into 4-6 chunks
- ✅ All chunks stored in Qdrant under `deal_id = cw_acmehospital_2026`
- ✅ `ingestion_log` now has 2 rows for Acme Hospital (invite + transcript)

**Validation Queries**:
```bash
# Confirm still only 1 deal record (no duplicate)
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT COUNT(*) FROM deals WHERE company_name LIKE '%Acme%';"
# Expected: 1

# Confirm 2 ingestion_log entries now
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT doc_type, chunk_count, ingested_at FROM ingestion_log \
   WHERE deal_id = 'cw_acmehospital_2026' ORDER BY ingested_at;"
# Expected: 2 rows — calendar_invite then call_transcript

# Confirm Qdrant now has vectors from both artifacts
curl -X POST http://localhost:6333/collections/deals/points/scroll \
  -H "Content-Type: application/json" \
  -d '{"limit": 20, "with_payload": true, "with_vector": false, "filter": {"must": [{"key": "deal_id", "match": {"value": "cw_acmehospital_2026"}}]}}' \
  | jq '.result.points | length'
# Expected: 5-7 total vectors (1 from invite + 4-6 from transcript)
```

---

### Test 2b: Deduplication - Duplicate Email Prevention

**Objective**: Verify the same email sent twice only processes once

**Steps**:
1. Forward the Test 1 calendar invite again (exact same content) to ingestion inbox
2. Wait 5 minutes
3. Check n8n Executions

**Expected Results**:
- ✅ New execution appears
- ✅ Deduplication Check node returns existing `message_id`
- ✅ Workflow terminates early (nodes after dedup check are NOT executed)
- ✅ Qdrant Insert node: NOT executed (grayed out)
- ✅ Postgres Log node: NOT executed

**Validation**:
```bash
# Count entries for same subject
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT COUNT(*) as entry_count \
   FROM ingestion_log \
   WHERE subject LIKE '%Acme Hospital Security Assessment%'"

# Expected: Still 1 (not 2)

# Verify same message_id
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT message_id, COUNT(*) as count \
   FROM ingestion_log \
   WHERE subject LIKE '%Acme Hospital%' \
   GROUP BY message_id \
   HAVING COUNT(*) > 1"

# Expected: Empty result (no duplicates)
```

**Pass Criteria**:
- Second execution terminates at dedup check
- No duplicate entries in `ingestion_log`
- No duplicate vectors in Qdrant

---

### Test 3: Low-Confidence Attribution - Human Confirmation Queue

**Objective**: Verify ambiguous emails route to attribution queue for human review

**Test Data**:
```
To: raustinholland+echo@gmail.com
Subject: Quick question
From: personal-email@example.com (NOT a known sender domain)
Body:
Hi,

I have a question about your compliance software offerings.

Can you send me more information?

Thanks
```

**Steps**:
1. Send email
2. Wait 5 minutes
3. Check n8n execution

**Expected Results**:
- ✅ Execution status: Success
- ✅ AI Classify node output:
  ```json
  {
    "company_name": "Unknown",
    "confidence": "low",
    "confidence_score": 0.3,
    "doc_type": "email"
  }
  ```
- ✅ Workflow routes to "Queue for Confirmation" branch
- ✅ Postgres: INSERT to `attribution_queue` table
- ✅ Qdrant Insert: NOT executed (low confidence = no auto-processing)

**Validation**:
```bash
# Check attribution queue
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT message_id, subject, ai_guess_company, ai_confidence, resolution \
   FROM attribution_queue \
   WHERE resolution = 'pending' \
   ORDER BY queued_at DESC LIMIT 5"

# Expected: Entry with subject "Quick question", resolution = "pending"

# Verify NOT in ingestion_log
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT COUNT(*) FROM ingestion_log WHERE subject = 'Quick question'"

# Expected: 0 (not processed until human confirms)
```

**Pass Criteria**:
- Email queued in `attribution_queue` with `resolution='pending'`
- NOT processed to Qdrant or `ingestion_log`
- Workflow completes successfully without errors

---

### Test 4: Medium-Confidence Attribution - Auto-Assign with Context

**Objective**: Verify medium-confidence emails auto-assign based on content analysis

**Test Data**:
```
To: raustinholland+echo@gmail.com
Subject: Follow-up discussion
From: unknown-sender@hospitaldomain.org
Body:
Austin,

Following up on our conversation about the cybersecurity assessment for St. Mary's Regional Hospital.

Our team reviewed the proposal and we'd like to schedule a call next week to discuss budget and timeline.

Looking forward to your response.

Best,
Michael Chen
IT Director
```

**Expected Results**:
- ✅ AI Classify: company_name = "St. Mary's Regional Hospital", confidence = "medium" (0.5-0.8)
- ✅ Auto-assigned to deal based on company name match
- ✅ Processed to Qdrant and `ingestion_log`

**Validation**:
```bash
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT deal_id, company_name FROM deals WHERE company_name LIKE '%Mary%'"
```

**Pass Criteria**:
- Medium confidence triggers auto-assignment
- Email processed normally (not queued)

---

### Test 5: Email with PDF Attachment

**Objective**: Verify PDF attachment text extraction and vectorization

**Test Data**:
- Create a 2-page PDF with sample deal content (use Google Docs > Download as PDF)
- Email to ingestion inbox with PDF attached

**Expected Results**:
- ✅ Gmail node: Attachment detected
- ✅ Extract from File node: PDF text extracted
- ✅ Postgres `ingestion_log`: `attachment_count = 1`
- ✅ Chunk count includes PDF content
- ✅ Qdrant vectors include PDF text

**Validation**:
```bash
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT attachment_count, chunk_count FROM ingestion_log ORDER BY ingested_at DESC LIMIT 1"

# Expected: attachment_count = 1, chunk_count > 5 (depending on PDF size)
```

**Note**: If PDF extraction fails, this is documented as a Phase 1.5 enhancement. Workflow should handle gracefully with warning log.

---

### Test 6: Long Email (Chunking Validation)

**Objective**: Verify proper text chunking with 500-token segments and 50-token overlap

**Test Data**:
Send email with ~2000-word body (approximately 3000 tokens):
```
Subject: Comprehensive Security Assessment Report - Acme Hospital

[Paste 2000-word document about HIPAA compliance, security vulnerabilities, remediation plan]
```

**Expected Results**:
- ✅ Text split into ~6-7 chunks (500 tokens each, 50 overlap)
- ✅ Contextual enrichment applied to each chunk
- ✅ Qdrant receives 6-7 separate vectors for this email
- ✅ Postgres `ingestion_log`: `chunk_count = 6` or 7

**Validation**:
```bash
# Check chunk count
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT chunk_count FROM ingestion_log ORDER BY ingested_at DESC LIMIT 1"

# Check Qdrant vectors for this email (by filtering on recent timestamp)
curl -X POST http://localhost:6333/collections/deals/points/scroll \
  -H "Content-Type: application/json" \
  -d '{"limit": 10, "with_payload": true, "with_vector": false}' | jq '.result.points | map(.payload.chunk_index)'
```

**Pass Criteria**:
- Proper segmentation (not one giant chunk)
- Chunk indices sequential (0, 1, 2, ...)
- Overlap preserved between chunks

---

### Test 7: Unicode and Special Characters

**Objective**: Verify handling of non-ASCII characters (emojis, foreign languages)

**Test Data**:
```
Subject: Project Update - Zürich Hospital 🏥
Body:
Bonjour Austin,

Quick update on the Zürich University Hospital project.

Budget: €250,000
Timeline: Q2 2026
Contact: François Müller

Key points:
✓ Executive sponsor confirmed
✓ Pain point identified
✓ Next meeting: März 15th

Looking forward to the próxima reunión! 🎉

Best regards,
José García
```

**Expected Results**:
- ✅ Email processed without errors
- ✅ Unicode characters preserved in Qdrant payload
- ✅ OpenAI embeddings handle non-English text

**Validation**:
```bash
# Check if unicode preserved
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT subject FROM ingestion_log ORDER BY ingested_at DESC LIMIT 1"

# Should show: "Project Update - Zürich Hospital 🏥"
```

---

### Test 8: Large Email (Memory/Performance Test)

**Objective**: Verify handling of very long emails without memory issues

**Test Data**:
- Email with 10,000-word body (~15,000 tokens)
- Should generate ~30 chunks

**Expected Results**:
- ✅ Workflow completes (may take 30-60 seconds)
- ✅ No memory errors
- ✅ ~30 chunks created
- ✅ All vectors inserted to Qdrant

**Monitoring**:
```bash
# Watch n8n logs during processing
docker logs -f clearwater-n8n

# Check for errors
docker logs clearwater-n8n | grep -i "error\|memory"
```

**Pass Criteria**:
- Completes without errors
- Processing time < 2 minutes
- No Docker container restarts

---

### Test 9: Gmail API Rate Limit Handling

**Objective**: Verify graceful handling of API rate limits

**Test Steps**:
1. Send 10 emails rapidly (within 1 minute)
2. Monitor n8n executions
3. Check for rate limit errors

**Expected Results**:
- First 5-7 emails: Process normally
- If rate limit hit: Workflow logs error, retries after backoff
- Eventually all emails process (may take 15-20 minutes)

**Validation**:
```bash
# Check for rate limit errors in logs
docker logs clearwater-n8n | grep -i "quota\|rate"

# Count processed vs sent
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT COUNT(*) FROM ingestion_log WHERE ingested_at > NOW() - INTERVAL '30 minutes'"
```

---

### Test 10: Service Restart Recovery

**Objective**: Verify system recovers gracefully from service restarts

**Steps**:
1. Send test email
2. Immediately restart n8n:
   ```bash
   docker compose restart n8n
   ```
3. Wait for n8n to recover (30 seconds)
4. Check if email eventually processes

**Expected Results**:
- ✅ n8n restarts successfully
- ✅ Workflow remains active after restart
- ✅ Gmail Trigger resumes polling
- ✅ Email processes on next poll (within 5 minutes)

**Pass Criteria**:
- No data loss
- Workflow reactivates automatically
- Email processes successfully

---

## Validation Command Cheat Sheet

### Quick Health Check
```bash
# All services running
docker compose ps

# Recent ingestion activity
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT COUNT(*) as recent_ingestions FROM ingestion_log WHERE ingested_at > NOW() - INTERVAL '1 hour'"

# Qdrant vector count
curl -s http://localhost:6333/collections/deals | jq '.result.points_count'

# n8n workflow executions (requires API key from n8n UI)
# Manual check: http://localhost:5678/executions
```

### Detailed Ingestion Log Query
```bash
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT
    id,
    subject,
    deal_id,
    doc_type,
    chunk_count,
    attachment_count,
    sender_email,
    ingested_at
   FROM ingestion_log
   ORDER BY ingested_at DESC
   LIMIT 10"
```

### Qdrant Vector Query with Filters
```bash
# All vectors for specific deal
curl -X POST http://localhost:6333/collections/deals/points/scroll \
  -H "Content-Type: application/json" \
  -d '{
    "limit": 10,
    "with_payload": true,
    "with_vector": false,
    "filter": {
      "must": [
        {"key": "deal_id", "match": {"value": "cw_acmehospital_2026"}}
      ]
    }
  }' | jq '.result.points'
```

---

## Test Execution Record

Use this table to track test execution:

| Test # | Test Name | Date | Status | Notes |
|--------|-----------|------|--------|-------|
| 1 | Calendar Invite - New Deal | | ⬜ Pass / ❌ Fail | |
| 2a | Call Transcript - Existing Deal | | ⬜ Pass / ❌ Fail | |
| 2b | Deduplication | | ⬜ Pass / ❌ Fail | |
| 3 | Low-Confidence Attribution | | ⬜ Pass / ❌ Fail | |
| 4 | Medium-Confidence Attribution | | ⬜ Pass / ❌ Fail | |
| 5 | PDF Attachment | | ⬜ Pass / ❌ Fail | |
| 6 | Long Email Chunking | | ⬜ Pass / ❌ Fail | |
| 7 | Unicode/Special Chars | | ⬜ Pass / ❌ Fail | |
| 8 | Large Email | | ⬜ Pass / ❌ Fail | |
| 9 | Rate Limit Handling | | ⬜ Pass / ❌ Fail | |
| 10 | Service Restart | | ⬜ Pass / ❌ Fail | |

---

## Known Issues and Limitations (Phase 1)

1. **PDF Extraction**: May require additional n8n nodes (pdf-parse library) - documented as Phase 1.5 enhancement
2. **5-Minute Poll Delay**: Gmail Trigger polls every 5 minutes - not real-time
3. **No Thread Reconstruction**: Each email processed independently - thread context not automatically linked
4. **20MB Attachment Limit**: Files >20MB skipped with warning (n8n binary data limit)
5. **English-Only Optimized**: Text chunking assumes English - multilingual support untested

---

## Performance Benchmarks (Expected)

| Metric | Expected Value | Notes |
|--------|----------------|-------|
| Email processing time | 10-30 seconds | Depends on email size |
| Embedding time (per chunk) | 1-2 seconds | OpenAI API latency |
| Qdrant insertion | < 1 second | Local Docker, minimal latency |
| Total end-to-end latency | 5-10 minutes | Includes Gmail poll interval |
| Throughput | ~10-20 emails/day | Current volume (MVP) |
| Max email size | 10,000 words | ~30 chunks, ~60 seconds total |

---

## Acceptance Criteria Summary

Phase 1 is **COMPLETE** when:
- ✅ All 10 test scenarios pass
- ✅ No errors in n8n execution logs for standard emails
- ✅ Deduplication working (zero duplicate entries)
- ✅ Low-confidence routing to attribution_queue functional
- ✅ Qdrant vectors queryable and returning correct results
- ✅ Postgres schema populated with test data
- ✅ Service restarts don't cause data loss

---

## Next Steps After Testing

Once all tests pass:
1. **Proceed to Phase 2**: Deploy Deal Health Scoring Agent (workflow-02-deal-health.json)
2. **Monitor production usage**: Watch for edge cases not covered in testing
3. **Tune confidence thresholds**: Adjust based on real attribution accuracy
4. **Optimize performance**: If processing >50 emails/day, consider reducing poll interval to 1 minute

**Estimated Phase 1 Testing Time**: 2-3 hours for full test suite execution
