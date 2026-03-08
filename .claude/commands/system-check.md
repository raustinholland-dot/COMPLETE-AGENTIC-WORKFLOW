---
name: system-check
description: >
  Run a full health check across all Clearwater services — Docker, n8n workflows,
  Postgres errors, Qdrant status, pending attribution, recent ingestion, and deal
  stats. Use when Austin asks about system status, health, or if something is down.
---

# /system-check — System Health Dashboard

Run a quick health check across all Clearwater Deal Intelligence Engine services. No arguments needed.

## Instructions

Run all of these checks. Where possible, run independent queries in parallel.

### Check 1: Docker Services

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Expect 5 services: n8n, postgres, qdrant, redis, metabase. Flag any missing or unhealthy.

### Check 2: Active n8n Workflows

```bash
N8N_API_KEY=$(grep N8N_API_KEY /Users/austinhollsnd/Desktop/COMPLETE\ AGENTIC\ WF/deal-intelligence-engine/.env | cut -d= -f2)
curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" "http://localhost:5678/api/v1/workflows?active=true&limit=50"
```

List active workflow names and IDs. Report the total count.

### Check 3: Recent Errors (workflow_errors table)

```bash
PGPASSWORD=$(grep POSTGRES_PASSWORD /Users/austinhollsnd/Desktop/COMPLETE\ AGENTIC\ WF/deal-intelligence-engine/.env | cut -d= -f2) psql -h localhost -p 5433 -U clearwater -d clearwater_deals -t -A -c "SELECT id, workflow_name, error_message, created_at FROM workflow_errors WHERE NOT acknowledged ORDER BY created_at DESC LIMIT 5"
```

If any unacknowledged errors exist, list them. Otherwise report "No unacknowledged errors."

### Check 4: Qdrant Status

```bash
curl -s http://localhost:6333/collections/deals
```

Report: collection status, total point count, segment count.

### Check 5: Pending Attribution

```bash
PGPASSWORD=$(grep POSTGRES_PASSWORD /Users/austinhollsnd/Desktop/COMPLETE\ AGENTIC\ WF/deal-intelligence-engine/.env | cut -d= -f2) psql -h localhost -p 5433 -U clearwater -d clearwater_deals -t -A -c "SELECT COUNT(*) FROM ingestion_log WHERE attribution_status='pending'"
```

Report count. Flag if > 10 pending.

### Check 6: Recent Ingestion (24h)

```bash
PGPASSWORD=$(grep POSTGRES_PASSWORD /Users/austinhollsnd/Desktop/COMPLETE\ AGENTIC\ WF/deal-intelligence-engine/.env | cut -d= -f2) psql -h localhost -p 5433 -U clearwater -d clearwater_deals -t -A -c "SELECT COUNT(*) FROM ingestion_log WHERE ingested_at > NOW() - INTERVAL '24 hours'"
```

Report count. Note if zero (no ingestion in 24h — may be normal on weekends).

### Check 7: n8n Error Executions

```bash
N8N_API_KEY=$(grep N8N_API_KEY /Users/austinhollsnd/Desktop/COMPLETE\ AGENTIC\ WF/deal-intelligence-engine/.env | cut -d= -f2)
curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" "http://localhost:5678/api/v1/executions?status=error&limit=5"
```

List recent failed executions: workflow name, error message (truncated), timestamp. If none, report "No recent execution errors."

### Check 8: Deal Stats

```bash
PGPASSWORD=$(grep POSTGRES_PASSWORD /Users/austinhollsnd/Desktop/COMPLETE\ AGENTIC\ WF/deal-intelligence-engine/.env | cut -d= -f2) psql -h localhost -p 5433 -U clearwater -d clearwater_deals -t -A -c "SELECT status, COUNT(*) FROM deals GROUP BY status ORDER BY count DESC"
```

Report deal counts by status.

## Output Format

Present as a clean dashboard:

```
CLEARWATER SYSTEM STATUS
========================

SERVICES
  n8n ............ [UP/DOWN] (uptime)
  Postgres ....... [UP/DOWN]
  Qdrant ......... [UP/DOWN] (X points)
  Redis .......... [UP/DOWN]
  Metabase ....... [UP/DOWN]

WORKFLOWS
  X active workflows
  [list names]

INGESTION
  Last 24h: X documents ingested
  Pending attribution: X

DEALS
  Active: X | Internal: X | Archived: X

QDRANT
  Collection: deals — X points

ERRORS
  Unacknowledged DB errors: X
  Recent n8n failures: X
  [list if any]

ISSUES
  [list any flagged problems, or "None detected"]
```

Flag issues for: any service down, error count > 0, pending attribution > 10, zero ingestion on a weekday.
