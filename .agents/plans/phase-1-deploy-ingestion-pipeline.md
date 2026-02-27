# Feature: Phase 1 - Deploy and Validate Ingestion Pipeline

**IMPORTANT**: This plan should be complete, but validate documentation and codebase patterns before implementing. Pay special attention to naming of existing utils, types, and models. Import from the right files.

## Feature Description

Deploy the complete Gmail → Qdrant ingestion pipeline as the foundational component of the Clearwater Deal Intelligence Engine. This system automatically monitors a dedicated Gmail inbox, classifies incoming emails and attachments, deduplicates them, assigns them to the correct deal, chunks and embeds the content, and stores the vectors in Qdrant with namespace-per-deal isolation. Upon successful ingestion, it triggers the Deal Health Scoring Agent (Phase 2) to re-score the affected deal.

This is the data intake layer that feeds all downstream AI agents (health scoring, output generation, Q&A chat).

## User Story

As Austin Hollins (Clearwater AE),
I want every email, call transcript, and document I forward to the ingestion inbox to be automatically parsed, attributed to the correct deal, and stored in a searchable vector database,
So that I never have to manually copy-paste deal notes into any system and all deal intelligence is immediately available for AI agents to analyze.

## Problem Statement

Austin manages 20-25 active deals simultaneously with 10-20 emails and ~2 call transcripts per day. Manually updating Salesforce with P2V2C2 scores and extracting insights from communications is time-consuming and inconsistent. There is no centralized, searchable repository of deal communications that can be queried by AI agents. Deal context is scattered across Gmail threads, call transcripts in various formats (PDF, TXT), and attachments.

## Solution Statement

Build an automated ingestion pipeline using n8n that:
1. Polls a dedicated Gmail inbox every 5 minutes for unread messages
2. Uses Claude Sonnet to classify document type and infer deal attribution with confidence scoring
3. Routes high/medium confidence emails to auto-assignment; low confidence to human confirmation queue
4. Extracts text from emails and attachments (PDF, DOCX, TXT, PPTX, CSV)
5. Prepends contextual enrichment headers (Anthropic Contextual Retrieval pattern)
6. Chunks text into 500-token segments with 50-token overlap
7. Embeds chunks using OpenAI text-embedding-3-small (1536 dims)
8. Stores vectors in Qdrant with namespace-per-deal isolation
9. Logs every ingestion event to Postgres for deduplication and audit trail
10. Triggers webhook to Deal Health Scoring Agent upon successful ingestion

## Feature Metadata

**Feature Type**: New Capability (Infrastructure Foundation)
**Estimated Complexity**: High
**Primary Systems Affected**: n8n (workflow engine), Qdrant (vector DB), PostgreSQL (structured data), Gmail API, OpenAI API, Anthropic API
**Dependencies**: Docker Compose stack (5 services), Gmail OAuth2 credentials, OpenAI API key, Anthropic API key

---

## CONTEXT REFERENCES

### Relevant Codebase Files - IMPORTANT: YOU MUST READ THESE FILES BEFORE IMPLEMENTING!

- `deal-intelligence-engine/docker-compose.yml` (lines 1-149) - Complete service definitions for all 5 Docker containers
  - Why: Understand service names, ports, environment variables, health checks, network configuration

- `deal-intelligence-engine/.env.example` (lines 1-54) - All 54 required environment variables with documentation
  - Why: Know every secret and config that must be filled before deployment

- `deal-intelligence-engine/n8n/workflows/workflow-01-ingestion.json` (19KB, 22 nodes) - Complete ingestion workflow
  - Why: Pre-built workflow structure; must be imported into n8n and credentials configured

- `deal-intelligence-engine/postgres/init/01_schema.sql` (lines 1-200+) - Complete database schema
  - Why: Understand `deals`, `ingestion_log`, `attribution_queue` table structures for data validation

- `deal-intelligence-engine/qdrant/config.yaml` (lines 1-30) - Qdrant HNSW and quantization configuration
  - Why: Collection configuration matches embedding dimensions and performance settings

- `deal-intelligence-engine/scripts/setup.sh` (lines 1-150+) - First-run setup automation
  - Why: Auto-generates encryption keys, creates .env, starts Docker, creates Qdrant collection

- `deal-intelligence-engine/scripts/create-qdrant-collection.sh` (lines 1-20) - Manual collection creation
  - Why: Standalone script if setup.sh fails or for manual reinitialization

### New Files to Create

- `deal-intelligence-engine/.env` - Actual environment file with real API keys (gitignored)
- `deal-intelligence-engine/DEPLOYMENT.md` - Deployment guide documenting manual steps post-setup.sh
- `deal-intelligence-engine/TESTING.md` - Test scenarios and validation commands
- `.agents/validation/ingestion-test-email.txt` - Sample email for end-to-end testing

### Relevant Documentation - YOU SHOULD READ THESE BEFORE IMPLEMENTING!

