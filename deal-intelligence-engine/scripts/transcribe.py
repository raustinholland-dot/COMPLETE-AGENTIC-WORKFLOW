"""
transcribe.py — Voice Memo → Whisper → Claude deal assignment → backfill/<deal>/

Usage:
    python3 scripts/transcribe.py              # process all unprocessed memos
    python3 scripts/transcribe.py --dry-run    # preview only, no API calls
    python3 scripts/transcribe.py --min-mins 2 # override min duration (default: 3)
    python3 scripts/transcribe.py --max-mins 90 # truncate recordings longer than N minutes (default: 120)

Routing logic:
  - Single deal (high/medium confidence) → backfill/<deal>/<date>_transcript-NN.txt
  - Multi-deal / internal call           → backfill/_internal/<date>_full.txt (full)
                                           + backfill/<deal>/<date>_transcript-NN.txt (verbatim excerpt per deal)
  - No deal mentioned                    → backfill/_internal/<date>_<topic-slug>.txt
"""

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

from dotenv import load_dotenv

# ── Load env ─────────────────────────────────────────────────────────────────
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

if not ANTHROPIC_API_KEY:
    sys.exit("ERROR: ANTHROPIC_API_KEY not found in .env")

import anthropic

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ── Constants ─────────────────────────────────────────────────────────────────
RECORDINGS_DIR = Path("/Users/austinhollsnd/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings")
DB_PATH        = RECORDINGS_DIR / "CloudRecordings.db"
BACKFILL_DIR   = Path(__file__).parent.parent / "backfill"
INTERNAL_DIR   = BACKFILL_DIR / "_internal"

WHISPER_MODEL     = Path(__file__).parent.parent / "models" / "ggml-medium.en.bin"
WHISPER_THREADS   = 8                  # M4 Pro — adjust if needed
WAV_SAMPLE_RATE   = 16000              # 16kHz mono — whisper.cpp native rate
WAV_CHANNELS      = 1
WAV_SAMPLE_WIDTH  = 2                  # 16-bit = 2 bytes

# ── Active Deals ─────────────────────────────────────────────────────────────
DEALS = {
    "american-medical-staffing": {"company": "American Medical Staffing", "domain": "americanmedicalstaffing.com"},
    "exer-urgent-care":          {"company": "Exer Urgent Care", "domain": "exerurgentcare.com"},
    "mississippi-state":         {"company": "Mississippi State University", "domain": "msstate.edu"},
    "pantherx":                  {"company": "PANTHERx Rare", "domain": "pantherxrare.com"},
    "pyramids-pharmacy":         {"company": "Pyramids Pharmacy", "domain": "pyramidspharmacy.com"},
    "velentium":                 {"company": "Velentium Medical", "domain": "velentiummedical.com"},
    "minaris":                   {"company": "Minaris Advanced Therapies", "domain": "minaris.com"},
    "ephicacy":                  {"company": "Ephicacy", "domain": "ephicacy.com"},
    "partnership-healthplan":    {"company": "Partnership HealthPlan of California", "domain": "partnershiphp.org"},
    "trustwell-living":          {"company": "Trustwell Living", "domain": "trustwellliving.com"},
    "dedicated-sleep":           {"company": "Dedicated Sleep", "domain": "dedicatedsleep.net"},
    "rise-services":             {"company": "RISE Services", "domain": "riseservicesinc.org"},
    "family-resource-home-care": {"company": "Family Resource Home Care", "domain": "familyrhc.com"},
    "primary-health-partners":   {"company": "Primary Health Partners Oklahoma", "domain": "primary-healthpartners.com"},
    "royal-community-support":   {"company": "Royal Community Support", "domain": "royalcsnj.com"},
    "paradigm-health":           {"company": "Paradigm Health", "domain": "plchealth.com"},
    "medelite":                  {"company": "MedElite", "domain": "medelitegrp.com"},
    "atlas-clinical":            {"company": "Atlas Clinical Research", "domain": "atlas-clinical.com"},
    "fella-health":              {"company": "Fella Health", "domain": "fellahealth.com"},
    "sca-pharma":                {"company": "SCA Pharma", "domain": "scapharma.com"},
    "advanced-dermatology":      {"company": "Advanced Dermatology PC", "domain": "advderm.net"},
    "life-care-home-health":     {"company": "Life Care Home Health", "domain": "lchhfamily.com"},
}


# ── DB / file helpers ─────────────────────────────────────────────────────────

