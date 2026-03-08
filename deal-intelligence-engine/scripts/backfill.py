"""
Historical Backfill Script — Clearwater Deal Intelligence Engine

Ingests historical deal content in chronological batches, scoring after
each batch to build a real score progression over time.

Usage:
    python3 scripts/backfill.py --deal velentium              # full run
    python3 scripts/backfill.py --deal velentium --dry-run    # parse only, no writes

What it does:
1. Reads all files from backfill/<deal>/
2. Extracts dates from content/filenames
3. Sorts files chronologically
4. Splits into batches (one per unique date or weekly bucket)
5. For each batch:
   a. Chunk + embed via OpenAI
   b. Write vectors to Qdrant
   c. Write rows to Postgres ingestion_log
   d. Fire CW-02 webhook → wait 120s for scoring
   e. Print the resulting score
6. Outputs full score history at the end

Requirements:
    pip3 install openai psycopg2-binary qdrant-client python-dotenv requests
"""

import argparse
import email
import hashlib
import os
import quopri
import re
import sys
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import anthropic
import requests
from dotenv import load_dotenv

# ── Load env ─────────────────────────────────────────────────────────────────
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY")
POSTGRES_HOST     = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT     = os.getenv("POSTGRES_PORT", "5433")
POSTGRES_DB       = os.getenv("POSTGRES_DB", "clearwater_deals")
POSTGRES_USER     = os.getenv("POSTGRES_USER", "clearwater")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
QDRANT_URL        = os.getenv("QDRANT_URL", "http://localhost:6333")
N8N_WEBHOOK_BASE  = os.getenv("N8N_WEBHOOK_BASE", "http://localhost:5678")

BACKFILL_DIR = Path(__file__).parent.parent / "backfill"
CHUNK_SIZE   = 400   # approximate tokens (words)
CHUNK_OVERLAP = 50
SCORE_WAIT_SECS = 120  # wait for CW-02 to finish scoring

