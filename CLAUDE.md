# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

---

## Project Overview

**Clearwater Deal Intelligence Engine** — A RAG-based AI automation system built on n8n for Austin Hollins (AE) at Clearwater Security & Compliance. The engine ingests deal communications (emails, call transcripts, PDFs, PowerPoints, CSVs) from a dedicated Gmail inbox into a Qdrant vector database, then orchestrates specialized AI agents to:

1. **Score every active deal** using the CPS/P2V2C2 methodology (22 tracked artifacts)
2. **Generate high-quality outputs** — follow-up emails, pre-call planners, branded Approach Document PDFs, executive PowerPoint presentations
3. **Answer deal questions** via an n8n chat widget (deal-scoped and cross-deal queries)
4. **Sync and prep for meetings** via Google Calendar integration (Phase 5+)

Clearwater sells cybersecurity, risk management, and compliance services to healthcare organizations. Primary user: Austin Hollins (~20-25 active deals at any time).

See [`.claude/PRD.md`](.claude/PRD.md) for full requirements across all 6 phases.

---

## Tech Stack

| Technology | Version | Purpose |
|---|---|---|
| n8n | 2.8.3 | Workflow automation engine (all pipelines) |
| Qdrant | 1.13.0 | Vector database — one namespace per deal |
| PostgreSQL | 16 | Structured data: deals, health scores, output history |
| Redis | 7 | Active session memory for chat agent (24h TTL) |
| Metabase | 0.51.5 | Deal health dashboard (connects to Postgres) |
| OpenAI `text-embedding-3-small` | — | Document embeddings (1536 dims) |
| Claude Sonnet 4.6 | — | Classification, Q&A, standard email outputs |
| Claude Opus 4.6 | — | P2V2C2 scoring, Approach Docs, exec PPTs |
| Docker + Docker Compose | — | All 5 services run together locally |
| Gmail API v1 | — | Ingestion trigger + output delivery |
| Google Calendar API v3 | — | Phase 5: calendar read + meeting prep |
| GitHub MCP Server | — | Claude Code commits workflows to GitHub |
| n8n-mcp (czlonkowski) | — | Claude Code ↔ n8n workflow authoring |

---

## Commands

```bash
# Deal Intelligence Engine — primary commands
cd deal-intelligence-engine

bash scripts/setup.sh              # First-run: generates secrets, starts Docker, creates Qdrant collection
docker compose up -d               # Start all 5 services (n8n, Qdrant, Postgres, Redis, Metabase)
docker compose down                # Stop all services
docker compose logs -f [service]   # Follow logs (e.g. n8n, qdrant, postgres)
docker compose restart [service]   # Restart a single service

# Qdrant collection (run once after first docker compose up)
bash scripts/create-qdrant-collection.sh

# Service URLs (after docker compose up)
# n8n:      http://localhost:5678
# Qdrant:   http://localhost:6333/dashboard
# Metabase: http://localhost:3000
# Postgres: localhost:5432
```

---

## Project Structure

```
deal-intelligence-engine/
├── docker-compose.yml              # All 5 Docker service definitions
├── .env.example                    # Template — copy to .env and fill in secrets
├── .env                            # Local secrets (gitignored)
├── .gitignore
│
├── n8n/
│   └── workflows/
│       ├── workflow-01-ingestion.json      # Phase 1: Gmail → classify → embed → Qdrant
│       ├── workflow-02-deal-health.json    # Phase 2: P2V2C2 scoring, 22 artifacts, DAP, trend
│       └── workflow-03-output-gen.json     # Phase 3: Email/PDF/PPT generation, output memory
│
├── postgres/
│   └── init/
│       └── 01_schema.sql           # Full schema: 7 tables + 3 Metabase views (auto-runs on first up)
│
├── qdrant/
│   └── config.yaml                 # HNSW index + int8 scalar quantization
│
├── templates/
│   ├── pdf/                        # Jinja2 HTML templates for Approach Document PDFs
│   └── pptx/                       # Branded Clearwater PowerPoint base files
│
└── scripts/
    ├── setup.sh                    # First-run setup script
    └── create-qdrant-collection.sh # Manual Qdrant collection init

.claude/
├── PRD.md                          # Full Product Requirements Document (all 6 phases)
├── memory/MEMORY.md                # Persistent session context: CPS methodology, architecture decisions
└── commands/                       # Custom Claude slash commands

CLAUDE.md                           # This file
```

