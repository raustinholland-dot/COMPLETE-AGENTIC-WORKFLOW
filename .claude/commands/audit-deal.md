---
name: audit-deal
description: >
  Run a comprehensive diagnostic audit for a specific deal — docs, chunks, scores,
  stakeholders, SF link, dismissals, calendar events, and recommendations. Use when
  Austin asks to check on a deal, diagnose scoring issues, or review deal health.
argument-hint: "<deal_name or deal_id>"
---

# /audit-deal — Per-Deal Diagnostic Report

Run a comprehensive audit for a specific deal. Argument: deal name or deal_id (partial match supported).

## Instructions

Use `$ARGUMENTS` as the deal identifier. Run these steps in order.

### Step 1: Find the deal

```bash
PGPASSWORD=$(grep POSTGRES_PASSWORD /Users/austinhollsnd/Desktop/COMPLETE\ AGENTIC\ WF/deal-intelligence-engine/.env | cut -d= -f2) psql -h localhost -p 5433 -U clearwater -d clearwater_deals -t -A -c "SELECT deal_id, company_name, deal_stage, status, salesforce_opp_id, salesforce_opp_name, close_date FROM deals WHERE deal_id ILIKE '%$ARGUMENTS%' OR company_name ILIKE '%$ARGUMENTS%' LIMIT 5"
```

If multiple matches, list them and ask Austin to pick. If zero matches, report and stop.

### Step 2: Run all diagnostic queries

For the matched deal (use its exact `deal_id` as X), run these queries in parallel:

1. **Doc count by type:**
   ```sql
   SELECT doc_type, COUNT(*) FROM ingestion_log WHERE deal_id='X' GROUP BY doc_type ORDER BY count DESC
   ```

2. **Total chunks in Postgres:**
   ```sql
   SELECT COALESCE(SUM(chunk_count), 0) FROM ingestion_log WHERE deal_id='X'
   ```

3. **Qdrant chunk count:**
   ```bash
   curl -s http://localhost:6333/collections/deals/points/count -H 'Content-Type: application/json' -d '{"filter":{"must":[{"key":"deal_id","match":{"value":"X"}}]}}'
   ```

4. **Score history (last 10):**
   ```sql
   SELECT scored_at, p2v2c2_total, critical_activity_stage, trigger_type FROM deal_health WHERE deal_id='X' ORDER BY scored_at DESC LIMIT 10
   ```

5. **Stakeholders:**
   ```sql
   SELECT name, title, role, email FROM deal_stakeholders WHERE deal_id='X'
   ```

6. **Output history (last 10):**
   ```sql
   SELECT output_type, recipient_email, status, created_at FROM outputs_log WHERE deal_id='X' ORDER BY created_at DESC LIMIT 10
   ```

7. **Dismiss patterns:**
   ```sql
   SELECT dismiss_reason, COUNT(*) FROM outputs_log WHERE deal_id='X' AND dismiss_reason IS NOT NULL GROUP BY dismiss_reason
   ```

8. **Calendar events (last 5):**
   ```sql
   SELECT subject, start_time, end_time FROM calendar_events WHERE deal_id='X' ORDER BY start_time DESC LIMIT 5
   ```

Use this pattern for all SQL queries:
```bash
PGPASSWORD=$(grep POSTGRES_PASSWORD /Users/austinhollsnd/Desktop/COMPLETE\ AGENTIC\ WF/deal-intelligence-engine/.env | cut -d= -f2) psql -h localhost -p 5433 -U clearwater -d clearwater_deals -t -A -c "<SQL>"
```

### Step 3: Present the audit report

Format results as a clean summary with these sections:

**Deal Info**
- Company name, deal_id, stage, status, SF Opp ID (or "NOT LINKED"), close date

**Content Inventory**
- Count by doc type (emails, transcripts, pdf_attachment, pptx_attachment, csv_attachment, xlsx_attachment, etc.)
- Total chunks: Postgres vs Qdrant. If they differ by more than 5%, flag as "CHUNK GAP — X% mismatch, possible embedding failures"

**Latest Score**
- P2V2C2 total out of 30, CAS, trigger type
- Trend: compare the last 2 scores. Rising/Falling/Stable.

**Stakeholders**
- List each with name, title, role, email

**Recent Outputs**
- Last 5 outputs with type, recipient, status, date

**Feedback Patterns**
- Dismiss reasons with counts. If none, say "No dismissals recorded."

**Upcoming Meetings**
- Next calendar events. If none, say "No calendar events."

**Recommendations**
Flag any of these issues found:
- No Salesforce link (missing salesforce_opp_id)
- Stale score (last scored_at > 7 days ago)
- Low doc count (fewer than 3 documents)
- Chunk gap between Postgres and Qdrant (>5%)
- No stakeholders identified
- Calendar-only deal (only doc type is calendar_invite)
- High dismiss rate (>50% of outputs dismissed)
