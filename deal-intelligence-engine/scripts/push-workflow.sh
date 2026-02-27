#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Clearwater Deal Intelligence Engine — Push Workflow to n8n
#
# Usage:
#   bash scripts/push-workflow.sh <workflow-file.json> [workflow-id]
#
# Examples:
#   bash scripts/push-workflow.sh n8n/workflows/workflow-01-ingestion.json
#   bash scripts/push-workflow.sh n8n/workflows/workflow-01-ingestion.json G6kZgyHCK0qHNhRj
#
# Behavior:
#   1. Strips all metadata fields not accepted by PUT /api/v1/workflows/{id}
#      (id, active, createdAt, updatedAt, versionId, triggerCount, tags, meta,
#       pinData, shared, isArchived, activeVersion, activeVersionId, description,
#       versionCounter). Also strips unknown settings sub-fields.
#   2. Uses temp files (not shell variables) to handle control characters safely
#      in Code node JavaScript content.
#   3. PUTs the clean payload to n8n.
#   4. Follows with deactivate → activate cycle to flush the execution engine
#      cache (required for schedule-triggered workflows; harmless for webhooks).
#   5. Verifies the workflow is active and reports the final state.
#
# Requirements:
#   - jq (brew install jq)
#   - n8n running at http://localhost:5678
#   - N8N_API_KEY set in .env or environment
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Config ───────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_DIR/.env"

N8N_URL="${N8N_URL:-http://localhost:5678}"

# Load N8N_API_KEY from .env if not already in environment
if [[ -z "${N8N_API_KEY:-}" && -f "$ENV_FILE" ]]; then
  N8N_API_KEY="$(grep -E '^N8N_API_KEY=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' | tr -d "'")"
fi

if [[ -z "${N8N_API_KEY:-}" ]]; then
  echo "ERROR: N8N_API_KEY not found. Set it in .env or export N8N_API_KEY=..." >&2
  exit 1
fi

# ── Args ─────────────────────────────────────────────────────────────────────
WORKFLOW_FILE="${1:-}"
if [[ -z "$WORKFLOW_FILE" ]]; then
  echo "Usage: bash scripts/push-workflow.sh <workflow-file.json> [workflow-id]" >&2
  exit 1
fi

