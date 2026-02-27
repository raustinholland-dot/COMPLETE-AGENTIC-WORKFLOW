# /prime — Session Primer for Clearwater Deal Intelligence Engine

Load all critical project context to start a fully informed session.

## What this command does

Read the following files in order and internalize their contents before responding:

1. Read `/Users/austinhollsnd/Desktop/COMPLETE AGENTIC WF/CLAUDE.md` — project overview, tech stack, architecture, key patterns
2. Read `/Users/austinhollsnd/Desktop/COMPLETE AGENTIC WF/.claude/PRD.md` — full product requirements, all 6 phases
3. Read `/Users/austinhollsnd/Desktop/COMPLETE AGENTIC WF/.claude/memory/MEMORY.md` — CPS/P2V2C2 methodology, architecture decisions, build order
4. Read `/Users/austinhollsnd/Desktop/COMPLETE AGENTIC WF/deal-intelligence-engine/.env` — current credentials and environment (do not display secrets)
5. Read `/Users/austinhollsnd/Desktop/COMPLETE AGENTIC WF/deal-intelligence-engine/docker-compose.yml` — service config
6. Read `/Users/austinhollsnd/Desktop/COMPLETE AGENTIC WF/deal-intelligence-engine/TESTING.md` — current test plan and execution status

## After reading

Check the current state of the system:
- Run `docker ps` to confirm all 5 services are running
- Check `~/.claude/mcp.json` to confirm n8n MCP is configured
- Query the n8n API or Postgres to confirm workflow CW-01 status

Then confirm to Austin:
- Which phase we are on
- What was last completed
- What the next task is
- Any issues detected

## Key facts to always know
- n8n: http://localhost:5678
- Qdrant: http://localhost:6333/dashboard
- Metabase: http://localhost:3000
- Postgres app DB: clearwater_deals (user: clearwater)
- Postgres n8n DB: n8n (user: clearwater)
- Gmail ingestion inbox: raustinholland+echo@gmail.com
- Austin's delivery email: austin.holland@clearwatersecurity.com
- Active workflow: CW-01 (ID: G6kZgyHCK0qHNhRj)
- n8n MCP server: clearwater-n8n (configured in ~/.claude.json)