---

## Key Files

| File | Why It Matters |
|---|---|
| `deal-intelligence-engine/docker-compose.yml` | Single source of truth for all service config and env vars |
| `deal-intelligence-engine/postgres/init/01_schema.sql` | All 7 tables + 3 Metabase views; modify here for schema changes |
| `deal-intelligence-engine/n8n/workflows/workflow-01-ingestion.json` | Gmail ingestion pipeline — start here for ingest changes |
| `deal-intelligence-engine/n8n/workflows/workflow-02-deal-health.json` | P2V2C2 scoring engine — all 22 artifacts, CAS, DAP |
| `deal-intelligence-engine/n8n/workflows/workflow-03-output-gen.json` | Output generation — email, PDF, PPT with output memory |
| `.claude/PRD.md` | Full requirements, all 6 phases, 22 artifact list, tech decisions |
| `.claude/memory/MEMORY.md` | CPS P2V2C2 scoring rubric, key roles (PC/PES/ES/DM), build order |

---

## Architecture

### Workflow Chain

```
Gmail Trigger (every 1 min)
  → Workflow 1: Ingestion Pipeline
      → classify → dedupe → chunk → embed → Qdrant insert
      → POST /webhook/deal-health-trigger
          → Workflow 2: Deal Health Agent
              → 15 RAG queries (one per CPS dimension)
              → Claude Opus scores all 22 artifacts
              → Postgres: insert to deal_health table
              → Nightly rescore also runs at 9pm ET

n8n Chat Widget
  → Workflow 4: Q&A Chat Agent (Phase 4, pending)
      → POST /webhook/output-request
          → Workflow 3: Output Generation Agent
              → retrieve output history → RAG → Claude generates
              → Gmail send to Austin's Outlook
              → Postgres: log to outputs_log
```

### Qdrant Design
- **Collection:** `deals` — 1536 dimensions, Cosine distance, int8 quantization
- **Namespace per deal:** `deal_id` (e.g. `cw_acmehospital_2025`)
- All retrieval queries are namespace-scoped — no cross-deal contamination
- Payload schema per chunk: `deal_id`, `company_name`, `sender_domain`, `deal_stage`, `doc_type`, `date_created`, `chunk_index`, `attribution_confidence`

### Postgres Tables
| Table | Purpose |
|---|---|
| `deals` | Master deal registry; maps deal slugs to Salesforce opp IDs |
| `ingestion_log` | Every processed email; deduplication by `message_id` |
| `deal_health` | Append-only P2V2C2 scores + all 22 artifacts per scoring run |
| `outputs_log` | Every AI-generated output per deal/contact — the output memory store |
| `attribution_queue` | Low-confidence emails awaiting Austin's confirmation |
| `calendar_events` | Phase 5: Google Calendar mirror linked to deals |
| `n8n_chat_histories` | Permanent agent conversation history (Postgres Chat Memory) |

---

## CPS Methodology (P2V2C2)

Clearwater's proprietary sales framework. The health agent scores 6 dimensions (0-5 each, 30 max total):

| Dimension | Score 0 | Score 5 |
|---|---|---|
| **Pain** | No knowledge of pain | ES agreed pain large enough to change |
| **Power** | No idea who is power | DAP steps on schedule |
| **Vision** | No idea of needs | ES painting vision to others in org |
| **Value** | Benefits unknown | DM agreed to financial terms |
| **Change** | No one committed | ES convinced DM they must change |
| **Control** | Buying process unknown | DAP complete |

**Additional tracked:** PE Sponsor Score (1-5), Critical Activity Stage (e.g. "3B: Document Approach"), DAP (14 milestones, 14-day gap rule flagged).

**5 Sales Stages:** Discover → Qualify → Prove → Negotiate → Close

**Key roles:** PC (Potential Champion), C (Champion), PES (Potential Executive Sponsor), ES (Executive Sponsor), DM (Ultimate Decision Maker), DAP (Dual Action Plan)