# ── Deal config ───────────────────────────────────────────────────────────────
DEAL_CONFIG = {
    "american-medical-staffing": {
        "deal_id": "cw_americanmedicalstaffing_2026",
        "company_name": "American Medical Staffing",
        "sender_domain": "americanmedicalstaffing.com",
        "deal_stage": "Discover",
    },
    "exer-urgent-care": {
        "deal_id": "cw_exerurgentcare_2026",
        "company_name": "Exer Urgent Care",
        "sender_domain": "exerurgentcare.com",
        "deal_stage": "Discover",
    },
    "mississippi-state": {
        "deal_id": "cw_mississippistate_2026",
        "company_name": "Mississippi State University",
        "sender_domain": "msstate.edu",
        "deal_stage": "Discover",
    },
    "pantherx": {
        "deal_id": "cw_pantherrx_rare_2026",
        "company_name": "PANTHERx Rare",
        "sender_domain": "pantherxrare.com",
        "deal_stage": "Discover",
    },
    "pyramids-pharmacy": {
        "deal_id": "cw_pyramidspharmacy_2026",
        "company_name": "Pyramids Pharmacy",
        "sender_domain": "pyramidspharmacy.com",
        "deal_stage": "Discover",
    },
    "velentium": {
        "deal_id": "cw_velentiummedical_2026",
        "company_name": "Velentium Medical",
        "sender_domain": "velentiummedical.com",
        "deal_stage": "Discover",
    },
    "minaris": {
        "deal_id": "cw_minaris_2026",
        "company_name": "Minaris Advanced Therapies",
        "sender_domain": "minaris.com",
        "deal_stage": "Discover",
    },
    "ephicacy": {
        "deal_id": "cw_ephicacy_2026",
        "company_name": "Ephicacy",
        "sender_domain": "ephicacy.com",
        "deal_stage": "Discover",
    },
    "partnership-healthplan": {
        "deal_id": "cw_partnershiphp_2026",
        "company_name": "Partnership HealthPlan of California",
        "sender_domain": "partnershiphp.org",
        "deal_stage": "Discover",
    },
    "trustwell-living": {
        "deal_id": "cw_trustwellliving_2026",
        "company_name": "Trustwell Living",
        "sender_domain": "trustwellliving.com",
        "deal_stage": "Discover",
    },
    "dedicated-sleep": {
        "deal_id": "cw_dedicatedsleep_2026",
        "company_name": "Dedicated Sleep",
        "sender_domain": "dedicatedsleep.net",
        "deal_stage": "Discover",
    },
    "rise-services": {
        "deal_id": "cw_riseservices_2026",
        "company_name": "RISE Services",
        "sender_domain": "riseservicesinc.org",
        "deal_stage": "Discover",
    },
    "family-resource-home-care": {
        "deal_id": "cw_familyrhc_2026",
        "company_name": "Family Resource Home Care",
        "sender_domain": "familyrhc.com",
        "deal_stage": "Discover",
    },
    "primary-health-partners": {
        "deal_id": "cw_primaryhealthpartners_2026",
        "company_name": "Primary Health Partners Oklahoma",
        "sender_domain": "primary-healthpartners.com",
        "deal_stage": "Discover",
    },
    "royal-community-support": {
        "deal_id": "cw_royalcommunity_2026",
        "company_name": "Royal Community Support",
        "sender_domain": "royalcsnj.com",
        "deal_stage": "Discover",
    },
    "paradigm-health": {
        "deal_id": "cw_paradigmhealth_2026",
        "company_name": "Paradigm Health",
        "sender_domain": "plchealth.com",
        "deal_stage": "Discover",
    },
    "medelite": {
        "deal_id": "cw_medelite_2026",
        "company_name": "MedElite",
        "sender_domain": "medelitegrp.com",
        "deal_stage": "Discover",
    },
    "atlas-clinical": {
        "deal_id": "cw_atlasclinical_2026",
        "company_name": "Atlas Clinical Research",
        "sender_domain": "atlas-clinical.com",
        "deal_stage": "Discover",
    },
    "fella-health": {
        "deal_id": "cw_fellahealth_2026",
        "company_name": "Fella Health",
        "sender_domain": "fellahealth.com",
        "deal_stage": "Discover",
    },
    "sca-pharma": {
        "deal_id": "cw_scapharma_2026",
        "company_name": "SCA Pharma",
        "sender_domain": "scapharma.com",
        "deal_stage": "Discover",
    },
    "advanced-dermatology": {
        "deal_id": "cw_advanceddermatology_2026",
        "company_name": "Advanced Dermatology PC",
        "sender_domain": "advderm.net",
        "deal_stage": "Discover",
    },
    "life-care-home-health": {
        "deal_id": "cw_life_care_home_health_2026",
        "company_name": "Life Care Home Health",
        "sender_domain": "lchhfamily.com",
        "deal_stage": "Discover",
    },
    "sandstone": {
        "deal_id": "cw_sandstonecare_2026",
        "company_name": "Sandstone Care",
        "sender_domain": "sandstonecare.com",
        "deal_stage": "Discover",
    },
    "auch-utech": {
        "deal_id": "cw_auchutech_2026",
        "company_name": "AUCH UTECH",
        "sender_domain": "utech.edu",
        "deal_stage": "Discover",
    },
    "st-croix-hospice": {
        "deal_id": "cw_stcroixhospice_2026",
        "company_name": "St. Croix Hospice",
        "sender_domain": "stcroixhospice.com",
        "deal_stage": "Discover",
    },
    "carehospice": {
        "deal_id": "cw_carehospice_2026",
        "company_name": "CareHospice",
        "sender_domain": "carehospice.com",
        "deal_stage": "Discover",
    },
    "personal-physicians-healthcare": {
        "deal_id": "cw_personalpyhc_2026",
        "company_name": "Personal Physicians Healthcare",
        "sender_domain": "personalpyhc.com",
        "deal_stage": "Discover",
    },
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_eml(path: Path) -> dict:
    """Parse a .eml file into {text, date, subject, sender}."""
    msg = email.message_from_bytes(path.read_bytes())

    subject = msg.get("Subject", "").strip()
    sender  = msg.get("From", "").strip()
    date_str = msg.get("Date", "")

    # Parse date
    date = datetime.now() - timedelta(days=30)
    try:
        from email.utils import parsedate_to_datetime
        date = parsedate_to_datetime(date_str).replace(tzinfo=None)
    except Exception:
        pass

    # Extract body
    body_parts = []
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if ct == "text/plain" and "attachment" not in cd:
                try:
                    body_parts.append(part.get_payload(decode=True).decode(errors="ignore"))
                except Exception:
                    pass
    else:
        try:
            body_parts.append(msg.get_payload(decode=True).decode(errors="ignore"))
        except Exception:
            body_parts.append(str(msg.get_payload()))

    body = "\n".join(body_parts).strip()
    # Strip quoted reply blocks (lines starting with >)
    body = "\n".join(l for l in body.splitlines() if not l.startswith(">"))
    body = re.sub(r'\n{3,}', '\n\n', body).strip()

    text = f"Subject: {subject}\nFrom: {sender}\nDate: {date.strftime('%Y-%m-%d')}\n\n{body}"
    return {"text": text, "date": date, "subject": subject, "sender": sender}


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunks.append(" ".join(words[i:i + chunk_size]))
        i += chunk_size - overlap
    return chunks


def extract_date(text, filename):
    """Extract earliest date from content or filename. Returns datetime."""
    patterns = [
        (r'Date:\s+\w+,\s+(\w+ \d+,\s+\d{4})', "%B %d, %Y"),
        (r'Exported:\s+(\d{4}-\d{2}-\d{2})',     "%Y-%m-%d"),
        (r'(\d{4}-\d{2}-\d{2})',                  "%Y-%m-%d"),
        (r'(\w+ \d{1,2},\s+\d{4})',               "%B %d, %Y"),
    ]
    for pattern, fmt in patterns:
        m = re.search(pattern, text[:3000])
        if m:
            try:
                return datetime.strptime(m.group(1).strip(), fmt)
            except ValueError:
                continue
    # Try filename
    m = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d")
        except ValueError:
            pass
    return datetime.now() - timedelta(days=30)


def detect_doc_type(filename, text):
    fn = filename.lower()
    if "transcript" in fn or "call" in fn:
        return "call_transcript"
    if "email" in fn or "from:" in text[:200].lower():
        return "email_thread"
    if "gemini" in fn:
        return "gemini_chat"
    if fn.endswith(".pdf"):
        return "pdf"
    if fn.endswith(".pptx"):
        return "presentation"
    return "document"


def generate_transcript_preamble(text: str, company_name: str, date_str: str) -> str:
    """
    Call Claude Sonnet to generate a 3-4 sentence preamble for a call transcript.
    Returns the preamble string, or empty string on failure.
    Only called for call_transcript doc type.
    """
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    if not ANTHROPIC_API_KEY:
        return ""

    snippet = text[:6000]
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=256,
            system=(
                "You are writing a brief preamble for a sales call transcript. "
                "Be factual and concise. Return ONLY the preamble text — no labels, "
                "no JSON, no markdown."
            ),
            messages=[{"role": "user", "content": f"""Write a 3-4 sentence preamble for this call transcript.
Include: who is on the call (names and roles if mentioned), the company being discussed ({company_name}),
the date ({date_str}), the type of call (discovery, follow-up, demo, etc.), and the key outcome or main topic.
If participants aren't named, describe them by role (e.g. "Austin Hollins (AE at Clearwater) and two representatives from {company_name}").

TRANSCRIPT (first 6000 chars):
{snippet}"""}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"  [preamble error] {e}")
        return ""


def embed_texts(texts):
    import openai
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=texts
    )
    return [item.embedding for item in response.data]