def get_all_memos(min_secs: int) -> list[dict]:
    """
    Query CloudRecordings.db for all memos >= min_secs duration.
    Includes the user-set title (ZENCRYPTEDTITLE) for deal matching.
    Skips recordings between midnight and 6am Central time (UTC-5/6) — butt-dials/accidents.
    """
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cur = conn.cursor()
        # UTC-6 offset (Central Standard). Recordings between 06:00-12:00 UTC = midnight-6am CT.
        cur.execute("""
            SELECT
                datetime(ZDATE + 978307200, 'unixepoch') as date_utc,
                ZDURATION as duration_secs,
                ZPATH as path,
                ZENCRYPTEDTITLE as title
            FROM ZCLOUDRECORDING
            WHERE ZDURATION >= ?
              AND CAST(strftime('%H', datetime(ZDATE + 978307200 - 21600, 'unixepoch')) AS INTEGER) BETWEEN 7 AND 22
            ORDER BY ZDATE
        """, (min_secs,))
        rows = cur.fetchall()
        return [
            {
                "date":          row[0],
                "date_str":      row[0][:10],
                "duration_secs": row[1],
                "duration_mins": round(row[1] / 60, 1),
                "filename":      row[2],
                "filepath":      RECORDINGS_DIR / row[2],
                "title":         (row[3] or "").strip(),
            }
            for row in rows
        ]
    finally:
        conn.close()


def find_existing_transcripts() -> set[str]:
    """
    Scan all .txt files in backfill/ for 'Source File:' headers.
    Returns a set of source filenames already processed.
    """
    processed = set()
    if not BACKFILL_DIR.exists():
        return processed
    for txt_file in BACKFILL_DIR.rglob("*.txt"):
        try:
            content = txt_file.read_text(encoding="utf-8", errors="replace")
            m = re.search(r"Source File:\s*(.+)", content)
            if m:
                processed.add(m.group(1).strip())
        except Exception:
            pass
    return processed


def get_next_transcript_number(deal_dir: Path) -> int:
    """Return the next available transcript number for a deal directory."""
    existing = list(deal_dir.glob("*transcript-*.txt")) if deal_dir.exists() else []
    if not existing:
        return 1
    numbers = []
    for f in existing:
        m = re.search(r"transcript-(\d+)", f.name)
        if m:
            numbers.append(int(m.group(1)))
    return max(numbers) + 1 if numbers else 1


# ── Audio processing ──────────────────────────────────────────────────────────

