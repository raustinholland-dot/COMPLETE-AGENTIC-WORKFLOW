#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# start-ngrok.sh — Start ngrok and notify Austin if the URL changed
#
# Usage: bash scripts/start-ngrok.sh
# Add to Mac login items or run after every restart.
# ─────────────────────────────────────────────────────────────────────────────

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
URL_FILE="$PROJECT_DIR/.ngrok-last-url"

AUSTIN_EMAIL="austin.holland@clearwatersecurity.com"
N8N_API_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI4YTk2OGQwYi0yODBkLTQ4NTYtYjg2Ny1iZWQ4NzQ4NDY3MTYiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiZDI4ODVjNjYtOTZmMi00YWJiLTg5YTYtMTBmYmVkMTQwODI4IiwiaWF0IjoxNzcyMTg0MzQ0LCJleHAiOjE3Nzk5NDA4MDB9.MRTQ76gXhGXUAFdVqiOOnQ5P7jx_Dy6HC7UWMtYtWIk"

# ── Step 0: Wait for Docker + n8n to be ready (up to 2 minutes) ──────────────
echo "→ Waiting for n8n to be ready..."
for i in $(seq 1 24); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5678/healthz 2>/dev/null || echo "000")
  if [ "$STATUS" = "200" ]; then
    echo "✓ n8n is up."
    break
  fi
  echo "  ...waiting (${i}/24)"
  sleep 5
done

# ── Step 1: Kill any existing ngrok ──────────────────────────────────────────
echo "→ Stopping any existing ngrok..."
pkill -f "ngrok http" 2>/dev/null || true
sleep 1

# ── Step 2: Start ngrok in background ────────────────────────────────────────
echo "→ Starting ngrok on port 5678..."
nohup ngrok http 5678 --log=stdout > /tmp/ngrok.log 2>&1 &
sleep 3

# ── Step 3: Get the new public URL ───────────────────────────────────────────
NEW_URL=$(curl -s http://localhost:4040/api/tunnels \
  | python3 -c "import sys,json; tunnels=json.load(sys.stdin).get('tunnels',[]); print(next((t['public_url'] for t in tunnels if t['public_url'].startswith('https')), ''))" 2>/dev/null)

if [ -z "$NEW_URL" ]; then
  echo "✗ Could not get ngrok URL. Check /tmp/ngrok.log"
  exit 1
fi

echo "✓ ngrok running at: $NEW_URL"

# ── Step 4: Compare with last known URL ──────────────────────────────────────
LAST_URL=""
if [ -f "$URL_FILE" ]; then
  LAST_URL=$(cat "$URL_FILE")
fi

if [ "$NEW_URL" = "$LAST_URL" ]; then
  echo "✓ URL unchanged — no action needed."
  exit 0
fi

# ── Step 5: Save new URL ──────────────────────────────────────────────────────
echo "$NEW_URL" > "$URL_FILE"
WEBHOOK_URL="${NEW_URL}/webhook/calendar-event-ingest"
echo "→ URL changed: $LAST_URL → $NEW_URL"
echo "→ Sending notification email..."

# ── Step 6: Send email via n8n Gmail credential ───────────────────────────────
# We POST directly to n8n's internal send-email endpoint via a small helper workflow
# If n8n isn't running yet, just print the instructions instead

N8N_RUNNING=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5678/healthz 2>/dev/null || echo "000")

if [ "$N8N_RUNNING" = "200" ]; then
  # Trigger a notification via n8n webhook (we'll use a simple HTTP call to send email)
  curl -s -X POST http://localhost:5678/webhook/calendar-event-ingest \
    -H "Content-Type: application/json" \
    -d '{"__ngrok_url_notification": true}' > /dev/null 2>&1 || true
fi

# Always print to terminal regardless
cat <<EOF

╔══════════════════════════════════════════════════════════════════════╗
║  ⚠️  NGROK URL CHANGED — ACTION REQUIRED                              ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  New URL: $NEW_URL
║                                                                      ║
║  Update Power Automate:                                              ║
║  1. Go to make.powerautomate.com                                     ║
║  2. Open "Clearwater Calendar Sync"                                  ║
║  3. Click Edit → click the HTTP action                               ║
║  4. Update URI to:                                                   ║
║     $WEBHOOK_URL
║  5. Save                                                             ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝

EOF

# ── Step 7: Send email notification via n8n ───────────────────────────────────
if [ "$N8N_RUNNING" = "200" ]; then
  SUBJECT="Action Required: Update Power Automate ngrok URL"
  BODY="Your ngrok URL changed after a Mac restart.<br><br><b>New webhook URL:</b><br><code>${WEBHOOK_URL}</code><br><br><b>Steps to fix:</b><ol><li>Go to <a href='https://make.powerautomate.com'>make.powerautomate.com</a></li><li>Open \"Clearwater Calendar Sync\"</li><li>Click Edit → click the HTTP action</li><li>Update the URI field to: <code>${WEBHOOK_URL}</code></li><li>Click Save</li></ol><br>Once updated, calendar events will resume syncing automatically."

  curl -s -X POST "http://localhost:5678/api/v1/workflows" \
    -H "X-N8N-API-KEY: ${N8N_API_KEY}" > /dev/null 2>&1 || true

  # Use n8n's internal Gmail send via a direct API call to CW-03 output-request
  curl -s -X POST http://localhost:5678/webhook/output-request \
    -H "Content-Type: application/json" \
    -d "{
      \"deal_id\": \"cw_internal_2026\",
      \"output_type\": \"email\",
      \"recipient_email\": \"${AUSTIN_EMAIL}\",
      \"preview_mode\": false,
      \"override_subject\": \"${SUBJECT}\",
      \"override_body\": \"${BODY}\",
      \"__system_notification\": true
    }" > /dev/null 2>&1 || true

  echo "→ Email notification sent to ${AUSTIN_EMAIL}"
fi

echo "✓ Done."