def write_to_qdrant(deal_config, chunks_with_embeddings):
    from qdrant_client import QdrantClient
    from qdrant_client.models import PointStruct
    client = QdrantClient(url=QDRANT_URL, check_compatibility=False)
    points = []
    for item in chunks_with_embeddings:
        points.append(PointStruct(
            id=str(uuid.uuid4()),
            vector=item["embedding"],
            payload={
                "deal_id":                deal_config["deal_id"],
                "company_name":           deal_config["company_name"],
                "sender_domain":          deal_config["sender_domain"],
                "deal_stage":             deal_config["deal_stage"],
                "doc_type":               item["doc_type"],
                "date_created":           item["date"].isoformat(),
                "chunk_index":            item["chunk_index"],
                "attribution_confidence": "high",
                "source_file":            item["filename"],
                "page_content":           item["text"],
            }
        ))
    if points:
        client.upsert(collection_name="deals", points=points)
    return len(points)


def write_to_postgres(deal_config, file_rows):
    import psycopg2
    conn = psycopg2.connect(
        host=POSTGRES_HOST, port=POSTGRES_PORT,
        dbname=POSTGRES_DB, user=POSTGRES_USER, password=POSTGRES_PASSWORD
    )
    cur = conn.cursor()
    # Ensure deal record exists
    cur.execute("""
        INSERT INTO deals (deal_id, company_name, sender_domains, deal_stage, is_active)
        VALUES (%s, %s, %s::text[], %s, true)
        ON CONFLICT (deal_id) DO NOTHING
    """, (deal_config["deal_id"], deal_config["company_name"],
          "{" + deal_config["sender_domain"] + "}", deal_config["deal_stage"]))

    for row in file_rows:
        msg_id = hashlib.md5(
            f"{deal_config['deal_id']}_{row['filename']}_{row['chunk_index']}".encode()
        ).hexdigest()
        cur.execute("""
            INSERT INTO ingestion_log
                (message_id, deal_id, doc_type, sender_domain,
                 attribution_confidence, attribution_status,
                 subject, qdrant_namespace, chunk_count)
            VALUES (%s, %s, %s, %s, 'high', 'confirmed', %s, %s, 1)
            ON CONFLICT (message_id) DO NOTHING
        """, (msg_id, deal_config["deal_id"], row["doc_type"],
              deal_config["sender_domain"],
              row["filename"],
              deal_config["deal_id"]))
    conn.commit()
    cur.close()
    conn.close()