def compress_to_wav(m4a_path: Path, out_wav: Path) -> bool:
    """Convert m4a to 16kHz mono 16-bit WAV using macOS afconvert."""
    result = subprocess.run(
        ["afconvert", "-f", "WAVE", "-d", f"LEI16@{WAV_SAMPLE_RATE}",
         "-c", str(WAV_CHANNELS), str(m4a_path), str(out_wav)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  [afconvert error] {result.stderr.strip()}")
        return False
    return True


def truncate_wav(wav_path: Path, max_secs: int, out_path: Path) -> bool:
    """Write a new WAV file containing only the first max_secs seconds."""
    try:
        with wave.open(str(wav_path), "rb") as wf:
            n_channels   = wf.getnchannels()
            sample_width = wf.getsampwidth()
            framerate    = wf.getframerate()
            max_frames   = min(wf.getnframes(), max_secs * framerate)
            frames       = wf.readframes(max_frames)
        with wave.open(str(out_path), "wb") as wf_out:
            wf_out.setnchannels(n_channels)
            wf_out.setsampwidth(sample_width)
            wf_out.setframerate(framerate)
            wf_out.writeframes(frames)
        return True
    except Exception as e:
        print(f"  [truncate_wav error] {e}")
        return False


def transcribe_file(audio_path: Path, max_secs: int | None = None) -> str | None:
    """
    Transcribe an audio file locally via whisper.cpp (ggml-medium.en).
    Converts to 16kHz WAV first, then runs whisper-cli.
    Zero API cost. ~2-3 min per 30 min recording on Apple Silicon.
    """
    if not WHISPER_MODEL.exists():
        print(f"  [ERROR] Whisper model not found at {WHISPER_MODEL}")
        return None

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        wav_path = tmp_path / (audio_path.stem.replace(" ", "_") + ".wav")

        print(f"  Converting to 16kHz WAV...")
        if not compress_to_wav(audio_path, wav_path):
            print(f"  [ERROR] afconvert failed — skipping")
            return None

        if max_secs is not None:
            trunc_path = tmp_path / (audio_path.stem.replace(" ", "_") + "_truncated.wav")
            print(f"  Truncating to first {max_secs // 60} minutes...")
            if truncate_wav(wav_path, max_secs, trunc_path):
                wav_path = trunc_path
            else:
                print(f"  [ERROR] Truncation failed — using full file")

        wav_size = wav_path.stat().st_size
        print(f"  WAV size: {wav_size / 1024 / 1024:.1f}MB")

        print(f"  Transcribing locally via whisper.cpp...")
        result = subprocess.run(
            ["whisper-cli",
             "-m", str(WHISPER_MODEL),
             "-f", str(wav_path),
             "-t", str(WHISPER_THREADS),
             "--no-timestamps"],
            capture_output=True, text=True,
        )

        if result.returncode != 0:
            print(f"  [whisper-cli error] {result.stderr.strip()}")
            return None

        transcript = result.stdout.strip()
        if not transcript:
            print(f"  [WARN] Empty transcript returned")
            return None

        return transcript


# ── Claude analysis ───────────────────────────────────────────────────────────

def analyse_transcript(transcript: str, filename: str) -> dict:
    """
    Send transcript to Claude Sonnet for full deal analysis.

    Returns a dict with one of two shapes:

    Single-deal call:
      {
        "call_type": "single_deal",
        "deal_slug": "<slug>",
        "confidence": "high|medium|low",
        "reasoning": "..."
      }

    Multi-deal / internal call:
      {
        "call_type": "internal",
        "deals": [
          {
            "deal_slug": "<slug>",
            "excerpt": "<verbatim passage(s) about this deal>"
          },
          ...
        ],
        "topic_slug": "<2-4-word-kebab-case topic, e.g. pipeline-review>"
      }

    No-deal call:
      {
        "call_type": "no_deal",
        "topic_slug": "<2-4-word-kebab-case topic, e.g. coaching-session>"
      }
    """
    # Use full transcript (up to ~30k chars — well within Sonnet context)
    snippet = transcript[:30000]
    deals_json = json.dumps(
        {slug: info["company"] for slug, info in DEALS.items()},
        indent=2
    )

    system_prompt = (
        "You are analyzing call transcripts for Austin Hollins, an Account Executive at "
        "Clearwater Security & Compliance. Austin sells cybersecurity and compliance services "
        "to healthcare organizations. His calls are either:\n"
        "  1. A call WITH a prospect/client about a specific deal\n"
        "  2. An internal Clearwater call (coaching, pipeline review, team meeting) where "
        "     multiple deals may be discussed\n"
        "  3. A call unrelated to any specific deal\n\n"
        "Return ONLY valid JSON, no other text."
    )

    user_prompt = f"""Analyze this call transcript and classify it.

TRANSCRIPT:
{snippet}

ACTIVE DEALS (slug → company name):
{deals_json}

Classify as ONE of these three types and return the matching JSON shape:

TYPE 1 — Single external deal call (Austin is talking WITH the prospect/client):
{{
  "call_type": "single_deal",
  "deal_slug": "<slug from list above, or null>",
  "confidence": "high|medium|low",
  "reasoning": "<1-2 sentences explaining why>"
}}

TYPE 2 — Internal Clearwater call where multiple deals are discussed (coaching, pipeline review, etc.):
{{
  "call_type": "internal",
  "deals": [
    {{
      "deal_slug": "<slug>",
      "excerpt": "<copy the verbatim passage(s) from the transcript where this deal is discussed — include enough context, at least a full paragraph>"
    }}
  ],
  "topic_slug": "<2-4 word kebab-case summary of call topic, e.g. 'pipeline-review' or 'q1-coaching-session'>"
}}

TYPE 3 — No specific deal mentioned:
{{
  "call_type": "no_deal",
  "topic_slug": "<2-4 word kebab-case summary, e.g. 'onboarding-call' or 'admin-discussion'>"
}}

Rules:
- Only include deals where there is substantive discussion (not just a passing mention of a company name).
- For excerpts, copy the actual transcript text verbatim — do not paraphrase or summarize.
- If Austin is clearly talking TO someone at a prospect company, it is a single_deal call even if he mentions other deals briefly.
- If deal_slug is null for single_deal, set confidence to "low"."""

    try:
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = response.content[0].text.strip()
        raw = re.sub(r"```json\n?", "", raw)
        raw = re.sub(r"```\n?", "", raw)
        return json.loads(raw.strip())
    except Exception as e:
        print(f"  [Claude error] {e}")
        return {"call_type": "no_deal", "topic_slug": "analysis-error"}


# ── File writing ──────────────────────────────────────────────────────────────

def build_header(memo: dict, label: str, extra_lines: list[str] | None = None) -> str:
    """Build the standard output file header."""
    lines = [
        "[VOICE MEMO TRANSCRIPT]",
        f"Date: {memo['date_str']}",
        f"Duration: {memo['duration_mins']} minutes",
        f"Source File: {memo['filename']}",
        f"Deal: {label}",
    ]
    if extra_lines:
        lines.extend(extra_lines)
    lines.append("[END HEADER]")
    lines.append("")
    return "\n".join(lines) + "\n"


def save_single_deal(memo: dict, transcript: str, deal_slug: str,
                     confidence: str, reasoning: str, dry_run: bool) -> str:
    """Save a single-deal transcript to backfill/<deal>/."""
    company_name = DEALS[deal_slug]["company"] if deal_slug and deal_slug in DEALS else "Unknown"
    if deal_slug and deal_slug in DEALS and confidence in ("high", "medium"):
        deal_dir = BACKFILL_DIR / deal_slug
        n        = get_next_transcript_number(deal_dir)
        filename = f"{memo['date_str']}_transcript-{n:02d}.txt"
        out_path = deal_dir / filename
    else:
        out_path = INTERNAL_DIR / f"{memo['date_str']}_{Path(memo['filename']).stem.replace(' ', '_')}.txt"
        company_name = "Unassigned"

    header  = build_header(memo, company_name,
                           extra_lines=[f"Identified by: Claude Sonnet (confidence: {confidence})",
                                        f"Reasoning: {reasoning}"])
    content = header + transcript

    if not dry_run:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")

    return str(out_path)


def save_internal_call(memo: dict, transcript: str, analysis: dict, dry_run: bool) -> list[str]:
    """
    Save an internal multi-deal call:
      - Full transcript → _internal/<date>_full_<topic>.txt
      - One excerpt file per deal → backfill/<deal>/<date>_transcript-NN.txt

    Returns list of all paths written.
    """
    topic_slug = analysis.get("topic_slug", "internal-call")
    saved_paths = []

    # Full transcript → _internal/
    full_path = INTERNAL_DIR / f"{memo['date_str']}_full_{topic_slug}.txt"
    full_header = build_header(memo, f"Internal — {topic_slug}",
                               extra_lines=["Call Type: internal (multi-deal)"])
    if not dry_run:
        INTERNAL_DIR.mkdir(parents=True, exist_ok=True)
        full_path.write_text(full_header + transcript, encoding="utf-8")
    saved_paths.append(str(full_path))

    # Per-deal excerpts
    for deal_entry in analysis.get("deals", []):
        slug    = deal_entry.get("deal_slug")
        excerpt = deal_entry.get("excerpt", "").strip()

        if not slug or slug not in DEALS or not excerpt:
            continue

        company_name = DEALS[slug]["company"]
        deal_dir     = BACKFILL_DIR / slug
        n            = get_next_transcript_number(deal_dir)
        filename     = f"{memo['date_str']}_transcript-{n:02d}.txt"
        out_path     = deal_dir / filename

        header = build_header(memo, company_name,
                              extra_lines=[
                                  f"Call Type: internal excerpt (full transcript in _internal/{full_path.name})",
                                  f"Topic: {topic_slug}",
                              ])
        content = header + excerpt

        if not dry_run:
            deal_dir.mkdir(parents=True, exist_ok=True)
            out_path.write_text(content, encoding="utf-8")
        saved_paths.append(str(out_path))

    return saved_paths


def save_no_deal(memo: dict, transcript: str, topic_slug: str, dry_run: bool) -> str:
    """Save a no-deal call to _internal/ with a topic label."""
    filename = f"{memo['date_str']}_{topic_slug}.txt"
    out_path = INTERNAL_DIR / filename
    header   = build_header(memo, f"Internal — {topic_slug}",
                            extra_lines=["Call Type: no deal mentioned"])
    content  = header + transcript

    if not dry_run:
        INTERNAL_DIR.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")

    return str(out_path)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Transcribe Voice Memos and assign to deals")
    parser.add_argument("--dry-run",  action="store_true", help="Preview only — no API calls or file writes")
    parser.add_argument("--min-mins", type=float, default=3.0,   help="Minimum memo duration in minutes (default: 3)")
    parser.add_argument("--max-mins", type=float, default=120.0, help="Truncate recordings longer than N minutes (default: 120)")
    args = parser.parse_args()

    min_secs = int(args.min_mins * 60)
    max_secs = int(args.max_mins * 60)

    print(f"{'[DRY RUN] ' if args.dry_run else ''}Voice Memo Transcription Pipeline")
    print(f"Min duration: {args.min_mins} min | Max: {args.max_mins} min | Backfill dir: {BACKFILL_DIR}")
    print("=" * 70)

    all_memos  = get_all_memos(min_secs)
    processed  = find_existing_transcripts()
    to_process = [m for m in all_memos if m["filename"] not in processed]

    print(f"Found {len(all_memos)} memos >= {args.min_mins} min | Already processed: {len(processed)} | To process: {len(to_process)}")
    print()

    if not to_process:
        print("Nothing to do — all memos already processed.")
        return

    stats = {
        "transcribed":    0,
        "single_deal":    0,
        "internal":       0,
        "no_deal":        0,
        "errors":         0,
        "deal_counts":    {},
    }

    for i, memo in enumerate(to_process, 1):
        filepath = memo["filepath"]
        print(f"[{i}/{len(to_process)}] {memo['filename']}  ({memo['duration_mins']} min)")

        if not filepath.exists():
            print(f"  [SKIP] File not found: {filepath}")
            stats["errors"] += 1
            continue

        file_size_mb = filepath.stat().st_size / 1024 / 1024
        truncated    = memo["duration_secs"] > max_secs
        dur_display  = f"{memo['duration_mins']} min" + (f" → truncating to {args.max_mins:.0f} min" if truncated else "")
        print(f"  Size: {file_size_mb:.1f}MB | Date: {memo['date_str']} | Duration: {dur_display}")

        if args.dry_run:
            print(f"  [DRY RUN] Would transcribe and classify")
            stats["transcribed"] += 1
            continue

        # ── Transcribe ────────────────────────────────────────────────────────
        print(f"  Transcribing via Whisper...")
        transcript = transcribe_file(filepath, max_secs=max_secs if truncated else None)
        if transcript is None:
            print(f"  [ERROR] Transcription failed — skipping")
            stats["errors"] += 1
            continue

        print(f"  Transcript: {len(transcript.split())} words")

        # ── Analyse ───────────────────────────────────────────────────────────
        print(f"  Analysing via Claude Sonnet...")
        analysis   = analyse_transcript(transcript, memo["filename"])
        call_type  = analysis.get("call_type", "no_deal")

        # ── Route & save ──────────────────────────────────────────────────────
        if call_type == "single_deal":
            deal_slug  = analysis.get("deal_slug")
            confidence = analysis.get("confidence", "low")
            reasoning  = analysis.get("reasoning", "")

            if deal_slug and deal_slug not in DEALS:
                print(f"  [WARN] Unknown slug '{deal_slug}' — routing to _internal")
                deal_slug = None

            company = DEALS[deal_slug]["company"] if deal_slug and deal_slug in DEALS else "unassigned"
            print(f"  Type: single_deal → {company} (confidence: {confidence})")

            out = save_single_deal(memo, transcript, deal_slug, confidence, reasoning, dry_run=False)
            print(f"  Saved: {out}")
            stats["transcribed"] += 1
            stats["single_deal"] += 1
            if deal_slug and confidence in ("high", "medium"):
                stats["deal_counts"][deal_slug] = stats["deal_counts"].get(deal_slug, 0) + 1

        elif call_type == "internal":
            deal_slugs = [d["deal_slug"] for d in analysis.get("deals", []) if d.get("deal_slug") in DEALS]
            companies  = [DEALS[s]["company"] for s in deal_slugs]
            topic      = analysis.get("topic_slug", "internal-call")
            print(f"  Type: internal | Topic: {topic} | Deals: {', '.join(companies) or 'none extracted'}")

            paths = save_internal_call(memo, transcript, analysis, dry_run=False)
            for p in paths:
                print(f"  Saved: {p}")
            stats["transcribed"] += 1
            stats["internal"] += 1
            for s in deal_slugs:
                stats["deal_counts"][s] = stats["deal_counts"].get(s, 0) + 1

        else:  # no_deal
            topic = analysis.get("topic_slug", "unknown")
            print(f"  Type: no_deal | Topic: {topic}")
            out = save_no_deal(memo, transcript, topic, dry_run=False)
            print(f"  Saved: {out}")
            stats["transcribed"] += 1
            stats["no_deal"] += 1

        print()

    # ── Summary ───────────────────────────────────────────────────────────────
    print("=" * 70)
    print("SUMMARY")
    print(f"  Transcribed:        {stats['transcribed']}")
    print(f"  Single-deal calls:  {stats['single_deal']}")
    print(f"  Internal calls:     {stats['internal']}")
    print(f"  No-deal calls:      {stats['no_deal']}")
    print(f"  Errors:             {stats['errors']}")

    if stats["deal_counts"]:
        print()
        print("  Deal transcript counts:")
        for slug, count in sorted(stats["deal_counts"].items(), key=lambda x: -x[1]):
            print(f"    {DEALS[slug]['company']}: {count}")

    print()
    print("Done.")


if __name__ == "__main__":
    main()
