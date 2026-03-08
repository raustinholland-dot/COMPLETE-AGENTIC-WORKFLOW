---
name: backfill-status
description: >
  Show which deals have backfill folders, which are calibrated, which still need
  processing. Use to see where you left off before running /smart-backfill.
---

# /backfill-status — Backfill Progress Dashboard

Show the current state of all deal backfills at a glance.

## Steps

### 1. Scan backfill folders

```bash
ls -d "/Users/austinhollsnd/Desktop/COMPLETE AGENTIC WF/deal-intelligence-engine/backfill/"*/ 2>/dev/null | while read dir; do
  name=$(basename "$dir")
  [[ "$name" == _* ]] && continue
  [[ "$name" == teams-raw ]] && continue
  txts=$(find "$dir" -name "*.txt" -not -name "emails-*" -not -name "gemini-*" | wc -l | tr -d ' ')
  emls=$(find "$dir" -name "*.eml" | wc -l | tr -d ' ')
  pdfs=$(find "$dir" -name "*.pdf" -o -name "*.pptx" | wc -l | tr -d ' ')
  echo "$name|$txts transcripts|$emls emails|$pdfs attachments"
done
```

### 2. Cross-reference with database

For each backfill folder, check the database for:
- Whether the deal exists in the `deals` table
- How many `ingestion_log` rows exist
- How many `deal_health` scores exist
- Whether the deal has been audited clean (run `audit_deal.py`)

```bash
cd "/Users/austinhollsnd/Desktop/COMPLETE AGENTIC WF/deal-intelligence-engine" && python3 scripts/audit_deal.py 2>&1 | grep -E "^  [✓✗]"
```

### 3. Present a summary table

Show Austin a table with columns:
- Deal name
- Backfill files (transcripts / emails / attachments)
- Status: **Calibrated** (audit clean), **Backfilled** (has scores but needs audit), **Pending** (has folder but not processed), **No folder** (deal exists but no backfill content)
- Score count and latest score

### 4. Recommend next action

Based on the status:
- If there are **Pending** deals: suggest starting `/smart-backfill all` to process them
- If there are **Backfilled** deals needing audit: suggest running the audit
- If all are calibrated: report all clean

### Calibrated deals (as of 2026-03-08)
These four have been fully audited and confirmed clean:
- Velentium (3 scores, 21/30)
- Life Care Home Health (1 score, 7/30)
- MedElite (1 score, 5/30)
- RISE Services (1 score, 4/30)