def fire_cw02(deal_id, batch_label):
    url = f"{N8N_WEBHOOK_BASE}/webhook/deal-health-trigger"
    try:
        requests.post(url, json={"deal_id": deal_id, "trigger_type": "backfill",
                                 "batch_label": batch_label}, timeout=5)
    except requests.exceptions.Timeout:
        pass  # fire-and-forget


def fetch_latest_score(deal_id):
    """Query Postgres for the most recent deal_health row."""
    import psycopg2
    try:
        conn = psycopg2.connect(
            host=POSTGRES_HOST, port=POSTGRES_PORT,
            dbname=POSTGRES_DB, user=POSTGRES_USER, password=POSTGRES_PASSWORD
        )
        cur = conn.cursor()
        cur.execute("""
            SELECT p2v2c2_total, pain_score, power_score, vision_score,
                   value_score, change_score, control_score,
                   critical_activity_stage, scored_at
            FROM deal_health
            WHERE deal_id = %s
            ORDER BY scored_at DESC
            LIMIT 1
        """, (deal_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row
    except Exception as e:
        print(f"  ⚠️  Could not fetch score: {e}")
        return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--deal", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--score-once", action="store_true",
                        help="Ingest all batches first, fire CW-02 once at the end (faster)")
    args = parser.parse_args()

    deal_name = args.deal.lower()
    if deal_name not in DEAL_CONFIG:
        print(f"Unknown deal '{deal_name}'. Available: {list(DEAL_CONFIG.keys())}")
        sys.exit(1)

    deal_config = DEAL_CONFIG[deal_name]
    deal_dir = BACKFILL_DIR / deal_name

    files = sorted([f for f in deal_dir.iterdir()
                    if f.is_file() and f.suffix in {".txt", ".pdf", ".pptx", ".csv", ".eml"}
                    and not f.name.startswith(".")])

    if not files:
        print(f"No files in {deal_dir}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"Backfill: {deal_config['company_name']}")
    print(f"Files: {len(files)}")
    print(f"{'='*60}\n")

    # ── Step 1: Parse all files, extract dates ────────────────────────────────
    parsed = []
    for f in files:
        if f.suffix == ".eml":
            eml = parse_eml(f)
            text = eml["text"]
            date = eml["date"]
            doc_type = "email_thread"
        else:
            text = f.read_text(encoding="utf-8", errors="ignore")
            text = text.replace('\u2028', '\n').replace('\u2029', '\n')
            # Skip internal excerpts (pipeline review calls routed here by transcribe.py)
            if "Call Type: internal excerpt" in text[:500]:
                print(f"  {f.name[:40]:40s} → SKIPPED (internal excerpt)")
                continue
            date = extract_date(text, f.name)
            doc_type = detect_doc_type(f.name, text)
        parsed.append({"file": f, "text": text, "date": date, "doc_type": doc_type})
        print(f"  {f.name[:40]:40s} → {doc_type:20s} | {date.strftime('%Y-%m-%d')}")

    # ── Step 2: Sort chronologically ─────────────────────────────────────────
    parsed.sort(key=lambda x: x["date"])

    # ── Step 3: Group into weekly batches ─────────────────────────────────────
    # Non-email files (transcripts, PDFs) get their own batch for precise scoring
    # Emails are grouped by ISO week so we score weekly not per-email
    weekly = defaultdict(list)
    solo_batches = []

    for p in parsed:
        if p["doc_type"] == "email_thread":
            week_key = p["date"].strftime("%Y-W%W")
            weekly[week_key].append(p)
        else:
            solo_batches.append((p["date"].strftime("%Y-%m-%d") + f"_{p['doc_type']}", [p]))

    weekly_batches = [(f"{wk}_emails", items)
                      for wk, items in sorted(weekly.items())]

    # Merge and re-sort all batches chronologically
    all_batches = sorted(solo_batches + weekly_batches, key=lambda x: x[0])

    print(f"\nBatches (score after each):")
    for label, items in all_batches:
        print(f"  {label}: {len(items)} file(s)")

    batches = all_batches

    if args.dry_run:
        print("\nDry run complete — no writes.")
        return

    # ── Step 4: Process each batch ────────────────────────────────────────────
    score_history = []

    for batch_idx, (batch_label, batch_files) in enumerate(all_batches):
        print(f"\n{'─'*60}")
        print(f"Batch {batch_idx+1}/{len(batches)}: {batch_label}")
        print(f"{'─'*60}")

        # Build chunks for this batch
        all_chunks = []
        for item in batch_files:
            # Generate preamble for call transcripts only
            preamble = ""
            if item["doc_type"] == "call_transcript":
                print(f"  Generating preamble for {item['file'].name}...")
                preamble = generate_transcript_preamble(
                    item["text"],
                    deal_config["company_name"],
                    item["date"].strftime("%Y-%m-%d"),
                )
                if preamble:
                    print(f"  Preamble: {preamble[:120]}...")

            context_header = (
                f"[DEAL CONTEXT]\n"
                f"Deal: {deal_config['company_name']} (ID: {deal_config['deal_id']})\n"
                f"Document Type: {item['doc_type']}\n"
                f"Date: {item['date'].strftime('%Y-%m-%d')}\n"
                f"Source File: {item['file'].name}\n"
                + (f"Summary: {preamble}\n" if preamble else "")
                + f"[END CONTEXT]\n\n"
                + (f"[CALL SUMMARY]\n{preamble}\n[END SUMMARY]\n\n" if preamble else "")
            )
            full_text = context_header + item["text"]
            chunks = chunk_text(full_text)
            for i, chunk in enumerate(chunks):
                all_chunks.append({
                    "text": chunk,
                    "date": item["date"],
                    "doc_type": item["doc_type"],
                    "filename": item["file"].name,
                    "chunk_index": i,
                })

        print(f"  Chunks: {len(all_chunks)}")

        # Embed
        print(f"  Embedding...")
        texts = [c["text"] for c in all_chunks]
        embeddings = []
        for i in range(0, len(texts), 100):
            batch_texts = texts[i:i+100]
            embeddings.extend(embed_texts(batch_texts))
            time.sleep(0.3)

        for i, emb in enumerate(embeddings):
            all_chunks[i]["embedding"] = emb

        # Write to Qdrant
        print(f"  Writing to Qdrant...")
        n = write_to_qdrant(deal_config, all_chunks)
        print(f"  ✅ {n} vectors")

        # Write to Postgres
        print(f"  Writing to Postgres...")
        write_to_postgres(deal_config, all_chunks)
        print(f"  ✅ ingestion_log updated")

        if not args.score_once:
            # Fire CW-02 after every batch (default behavior)
            print(f"  Firing CW-02 health scoring...")
            fire_cw02(deal_config["deal_id"], batch_label)

            # Wait for scoring to complete
            print(f"  Waiting {SCORE_WAIT_SECS}s for CW-02 to score...", end="", flush=True)
            for _ in range(SCORE_WAIT_SECS // 10):
                time.sleep(10)
                print(".", end="", flush=True)
            print()

            # Fetch result
            row = fetch_latest_score(deal_config["deal_id"])
            if row:
                total, pain, power, vision, value, change, control, cas, scored_at = row
                print(f"\n  Score: {total}/30  CAS: {cas}")
                print(f"  P={pain} Po={power} V={vision} Va={value} Ch={change} Co={control}")
                score_history.append({
                    "batch": batch_label,
                    "total": total, "cas": cas,
                    "pain": pain, "power": power, "vision": vision,
                    "value": value, "change": change, "control": control,
                })
            else:
                print(f"  ⚠️  No score found yet (CW-02 may still be running)")

    if args.score_once:
        # Fire CW-02 once after all batches are ingested
        final_label = all_batches[-1][0] if all_batches else "final"
        print(f"\n{'─'*60}")
        print(f"  All batches ingested. Firing CW-02 once (--score-once)...")
        fire_cw02(deal_config["deal_id"], final_label)

        print(f"  Waiting {SCORE_WAIT_SECS}s for CW-02 to score...", end="", flush=True)
        for _ in range(SCORE_WAIT_SECS // 10):
            time.sleep(10)
            print(".", end="", flush=True)
        print()

        row = fetch_latest_score(deal_config["deal_id"])
        if row:
            total, pain, power, vision, value, change, control, cas, scored_at = row
            print(f"\n  Final Score: {total}/30  CAS: {cas}")
            print(f"  P={pain} Po={power} V={vision} Va={value} Ch={change} Co={control}")
            score_history.append({
                "batch": "final (all batches)",
                "total": total, "cas": cas,
                "pain": pain, "power": power, "vision": vision,
                "value": value, "change": change, "control": control,
            })
        else:
            print(f"  ⚠️  No score found yet (CW-02 may still be running)")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"SCORE HISTORY — {deal_config['company_name']}")
    print(f"{'='*60}")
    for s in score_history:
        print(f"  {s['batch']:45s} → {s['total']:2d}/30  CAS: {s['cas']}")
    print()


if __name__ == "__main__":
    main()
