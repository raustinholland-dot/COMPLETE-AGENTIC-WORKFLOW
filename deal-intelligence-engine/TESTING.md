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

### Test 1: Happy Path - Standard Email Ingestion

**Objective**: Verify complete end-to-end flow from Gmail to Qdrant with high-confidence attribution

**Test Data**:
```
To: raustinholland+echo@gmail.com
Subject: Project Update - Acme Hospital Security Assessment
From: Your regular Gmail account
Body:
Hi Austin,

Quick update on our HIPAA compliance project at Acme Hospital.

Company: Acme Hospital
Contact: Dr. Sarah Johnson, CIO
Budget Status: Approved - $180K for Q2 2026
Current Stage: Qualify

Key Points:
- Executive sponsor confirmed: Jane Doe (CFO)
- Pain point: Failed last year's HIPAA audit - 23 violations
- Vision: Achieve full HIPAA compliance by Q3 2026
- Value proposition: Avoid $1.5M in potential fines
- Next meeting: March 1st with full exec team

Champion identified: Tom Wilson (CISO) - highly engaged

Test ID: test-001-happy-path-2026-02-26
```

**Steps**:
1. Send email to ingestion inbox
2. Wait 5 minutes (Gmail Trigger poll interval)
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
    "confidence_score": 0.95,
    "doc_type": "email"
  }
  ```
- ✅ Deduplication Check: Empty result (new email)
- ✅ Deal Assignment: `deal_id` = "cw_acmehospital_2026" (or similar slug)
- ✅ Contextual Enrichment: Chunks prepended with `[DEAL CONTEXT]` header
- ✅ OpenAI Embeddings: Array of 1536-dim vectors generated
- ✅ Qdrant Insert: Success response
- ✅ Postgres Log: 1 row inserted to `ingestion_log`

**Validation Queries**:
```bash
# Check ingestion_log
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT message_id, deal_id, doc_type, chunk_count, sender_email \
   FROM ingestion_log \
   WHERE subject LIKE '%Acme Hospital%' \
   ORDER BY ingested_at DESC LIMIT 1"

# Expected: 1 row with deal_id starting with "cw_", chunk_count > 0

# Check Qdrant vectors
curl -X POST http://localhost:6333/collections/deals/points/scroll \
  -H "Content-Type: application/json" \
  -d '{"limit": 5, "with_payload": true, "with_vector": false, "filter": {"must": [{"key": "company_name", "match": {"value": "Acme Hospital"}}]}}' | jq '.result.points | length'

# Expected: At least 1 point found

# Check deal record created
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT deal_id, company_name, sender_domains, is_active FROM deals WHERE company_name LIKE '%Acme%'"

# Expected: 1 row with deal_id = "cw_acmehospital_2026"
```

**Pass Criteria**:
- All nodes executed successfully (22/22 green)
- Email data correctly extracted and stored
- Vectors queryable in Qdrant
- Database entries created

---

### Test 2: Deduplication - Duplicate Email Prevention

**Objective**: Verify the same email sent twice only processes once

**Steps**:
1. Forward Test 1 email again (exact same content) to ingestion inbox
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
| 1 | Happy Path | | ⬜ Pass / ❌ Fail | |
| 2 | Deduplication | | ⬜ Pass / ❌ Fail | |
| 3 | Low-Confidence | | ⬜ Pass / ❌ Fail | |
| 4 | Medium-Confidence | | ⬜ Pass / ❌ Fail | |
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