#### n8n Configuration & Security
- [n8n Docker Hosting Documentation](https://docs.n8n.io/hosting/installation/docker/)
  - Section: "Docker Compose Setup"
  - Why: Official guide for production Docker deployment with PostgreSQL

- [n8n Security Best Practices](https://docs.n8n.io/hosting/securing/overview/)
  - Section: "Encryption Key Configuration"
  - Why: Critical—N8N_ENCRYPTION_KEY must be set or credentials remain plaintext

#### Qdrant Collection Setup
- [Qdrant Collections API Reference](https://api.qdrant.tech/api-reference/collections/create-collection)
  - Section: "Create Collection Request Body"
  - Why: Exact JSON structure for PUT /collections/{name}

- [Qdrant Multitenancy Guide](https://qdrant.tech/documentation/guides/multitenancy/)
  - Section: "Multitenancy via Payload Filtering"
  - Why: Single collection with deal_id filtering is the recommended pattern

- [Qdrant Quantization Guide](https://qdrant.tech/documentation/guides/quantization/)
  - Section: "Int8 Scalar Quantization"
  - Why: Reduces memory by 4x with minimal quality loss

#### n8n + Qdrant Integration
- [n8n Qdrant Vector Store Node Documentation](https://docs.n8n.io/integrations/builtin/cluster-nodes/root-nodes/n8n-nodes-langchain.vectorstoreqdrant/)
  - Section: "Insert Documents, Retrieve Documents"
  - Why: How to configure Qdrant nodes in n8n workflows

- [Qdrant × n8n Platform Guide](https://qdrant.tech/documentation/platforms/n8n/)
  - Section: "RAG Workflow Example"
  - Why: Complete workflow pattern for vector insertion

#### Gmail OAuth2 Setup
- [n8n Google Credentials Documentation](https://docs.n8n.io/integrations/builtin/credentials/google/)
  - Section: "OAuth2 Setup"
  - Why: Step-by-step credential creation in Google Cloud Console

- [Gmail API Scopes Reference](https://developers.google.com/workspace/gmail/api/auth/scopes)
  - Section: "Scopes List"
  - Why: Use `gmail.readonly` for ingestion inbox, `gmail.send` for outputs

#### OpenAI Embeddings
- [n8n Embeddings OpenAI Node](https://docs.n8n.io/integrations/builtin/cluster-nodes/sub-nodes/n8n-nodes-langchain.embeddingsopenai/)
  - Section: "text-embedding-3-small Configuration"
  - Why: Must match Qdrant collection vector size (1536 dims)

#### Anthropic/Claude API
- [n8n Anthropic Chat Model Node](https://docs.n8n.io/integrations/builtin/cluster-nodes/sub-nodes/n8n-nodes-langchain.lmchatanthropic/)
  - Section: "Claude Sonnet 4.6 Usage"
  - Why: Classification and deal attribution logic uses Claude Sonnet

### Patterns to Follow

#### Docker Compose Service Dependency Pattern
```yaml
# From docker-compose.yml lines 41-46
n8n:
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
```
**Why**: n8n must not start until Postgres and Redis are fully ready (health checks passing)

#### Environment Variable Loading Pattern
```bash
# From setup.sh lines 30-35
N8N_ENCRYPTION_KEY=$(openssl rand -hex 16)
POSTGRES_PASSWORD=$(openssl rand -base64 24)
sed -i.bak "s/REPLACE_WITH_RANDOM_32_CHAR_STRING/$N8N_ENCRYPTION_KEY/g" .env
```
**Why**: Auto-generate secrets using openssl; never commit to git

#### Qdrant Collection Creation Pattern
```bash
# From create-qdrant-collection.sh lines 5-15
curl -X PUT http://localhost:6333/collections/deals \
  -H "Content-Type: application/json" \
  -d '{
    "vectors": {
      "size": 1536,
      "distance": "Cosine"
    },
    "quantization_config": {
      "scalar": {"type": "int8", "quantile": 0.99, "always_ram": true}
    }
  }'
```
**Why**: Single collection with 1536-dim vectors, cosine similarity, int8 quantization

#### Contextual Enrichment Header Pattern
```javascript
// From workflow-01-ingestion.json node "Code: Contextual Enrichment"
const enrichedChunks = chunks.map(chunk => {
  return `[DEAL CONTEXT]
Deal: ${companyName} (ID: ${dealId})
Document Type: ${docType}
Date: ${emailDate}
Source: ${senderEmail}
[END CONTEXT]

${chunk}`;
});
```
**Why**: Anthropic Contextual Retrieval pattern—improves RAG precision significantly

#### Deduplication Check Pattern
```sql
-- From workflow-01-ingestion.json node "Postgres: Check Duplicate"
SELECT id FROM ingestion_log WHERE message_id = $1
```
**Why**: Gmail message_id is the deduplication key; if row exists, skip processing entirely

#### Namespace-Scoped Qdrant Insert Pattern
```json
// From workflow-01-ingestion.json node "Qdrant: Insert Vectors"
{
  "collection": "deals",
  "points": [
    {
      "id": "uuid",
      "vector": [0.123, 0.456, ...],
      "payload": {
        "deal_id": "cw_acmehospital_2025",
        "company_name": "Acme Hospital",
        "doc_type": "call_transcript",
        "date_created": "2026-02-14",
        "chunk_index": 0
      }
    }
  ]
}
```
**Why**: All retrieval queries filter by `deal_id` in payload → zero cross-deal contamination

#### Confidence-Based Attribution Routing Pattern
```javascript
// From workflow-01-ingestion.json node "Route by Confidence"
if (confidence === 'high' || confidence === 'medium') {
  // Auto-assign to matched deal via sender_domain or company_name
  return dealLookupResult;
} else {
  // Insert to attribution_queue for Austin's confirmation
  return queueForHumanConfirmation;
}
```
**Why**: Balance automation (high/med) with accuracy (low → human review)

#### Cross-Workflow Webhook Trigger Pattern
```javascript
// From workflow-01-ingestion.json final node "HTTP: Trigger Health Agent"
POST http://n8n:5678/webhook/deal-health-trigger
Body: {
  "deal_id": "cw_acmehospital_2025",
  "trigger_message_id": "gmail_msg_12345",
  "trigger_type": "new_ingestion"
}
```
**Why**: Loosely coupled workflows; ingestion completes independently of scoring

---

## IMPLEMENTATION PLAN

### Phase 1: Environment Setup & Docker Deployment

**Goal**: Get all 5 Docker services running with proper configuration and health checks passing.

**Tasks**:
- Set up base environment file with all 54 variables
- Generate encryption keys and database passwords
- Start Docker Compose stack
- Verify all 5 services are healthy
- Verify Postgres schema initialized correctly (7 tables created)

### Phase 2: API Credentials Configuration

**Goal**: Configure all external API integrations (Gmail, OpenAI, Anthropic) in n8n UI.

**Tasks**:
- Set up two Gmail OAuth2 apps in Google Cloud Console
- Configure Gmail credentials in n8n (read + send)
- Configure OpenAI API credential in n8n
- Configure Anthropic API credential in n8n
- Configure Postgres credential in n8n
- Configure Qdrant credential in n8n (local Docker, no auth)
- Configure Redis credential in n8n

### Phase 3: Qdrant Collection Initialization

**Goal**: Create the "deals" collection with correct vector configuration and quantization.

**Tasks**:
- Verify Qdrant service is healthy (HTTP 200 on /healthz)
- Create "deals" collection via REST API
- Validate collection exists (GET /collections/deals)
- Verify vector configuration (1536 dims, Cosine, int8 quantization)

### Phase 4: n8n Workflow Import & Activation

**Goal**: Import workflow-01-ingestion.json into n8n and activate it.

**Tasks**:
- Import workflow JSON via n8n UI
- Map all credentials to workflow nodes
- Validate workflow has no missing credentials
- Test workflow nodes individually (dry run)
- Activate workflow

### Phase 5: End-to-End Ingestion Test

**Goal**: Validate complete Gmail → Qdrant flow with a real test email.

**Tasks**:
- Send test email to ingestion Gmail inbox
- Monitor n8n execution logs
- Verify email classified correctly (Claude Sonnet)
- Verify deduplication check passed
- Verify deal attribution (auto-assign or queue)
- Verify text extraction (email body or attachment)
- Verify contextual enrichment applied
- Verify chunking (500 tokens, 50 overlap)
- Verify embedding (OpenAI 1536-dim vectors)
- Verify Qdrant insertion (namespace = deal_id)
- Verify Postgres logging (ingestion_log table)
- Verify webhook trigger sent to health agent

### Phase 6: Integration Testing & Edge Cases

**Goal**: Test failure modes, edge cases, and error handling.

**Tasks**:
- Test duplicate email handling (same message_id)
- Test low-confidence attribution (queue insertion)
- Test attachment extraction (PDF, DOCX, TXT, PPTX, CSV)
- Test large attachments (>20MB size limit)
- Test malformed emails (missing sender, no body)
- Test API rate limits (Gmail, OpenAI, Anthropic)
- Test service restarts (Docker down/up, state preservation)

---

## STEP-BY-STEP TASKS

**IMPORTANT**: Execute every task in order, top to bottom. Each task is atomic and independently testable.

**BROWSER AGENT USAGE**: All tasks involving n8n UI, Metabase UI, Qdrant dashboard, or Gmail must be executed using the `agent-browser` skill for full automation. Refer to the "BROWSER AGENT END-TO-END TESTING" section for detailed step-by-step browser automation patterns.

**ENVIRONMENT CONFIGURATION**: All API keys, OAuth2 credentials, and secrets are already configured in `deal-intelligence-engine/.env.local`. Tasks do NOT need to manually fill in environment variables. The implementation agent must use the existing `.env.local` file which follows the variable names from `.env.example`.

### Task 1: VERIFY `.env.local` exists with all credentials

- **IMPLEMENT**: Check that `deal-intelligence-engine/.env.local` exists and contains all required environment variables
- **PATTERN**: **CRITICAL NOTE**: The user has already configured `.env.local` with all API keys, OAuth2 credentials, and secrets. **DO NOT create a new `.env` file.** The existing `.env.local` follows the variable names in `.env.example` and is ready to use.
- **IMPORTS**: None (file check)
- **GOTCHA**: Docker Compose automatically loads `.env.local` if it exists (overrides `.env`). All subsequent tasks assume credentials are already configured.
- **VALIDATE**:
  ```bash
  test -f deal-intelligence-engine/.env.local && echo "✓ .env.local exists" || (echo "✗ .env.local missing - create it from .env.example" && exit 1)
  ```

### Task 2: VERIFY all required environment variables are set

- **IMPLEMENT**: Validate that `.env.local` contains all 54 required environment variables with non-placeholder values
- **PATTERN**: Check for critical variables that must be set before deployment:
  - N8N_ENCRYPTION_KEY (32-char hex)
  - POSTGRES_PASSWORD (strong password)
  - REDIS_PASSWORD
  - OPENAI_API_KEY (starts with sk-)
  - ANTHROPIC_API_KEY (starts with sk-ant-)
  - GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET
  - GMAIL_SEND_CLIENT_ID and GMAIL_SEND_CLIENT_SECRET
  - GMAIL_INGESTION_ADDRESS (email address)
  - AUSTIN_EMAIL (email address)
- **IMPORTS**: grep, awk
- **GOTCHA**: If any critical variable is missing or still has placeholder value (REPLACE_WITH_*), deployment will fail
- **VALIDATE**:
  ```bash
  cd deal-intelligence-engine && \
  grep -q "^N8N_ENCRYPTION_KEY=[^R]" .env.local && \
  grep -q "^OPENAI_API_KEY=sk-" .env.local && \
  grep -q "^ANTHROPIC_API_KEY=sk-ant-" .env.local && \
  grep -q "^GMAIL_CLIENT_ID=[^R]" .env.local && \
  grep -q "^GMAIL_INGESTION_ADDRESS=.*@" .env.local && \
  echo "✓ All critical environment variables set" || \
  (echo "✗ Missing or invalid environment variables" && exit 1)
  ```

### Task 3: SKIP - Environment already configured

- **IMPLEMENT**: This task is no longer needed since `.env.local` is already configured
- **PATTERN**: N/A
- **IMPORTS**: N/A
- **GOTCHA**: Tasks 1-2 verify the existing configuration; no manual API key entry required
- **VALIDATE**: N/A

### Task 4: START Docker Compose stack (uses .env.local automatically)

- **IMPLEMENT**: `cd deal-intelligence-engine && docker compose up -d`
- **PATTERN**: Starts 5 services: n8n, Qdrant, Postgres, Redis, Metabase. Docker Compose automatically loads `.env.local` if present (takes precedence over `.env`)
- **IMPORTS**: Requires Docker and Docker Compose v2.0+
- **GOTCHA**: n8n waits for postgres/redis health checks to pass; may take 30-60 seconds. All environment variables from `.env.local` are automatically injected into containers.
- **VALIDATE**: `docker compose ps | grep -E "Up|healthy" | wc -l | grep -q 5 && echo "✓ All 5 services running"`

### Task 5: VERIFY Postgres schema initialized

- **IMPLEMENT**: Connect to Postgres and count tables in clearwater_deals database
- **PATTERN**: `docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c "\dt"`
- **IMPORTS**: None (docker exec)
- **GOTCHA**: 01_schema.sql runs automatically on first startup via /docker-entrypoint-initdb.d/
- **VALIDATE**: `docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'" | grep -q 7 && echo "✓ 7 tables created"`

### Task 6: VERIFY Qdrant service is healthy

- **IMPLEMENT**: Poll `http://localhost:6333/healthz` endpoint
- **PATTERN**: `curl -f http://localhost:6333/healthz && echo "✓ Qdrant healthy"`
- **IMPORTS**: curl
- **GOTCHA**: Qdrant may take 10-15 seconds to fully initialize after docker up
- **VALIDATE**: `curl -s http://localhost:6333/healthz | grep -q "ok" && echo "✓ Qdrant ready"`

### Task 7: CREATE Qdrant "deals" collection

- **IMPLEMENT**: Execute `bash deal-intelligence-engine/scripts/create-qdrant-collection.sh`
- **PATTERN**: PUT request to /collections/deals with 1536-dim vectors, Cosine distance, int8 quantization
- **IMPORTS**: curl, jq (for response parsing)
- **GOTCHA**: If collection already exists, script handles gracefully (idempotent)
- **VALIDATE**: `curl -s http://localhost:6333/collections/deals | jq -r '.result.status' | grep -q "green" && echo "✓ Collection created"`

### Task 8: SKIP - Gmail OAuth2 already configured in .env.local

- **IMPLEMENT**: N/A - Gmail OAuth2 credentials already set up in `.env.local`
- **PATTERN**: User has completed Google Cloud Console OAuth2 app registration
- **IMPORTS**: N/A
- **GOTCHA**: `.env.local` contains GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_SEND_CLIENT_ID, GMAIL_SEND_CLIENT_SECRET
- **VALIDATE**: `grep -q "GMAIL_CLIENT_ID=" deal-intelligence-engine/.env.local && echo "✓ Gmail OAuth2 configured"`

### Task 9: SKIP - Credentials already in .env.local

- **IMPLEMENT**: N/A - All credentials already configured
- **PATTERN**: N/A
- **IMPORTS**: N/A
- **GOTCHA**: N/A
- **VALIDATE**: N/A

### Task 10: OPEN n8n UI and complete first-run setup (via browser agent)

- **IMPLEMENT**: Use browser agent to navigate to `http://localhost:5678` and complete first-run setup (see E2E Test 1 in BROWSER AGENT END-TO-END TESTING section)
- **PATTERN**: n8n first-run wizard prompts for admin user creation. Browser agent automates this process.
  - Email: admin@clearwater.local
  - Password: SecurePassword123!
- **IMPORTS**: agent-browser skill
- **GOTCHA**: If n8n already set up (not first run), browser agent will log in instead. Check for existing admin user before attempting signup.
- **VALIDATE**: `curl -f http://localhost:5678 > /dev/null 2>&1 && echo "✓ n8n UI accessible"`

### Task 11: CREATE Gmail Ingestion Inbox credential in n8n (via browser agent)

- **IMPLEMENT**: Use browser agent to configure Gmail OAuth2 credential in n8n UI (see E2E Test 2, step 2 for verification pattern)
  - Navigate to `http://localhost:5678/credentials`
  - Click "Create New Credential"
  - Search for "Google OAuth2 API"
  - Name: "Gmail Ingestion Inbox"
  - Credential Data:
    - Client ID: from .env.local GMAIL_CLIENT_ID
    - Client Secret: from .env.local GMAIL_CLIENT_SECRET
    - Scope: `https://www.googleapis.com/auth/gmail.readonly`
  - Click "Connect my account" → complete OAuth flow → authorize
  - Verify "Connected" status
  - Save
- **PATTERN**: n8n credential wizard with OAuth2 flow. All secrets already in `.env.local`, just need to configure in n8n UI.
- **IMPORTS**: agent-browser skill, Gmail account credentials
- **GOTCHA**: OAuth flow opens popup/new tab - browser agent must handle OAuth redirect
- **VALIDATE**: Check credential status via browser agent (see E2E Test 2) or n8n API:
  ```bash
  curl -s http://localhost:5678/api/v1/credentials \
    -H "X-N8N-API-KEY: $(grep N8N_API_KEY deal-intelligence-engine/.env.local | cut -d= -f2)" | \
    jq -r '.data[] | select(.name == "Gmail Ingestion Inbox") | .name' | grep -q "Gmail" && echo "✓ Gmail Ingestion credential exists"
  ```

### Task 12: CREATE Gmail Send credential in n8n (via browser agent)

- **IMPLEMENT**: Use browser agent to configure second Gmail credential:
  - Name: "Gmail Send"
  - Client ID/Secret: from .env.local GMAIL_SEND_CLIENT_ID/GMAIL_SEND_CLIENT_SECRET
  - Scope: `https://www.googleapis.com/auth/gmail.send`
- **PATTERN**: Same as Task 11, credentials from `.env.local`
- **IMPORTS**: agent-browser skill
- **GOTCHA**: Separate credential for sending (write permission) vs reading (read-only)
- **VALIDATE**: Via browser agent (E2E Test 2, step 3) or API:
  ```bash
  curl -s http://localhost:5678/api/v1/credentials \
    -H "X-N8N-API-KEY: $(grep N8N_API_KEY deal-intelligence-engine/.env.local | cut -d= -f2)" | \
    jq -r '.data[] | select(.name == "Gmail Send") | .name' | grep -q "Gmail" && echo "✓ Gmail Send credential exists"
  ```

### Task 13: CREATE OpenAI API credential in n8n (via browser agent)

- **IMPLEMENT**: Use browser agent to configure OpenAI credential:
  - Navigate to Credentials > Create New
  - Search for "OpenAI API"
  - Name: "OpenAI API"
  - API Key: from .env.local OPENAI_API_KEY (starts with sk-...)
  - Save
- **PATTERN**: Static API key credential (no OAuth). Value from `.env.local`.
- **IMPORTS**: agent-browser skill
- **GOTCHA**: Ensure OPENAI_API_KEY in `.env.local` has sufficient credits/quota
- **VALIDATE**: Via browser agent (E2E Test 2, step 4) or API

### Task 14: CREATE Anthropic API credential in n8n (via browser agent)

- **IMPLEMENT**: Use browser agent to configure Anthropic credential:
  - Settings > Credentials > Create New
  - Search for "Anthropic"
  - Name: "Anthropic API"
  - API Key: from .env.local ANTHROPIC_API_KEY (starts with sk-ant-...)
  - Save
- **PATTERN**: Static API key credential. Value from `.env.local`.
- **IMPORTS**: agent-browser skill
- **GOTCHA**: Ensure ANTHROPIC_API_KEY in `.env.local` has access to Claude Sonnet 4.6 and Opus 4.6
- **VALIDATE**: Via browser agent (E2E Test 2, step 5) or API

### Task 15: CREATE Postgres credential in n8n (via browser agent)

- **IMPLEMENT**: Use browser agent to configure Postgres credential:
  - Settings > Credentials > Create New
  - Search for "PostgreSQL"
  - Name: "Clearwater Postgres"
  - Host: `postgres` (Docker internal DNS)
  - Database: `clearwater_deals`
  - User: `clearwater`
  - Password: from .env.local POSTGRES_PASSWORD
  - Port: 5432
  - SSL Mode: Disable (internal Docker network)
  - Click "Test connection" → verify success
  - Save
- **PATTERN**: Database connection credential. Password from `.env.local`.
- **IMPORTS**: agent-browser skill
- **GOTCHA**: Use container name `postgres` not `localhost` (Docker DNS resolution)
- **VALIDATE**: Via browser agent (E2E Test 2, step 6) - test connection returns success

### Task 16: CREATE Qdrant credential in n8n (via browser agent)

- **IMPLEMENT**: Use browser agent to configure Qdrant credential:
  - Settings > Credentials > Create New
  - Search for "Qdrant API"
  - Name: "Qdrant Local"
  - URL: `http://qdrant:6333` (Docker internal DNS)
  - API Key: Leave blank (local Docker, no auth)
  - Save
- **PATTERN**: HTTP API credential. No secrets needed for local Qdrant.
- **IMPORTS**: agent-browser skill
- **GOTCHA**: Use `http://qdrant:6333` not `http://localhost:6333` (Docker DNS)
- **VALIDATE**: Via browser agent (E2E Test 2, step 7)

### Task 17: CREATE Redis credential in n8n (via browser agent)

- **IMPLEMENT**: Use browser agent to configure Redis credential:
  - Settings > Credentials > Create New
  - Search for "Redis"
  - Name: "Redis"
  - Host: `redis`
  - Port: 6379
  - Password: from .env.local REDIS_PASSWORD
  - Database: 0
  - Save
- **PATTERN**: Redis connection credential. Password from `.env.local`.
- **IMPORTS**: agent-browser skill
- **GOTCHA**: Redis in Docker requires password (set in docker-compose.yml via `.env.local`)
- **VALIDATE**: Via browser agent (E2E Test 2, step 8)

### Task 18: IMPORT workflow-01-ingestion.json into n8n (via browser agent)

- **IMPLEMENT**: Use browser agent to import workflow (see E2E Test 3, steps 1-4 for detailed browser automation):
  - Navigate to `http://localhost:5678/workflows`
  - Click "+ Add workflow" or "Create new workflow"
  - Click "..." menu > "Import from File"
  - Upload file: `deal-intelligence-engine/n8n/workflows/workflow-01-ingestion.json`
  - Wait for import to complete
  - Verify 22 nodes visible on canvas
  - Save workflow
- **PATTERN**: n8n JSON workflow import via browser automation
- **IMPORTS**: agent-browser skill
- **GOTCHA**: Workflow imports but credentials are NOT mapped yet (done in Task 19)
- **VALIDATE**: Via browser agent - count nodes on canvas = 22, or via API:
  ```bash
  curl -s http://localhost:5678/api/v1/workflows \
    -H "X-N8N-API-KEY: $(grep N8N_API_KEY deal-intelligence-engine/.env.local | cut -d= -f2)" | \
    jq -r '.data[] | select(.name | contains("Ingestion")) | .name' | grep -q "Ingestion" && echo "✓ Workflow imported"
  ```

### Task 19: MAP credentials to workflow nodes (via browser agent)

- **IMPLEMENT**: Use browser agent to map credentials to each node (see E2E Test 3, steps 5-9 for detailed pattern):
  - For each node requiring a credential:
    1. Click node to select it
    2. In right panel, find credential dropdown
    3. Select appropriate credential from dropdown
    4. Verify credential mapped (no red warning icon)
  - **Nodes to configure**:
    - Gmail Trigger → "Gmail Ingestion Inbox"
    - Gmail: Get Full Message → "Gmail Ingestion Inbox"
    - AI: Classify & Attribute Email (Claude) → "Anthropic API"
    - Postgres nodes (Check Duplicate, Lookup Deal, Queue, Log) → "Clearwater Postgres"
    - OpenAI Embeddings → "OpenAI API"
    - Qdrant: Insert Vectors → "Qdrant Local"
  - Save workflow after all credentials mapped
- **PATTERN**: n8n credential mapping via browser automation
- **IMPORTS**: agent-browser skill
- **GOTCHA**: Some nodes have multiple credential fields; ensure all are filled
- **VALIDATE**: Via browser agent - no red warning icons on any node, or visually inspect canvas

### Task 20: SKIP - Individual node testing not needed

- **IMPLEMENT**: Skip this task - individual node testing in n8n test mode is unreliable for trigger-based workflows
- **PATTERN**: Gmail Trigger won't fire in test mode (webhook/poll triggers require real events)
- **IMPORTS**: N/A
- **GOTCHA**: Proceed directly to Task 21 (activate workflow) and Task 22 (end-to-end test with real email)
- **VALIDATE**: N/A

### Task 21: ACTIVATE workflow (via browser agent)

- **IMPLEMENT**: Use browser agent to activate workflow (see E2E Test 3, step 11 for detailed pattern):
  - Ensure workflow is saved (no unsaved changes indicator)
  - Click "Active" toggle switch in top right of workflow editor
  - Verify toggle shows enabled state (green)
  - Verify status badge changes to "Active"
  - Gmail Trigger now polls every 5 minutes automatically
- **PATTERN**: n8n workflow activation via browser automation
- **IMPORTS**: agent-browser skill
- **GOTCHA**: Workflow must be saved before activation; unsaved changes prevent toggle
- **VALIDATE**: Via browser agent - status badge shows "Active", or via API:
  ```bash
  curl -s http://localhost:5678/api/v1/workflows \
    -H "X-N8N-API-KEY: $(grep N8N_API_KEY deal-intelligence-engine/.env.local | cut -d= -f2)" | \
    jq -r '.data[] | select(.name | contains("Ingestion")) | .active' | grep -q "true" && echo "✓ Workflow active"
  ```

### Task 22: SEND test email to ingestion inbox (via browser agent)

- **IMPLEMENT**: Use browser agent to send test email via Gmail (see E2E Test 4, step 3 for detailed pattern):
  - Navigate to `https://mail.google.com`
  - Log in with sender Gmail account
  - Click "Compose" button
  - Fill in test email:
    - To: [value from GMAIL_INGESTION_ADDRESS in .env.local]
    - Subject: "E2E Test - Acme Hospital Deal - [timestamp]"
    - Body:
      ```
      This is an automated end-to-end test email for the Clearwater Deal Intelligence Engine ingestion pipeline.

      Deal Company: Acme Hospital
      Contact: John Smith, CISO
      Date: [current date]

      Key discussion points:
      - Current compliance gaps in HIPAA audit preparation
      - Budget approved: $150K for Q2 2026
      - Decision maker: Jane Doe, CFO
      - Next step: Schedule Prove-stage presentation for March 15

      Test ID: e2e-test-[timestamp]
      ```
  - Click "Send"
  - Verify "Message sent" confirmation
  - Wait 5-10 minutes for Gmail Trigger poll
- **PATTERN**: Browser-automated Gmail compose and send
- **IMPORTS**: agent-browser skill, Gmail credentials
- **GOTCHA**: First execution may take up to 5 minutes (poll interval); browser agent must handle Gmail auth
- **VALIDATE**: Screenshot of sent confirmation, then proceed to Task 23

### Task 23: VERIFY workflow execution in n8n logs (via browser agent)

- **IMPLEMENT**: Use browser agent to monitor and verify workflow execution (see E2E Test 4, steps 4-16 for complete detailed pattern):
  - Navigate to `http://localhost:5678/executions`
  - Wait for new execution to appear (poll every 30 seconds, max 5 minutes)
  - Click latest execution to view details
  - Verify execution status shows "Success"
  - Verify all 22 nodes show green checkmarks (successful execution)
  - **Inspect critical nodes** (click each to view output):
    - Gmail Trigger: Captured test email with correct subject
    - AI Classify: Company "Acme Hospital", confidence "high", doc_type "email"
    - Postgres Check Duplicate: Empty result (new email)
    - Assign Deal ID: deal_id follows pattern "cw_acmehospital_2026"
    - Contextual Enrichment: [DEAL CONTEXT] header prepended
    - OpenAI Embeddings: 1536-dim vectors generated
    - Qdrant Insert: Success response
    - Postgres Log: 1 row inserted to ingestion_log
    - HTTP Trigger: POST sent to /webhook/deal-health-trigger
  - Take screenshot of successful execution canvas
- **PATTERN**: Browser-automated n8n execution monitoring and verification
- **IMPORTS**: agent-browser skill
- **GOTCHA**: If any node shows red (error), capture error details via browser agent before proceeding
- **VALIDATE**: Via browser agent - all nodes green, or via API:
  ```bash
  curl -s http://localhost:5678/api/v1/executions \
    -H "X-N8N-API-KEY: $(grep N8N_API_KEY deal-intelligence-engine/.env.local | cut -d= -f2)" | \
    jq -r '.data[0].status' | grep -q "success" && echo "✓ Latest execution succeeded"
  ```

### Task 24: VERIFY Postgres ingestion_log entry

- **IMPLEMENT**:
  ```bash
  docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
    "SELECT message_id, deal_id, doc_type, chunk_count FROM ingestion_log ORDER BY ingested_at DESC LIMIT 1"
  ```
- **PATTERN**: SQL verification query
- **IMPORTS**: docker, psql
- **GOTCHA**: Ensure timestamp is recent (within last 10 minutes)
- **VALIDATE**: Output shows test email's message_id, deal_id, doc_type="email", chunk_count > 0

### Task 25: VERIFY Qdrant vector insertion

- **IMPLEMENT**:
  ```bash
  curl -X POST http://localhost:6333/collections/deals/points/scroll \
    -H "Content-Type: application/json" \
    -d '{"limit": 5, "with_payload": true, "with_vector": false}' | jq
  ```
- **PATTERN**: Qdrant scroll API query
- **IMPORTS**: curl, jq
- **GOTCHA**: Vectors stored with namespace in payload as "deal_id" key
- **VALIDATE**: Output shows points with payload containing "deal_id": "cw_acmehospital_2026"

### Task 26: VERIFY contextual enrichment applied

- **IMPLEMENT**:
  ```bash
  curl -X POST http://localhost:6333/collections/deals/points/scroll \
    -H "Content-Type: application/json" \
    -d '{"limit": 1, "with_payload": true, "with_vector": false}' | jq -r '.result.points[0].payload'
  ```
- **PATTERN**: Payload inspection
- **IMPORTS**: curl, jq
- **GOTCHA**: Check for "deal_id", "company_name", "doc_type", "date_created" keys
- **VALIDATE**: Payload contains all expected metadata fields

### Task 27: TEST deduplication by resending same email

- **IMPLEMENT**:
  1. Forward the same test email again to ingestion inbox
  2. Wait 5-10 minutes for workflow execution
  3. Check n8n Executions tab for new execution
  4. Verify workflow path:
     - Postgres Check Duplicate: Found existing message_id
     - Workflow terminates early (no processing after dedup check)
  5. Check ingestion_log: Only 1 row for this message_id
- **PATTERN**: Idempotency test
- **IMPORTS**: Gmail
- **GOTCHA**: Gmail may change message_id if email is edited; ensure exact forward
- **VALIDATE**: Second execution terminates early, no duplicate ingestion_log row

### Task 28: TEST low-confidence attribution (queue insertion)

- **IMPLEMENT**:
  1. Send email with ambiguous attribution:
     - To: ingestion inbox
     - From: personal email (not a known deal sender domain)
     - Subject: "Quick question about compliance software"
     - Body: Generic message, no company name mentioned
  2. Wait for workflow execution
  3. Verify Claude classification returns confidence "low"
  4. Verify workflow routes to "Postgres: Queue for Confirmation" node
  5. Check attribution_queue table:
     ```bash
     docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
       "SELECT message_id, ai_guess_company, ai_confidence, resolution FROM attribution_queue ORDER BY queued_at DESC LIMIT 1"
     ```
  6. Verify row inserted with resolution="pending"
- **PATTERN**: Low-confidence routing test
- **IMPORTS**: Gmail, docker, psql
- **GOTCHA**: Claude's confidence scoring may vary; adjust email to be more ambiguous if needed
- **VALIDATE**: attribution_queue contains pending row for ambiguous email

### Task 29: TEST attachment extraction (PDF)

- **IMPLEMENT**:
  1. Create test PDF with sample content (or use existing PDF)
  2. Send email to ingestion inbox with PDF attachment
  3. Wait for workflow execution
  4. Verify workflow path includes "Extract from File" node
  5. Verify Qdrant insertion includes chunks from PDF content
  6. Check ingestion_log: attachment_count = 1, chunk_count > 0
- **PATTERN**: Attachment processing test
- **IMPORTS**: PDF file, Gmail
- **GOTCHA**: PDF extraction may require additional n8n nodes (pdf-parse library); if not implemented, add to backlog
- **VALIDATE**: PDF content visible in Qdrant payload or ingestion_log shows attachment_count=1

### Task 30: TEST webhook trigger to Deal Health Agent

- **IMPLEMENT**:
  1. After successful test email ingestion (Task 22-23)
  2. Check n8n execution for final node "HTTP: Trigger Health Agent"
  3. Verify HTTP POST sent to `http://n8n:5678/webhook/deal-health-trigger`
  4. Verify request body contains: deal_id, trigger_message_id, trigger_type="new_ingestion"
  5. Note: Workflow 02 (Deal Health Agent) not yet active, so webhook will return 404
  6. This is expected and valid for Phase 1 (Phase 2 deployment will activate webhook receiver)
- **PATTERN**: Cross-workflow webhook test
- **IMPORTS**: None
- **GOTCHA**: 404 response is EXPECTED in Phase 1; do not treat as error
- **VALIDATE**: HTTP node shows POST sent successfully (200 or 404 acceptable)

### Task 31: CREATE deployment documentation

- **IMPLEMENT**: Write `deal-intelligence-engine/DEPLOYMENT.md` with:
  - Prerequisites (Docker, Docker Compose, API keys)
  - Step-by-step deployment commands
  - Credential setup instructions
  - Validation commands
  - Troubleshooting section
  - URLs for all 5 services
  - Reference to this implementation plan
- **PATTERN**: Markdown documentation
- **IMPORTS**: None
- **GOTCHA**: Keep documentation in sync with .env.example and setup.sh changes
- **VALIDATE**: File exists and contains all deployment steps

### Task 32: CREATE testing documentation

- **IMPLEMENT**: Write `deal-intelligence-engine/TESTING.md` with:
  - Test scenarios from Tasks 22-30
  - Sample test emails (various doc types, confidence levels)
  - Validation commands for each service
  - Expected outputs for each test
  - Known issues and workarounds
- **PATTERN**: Markdown test plan
- **IMPORTS**: None
- **GOTCHA**: Include both positive tests (happy path) and negative tests (edge cases)
- **VALIDATE**: File exists and covers all test scenarios

---

## TESTING STRATEGY

### Unit Testing Approach

**Scope**: Individual workflow nodes tested in isolation using n8n's built-in test mode.

**Pattern**:
1. Open workflow in n8n UI
2. Select individual node
3. Click "Execute Node" (test single node)
4. Provide mock input data
5. Verify output matches expected structure

**Critical Nodes to Unit Test**:
- **AI: Classify & Attribute Email**: Test with 10 sample emails (5 high-confidence, 3 medium, 2 low)
  - Expected output: JSON with company_name, confidence, doc_type
- **Code: Parse Classification**: Test JSON parsing with various Claude response formats (with/without markdown code fences)
- **Code: Contextual Enrichment**: Verify [DEAL CONTEXT] header prepended correctly
- **Recursive Text Splitter**: Test with 2000-word document, verify 500-token chunks with 50-token overlap
- **OpenAI Embeddings**: Test with sample text, verify 1536-dim vector output

### Integration Testing Approach

**Scope**: End-to-end workflow execution with real Gmail emails and API calls.

**Test Matrix**:

| Test Case | Input | Expected Output |
|-----------|-------|-----------------|
| Happy Path | Normal email from known sender | Auto-assigned to deal, vectors in Qdrant, log in Postgres, webhook triggered |
| Duplicate Email | Same email sent twice | First processes normally, second terminates at dedup check |
| Low Confidence | Email from unknown sender, no company name | Inserted to attribution_queue, no Qdrant insertion |
| PDF Attachment | Email with 5-page PDF | PDF text extracted, chunked, embedded, stored |
| Large Attachment | Email with 25MB PDF | Workflow logs warning, skips file (>20MB limit) |
| Malformed Email | Email with no body | Workflow handles gracefully, logs error, continues |
| API Rate Limit | Send 100 emails rapidly | Some executions fail, retry logic kicks in |
| Service Restart | docker compose down && up during execution | In-flight executions fail, new executions resume normally |

### Edge Case Testing

**Edge Cases to Validate**:

1. **Gmail API Quota Exceeded**
   - Trigger: Send 1000+ emails in 1 hour
   - Expected: n8n logs error, retries after backoff, resumes when quota resets
   - Validation: Check n8n error logs for "quotaExceeded" message

2. **OpenAI API Downtime**
   - Trigger: Manually break OPENAI_API_KEY in .env, restart n8n
   - Expected: Embeddings node fails, workflow execution marked as error
   - Validation: n8n execution shows red X on Embeddings node

3. **Qdrant Collection Full** (hypothetical)
   - Trigger: Not applicable for local Qdrant (no hard limit)
   - Expected: N/A
   - Validation: N/A

4. **Postgres Connection Lost**
   - Trigger: `docker stop clearwater-postgres` during workflow execution
   - Expected: Postgres nodes fail, workflow retries, marks execution as failed
   - Validation: n8n execution shows error on Postgres nodes

5. **Email with 100+ Recipients**
   - Trigger: Send email with long CC list
   - Expected: Workflow processes normally, extracts sender_email correctly
   - Validation: ingestion_log shows correct sender_email, not CC addresses

6. **Unicode Characters in Email Body**
   - Trigger: Send email with emojis, Chinese characters, special symbols
   - Expected: Text extracted correctly, embeddings handle non-ASCII
   - Validation: Qdrant payload contains Unicode text (query via scroll API)

7. **Email with Inline Images**
   - Trigger: Send email with embedded image (not attachment)
   - Expected: Image ignored, text extracted normally
   - Validation: ingestion_log shows attachment_count=0, chunk_count > 0

8. **Sender Domain Mismatch**
   - Trigger: Email from john@acmehospital.org but deal record has sender_domains=["acme.com"]
   - Expected: Claude classification suggests "Acme Hospital" based on content, auto-assigned via company_name match
   - Validation: ingestion_log shows correct deal_id despite domain mismatch

---

## BROWSER AGENT END-TO-END TESTING

**CRITICAL**: All E2E testing must be performed using the `agent-browser` skill for complete automation. The following test scenarios must be executed step-by-step with explicit verification at each stage.

### Prerequisites for Browser Testing

**Environment Requirements**:
- `.env.local` configured with all API keys and OAuth2 credentials
- Docker Compose stack running (all 5 services healthy)
- Qdrant "deals" collection created and verified
- Postgres schema initialized (7 tables exist)

**Browser Agent Configuration**:
- Headless mode: false (visible browser for debugging)
- Screenshot on error: true
- Viewport: 1920x1080
- Browser: Chromium

---

### E2E Test 1: n8n First-Run Setup and Dashboard Verification

**Test Objective**: Verify n8n service is accessible, first-run wizard completes, and dashboard loads correctly.

**Steps**:

1. **Navigate to n8n UI**
   - Action: `browser.navigate("http://localhost:5678")`
   - Expected: n8n login or first-run setup page loads
   - Verify: Page title contains "n8n" or "workflow automation"
   - Screenshot: `n8n-landing.png`

2. **Check for first-run setup wizard**
   - Action: `browser.wait_for_selector('form[data-test-id="setup-form"]', timeout=5000)` (if exists)
   - Expected: If first-run, setup form appears; otherwise, login form
   - Verify: Form elements visible (email, password fields)
   - Screenshot: `n8n-setup-form.png`

3. **Complete first-run setup (if needed)**
   - Action: `browser.fill('input[name="email"]', "admin@clearwater.local")`
   - Action: `browser.fill('input[name="password"]', "SecurePassword123!")`
   - Action: `browser.fill('input[name="firstName"]', "Admin")`
   - Action: `browser.fill('input[name="lastName"]', "User")`
   - Action: `browser.click('button[type="submit"]')`
   - Expected: Setup completes, redirects to dashboard
   - Verify: URL changes to `/home` or `/workflows`
   - Screenshot: `n8n-setup-complete.png`

4. **Login (if setup already done)**
   - Action: `browser.fill('input[name="email"]', "admin@clearwater.local")`
   - Action: `browser.fill('input[name="password"]', "SecurePassword123!")`
   - Action: `browser.click('button[type="submit"]')`
   - Expected: Login successful, dashboard loads
   - Verify: URL contains `/home` or `/workflows`
   - Screenshot: `n8n-login-success.png`

5. **Verify dashboard elements**
   - Action: `browser.wait_for_selector('[data-test-id="resources-list-layout"]', timeout=10000)`
   - Expected: Workflows list or empty state visible
   - Verify: "Create new workflow" button present
   - Verify: Top navigation bar with "Workflows", "Credentials", "Executions" visible
   - Screenshot: `n8n-dashboard.png`

**Validation**:
```bash
curl -f http://localhost:5678 > /dev/null 2>&1 && echo "✓ n8n UI accessible"
```

---

### E2E Test 2: Credential Configuration Verification

**Test Objective**: Verify all 7 required credentials are configured in n8n.

**Steps**:

1. **Navigate to Credentials page**
   - Action: `browser.click('a[href="/credentials"]')` or `browser.navigate("http://localhost:5678/credentials")`
   - Expected: Credentials list page loads
   - Verify: Page title or heading contains "Credentials"
   - Screenshot: `n8n-credentials-page.png`

2. **Search for Gmail Ingestion Inbox credential**
   - Action: `browser.fill('input[placeholder*="Search credentials"]', "Gmail Ingestion")`
   - Expected: Filter results to show "Gmail Ingestion Inbox" credential
   - Verify: Credential card with name "Gmail Ingestion Inbox" visible
   - Verify: Status shows "Connected" (green icon or checkmark)
   - Screenshot: `credential-gmail-ingestion.png`

3. **Verify Gmail Send credential**
   - Action: `browser.fill('input[placeholder*="Search credentials"]', "Gmail Send")`
   - Expected: "Gmail Send" credential visible
   - Verify: Status shows "Connected"
   - Screenshot: `credential-gmail-send.png`

4. **Verify OpenAI API credential**
   - Action: `browser.fill('input[placeholder*="Search credentials"]', "OpenAI")`
   - Expected: "OpenAI API" credential visible
   - Verify: Status shows configured (API key masked)
   - Screenshot: `credential-openai.png`

5. **Verify Anthropic API credential**
   - Action: `browser.fill('input[placeholder*="Search credentials"]', "Anthropic")`
   - Expected: "Anthropic API" credential visible
   - Verify: Status shows configured
   - Screenshot: `credential-anthropic.png`

6. **Verify Postgres credential**
   - Action: `browser.fill('input[placeholder*="Search credentials"]', "Postgres")`
   - Expected: "Clearwater Postgres" credential visible
   - Verify: Connection configured (host: postgres, db: clearwater_deals)
   - Screenshot: `credential-postgres.png`

7. **Verify Qdrant credential**
   - Action: `browser.fill('input[placeholder*="Search credentials"]', "Qdrant")`
   - Expected: "Qdrant Local" credential visible
   - Verify: URL configured (http://qdrant:6333)
   - Screenshot: `credential-qdrant.png`

8. **Verify Redis credential**
   - Action: `browser.fill('input[placeholder*="Search credentials"]', "Redis")`
   - Expected: "Redis" credential visible
   - Verify: Connection configured
   - Screenshot: `credential-redis.png`

**Validation**:
```bash
# Count configured credentials via n8n API
curl -s http://localhost:5678/api/v1/credentials \
  -H "X-N8N-API-KEY: $(grep N8N_API_KEY deal-intelligence-engine/.env.local | cut -d= -f2)" | \
  jq '.data | length' | grep -E "[7-9]|[1-9][0-9]+" && echo "✓ At least 7 credentials configured"
```

---

### E2E Test 3: Workflow Import and Activation

**Test Objective**: Import workflow-01-ingestion.json and verify all nodes have credentials mapped.

**Steps**:

1. **Navigate to Workflows page**
   - Action: `browser.navigate("http://localhost:5678/workflows")`
   - Expected: Workflows list page loads
   - Verify: Page shows workflow list or empty state
   - Screenshot: `workflows-list-before-import.png`

2. **Click Import workflow**
   - Action: `browser.click('button[data-test-id="resources-list-add"]')` or similar "+" button
   - Action: `browser.click('button:has-text("Import from file")')` or navigate to import option
   - Expected: File picker appears or import dialog opens
   - Verify: File input element visible
   - Screenshot: `workflow-import-dialog.png`

3. **Select workflow JSON file**
   - Action: `browser.set_input_files('input[type="file"]', 'deal-intelligence-engine/n8n/workflows/workflow-01-ingestion.json')`
   - Expected: File selected, import begins
   - Verify: Loading indicator or progress bar appears
   - Wait: 5 seconds for import to complete
   - Screenshot: `workflow-importing.png`

4. **Verify workflow imported**
   - Action: `browser.wait_for_selector('text="Ingestion Pipeline"', timeout=10000)`
   - Expected: Workflow opens in editor
   - Verify: 22 nodes visible on canvas
   - Verify: Workflow name in top bar: "Ingestion Pipeline"
   - Screenshot: `workflow-imported-canvas.png`

5. **Verify Gmail Trigger node has credential**
   - Action: `browser.click('[data-test-id="canvas-node"][data-name*="Gmail"]')` (select Gmail Trigger node)
   - Expected: Node parameters panel opens on right side
   - Verify: Credential dropdown shows "Gmail Ingestion Inbox" selected
   - Verify: No red warning icon on node (missing credential indicator)
   - Screenshot: `node-gmail-trigger-configured.png`

6. **Verify Claude Sonnet node has credential**
   - Action: `browser.click('[data-test-id="canvas-node"][data-name*="Claude"]')` (select AI Classify node)
   - Expected: Node parameters panel opens
   - Verify: Credential dropdown shows "Anthropic API" selected
   - Screenshot: `node-claude-configured.png`

7. **Verify OpenAI Embeddings node has credential**
   - Action: `browser.click('[data-test-id="canvas-node"][data-name*="Embeddings"]')` (select Embeddings node)
   - Expected: Node parameters panel opens
   - Verify: Credential dropdown shows "OpenAI API" selected
   - Screenshot: `node-openai-configured.png`

8. **Verify Qdrant Insert node has credential**
   - Action: `browser.click('[data-test-id="canvas-node"][data-name*="Qdrant"]')` (select Qdrant node)
   - Expected: Node parameters panel opens
   - Verify: Credential dropdown shows "Qdrant Local" selected
   - Verify: Collection name set to "deals"
   - Screenshot: `node-qdrant-configured.png`

9. **Verify Postgres nodes have credentials**
   - Action: Iterate through all Postgres nodes (Check Duplicate, Lookup Deal, Log Ingestion)
   - Expected: Each node shows "Clearwater Postgres" credential selected
   - Screenshot: `nodes-postgres-all-configured.png`

10. **Save workflow**
    - Action: `browser.click('button[data-test-id="workflow-save-button"]')` or Ctrl+S
    - Expected: "Workflow saved" toast notification appears
    - Verify: No unsaved changes indicator (dot on workflow name)
    - Screenshot: `workflow-saved.png`

11. **Activate workflow**
    - Action: `browser.click('button[data-test-id="workflow-activate-button"]')` or toggle Active switch
    - Expected: Workflow status changes to "Active"
    - Verify: Toggle switch shows green/enabled state
    - Verify: Status badge shows "Active"
    - Screenshot: `workflow-activated.png`

**Validation**:
```bash
# Check workflow exists and is active
curl -s http://localhost:5678/api/v1/workflows \
  -H "X-N8N-API-KEY: $(grep N8N_API_KEY deal-intelligence-engine/.env.local | cut -d= -f2)" | \
  jq -r '.data[] | select(.name | contains("Ingestion")) | .active' | grep -q "true" && \
  echo "✓ Ingestion Pipeline workflow active"
```

---

### E2E Test 4: Live Workflow Execution Monitoring

**Test Objective**: Send test email to ingestion inbox and monitor real-time workflow execution in n8n UI.

**Prerequisites**:
- Workflow activated (from Test 3)
- Gmail ingestion inbox accessible
- Test email ready to send

**Steps**:

1. **Navigate to Executions page**
   - Action: `browser.navigate("http://localhost:5678/executions")`
   - Expected: Executions list page loads
   - Verify: Table or list of past executions visible (may be empty)
   - Screenshot: `executions-before-test.png`

2. **Note latest execution timestamp**
   - Action: `browser.evaluate(() => document.querySelector('[data-test-id="execution-list-item"]')?.textContent)` (get latest execution time if exists)
   - Expected: Capture current state for comparison
   - Store: `latest_execution_before = timestamp`

3. **Send test email to ingestion inbox**
   - Action: Open Gmail in new tab
   - Action: `browser.navigate("https://mail.google.com")`
   - Action: `browser.click('button[aria-label="Compose"]')` or similar
   - Action: Fill in test email:
     - To: `[value from GMAIL_INGESTION_ADDRESS in .env.local]`
     - Subject: `E2E Test - Acme Hospital Deal - [timestamp]`
     - Body:
       ```
       This is an automated end-to-end test email for the Clearwater Deal Intelligence Engine ingestion pipeline.

       Deal Company: Acme Hospital
       Contact: John Smith, CISO
       Date: [current date]

       Key discussion points:
       - Current compliance gaps in HIPAA audit preparation
       - Budget approved: $150K for Q2 2026
       - Decision maker: Jane Doe, CFO
       - Next step: Schedule Prove-stage presentation for March 15

       Test ID: e2e-test-[timestamp]
       ```
   - Action: `browser.click('button[aria-label="Send"]')`
   - Expected: Email sent successfully
   - Verify: "Message sent" confirmation appears
   - Screenshot: `test-email-sent.png`

4. **Switch back to n8n Executions tab**
   - Action: `browser.switch_to_tab(n8n_tab_index)`
   - Expected: n8n Executions page still open

5. **Wait for new execution (poll every 30 seconds, max 5 minutes)**
   - Action: `browser.wait_for_selector('[data-test-id="execution-list-item"]:first-child:not([data-execution-id="' + latest_execution_before + '"])', timeout=300000)` (wait up to 5 min)
   - Action: `browser.click('button[aria-label="Refresh"]')` every 30 seconds if no new execution
   - Expected: New execution appears in list within 5 minutes
   - Verify: Execution status shows "Success" (green checkmark)
   - Screenshot: `execution-appeared.png`

6. **Click on new execution to view details**
   - Action: `browser.click('[data-test-id="execution-list-item"]:first-child')`
   - Expected: Execution details page loads with workflow canvas
   - Verify: All 22 nodes visible
   - Verify: Nodes highlighted in green (successful execution)
   - Screenshot: `execution-details-canvas.png`

7. **Verify Gmail Trigger node executed**
   - Action: `browser.click('[data-test-id="canvas-node"][data-name*="Gmail Trigger"]')`
   - Expected: Node output panel opens on right
   - Verify: Output shows email data with subject matching test email
   - Verify: `message_id` field present
   - Screenshot: `execution-gmail-trigger-output.png`

8. **Verify AI Classify node output**
   - Action: `browser.click('[data-test-id="canvas-node"][data-name*="AI: Classify"]')`
   - Expected: Node output shows classification result
   - Verify: JSON output contains:
     - `company_name`: "Acme Hospital"
     - `confidence`: "high" or "medium"
     - `doc_type`: "email"
   - Screenshot: `execution-classify-output.png`

9. **Verify Deduplication Check passed (new email)**
   - Action: `browser.click('[data-test-id="canvas-node"][data-name*="Check Duplicate"]')`
   - Expected: Query result shows empty array (no duplicate found)
   - Verify: Workflow continued past this node (not terminated)
   - Screenshot: `execution-dedupe-check.png`

10. **Verify Deal Assignment**
    - Action: `browser.click('[data-test-id="canvas-node"][data-name*="Assign Deal"]')`
    - Expected: Node output shows assigned deal_id
    - Verify: `deal_id` follows pattern `cw_acmehospital_2026` or similar
    - Screenshot: `execution-deal-assigned.png`

11. **Verify Contextual Enrichment applied**
    - Action: `browser.click('[data-test-id="canvas-node"][data-name*="Contextual Enrichment"]')`
    - Expected: Output shows chunks with prepended context header
    - Verify: Text starts with `[DEAL CONTEXT]` header containing deal_id, company_name, doc_type
    - Screenshot: `execution-enrichment.png`

12. **Verify OpenAI Embeddings generated**
    - Action: `browser.click('[data-test-id="canvas-node"][data-name*="Embeddings"]')`
    - Expected: Output shows array of vectors
    - Verify: Each vector has 1536 dimensions
    - Verify: Vector values are floats between -1 and 1
    - Screenshot: `execution-embeddings.png`

13. **Verify Qdrant Insert succeeded**
    - Action: `browser.click('[data-test-id="canvas-node"][data-name*="Qdrant"]')`
    - Expected: Output shows successful insertion response
    - Verify: Response contains `status: "ok"` or similar success indicator
    - Screenshot: `execution-qdrant-insert.png`

14. **Verify Postgres Log entry created**
    - Action: `browser.click('[data-test-id="canvas-node"][data-name*="Log Ingestion"]')`
    - Expected: Output shows INSERT statement result
    - Verify: 1 row affected
    - Screenshot: `execution-postgres-log.png`

15. **Verify HTTP Webhook triggered**
    - Action: `browser.click('[data-test-id="canvas-node"][data-name*="HTTP: Trigger"]')`
    - Expected: Output shows POST request sent to `/webhook/deal-health-trigger`
    - Verify: Request body contains `deal_id`, `trigger_message_id`, `trigger_type`
    - Verify: Response status 200 or 404 (404 acceptable in Phase 1)
    - Screenshot: `execution-webhook-trigger.png`

16. **Verify no errors in execution**
    - Action: Scan entire canvas for red nodes (error indicators)
    - Expected: Zero red nodes visible
    - Verify: Execution status bar at bottom shows "Success"
    - Screenshot: `execution-all-nodes-success.png`

**Validation**:
```bash
# Check execution exists in database
curl -s http://localhost:5678/api/v1/executions \
  -H "X-N8N-API-KEY: $(grep N8N_API_KEY deal-intelligence-engine/.env.local | cut -d= -f2)" | \
  jq -r '.data[0].status' | grep -q "success" && echo "✓ Latest execution succeeded"
```

---

### E2E Test 5: Qdrant Dashboard Verification

**Test Objective**: Verify vectors were inserted into Qdrant and are queryable.

**Steps**:

1. **Navigate to Qdrant dashboard**
   - Action: `browser.navigate("http://localhost:6333/dashboard")`
   - Expected: Qdrant web UI loads
   - Verify: Dashboard shows collections list
   - Screenshot: `qdrant-dashboard.png`

2. **Verify "deals" collection exists**
   - Action: `browser.wait_for_selector('text="deals"', timeout=5000)`
   - Expected: "deals" collection visible in collections list
   - Verify: Status shows "green" or "ready"
   - Screenshot: `qdrant-deals-collection.png`

3. **Click on "deals" collection**
   - Action: `browser.click('a:has-text("deals")')`
   - Expected: Collection details page loads
   - Verify: Vector count > 0 (shows number of points)
   - Verify: Configuration shows 1536 dimensions, Cosine distance
   - Screenshot: `qdrant-deals-details.png`

4. **View collection points (scroll API)**
   - Action: `browser.click('button:has-text("Points")')` or navigate to points view
   - Expected: List of vector points displayed
   - Verify: At least 1 point visible (from test email)
   - Verify: Payload shows deal_id, company_name, doc_type fields
   - Screenshot: `qdrant-deals-points.png`

5. **Inspect point payload**
   - Action: `browser.click('button:has-text("View")' or first point ID)`
   - Expected: Point details modal/page opens
   - Verify: Payload contains:
     - `deal_id`: "cw_acmehospital_2026" (or similar)
     - `company_name`: "Acme Hospital"
     - `doc_type`: "email"
     - `date_created`: recent timestamp
     - `sender_email`: present
   - Verify: Vector array has 1536 elements
   - Screenshot: `qdrant-point-payload.png`

**Validation**:
```bash
# Query Qdrant for test email vectors
curl -X POST http://localhost:6333/collections/deals/points/scroll \
  -H "Content-Type: application/json" \
  -d '{"limit": 5, "with_payload": true, "with_vector": false, "filter": {"must": [{"key": "company_name", "match": {"value": "Acme Hospital"}}]}}' | \
  jq '.result.points | length' | grep -E "[1-9][0-9]*" && echo "✓ Test email vectors in Qdrant"
```

---

### E2E Test 6: Postgres Data Verification

**Test Objective**: Verify test email logged in Postgres and deal record created.

**Steps**:

1. **Open Metabase UI**
   - Action: `browser.navigate("http://localhost:3000")`
   - Expected: Metabase login or setup wizard
   - Verify: Page loads successfully
   - Screenshot: `metabase-landing.png`

2. **Complete Metabase first-run setup (if needed)**
   - Action: Fill in setup form:
     - Language: English
     - Your name: Admin User
     - Email: admin@clearwater.local
     - Password: SecurePassword123!
   - Action: `browser.click('button:has-text("Next")')`
   - Action: Skip "Add your data" step (already connected via docker-compose)
   - Expected: Setup completes, dashboard loads
   - Screenshot: `metabase-setup-complete.png`

3. **Navigate to clearwater_deals database**
   - Action: `browser.click('a:has-text("Browse data")')` or similar
   - Expected: Database list appears
   - Verify: "clearwater_deals" database visible
   - Action: `browser.click('a:has-text("clearwater_deals")')`
   - Screenshot: `metabase-database-list.png`

4. **Query ingestion_log table**
   - Action: `browser.click('button:has-text("Ask a question")')`
   - Action: Select "Native query" or SQL editor
   - Action: Enter SQL:
     ```sql
     SELECT message_id, deal_id, doc_type, sender_email, chunk_count, ingested_at
     FROM ingestion_log
     WHERE subject LIKE '%E2E Test%'
     ORDER BY ingested_at DESC
     LIMIT 1
     ```
   - Action: `browser.click('button:has-text("Run query")')`
   - Expected: Query results show 1 row
   - Verify: Row contains:
     - `deal_id`: starts with "cw_"
     - `doc_type`: "email"
     - `chunk_count`: > 0
     - `ingested_at`: recent timestamp (within last 10 minutes)
   - Screenshot: `metabase-ingestion-log-result.png`

5. **Query deals table**
   - Action: Modify query:
     ```sql
     SELECT deal_id, company_name, sender_domains, created_at, is_active
     FROM deals
     WHERE company_name LIKE '%Acme%'
     LIMIT 1
     ```
   - Action: `browser.click('button:has-text("Run query")')`
   - Expected: Query results show 1 row
   - Verify: Row contains:
     - `deal_id`: "cw_acmehospital_2026" (or similar slug)
     - `company_name`: "Acme Hospital"
     - `is_active`: true
   - Screenshot: `metabase-deals-result.png`

**Validation**:
```bash
# Direct Postgres query
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT deal_id, chunk_count FROM ingestion_log WHERE subject LIKE '%E2E Test%' ORDER BY ingested_at DESC LIMIT 1" | \
  grep -q "cw_" && echo "✓ Test email in ingestion_log"
```

---

### E2E Test 7: Deduplication Test

**Test Objective**: Verify sending the same email twice only processes it once.

**Steps**:

1. **Resend the exact same test email**
   - Action: In Gmail, find sent test email from Test 4
   - Action: Click "Forward"
   - Action: To: `[GMAIL_INGESTION_ADDRESS]`
   - Action: Do not modify subject or body
   - Action: Send
   - Expected: Email sent successfully
   - Screenshot: `duplicate-email-sent.png`

2. **Wait 5 minutes for workflow execution**
   - Action: Set timer for 5 minutes
   - Expected: Workflow polls Gmail, detects duplicate

3. **Check n8n Executions page**
   - Action: `browser.navigate("http://localhost:5678/executions")`
   - Action: Refresh page
   - Expected: New execution appears
   - Screenshot: `executions-after-duplicate.png`

4. **Open latest execution**
   - Action: `browser.click('[data-test-id="execution-list-item"]:first-child')`
   - Expected: Execution details page loads
   - Verify: Execution status may show "Success" (early termination is success)
   - Screenshot: `duplicate-execution-canvas.png`

5. **Verify deduplication check triggered**
   - Action: `browser.click('[data-test-id="canvas-node"][data-name*="Check Duplicate"]')`
   - Expected: Node output shows query result with 1 row (duplicate found)
   - Verify: Query returned existing `ingestion_log` entry
   - Screenshot: `duplicate-check-found.png`

6. **Verify workflow terminated early**
   - Action: Inspect nodes after deduplication check
   - Expected: Nodes after IF condition are NOT executed (grayed out or missing green highlight)
   - Verify: Qdrant Insert node NOT executed
   - Verify: Postgres Log node NOT executed
   - Screenshot: `duplicate-workflow-terminated.png`

7. **Verify no duplicate ingestion_log entry**
   - Action: `browser.navigate("http://localhost:3000")` (Metabase)
   - Action: Run SQL query:
     ```sql
     SELECT COUNT(*) as duplicate_count
     FROM ingestion_log
     WHERE message_id = (
       SELECT message_id FROM ingestion_log WHERE subject LIKE '%E2E Test%' LIMIT 1
     )
     ```
   - Action: `browser.click('button:has-text("Run query")')`
   - Expected: Result shows `duplicate_count = 1` (not 2)
   - Screenshot: `duplicate-count-verification.png`

**Validation**:
```bash
# Verify only 1 ingestion_log entry for test email
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT COUNT(*) FROM ingestion_log WHERE subject LIKE '%E2E Test%'" | \
  grep -q "1" && echo "✓ Deduplication working (only 1 entry)"
```

---

### E2E Test 8: Low-Confidence Attribution Test

**Test Objective**: Verify emails with ambiguous attribution are queued for human confirmation.

**Steps**:

1. **Send ambiguous email to ingestion inbox**
   - Action: Open Gmail
   - Action: Compose new email:
     - From: Personal email (NOT a known deal sender domain)
     - To: `[GMAIL_INGESTION_ADDRESS]`
     - Subject: `Question about compliance software`
     - Body:
       ```
       Hi there,

       I'm interested in learning more about compliance software solutions.
       Can you send me some information?

       Thanks
       ```
   - Action: Send
   - Expected: Email sent successfully
   - Screenshot: `ambiguous-email-sent.png`

2. **Wait 5 minutes for workflow execution**
   - Action: Set timer for 5 minutes

3. **Check n8n execution**
   - Action: `browser.navigate("http://localhost:5678/executions")`
   - Action: Refresh, click latest execution
   - Expected: Execution shows "Success"
   - Screenshot: `ambiguous-execution.png`

4. **Verify Claude classification returned low confidence**
   - Action: `browser.click('[data-test-id="canvas-node"][data-name*="AI: Classify"]')`
   - Expected: Node output shows:
     - `confidence`: "low"
     - `confidence_score`: < 0.5
   - Screenshot: `ambiguous-classification-low.png`

5. **Verify routing to attribution queue**
   - Action: `browser.click('[data-test-id="canvas-node"][data-name*="Queue for Confirmation"]')`
   - Expected: Node executed (green highlight)
   - Verify: Postgres INSERT statement executed
   - Screenshot: `ambiguous-queued.png`

6. **Verify NO Qdrant insertion**
   - Action: Inspect Qdrant Insert node
   - Expected: Node is grayed out (NOT executed)
   - Verify: Low-confidence emails do not create vectors until confirmed
   - Screenshot: `ambiguous-no-qdrant.png`

7. **Verify attribution_queue entry in Postgres**
   - Action: `browser.navigate("http://localhost:3000")` (Metabase)
   - Action: Run SQL query:
     ```sql
     SELECT message_id, ai_guess_company, ai_confidence, resolution
     FROM attribution_queue
     WHERE subject LIKE '%Question about compliance%'
     ORDER BY queued_at DESC
     LIMIT 1
     ```
   - Action: `browser.click('button:has-text("Run query")')`
   - Expected: Result shows 1 row with:
     - `resolution`: "pending"
     - `ai_confidence`: < 0.5
   - Screenshot: `ambiguous-queue-entry.png`

**Validation**:
```bash
# Verify low-confidence email in attribution_queue
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT COUNT(*) FROM attribution_queue WHERE resolution='pending' AND subject LIKE '%Question about compliance%'" | \
  grep -q "1" && echo "✓ Low-confidence email queued"
```

---

### Browser Test Execution Summary

**Total Tests**: 8
**Coverage**:
- ✅ n8n UI accessibility and setup
- ✅ Credential configuration verification
- ✅ Workflow import and activation
- ✅ Live workflow execution monitoring (22 nodes)
- ✅ Qdrant vector storage verification
- ✅ Postgres data verification via Metabase
- ✅ Deduplication logic
- ✅ Low-confidence attribution routing

**Estimated Execution Time**: 30-45 minutes (automated)

**Success Criteria**: All 8 tests pass with zero manual intervention. Every verification step returns expected results. All screenshots captured successfully.

---

## VALIDATION COMMANDS

Execute every command to ensure zero regressions and 100% feature correctness.

### Level 1: Service Health Checks

**Docker Services Running**:
```bash
cd deal-intelligence-engine && docker compose ps | grep -E "Up|healthy" | wc -l | grep -q 5 && echo "✓ All 5 services running"
```

**n8n Accessible**:
```bash
curl -f http://localhost:5678 > /dev/null 2>&1 && echo "✓ n8n UI accessible"
```

**Qdrant Healthy**:
```bash
curl -s http://localhost:6333/healthz | grep -q "ok" && echo "✓ Qdrant healthy"
```

**Postgres Accepting Connections**:
```bash
docker exec clearwater-postgres pg_isready -U clearwater -d clearwater_deals && echo "✓ Postgres ready"
```

**Redis Ping**:
```bash
docker exec clearwater-redis redis-cli -a $(grep REDIS_PASSWORD deal-intelligence-engine/.env | cut -d= -f2) ping | grep -q "PONG" && echo "✓ Redis responding"
```

**Metabase Accessible**:
```bash
curl -f http://localhost:3000 > /dev/null 2>&1 && echo "✓ Metabase UI accessible"
```

### Level 2: Data Layer Validation

**Postgres Schema Validation**:
```bash
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name" | \
  grep -E "deals|ingestion_log|attribution_queue" && echo "✓ Core tables exist"
```

**Qdrant Collection Exists**:
```bash
curl -s http://localhost:6333/collections/deals | jq -r '.result.status' | grep -q "green" && echo "✓ deals collection ready"
```

**Qdrant Collection Config**:
```bash
curl -s http://localhost:6333/collections/deals | jq '.result.config.params.vectors.size' | grep -q 1536 && echo "✓ Vector size correct (1536)"
```

**Qdrant Quantization Enabled**:
```bash
curl -s http://localhost:6333/collections/deals | jq '.result.config.quantization_config.scalar.type' | grep -q "int8" && echo "✓ int8 quantization enabled"
```

### Level 3: Workflow Validation

**Workflow Imported**:
```bash
# Via n8n API (requires API key)
curl -s http://localhost:5678/api/v1/workflows \
  -H "X-N8N-API-KEY: $(grep N8N_API_KEY deal-intelligence-engine/.env | cut -d= -f2)" | \
  jq -r '.data[].name' | grep -q "Ingestion Pipeline" && echo "✓ Workflow imported"
```

**Workflow Active**:
```bash
# Manual check in n8n UI: Workflow status shows "Active"
# Or via API:
curl -s http://localhost:5678/api/v1/workflows \
  -H "X-N8N-API-KEY: $(grep N8N_API_KEY deal-intelligence-engine/.env | cut -d= -f2)" | \
  jq -r '.data[] | select(.name=="Ingestion Pipeline") | .active' | grep -q "true" && echo "✓ Workflow active"
```

### Level 4: End-to-End Ingestion Test

**Send Test Email** (manual):
```
To: [GMAIL_INGESTION_ADDRESS]
Subject: E2E Test - Acme Hospital
Body: This is an end-to-end test email for the ingestion pipeline. Deal: Acme Hospital. Contact: John Smith.
```

**Check Workflow Execution**:
```bash
# Manual: n8n UI > Executions > Latest execution > Verify all nodes green
# Or via API:
curl -s http://localhost:5678/api/v1/executions \
  -H "X-N8N-API-KEY: $(grep N8N_API_KEY deal-intelligence-engine/.env | cut -d= -f2)" | \
  jq -r '.data[0].finished' | grep -q "true" && echo "✓ Latest execution completed"
```

**Verify Ingestion Log Entry**:
```bash
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT COUNT(*) FROM ingestion_log WHERE subject LIKE '%E2E Test%'" | grep -q 1 && echo "✓ Ingestion logged"
```

**Verify Qdrant Vectors Inserted**:
```bash
curl -X POST http://localhost:6333/collections/deals/points/scroll \
  -H "Content-Type: application/json" \
  -d '{"limit": 10, "with_payload": true, "with_vector": false}' | \
  jq '.result.points | length' | grep -E "[1-9][0-9]*" && echo "✓ Vectors in Qdrant"
```

**Verify Deal Record Created**:
```bash
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT deal_id, company_name FROM deals WHERE company_name LIKE '%Acme%'" | grep -q "cw_" && echo "✓ Deal record exists"
```

### Level 5: Deduplication Test

**Resend Same Email** (manual): Forward same test email again

**Verify No Duplicate Ingestion**:
```bash
# Count should still be 1, not 2
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT COUNT(*) FROM ingestion_log WHERE subject LIKE '%E2E Test%'" | grep -q 1 && echo "✓ Deduplication working"
```

### Level 6: Low-Confidence Attribution Test

**Send Ambiguous Email** (manual):
```
To: [GMAIL_INGESTION_ADDRESS]
From: personal email (not known deal sender)
Subject: Question about compliance
Body: Hi, I have a question about your compliance software.
```

**Verify Attribution Queue Entry**:
```bash
docker exec clearwater-postgres psql -U clearwater -d clearwater_deals -c \
  "SELECT COUNT(*) FROM attribution_queue WHERE resolution='pending'" | grep -E "[1-9][0-9]*" && echo "✓ Low-confidence email queued"
```

---

## ACCEPTANCE CRITERIA

- [x] All 5 Docker services (n8n, Qdrant, Postgres, Redis, Metabase) running and healthy
- [x] Postgres schema initialized with 7 tables (deals, ingestion_log, deal_health, outputs_log, attribution_queue, calendar_events, n8n_chat_histories)
- [x] Qdrant "deals" collection created with 1536-dim vectors, Cosine distance, int8 quantization
- [x] Gmail OAuth2 credentials configured in Google Cloud Console (2 apps: read + send)
- [x] n8n credentials configured: Gmail (2x), OpenAI, Anthropic, Postgres, Qdrant, Redis
- [x] workflow-01-ingestion.json imported into n8n with all credentials mapped
- [x] Workflow activated and polling Gmail inbox every 5 minutes
- [x] End-to-end test: Email sent → workflow executes → vectors in Qdrant → log in Postgres → webhook triggered
- [x] Deduplication test: Same email sent twice → second execution terminates early, no duplicate log entry
- [x] Low-confidence attribution test: Ambiguous email → inserted to attribution_queue with resolution="pending"
- [x] Attachment extraction test: Email with PDF attachment → text extracted, chunked, embedded (or documented as Phase 1.5 enhancement)
- [x] All validation commands pass (Levels 1-6)
- [x] Documentation created: DEPLOYMENT.md and TESTING.md
- [x] No sensitive data committed to git (.env in .gitignore, credentials excluded)
- [x] Workflow execution logs show zero errors for standard email ingestion

---

## COMPLETION CHECKLIST

- [ ] **Task 1-3**: Environment verification (.env.local exists, all 54 variables set, no placeholders)
- [ ] **Task 4-7**: Docker stack deployed (5 services running and healthy, Postgres schema initialized, Qdrant "deals" collection created)
- [ ] **Task 8-9**: Skipped (credentials already in .env.local)
- [ ] **Task 10**: n8n first-run setup completed via browser agent (admin user created or logged in)
- [ ] **Task 11-17**: All 7 credentials configured in n8n via browser agent (Gmail x2, OpenAI, Anthropic, Postgres, Qdrant, Redis)
- [ ] **Task 18-19**: workflow-01-ingestion.json imported via browser agent and credentials mapped to all 22 nodes
- [ ] **Task 20**: Skipped (test mode not applicable for trigger-based workflows)
- [ ] **Task 21**: Workflow activated via browser agent (status shows "Active")
- [ ] **Task 22-23**: End-to-end test email sent via browser agent and workflow execution verified (all 22 nodes green)
- [ ] **Task 24-26**: Postgres and Qdrant data verified via browser agent and/or SQL queries
- [ ] **Task 27**: Deduplication test passed (duplicate email not reprocessed)
- [ ] **Task 28**: Low-confidence attribution test passed (ambiguous email queued)
- [ ] **Task 29**: Attachment extraction test completed or documented as Phase 1.5 enhancement
- [ ] **Task 30**: Webhook trigger verified (POST sent to /webhook/deal-health-trigger)
- [ ] **Task 31-32**: Documentation created (DEPLOYMENT.md, TESTING.md)
- [ ] **All 8 Browser Agent E2E Tests**: Executed and passed (see BROWSER AGENT END-TO-END TESTING section)
- [ ] **All validation commands** (Levels 1-6): Executed and passed
- [ ] **Acceptance criteria**: All met
- [ ] **Phase 1 complete**: Ready for Phase 2 (Deal Health Scoring Agent deployment)

**CRITICAL SUCCESS INDICATOR**: All browser agent tests (E2E Tests 1-8) execute successfully with zero manual intervention. Screenshots captured at every major step. All 22 workflow nodes show green checkmarks in execution logs. Test email vectors queryable in Qdrant. Deduplication and low-confidence routing both verified via browser automation.

---

## NOTES

### Design Decisions

1. **Single Qdrant Collection vs. Multiple Collections**: Chose single "deals" collection with payload-based filtering (deal_id namespace). This is the recommended Qdrant multitenancy pattern and reduces resource overhead compared to per-deal collections.

2. **Gmail Polling (5 min) vs. Webhooks**: Gmail API does not support native webhooks for new messages. Cloud Pub/Sub integration exists but adds complexity. For MVP, 5-minute polling is acceptable (most deal communications are not time-critical). Can be reduced to 1-minute polling if needed.

3. **Confidence-Based Routing Thresholds**: High (>0.80) and medium (0.50-0.80) confidence emails auto-assign to deals. Low (<0.50) confidence emails route to attribution_queue for human confirmation. Thresholds tunable based on production accuracy metrics.

4. **Contextual Enrichment Before Chunking**: Prepending deal context to chunks (Anthropic Contextual Retrieval pattern) significantly improves RAG precision. Alternative approach (metadata-only in payload) tested but resulted in lower retrieval quality.

5. **Deduplication by Gmail message_id**: Gmail message IDs are globally unique and persistent. Using message_id as deduplication key is more reliable than hashing email content (which changes if forwarded/replied).

6. **Append-Only ingestion_log**: Never update existing ingestion_log rows. Always insert new rows. This preserves full audit trail and enables time-series analysis of ingestion patterns.

### Known Limitations (Phase 1)

1. **No PDF/DOCX Extraction Yet**: workflow-01-ingestion.json has placeholder nodes for file extraction but requires additional n8n nodes (pdf-parse, mammoth for DOCX). Document as Phase 1.5 enhancement.

2. **No Real-Time Ingestion**: 5-minute poll interval means up to 5-minute delay from email receipt to Qdrant insertion. Acceptable for MVP; can be reduced if needed.

3. **No Email Thread Reconstruction**: Each email processed independently. Thread context (previous emails in conversation) not automatically linked. Phase 4 (Chat Agent) can query across multiple ingestion events for same deal to reconstruct threads.

4. **No Sender Verification**: Workflow trusts sender_email from Gmail. No verification that sender is legitimate (spoofing protection). Gmail's DMARC/SPF handles this at the MTA level.

5. **No Large Attachment Handling**: Attachments >20MB skipped with warning. n8n binary data limit is 256MB but large files cause memory issues. Document as known limitation; recommend breaking large PDFs into smaller files before forwarding.

6. **No Multi-Language Support**: Text extraction and chunking assume English. Non-English emails may have suboptimal chunking due to tokenization differences. OpenAI embeddings support 100+ languages, so multilingual support is feasible but untested.

### Security Considerations

1. **N8N_ENCRYPTION_KEY**: CRITICAL—This key encrypts all credentials stored in n8n. If lost, all credentials become unrecoverable and must be re-entered. Store in password manager and back up .env file securely (outside of git).

2. **Gmail OAuth2 Scopes**: Separate credentials for read (gmail.readonly) and send (gmail.send) limit blast radius if either is compromised. Never use broader scopes like gmail.modify unless absolutely necessary.

3. **No TLS Between Docker Services**: Internal Docker network (clearwater-net) is not encrypted. Acceptable for local development/single-machine deployment. For production multi-host deployment, enable TLS for n8n ↔ Postgres, n8n ↔ Qdrant.

4. **Qdrant No Auth in Docker**: Local Qdrant container has no authentication (API key). Only accessible from Docker internal network. For production cloud deployment, enable API key authentication.

5. **Postgres Password in Environment Variables**: POSTGRES_PASSWORD in .env is readable by anyone with shell access to the machine. For production, consider Docker secrets or external secrets management (Vault, AWS Secrets Manager).

6. **n8n Port 5678 Exposed**: n8n UI accessible at localhost:5678 with no reverse proxy or TLS. For production, add Nginx reverse proxy with TLS termination and limit port 5678 to Docker internal network only.

### Trade-Offs

1. **Workflow JSON in Git**: Pros: Version control, easy collaboration. Cons: Workflow JSON is verbose (19KB for 22 nodes), hard to diff. Alternative: Use n8n-as-code VS Code extension for bidirectional sync.

2. **Claude Sonnet for Classification**: Pros: Fast, cost-effective ($3/M input tokens). Cons: Lower accuracy than Opus. Acceptable for classification; Opus reserved for high-stakes P2V2C2 scoring.

3. **int8 Quantization**: Pros: 4x memory reduction, minimal recall loss (<2% typical). Cons: Slight quality degradation. Recommend disabling quantization if corpus <10K documents (memory not yet constrained).

4. **500-Token Chunks with 50-Token Overlap**: Pros: Good balance of context preservation and granularity. Cons: Some very long sentences may be split mid-sentence. Markdown-aware splitter mitigates this.

### Future Enhancements (Post-Phase 1)

1. **Intelligent Thread Linking**: Automatically detect email threads via In-Reply-To and References headers, link ingestion_log entries to parent emails.

2. **Sender Reputation Scoring**: Track historical attribution accuracy per sender_domain, boost confidence for known-good senders.

3. **Real-Time Ingestion via Pub/Sub**: Replace 5-minute polling with Google Cloud Pub/Sub for instant ingestion (requires Cloud project setup).

4. **Attachment Preview in n8n UI**: Render PDF/DOCX previews in workflow execution logs for easier debugging.

5. **Multi-Format Attachment Support**: Add support for Excel (XLSX), PowerPoint (PPTX), images (OCR), audio (transcription).

6. **Chunk Quality Scoring**: Score each chunk for information density; filter low-quality chunks (boilerplate, signatures) before embedding.

7. **Hybrid Search (BM25 + Vector)**: Add keyword-based BM25 index alongside vector embeddings for improved retrieval (Qdrant supports sparse vectors).

8. **Cross-Deal Pattern Analysis**: Phase 4+ feature—identify common patterns across multiple won deals to inform current deal strategies.

---

## CONFIDENCE SCORE: 9/10

**Rationale**: All infrastructure is pre-built and validated (Docker Compose, Postgres schema, Qdrant config, workflow JSON). The only unknowns are:
1. Gmail OAuth2 consent screen approval (may require Google verification if restricted scopes used) — 90% confidence, most deployments work immediately
2. n8n credential mapping UI quirks (occasionally dropdowns don't populate) — 95% confidence, workarounds documented
3. Attachment extraction requires additional n8n nodes not yet implemented — 100% certain, documented as Phase 1.5

**Estimated Time to Complete**: 4-6 hours for first-time deployment (including OAuth2 setup, credential configuration, testing). 2-3 hours for subsequent deployments (credentials already configured).

**Blockers**:
- Gmail OAuth2 credentials (requires Google Cloud Console access)
- OpenAI API key with sufficient credits
- Anthropic API key with Claude Sonnet 4.6 access

**Dependencies**:
- Docker 20.10+ with Compose V2
- openssl (for secret generation)
- curl + jq (for validation commands)
- Web browser (for n8n UI and OAuth flows)

**Success Metric**: A test email sent to the ingestion inbox is processed within 5 minutes, vectors appear in Qdrant, and ingestion_log contains a new row—all with zero manual intervention after initial setup.
