---
name: prime
description: >
  Load all critical project context (CLAUDE.md, PRD, MEMORY, patterns, env, docker-compose)
  and verify system state to start a fully informed session. Use at the beginning of any
  new conversation or when Austin says to prime, load context, or get oriented.
---

# /prime — Session Primer for Clearwater Deal Intelligence Engine

Load all critical project context to start a fully informed session.

## What this command does

Read the following files in order and internalize their contents before responding:

1. Read `/Users/austinhollsnd/Desktop/COMPLETE AGENTIC WF/CLAUDE.md` — project overview, tech stack, architecture, key patterns
2. Read `/Users/austinhollsnd/Desktop/COMPLETE AGENTIC WF/.claude/PRD.md` — phase status and Phase 6 requirements
3. Read `/Users/austinhollsnd/.claude/projects/-Users-austinhollsnd-Desktop-COMPLETE-AGENTIC-WF/memory/MEMORY.md` — workflow IDs, architecture decisions, current task list
4. Read `/Users/austinhollsnd/.claude/projects/-Users-austinhollsnd-Desktop-COMPLETE-AGENTIC-WF/memory/patterns.md` — critical n8n patterns, deploy loop, known broken things
5. Read `/Users/austinhollsnd/Desktop/COMPLETE AGENTIC WF/deal-intelligence-engine/.env` — current credentials and environment (do not display secrets)
6. Read `/Users/austinhollsnd/Desktop/COMPLETE AGENTIC WF/deal-intelligence-engine/docker-compose.yml` — service config

## After reading

Check the current state of the system:
- Run `docker ps` to confirm all 5 services are running
- Query the n8n API to confirm active workflows (CW-01, CW-02, Workflow 3a, 3e)

Then confirm to Austin:
- Which phase we are on
- What was last completed
- What the next task is
- Any issues detected

## Standing rules (always enforce)
- **n8n MCP is DISABLED permanently.** Never use MCP tools to modify workflows. Deploy loop only via `push-workflow.sh` or direct n8n API calls.
- **LangChain sub-nodes for Qdrant are broken** (`documentDefaultDataLoader` crashes in n8n 2.9.4). Always use direct HTTP API calls for embed + upsert.
- **Always verify live n8n state before retesting.** After any workflow change, re-pull the workflow from the API and confirm the target node changed before asking Austin to test.
- **Never use local JSON as source of truth** — always pull live from n8n API before editing.

## Key facts to always know
- n8n: http://localhost:5678
- Qdrant: http://localhost:6333/dashboard
- Metabase: http://localhost:3000
- Postgres app DB: clearwater_deals (port 5433, user: clearwater)
- Postgres n8n DB: n8n (user: clearwater)
- Ingestion: PA/Outlook webhook (NOT Gmail) — ngrok tunnel active
- Austin's delivery email: austin.holland@clearwatersecurity.com
- CW-01 Ingestion: G6kZgyHCK0qHNhRj
- CW-02 Health Scoring: oOnzLBeQzu5M7nc4
- Workflow 3a Chat Trigger: ZS64jSadlOIPrert
- Workflow 3e Generate Output: K2i48dUP1MgYXQzA