Full scoring rubric in [`.claude/memory/MEMORY.md`](.claude/memory/MEMORY.md).

---

## Key Patterns

### Ingestion Deduplication
Gmail `message_id` is the deduplication key. Before processing any email, check `ingestion_log` for an existing record with that `message_id`. If found, skip entirely.

### Contextual Enrichment
Every chunk is prepended with a `[DEAL CONTEXT]` header before embedding:
```
[DEAL CONTEXT]
Deal: Acme Health (ID: cw_acmehospital_2025)
Document Type: call_transcript
Date: 2026-02-14
Source: john.smith@acmehospital.org
[END CONTEXT]

[chunk content...]
```
This dramatically improves RAG retrieval precision (Anthropic Contextual Retrieval pattern).

### Deal Attribution Confidence Routing
- **High/medium** → auto-assign to matching deal in `deals` table by sender domain or company name
- **Low** → insert to `attribution_queue`; surfaced to Austin via chat widget for confirmation

### Append-Only Health History
The `deal_health` table **never updates** existing rows — always inserts a new row per scoring run. This preserves the full audit trail of P2V2C2 scores over time for trend analysis.

### Output Memory
Before generating any output, the agent queries `outputs_log` for all prior outputs to the same `recipient_email` for the same `deal_id`. This history is injected into the Claude prompt so every output builds on prior communications rather than repeating them.

### JSON Parsing Fallback
All Claude JSON responses are stripped of markdown code fences before parsing:
```js
const cleaned = raw.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
const parsed = JSON.parse(cleaned);
```

---

## Environment Variables

All secrets in `deal-intelligence-engine/.env` (gitignored). Template at `.env.example`.

```bash
N8N_ENCRYPTION_KEY=        # 32-char random string (auto-generated by setup.sh)
POSTGRES_PASSWORD=          # Strong password
REDIS_PASSWORD=             # Redis auth

OPENAI_API_KEY=             # sk-... (for text-embedding-3-small)
ANTHROPIC_API_KEY=          # sk-ant-... (for Claude Sonnet + Opus)

GMAIL_CLIENT_ID=            # Ingestion inbox OAuth2 (Google Cloud Console)
GMAIL_CLIENT_SECRET=
GMAIL_SEND_CLIENT_ID=       # Send outputs OAuth2
GMAIL_SEND_CLIENT_SECRET=
GMAIL_INGESTION_ADDRESS=    # Dedicated deal Intel Gmail address

GOOGLE_CALENDAR_CLIENT_ID=  # Phase 5 — read-only calendar
GOOGLE_CALENDAR_CLIENT_SECRET=

AUSTIN_EMAIL=               # Outlook address that receives all AI-generated outputs

GITHUB_TOKEN=               # PAT for GitHub MCP
GITHUB_REPO=                # username/repo for workflow version control
```

---

## n8n Credentials Required

Configure these in n8n (`http://localhost:5678/credentials`) after first run:

| Credential Name | Type | Notes |
|---|---|---|
| `Gmail Ingestion Inbox` | Gmail OAuth2 | Ingestion inbox — read + download attachments |
| `Gmail Send` | Gmail OAuth2 | Send outputs to Austin's Outlook |
| `Anthropic API` | Anthropic | Claude Sonnet + Opus |
| `OpenAI API` | OpenAI | text-embedding-3-small |
| `Clearwater Postgres` | PostgreSQL | host: `postgres`, db: `clearwater_deals`, user: `clearwater` |
| `Qdrant Local` | Qdrant | host: `http://qdrant:6333` |
| `Redis` | Redis | host: `redis`, password: from `.env` |

---

## MCP Setup (Claude Code ↔ n8n)

```bash
# After n8n is running, get your API key from n8n Settings → API
claude mcp add n8n-mcp \
  --env MCP_MODE=stdio \
  --env N8N_API_URL=http://localhost:5678 \
  --env N8N_API_KEY=<your-n8n-api-key> \
  --env DISABLE_CONSOLE_OUTPUT=true \
  -- npx -y n8n-mcp
```

Optionally install [n8n-skills](https://github.com/czlonkowski/n8n-skills) for better workflow generation quality.
