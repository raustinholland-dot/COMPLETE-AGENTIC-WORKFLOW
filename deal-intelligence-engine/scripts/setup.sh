#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Clearwater Deal Intelligence Engine — First-Run Setup
# Run once after cloning: bash scripts/setup.sh
# ─────────────────────────────────────────────────────────────────────────────

set -e

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║     Clearwater Deal Intelligence Engine — Setup           ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# ── 1. Check dependencies ────────────────────────────────────────────────────
echo "▶ Checking dependencies..."

if ! command -v docker &> /dev/null; then
  echo "  ✗ Docker not found. Install Docker Desktop: https://www.docker.com/products/docker-desktop/"
  exit 1
fi

if ! command -v docker &> /dev/null || ! docker compose version &> /dev/null; then
  echo "  ✗ Docker Compose not found. Update Docker Desktop to latest version."
  exit 1
fi

echo "  ✓ Docker: $(docker --version | cut -d' ' -f3 | tr -d ',')"
echo "  ✓ Docker Compose: $(docker compose version --short)"

# ── 2. Create .env from template ─────────────────────────────────────────────
if [ ! -f .env ]; then
  echo ""
  echo "▶ Creating .env from template..."
  cp .env.example .env

  # Generate random secrets
  N8N_KEY=$(openssl rand -hex 16)
  PG_PASS=$(openssl rand -base64 24 | tr -d '/+=')
  REDIS_PASS=$(openssl rand -base64 16 | tr -d '/+=')

  # Insert generated values
  sed -i.bak "s/REPLACE_WITH_RANDOM_32_CHAR_STRING/$N8N_KEY/" .env
  sed -i.bak "s/REPLACE_WITH_STRONG_PASSWORD/$PG_PASS/" .env
  sed -i.bak "s/REPLACE_WITH_REDIS_PASSWORD/$REDIS_PASS/" .env
  rm -f .env.bak

  echo "  ✓ .env created with auto-generated secrets"
  echo ""
  echo "  ⚠️  IMPORTANT: Open .env and fill in these required values:"
  echo "     - OPENAI_API_KEY"
  echo "     - ANTHROPIC_API_KEY"
  echo "     - GMAIL_CLIENT_ID + GMAIL_CLIENT_SECRET (ingestion inbox)"
  echo "     - GMAIL_SEND_CLIENT_ID + GMAIL_SEND_CLIENT_SECRET (send outputs)"
  echo "     - GMAIL_INGESTION_ADDRESS (your dedicated deal ingestion Gmail address)"
  echo "     - AUSTIN_EMAIL (your Outlook address for receiving outputs)"
  echo "     - GITHUB_TOKEN + GITHUB_REPO"
  echo ""
  read -p "  Press Enter after filling in .env to continue..."
else
  echo "  ✓ .env already exists, skipping"
fi

# ── 3. Create template directories ───────────────────────────────────────────
echo ""
echo "▶ Creating template directories..."
mkdir -p templates/pdf/generated
mkdir -p templates/pptx/generated
echo "  ✓ templates/pdf/generated"
echo "  ✓ templates/pptx/generated"

# ── 4. Start Docker Compose ───────────────────────────────────────────────────
echo ""
echo "▶ Starting Docker Compose stack (this may take 2-3 min on first run)..."
docker compose up -d

echo ""
echo "  Waiting for services to be healthy..."
sleep 15

# ── 5. Create Qdrant collection ───────────────────────────────────────────────
echo ""
echo "▶ Creating Qdrant 'deals' collection..."

QDRANT_READY=false
for i in {1..12}; do
  if curl -sf http://localhost:6333/healthz > /dev/null 2>&1; then
    QDRANT_READY=true
    break
  fi
  echo "  Waiting for Qdrant... ($i/12)"
  sleep 5
done

if [ "$QDRANT_READY" = true ]; then
  RESPONSE=$(curl -s -X PUT http://localhost:6333/collections/deals \
    -H "Content-Type: application/json" \
    -d '{
      "vectors": {
        "size": 1536,
        "distance": "Cosine",
        "on_disk": false
      },
      "optimizers_config": {
        "default_segment_number": 2
      },
      "quantization_config": {
        "scalar": {
          "type": "int8",
          "quantile": 0.99,
          "always_ram": true
        }
      }
    }')

  if echo "$RESPONSE" | grep -q '"result":true'; then
    echo "  ✓ Qdrant 'deals' collection created"
  elif echo "$RESPONSE" | grep -q "already exists"; then
    echo "  ✓ Qdrant 'deals' collection already exists"
  else
    echo "  ⚠ Qdrant response: $RESPONSE"
    echo "  Run manually: bash scripts/create-qdrant-collection.sh"
  fi
else
  echo "  ⚠ Qdrant not ready yet. Run manually after startup: bash scripts/create-qdrant-collection.sh"
fi

# ── 6. Check Postgres ─────────────────────────────────────────────────────────
echo ""
echo "▶ Checking Postgres schema..."
PG_READY=false
for i in {1..12}; do
  if docker compose exec -T postgres pg_isready -U clearwater -d clearwater_deals > /dev/null 2>&1; then
    PG_READY=true
    break
  fi
  echo "  Waiting for Postgres... ($i/12)"
  sleep 5
done

if [ "$PG_READY" = true ]; then
  TABLE_COUNT=$(docker compose exec -T postgres psql -U clearwater -d clearwater_deals -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null | tr -d ' ')
  echo "  ✓ Postgres ready — $TABLE_COUNT tables created from schema"
else
  echo "  ⚠ Postgres not ready. Check: docker compose logs postgres"
fi

# ── 7. Summary ────────────────────────────────────────────────────────────────
echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║               Setup Complete! 🎉                          ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "  Service URLs:"
echo "  ┌─────────────────────────────────────────────────────┐"
echo "  │  n8n           →  http://localhost:5678             │"
echo "  │  Qdrant UI     →  http://localhost:6333/dashboard   │"
echo "  │  Metabase      →  http://localhost:3000             │"
echo "  │  Postgres      →  localhost:5432                    │"
echo "  │  Redis         →  localhost:6379                    │"
echo "  └─────────────────────────────────────────────────────┘"
echo ""
echo "  Next Steps:"
echo "  1. Open n8n at http://localhost:5678 and complete first-run setup"
echo "  2. In n8n, add credentials:"
echo "     - Gmail OAuth2 (ingestion inbox)"
echo "     - Gmail OAuth2 (send outputs)"
echo "     - OpenAI API"
echo "     - Anthropic API"
echo "     - Postgres (host: postgres, db: clearwater_deals, user: clearwater)"
echo "     - Qdrant (host: http://qdrant:6333)"
echo "     - Redis (host: redis, password: from .env)"
echo "  3. Import workflow JSONs from n8n/workflows/ into n8n"
echo "  4. Set up Metabase at http://localhost:3000 (connect to Postgres)"
echo "  5. Set up n8n-mcp in Claude Code:"
echo "     claude mcp add n8n-mcp \\"
echo "       --env MCP_MODE=stdio \\"
echo "       --env N8N_API_URL=http://localhost:5678 \\"
echo "       --env N8N_API_KEY=<your-n8n-api-key> \\"
echo "       --env DISABLE_CONSOLE_OUTPUT=true \\"
echo "       -- npx -y n8n-mcp"
echo ""
echo "  See SETUP.md for detailed credential configuration instructions."
echo ""