# Resolve relative paths from the project root
if [[ ! "$WORKFLOW_FILE" = /* ]]; then
  WORKFLOW_FILE="$PROJECT_DIR/$WORKFLOW_FILE"
fi

if [[ ! -f "$WORKFLOW_FILE" ]]; then
  echo "ERROR: File not found: $WORKFLOW_FILE" >&2
  exit 1
fi

# ── Get workflow ID ───────────────────────────────────────────────────────────
# Priority: CLI arg > id field in JSON file
WORKFLOW_ID="${2:-}"
if [[ -z "$WORKFLOW_ID" ]]; then
  WORKFLOW_ID="$(jq -r '.id // empty' "$WORKFLOW_FILE")"
fi

if [[ -z "$WORKFLOW_ID" ]]; then
  echo "ERROR: No workflow ID found. Either add 'id' to the JSON or pass it as second arg." >&2
  exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Clearwater n8n Workflow Push"
echo "  File    : $WORKFLOW_FILE"
echo "  ID      : $WORKFLOW_ID"
echo "  n8n URL : $N8N_URL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Check jq is available ─────────────────────────────────────────────────────
if ! command -v jq &>/dev/null; then
  echo "ERROR: jq is required. Install with: brew install jq" >&2
  exit 1
fi

# ── Verify n8n is reachable ───────────────────────────────────────────────────
echo ""
echo "Step 1/4: Verifying n8n is reachable..."
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  "$N8N_URL/api/v1/workflows/$WORKFLOW_ID")

if [[ "$HTTP_STATUS" != "200" ]]; then
  echo "ERROR: GET /api/v1/workflows/$WORKFLOW_ID returned HTTP $HTTP_STATUS" >&2
  echo "  Check that n8n is running and the workflow ID / API key are correct." >&2
  exit 1
fi
echo "  ✓ n8n reachable, workflow $WORKFLOW_ID exists"

# ── Build clean payload ───────────────────────────────────────────────────────
# n8n 2.9.x PUT /api/v1/workflows/{id} accepts ONLY these top-level fields:
#   name, nodes, connections, settings, staticData
#
# The settings object also enforces a strict allowlist — strip any fields
# not in the allowed set. Fields that cause 400 in n8n 2.9.x include:
#   availableInMCP, timeSavedMode, binaryMode (and any other non-standard fields)
#
# We write to a temp file (not a shell variable) to safely preserve control
# characters that appear in Code node JavaScript content.
echo ""
echo "Step 2/4: Building clean PUT payload (stripping metadata fields)..."

TMP_PAYLOAD=$(mktemp)
jq '{
  name,
  nodes,
  connections,
  staticData,
  settings: (
    if .settings and (.settings | type) == "object" then {
      executionOrder: .settings.executionOrder,
      saveManualExecutions: .settings.saveManualExecutions,
      callerPolicy: .settings.callerPolicy,
      errorWorkflow: .settings.errorWorkflow,
      saveDataSuccessExecution: .settings.saveDataSuccessExecution,
      saveDataErrorExecution: .settings.saveDataErrorExecution,
      executionTimeout: .settings.executionTimeout,
      timezone: .settings.timezone,
      saveExecutionProgress: .settings.saveExecutionProgress
    } | del(.[] | nulls)
    else empty
    end
  )
}' "$WORKFLOW_FILE" > "$TMP_PAYLOAD"

NODE_COUNT=$(jq '.nodes | length' "$TMP_PAYLOAD")
echo "  ✓ Payload ready — $NODE_COUNT nodes"

# ── PUT the workflow ──────────────────────────────────────────────────────────
echo ""
echo "Step 3/4: Pushing to n8n..."
TMP_BODY=$(mktemp)
PUT_HTTP_STATUS=$(curl -s -o "$TMP_BODY" -w "%{http_code}" \
  -X PUT "$N8N_URL/api/v1/workflows/$WORKFLOW_ID" \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  --data-binary @"$TMP_PAYLOAD")
PUT_BODY=$(cat "$TMP_BODY")
rm -f "$TMP_BODY" "$TMP_PAYLOAD"

if [[ "$PUT_HTTP_STATUS" != "200" ]]; then
  echo "ERROR: PUT returned HTTP $PUT_HTTP_STATUS" >&2
  echo "Response body:" >&2
  echo "$PUT_BODY" | jq . 2>/dev/null || echo "$PUT_BODY" >&2
  exit 1
fi

UPDATED_AT=$(echo "$PUT_BODY" | jq -r '.updatedAt // "unknown"')
echo "  ✓ PUT successful (HTTP 200) — updatedAt: $UPDATED_AT"

# ── Deactivate → Activate cycle to flush execution engine cache ───────────────
# This forces the ActiveWorkflowManager to deregister the old version and
# re-register from the updated DB record. Required for schedule-triggered
# workflows; for webhook-triggered workflows it also re-registers webhook paths.
echo ""
echo "Step 4/4: Flushing execution engine cache (deactivate → activate)..."

# Deactivate
DEACT_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST "$N8N_URL/api/v1/workflows/$WORKFLOW_ID/deactivate" \
  -H "X-N8N-API-KEY: $N8N_API_KEY")

if [[ "$DEACT_STATUS" != "200" ]]; then
  echo "  WARNING: Deactivate returned HTTP $DEACT_STATUS (workflow may already be inactive)"
fi

# Brief pause to let n8n complete deregistration before re-activating
sleep 1

# Activate
ACT_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST "$N8N_URL/api/v1/workflows/$WORKFLOW_ID/activate" \
  -H "X-N8N-API-KEY: $N8N_API_KEY")

if [[ "$ACT_STATUS" != "200" ]]; then
  echo "ERROR: Activate returned HTTP $ACT_STATUS — workflow may be inactive!" >&2
  echo "  Check n8n UI at $N8N_URL and manually activate the workflow." >&2
  exit 1
fi

echo "  ✓ Workflow deactivated and re-activated — execution cache flushed"

# ── Final verification ────────────────────────────────────────────────────────
TMP_VERIFY=$(mktemp)
curl -s -o "$TMP_VERIFY" \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  "$N8N_URL/api/v1/workflows/$WORKFLOW_ID"

VERIFY_ACTIVE=$(jq -r '.active' "$TMP_VERIFY")
VERIFY_NODES=$(jq '.nodes | length' "$TMP_VERIFY")
VERIFY_UPDATED=$(jq -r '.updatedAt' "$TMP_VERIFY")
rm -f "$TMP_VERIFY"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✓ Push complete"
echo "  Active  : $VERIFY_ACTIVE"
echo "  Nodes   : $VERIFY_NODES"
echo "  Updated : $VERIFY_UPDATED"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
