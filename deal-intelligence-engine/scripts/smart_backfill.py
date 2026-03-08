"""
Smart Backfill Script — Clearwater Deal Intelligence Engine

A smarter backfill that reconstructs deal timelines accurately by:
1. Using calendar events as timeline anchors
2. Deduplicating email threads (only net-new content per reply)
3. Scoring only after real milestones (calls, client responses, docs)
4. Classifying files intelligently (voice memos, transcripts, research)
5. Sorting all content chronologically and batching by milestone

Usage:
    python3 scripts/smart_backfill.py --deal velentium                # full run
    python3 scripts/smart_backfill.py --deal velentium --dry-run      # analyze only
    python3 scripts/smart_backfill.py --deal velentium --skip-scoring # ingest only
    python3 scripts/smart_backfill.py --deal velentium --clean        # wipe + re-ingest
    python3 scripts/smart_backfill.py --deal all                      # all deals with gaps
    python3 scripts/smart_backfill.py --deal all --clean              # wipe + re-ingest all

Requirements:
    pip3 install openai psycopg2-binary qdrant-client python-dotenv requests anthropic
"""

import argparse
import email as email_module
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

from dotenv import load_dotenv

# ── Import shared functions from backfill.py ─────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from backfill import (
    DEAL_CONFIG,
    chunk_text,
    embed_texts,
    write_to_qdrant,
    write_to_postgres,
    fire_cw02,
    fetch_latest_score,
    generate_transcript_preamble,
)

# ── Load env ─────────────────────────────────────────────────────────────────
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

POSTGRES_HOST     = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT     = os.getenv("POSTGRES_PORT", "5433")
POSTGRES_DB       = os.getenv("POSTGRES_DB", "clearwater_deals")
POSTGRES_USER     = os.getenv("POSTGRES_USER", "clearwater")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")

N8N_WEBHOOK_BASE  = os.getenv("N8N_WEBHOOK_BASE", "http://localhost:5678")

BACKFILL_DIR = Path(__file__).parent.parent / "backfill"
STATE_DIR    = BACKFILL_DIR / "_state"
SCORE_WAIT_SECS = 120

# ── File classification ──────────────────────────────────────────────────────

# Pattern for "On <date> <name> wrote:" lines that start quoted blocks
ON_WROTE_RE = re.compile(
    r'^On\s+.{10,80}\s+wrote:\s*$', re.MULTILINE
)

# Pattern to strip Re:/FW:/Fwd: and trailing numbers from subjects
SUBJECT_NORMALIZE_RE = re.compile(
    r'^(?:Re|RE|Fwd|FW|Fw)[\-:]?\s*', re.IGNORECASE
)
SUBJECT_TRAILING_NUM_RE = re.compile(r'\s*\d+\s*$')


def classify_file(filepath: Path, text: str) -> dict:
    """Classify a file into a content type with metadata.

    Returns dict with keys:
        type: call_transcript | voice_memo | email_export | gemini_notes |
              eml | pdf | pptx | document
        score_worthy: bool — should CW-02 fire after this?
        priority: high | medium | low
    """
    fn = filepath.name.lower()
    suffix = filepath.suffix.lower()

    # .eml files
    if suffix == ".eml":
        return {"type": "eml", "score_worthy": False, "priority": "medium"}

    # .pdf / .pptx — high signal docs
    if suffix == ".pdf":
        return {"type": "pdf", "score_worthy": True, "priority": "high"}
    if suffix == ".pptx":
        return {"type": "pptx", "score_worthy": True, "priority": "high"}

    # Transcript files with date prefix
    if "transcript" in fn and suffix == ".txt":
        # Check for voice memo header
        if "[VOICE MEMO TRANSCRIPT]" in text[:500]:
            return {"type": "voice_memo", "score_worthy": False, "priority": "low"}
        # Regular call transcript
        return {"type": "call_transcript", "score_worthy": True, "priority": "high"}

    # Exported email text files
    if fn.startswith("emails-") and suffix == ".txt":
        return {"type": "email_export", "score_worthy": False, "priority": "medium"}

    # Gemini research exports
    if fn.startswith("gemini-") and suffix == ".txt":
        return {"type": "gemini_notes", "score_worthy": False, "priority": "low"}

    # Fallback
    return {"type": "document", "score_worthy": False, "priority": "medium"}


# ── Email thread dedup ───────────────────────────────────────────────────────

def normalize_subject(subject: str) -> str:
    """Strip Re:/FW:/Fwd: prefixes and trailing numbers to get thread root."""
    s = subject.strip()
    # Iteratively strip prefixes (handles Re: Re: FW: chains)
    changed = True
    while changed:
        new_s = SUBJECT_NORMALIZE_RE.sub('', s).strip()
        changed = new_s != s
        s = new_s
    # Strip trailing numbers (e.g., "Following up - Velentium 14" -> "Following up - Velentium")
    s = SUBJECT_TRAILING_NUM_RE.sub('', s).strip()
    return s


def extract_net_new_content(body: str) -> str:
    """Extract only the net-new content from an email body.

    Strips everything after the first:
    - "From: Name <email>" line (forwarded block)
    - "On ... wrote:" line (quoted reply header)
    - Lines starting with ">" (quoted text)
    - "-----Original Message-----" separator
    - "_" * 10+ separator lines
    """
    lines = body.splitlines()
    net_new_lines = []

    for line in lines:
        stripped = line.strip()

        # Stop at quoted reply headers
        if re.match(r'^From:\s+.+<.+@.+>', stripped):
            break
        if re.match(r'^From:\s+.+@.+', stripped):
            break
        if ON_WROTE_RE.match(stripped):
            break
        if stripped.startswith('>'):
            break
        if stripped == '-----Original Message-----':
            break
        if re.match(r'^_{10,}$', stripped):
            break
        # Outlook-style separator
        if re.match(r'^-{5,}\s*Original Message\s*-{5,}$', stripped, re.IGNORECASE):
            break

        net_new_lines.append(line)

    # Clean up trailing whitespace and signatures
    text = '\n'.join(net_new_lines).strip()
    # Remove common email signatures (sent from iPhone, etc.)
    text = re.sub(r'\n\s*Sent from my .*$', '', text, flags=re.IGNORECASE).strip()
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


def parse_eml_enhanced(path: Path) -> dict:
    """Parse a .eml file with enhanced thread dedup support.

    Returns dict with:
        text: full parsed text (with headers)
        net_new_text: only the new content (quoted replies stripped)
        date: datetime
        subject: raw subject
        normalized_subject: thread root subject
        sender: sender string
        sender_email: extracted email address
        is_client_response: bool — is this from someone outside Clearwater?
    """
    raw_bytes = path.read_bytes()
    msg = email_module.message_from_bytes(raw_bytes)

    subject = msg.get("Subject", "").strip()
    sender = msg.get("From", "").strip()
    date_str = msg.get("Date", "")

    # Parse date
    date = datetime.now() - timedelta(days=30)
    try:
        date = parsedate_to_datetime(date_str).replace(tzinfo=None)
    except Exception:
        pass

    # Extract sender email
    email_match = re.search(r'<([^>]+)>', sender)
    sender_email = email_match.group(1).lower() if email_match else sender.lower()

    # Extract To: header
    to_raw = msg.get("To", "").strip()
    to_email_match = re.search(r'<([^>]+)>', to_raw)
    to_email = to_email_match.group(1).lower() if to_email_match else to_raw.lower()
    # Extract display name from "Name <email>" format
    to_name_match = re.match(r'^"?([^"<]+)"?\s*<', to_raw)
    to_name = to_name_match.group(1).strip() if to_name_match else ""

    # Determine if client response (not from clearwater domains)
    clearwater_domains = {"clearwatersecurity.com", "clearwatercompliance.com",
                          "clearwater.com", "clearwaterai.com"}
    sender_domain = sender_email.split("@")[-1] if "@" in sender_email else ""
    is_client = sender_domain not in clearwater_domains and sender_domain != ""

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

    full_body = "\n".join(body_parts).strip()

    # Get net-new content only
    net_new = extract_net_new_content(full_body)

    # Build formatted text with headers
    header = f"Subject: {subject}\nFrom: {sender}\nDate: {date.strftime('%Y-%m-%d')}\n\n"
    full_text = header + full_body
    net_new_text = header + net_new if net_new else ""

    return {
        "text": full_text,
        "net_new_text": net_new_text,
        "net_new_body": net_new,
        "date": date,
        "subject": subject,
        "normalized_subject": normalize_subject(subject),
        "sender": sender,
        "sender_email": sender_email,
        "is_client_response": is_client,
        "to_email": to_email,
        "to_name": to_name,
    }


def group_emails_by_thread(eml_entries: list) -> list:
    """Group parsed .eml entries by normalized subject into threads.

    Returns list of thread dicts:
        thread_subject: str
        emails: list of parsed eml dicts (sorted oldest first)
        has_client_response: bool
        unique_content_count: int (emails with >= 50 chars net-new)
        skipped_count: int (emails with < 50 chars net-new)
    """
    threads = defaultdict(list)
    for entry in eml_entries:
        threads[entry["normalized_subject"]].append(entry)

    result = []
    for subj, emails in threads.items():
        # Sort by date oldest first
        emails.sort(key=lambda e: e["date"])

        unique_emails = []
        skipped = 0
        has_client = False

        for em in emails:
            if em["is_client_response"]:
                has_client = True

            net_new = em.get("net_new_body", "")
            if len(net_new.strip()) < 50:
                skipped += 1
                continue

            unique_emails.append(em)

        result.append({
            "thread_subject": subj,
            "emails": unique_emails,
            "all_emails": emails,
            "has_client_response": has_client,
            "unique_content_count": len(unique_emails),
            "skipped_count": skipped,
        })

    # Sort threads by earliest email date
    result.sort(key=lambda t: t["emails"][0]["date"] if t["emails"] else datetime.max)
    return result


# ── Outbound email extraction (Prior Outputs) ────────────────────────────────

def extract_outbound_emails(eml_entries: list, deal_config: dict) -> list:
    """Extract outbound Clearwater emails for insertion into outputs_log.

    Filters for emails where is_client_response == False (FROM a Clearwater domain),
    with >= 50 chars net-new body content.

    Returns list of dicts ready for Postgres insert into outputs_log.
    """
    outbound = []
    for entry in eml_entries:
        if entry["is_client_response"]:
            continue

        net_new = entry.get("net_new_body", "")
        if len(net_new.strip()) < 50:
            continue

        # Build a synthetic gmail_message_id for dedup
        date_str = entry["date"].strftime("%Y%m%d")
        subject_hash = abs(hash(entry["subject"])) % 100000
        synthetic_id = f"backfill_outbound_{deal_config['deal_id']}_{date_str}_{subject_hash}"

        # Classify the output_type based on recipient and content
        to_email = entry.get("to_email", "")
        to_domain = to_email.split("@")[-1] if "@" in to_email else ""
        clearwater_domains = {"clearwatersecurity.com", "clearwatercompliance.com",
                              "clearwater.com", "clearwaterai.com"}
        is_internal = to_domain in clearwater_domains

        if is_internal:
            # Determine internal type from content/subject
            subj_lower = entry["subject"].lower()
            if any(kw in subj_lower for kw in ("pre-call", "pre call", "prep", "planner", "agenda")):
                output_type = "pre_call_planner"
            else:
                output_type = "internal_team_update"
        else:
            subj_lower = entry["subject"].lower()
            if any(kw in subj_lower for kw in ("overview", "deck", "capabilities", "one-pager")):
                output_type = "overview_deck"
            else:
                output_type = "follow_up_email"

        outbound.append({
            "deal_id": deal_config["deal_id"],
            "output_type": output_type,
            "recipient_email": to_email,
            "recipient_name": entry.get("to_name", ""),
            "subject": entry["subject"],
            "content_summary": net_new[:200],
            "full_content": net_new,
            "sent_at": entry["date"],
            "triggered_by": "backfill_historical",
            "gmail_message_id": synthetic_id,
            "status": "sent",
        })

    # Sort by date
    outbound.sort(key=lambda x: x["sent_at"])
    return outbound


def insert_outbound_emails(outbound: list, deal_config: dict) -> int:
    """Insert outbound emails into outputs_log as historical Prior Outputs.

    Deduplicates by checking for existing rows with same deal_id + subject + sent_at date.
    Returns the number of rows inserted.
    """
    import psycopg2
    inserted = 0
    try:
        conn = psycopg2.connect(
            host=POSTGRES_HOST, port=int(POSTGRES_PORT),
            dbname=POSTGRES_DB, user=POSTGRES_USER, password=POSTGRES_PASSWORD
        )
        cur = conn.cursor()

        for ob in outbound:
            # Check for existing row with same deal + subject + date
            cur.execute("""
                SELECT 1 FROM outputs_log
                WHERE deal_id = %s AND subject = %s AND sent_at::date = %s::date
                LIMIT 1
            """, (ob["deal_id"], ob["subject"], ob["sent_at"]))
            if cur.fetchone():
                continue

            cur.execute("""
                INSERT INTO outputs_log
                    (deal_id, output_type, recipient_email, recipient_name,
                     subject, content_summary, full_content, sent_at,
                     triggered_by, gmail_message_id, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                ob["deal_id"], ob["output_type"], ob["recipient_email"],
                ob["recipient_name"], ob["subject"], ob["content_summary"],
                ob["full_content"], ob["sent_at"], ob["triggered_by"],
                ob["gmail_message_id"], ob["status"],
            ))
            inserted += 1

        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"  [error] Could not insert outbound emails: {e}")
    return inserted


# ── Calendar cross-reference ─────────────────────────────────────────────────

def get_calendar_events(deal_id: str) -> list:
    """Pull calendar events from Postgres for a deal."""
    import psycopg2
    try:
        conn = psycopg2.connect(
            host=POSTGRES_HOST, port=int(POSTGRES_PORT),
            dbname=POSTGRES_DB, user=POSTGRES_USER, password=POSTGRES_PASSWORD
        )
        cur = conn.cursor()
        cur.execute("""
            SELECT title, start_time, end_time, attendees
            FROM calendar_events WHERE deal_id = %s ORDER BY start_time
        """, (deal_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [{"title": r[0], "start_time": r[1], "end_time": r[2],
                 "attendees": r[3]} for r in rows]
    except Exception as e:
        print(f"  [calendar] Could not fetch events: {e}")
        return []


def match_to_calendar(content_date: datetime, calendar_events: list,
                      tolerance_days: int = 1) -> dict | None:
    """Find a calendar event matching a content date within tolerance."""
    for evt in calendar_events:
        evt_date = evt["start_time"]
        if evt_date is None:
            continue
        # Handle timezone-aware datetimes
        if hasattr(evt_date, 'tzinfo') and evt_date.tzinfo is not None:
            evt_date = evt_date.replace(tzinfo=None)
        delta = abs((content_date.date() - evt_date.date()).days)
        if delta <= tolerance_days:
            return evt
    return None


# ── Progress tracking ────────────────────────────────────────────────────────

def load_progress() -> dict:
    """Load progress state from JSON file."""
    progress_file = STATE_DIR / "smart_progress.json"
    if progress_file.exists():
        return json.loads(progress_file.read_text())
    return {"completed_deals": [], "deal_milestones": {}}


def save_progress(progress: dict):
    """Save progress state to JSON file."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    progress_file = STATE_DIR / "smart_progress.json"
    progress["last_updated"] = datetime.now().isoformat()
    progress_file.write_text(json.dumps(progress, indent=2, default=str))


# ── Milestone batching ───────────────────────────────────────────────────────

class ContentItem:
    """A single piece of content to be ingested."""
    def __init__(self, filepath: Path, text: str, date: datetime,
                 file_type: str, doc_type: str, score_worthy: bool,
                 priority: str, calendar_match: dict = None,
                 thread_subject: str = None, is_client_response: bool = False):
        self.filepath = filepath
        self.text = text
        self.date = date
        self.file_type = file_type        # internal classification
        self.doc_type = doc_type           # Qdrant doc_type
        self.score_worthy = score_worthy
        self.priority = priority
        self.calendar_match = calendar_match
        self.thread_subject = thread_subject
        self.is_client_response = is_client_response

    def __repr__(self):
        return f"<{self.file_type}: {self.filepath.name} @ {self.date.strftime('%Y-%m-%d')}>"


class Milestone:
    """A group of content items that form a scoring milestone."""
    def __init__(self, label: str, date: datetime, trigger_type: str,
                 should_score: bool = True):
        self.label = label
        self.date = date
        self.trigger_type = trigger_type   # call_transcript | client_response | document | bundle
        self.should_score = should_score
        self.items = []

    def add(self, item: ContentItem):
        self.items.append(item)

    @property
    def chunk_estimate(self) -> int:
        """Rough estimate of total chunks."""
        total_words = sum(len(item.text.split()) for item in self.items)
        return max(1, total_words // 350)

    def __repr__(self):
        return f"<Milestone: {self.label} ({len(self.items)} items, score={self.should_score})>"


def build_milestones(items: list, calendar_events: list) -> list:
    """Organize content items into milestone groups.

    Rules:
    - Each call transcript = its own milestone (score after)
    - Email threads grouped by week; score only if client response
    - PDFs/PPTXs = own milestone (score after)
    - Voice memos, gemini, forwarded-only emails = bundle with next milestone
    - Low-signal items between milestones accumulate
    """
    if not items:
        return []

    # Sort by date
    items.sort(key=lambda x: x.date)

    milestones = []
    pending_low_signal = []  # accumulate between milestones

    # First pass: identify natural milestones
    i = 0
    while i < len(items):
        item = items[i]

        if item.file_type == "call_transcript":
            # Call transcript = standalone milestone
            cal_match = item.calendar_match
            label_suffix = ""
            if cal_match:
                title = cal_match.get("title", "Unknown Meeting")
                label_suffix = f" ({title} -- calendar match)"

            m = Milestone(
                label=f"{item.date.strftime('%b %d, %Y')} — Call Transcript{label_suffix}",
                date=item.date,
                trigger_type="call_transcript",
                should_score=True,
            )
            # Attach any pending low-signal items
            for ls in pending_low_signal:
                m.add(ls)
            pending_low_signal = []
            m.add(item)
            milestones.append(m)
            i += 1

        elif item.file_type in ("pdf", "pptx"):
            # Document = standalone milestone
            m = Milestone(
                label=f"{item.date.strftime('%b %d, %Y')} — Document ({item.filepath.name})",
                date=item.date,
                trigger_type="document",
                should_score=True,
            )
            for ls in pending_low_signal:
                m.add(ls)
            pending_low_signal = []
            m.add(item)
            milestones.append(m)
            i += 1

        elif item.file_type == "eml":
            # Collect all emails in the same week
            week_start = item.date - timedelta(days=item.date.weekday())
            week_end = week_start + timedelta(days=7)
            week_emails = []
            has_client = False

            while i < len(items) and items[i].file_type == "eml" and items[i].date < week_end:
                week_emails.append(items[i])
                if items[i].is_client_response:
                    has_client = True
                i += 1

            # Group into a milestone
            if week_emails:
                earliest = min(e.date for e in week_emails)
                latest = max(e.date for e in week_emails)
                date_range = earliest.strftime('%b %d')
                if earliest.date() != latest.date():
                    date_range += f" - {latest.strftime('%b %d, %Y')}"
                else:
                    date_range += f", {earliest.strftime('%Y')}"

                m = Milestone(
                    label=f"{date_range} — Email Exchanges",
                    date=earliest,
                    trigger_type="client_response" if has_client else "bundle",
                    should_score=has_client,
                )
                for ls in pending_low_signal:
                    m.add(ls)
                pending_low_signal = []
                for we in week_emails:
                    m.add(we)
                milestones.append(m)

        elif item.file_type in ("voice_memo", "gemini_notes", "email_export"):
            # Low-signal — accumulate for next milestone
            pending_low_signal.append(item)
            i += 1

        else:
            # Unknown — treat as low signal
            pending_low_signal.append(item)
            i += 1

    # If there are leftover low-signal items with no following milestone,
    # attach them to the last milestone or create a bundle
    if pending_low_signal:
        if milestones:
            for ls in pending_low_signal:
                milestones[-1].add(ls)
        else:
            # All content is low-signal — create one bundle milestone
            earliest = min(ls.date for ls in pending_low_signal)
            m = Milestone(
                label=f"{earliest.strftime('%b %d, %Y')} — Initial Content",
                date=earliest,
                trigger_type="bundle",
                should_score=True,  # Score first content regardless
            )
            for ls in pending_low_signal:
                m.add(ls)
            milestones.append(m)

    # ── Post-processing: merge consecutive same-day milestones ────────────
    # When a call transcript and emails (or other content) fall on the same day,
    # merge them into a single milestone to avoid wasteful duplicate scoring.
    # The call_transcript label wins; should_score is True if either had it.
    if len(milestones) > 1:
        merged = [milestones[0]]
        for m in milestones[1:]:
            prev = merged[-1]
            if prev.date.date() == m.date.date():
                # Merge m into prev — pick the call_transcript label if either has one
                if m.trigger_type == "call_transcript" and prev.trigger_type != "call_transcript":
                    prev.label = m.label
                    prev.trigger_type = m.trigger_type
                # Preserve scoring if either milestone warranted it
                if m.should_score:
                    prev.should_score = True
                # Move all items from m into prev
                for item in m.items:
                    prev.add(item)
            else:
                merged.append(m)
        milestones = merged

    # Special case: first milestone should always score (first content for deal)
    if milestones and not milestones[0].should_score:
        milestones[0].should_score = True

    return milestones


# ── Dry run display ──────────────────────────────────────────────────────────

TYPE_ICONS = {
    "call_transcript": ">>",
    "voice_memo": "//",
    "eml": "@@",
    "email_export": "@@",
    "pdf": "[]",
    "pptx": "[]",
    "gemini_notes": "~~",
    "document": "..",
}


def format_filesize(path: Path) -> str:
    """Human-readable file size."""
    try:
        size = path.stat().st_size
        if size < 1024:
            return f"{size}B"
        elif size < 1024 * 1024:
            return f"{size/1024:.1f}KB"
        else:
            return f"{size/(1024*1024):.1f}MB"
    except Exception:
        return "??"


def print_dry_run(deal_config: dict, milestones: list, calendar_events: list,
                  thread_info: list, total_skipped: int, outbound_emails: list = None):
    """Print the dry-run analysis plan."""
    company = deal_config["company_name"]
    deal_id = deal_config["deal_id"]

    print(f"\nSMART BACKFILL PLAN -- {company}")
    print("=" * 60)

    # Calendar events
    if calendar_events:
        print(f"\nCalendar Events:")
        for evt in calendar_events:
            start = evt["start_time"]
            if hasattr(start, 'strftime'):
                date_str = start.strftime('%b %d')
            else:
                date_str = str(start)
            attendees = evt.get("attendees", "") or ""
            if isinstance(attendees, str) and len(attendees) > 60:
                attendees = attendees[:60] + "..."
            print(f"  {date_str:8s} {evt['title'] or 'Untitled'}")
            if attendees:
                print(f"           Attendees: {attendees}")
    else:
        print(f"\nCalendar Events: None found in Postgres")

    # Timeline
    print(f"\nTimeline Reconstruction:")
    total_chunks = 0
    score_count = 0

    for idx, milestone in enumerate(milestones, 1):
        print(f"\n  Milestone {idx} -- {milestone.label}")

        for item in milestone.items:
            icon = TYPE_ICONS.get(item.file_type, "..")
            size = format_filesize(item.filepath)
            name = item.filepath.name
            if len(name) > 55:
                name = name[:52] + "..."

            extra = ""
            if item.calendar_match:
                title = item.calendar_match.get("title", "")
                extra = f" <- calendar: {title}"
            if item.thread_subject:
                extra = f" (thread: {item.thread_subject[:40]})"
            if item.file_type == "voice_memo":
                extra += " [bundled, no scoring]"
            if item.file_type == "gemini_notes":
                extra += " [research notes, no scoring]"

            print(f"    {icon} {name:55s} ({item.file_type}, {size}){extra}")

        total_chunks += milestone.chunk_estimate
        score_label = "YES" if milestone.should_score else "NO"
        if milestone.should_score:
            score_count += 1
            reason = milestone.trigger_type
            if reason == "call_transcript":
                reason = "call transcript"
            elif reason == "client_response":
                reason = "client response in thread"
            elif reason == "document":
                reason = "document/presentation"
            elif reason == "bundle":
                reason = "first content"
            print(f"    -> Score after: {score_label} ({reason})")
        else:
            print(f"    -> Score after: {score_label}")

    # Thread info
    if thread_info:
        print(f"\n  Email Thread Summary:")
        for t in thread_info:
            total_in_thread = t["unique_content_count"] + t["skipped_count"]
            print(f"    \"{t['thread_subject'][:50]}\" "
                  f"({total_in_thread} replies -> {t['unique_content_count']} with unique content)")

    # Skipped
    if total_skipped > 0:
        print(f"\n  Skipped:")
        print(f"    x {total_skipped} .eml files with <50 chars new content (quoted replies only)")

    # Outbound emails (Prior Outputs)
    if outbound_emails:
        print(f"\n  Outbound Emails (-> outputs_log as Prior Outputs): {len(outbound_emails)}")
        for ob in outbound_emails:
            date_str = ob["sent_at"].strftime("%b %d")
            to = ob["recipient_email"][:40] if ob["recipient_email"] else "unknown"
            subj = ob["subject"][:50] if ob["subject"] else "(no subject)"
            print(f"    {date_str:8s} -> {to:40s} \"{subj}\"")

    # Summary
    api_calls = total_chunks  # embedding calls (batched by 100)
    api_batches = max(1, total_chunks // 100) + (1 if total_chunks % 100 else 0)
    outbound_count = len(outbound_emails) if outbound_emails else 0
    print(f"\n  Summary: {len(milestones)} milestones, ~{total_chunks} chunks, "
          f"~{api_batches} embedding API calls, {score_count} scoring triggers"
          + (f", {outbound_count} outbound emails" if outbound_count else ""))
    if score_count > 0:
        print(f"  Estimated time: ~{score_count * 2.5:.0f} min "
              f"(scoring wait: {score_count} x {SCORE_WAIT_SECS}s)")
    print()


# ── Ingestion engine ─────────────────────────────────────────────────────────

def ingest_milestone(deal_config: dict, milestone: Milestone,
                     milestone_idx: int, total_milestones: int,
                     calendar_events: list, skip_scoring: bool = False) -> dict | None:
    """Ingest all content items in a milestone, optionally score after.

    Returns score dict if scored, else None.
    """
    print(f"\n{'─'*60}")
    print(f"Milestone {milestone_idx}/{total_milestones}: {milestone.label}")
    print(f"{'─'*60}")

    all_chunks = []

    for item in milestone.items:
        # Generate preamble for call transcripts
        preamble = ""
        if item.file_type == "call_transcript":
            print(f"  Generating preamble for {item.filepath.name}...")
            preamble = generate_transcript_preamble(
                item.text,
                deal_config["company_name"],
                item.date.strftime("%Y-%m-%d"),
            )
            if preamble:
                print(f"  Preamble: {preamble[:120]}...")

        # Build context header
        cal_info = ""
        if item.calendar_match:
            title = item.calendar_match.get("title", "")
            attendees = item.calendar_match.get("attendees", "") or ""
            cal_info = f"Meeting: {title}"
            if attendees:
                cal_info += f" with {attendees}"
            cal_info += "\n"

        # Map file_type to Qdrant doc_type
        doc_type_map = {
            "call_transcript": "call_transcript",
            "voice_memo": "voice_memo",
            "eml": "email_thread",
            "email_export": "email_thread",
            "pdf": "pdf",
            "pptx": "presentation",
            "gemini_notes": "gemini_chat",
            "document": "document",
        }
        qdrant_doc_type = doc_type_map.get(item.file_type, "document")

        is_internal_note = (item.file_type == "voice_memo"
                            and "Call Type: internal excerpt" in item.text[:500])
        context_header = (
            f"[DEAL CONTEXT]\n"
            f"Deal: {deal_config['company_name']} (ID: {deal_config['deal_id']})\n"
            f"Document Type: {qdrant_doc_type}\n"
            + (f"Note: INTERNAL — Austin's personal notes/voice memo about this deal\n"
               if is_internal_note else "")
            + f"Date: {item.date.strftime('%Y-%m-%d')}\n"
            f"Source File: {item.filepath.name}\n"
            + (f"{cal_info}" if cal_info else "")
            + (f"Summary: {preamble}\n" if preamble else "")
            + f"[END CONTEXT]\n\n"
            + (f"[CALL SUMMARY]\n{preamble}\n[END SUMMARY]\n\n" if preamble else "")
        )

        full_text = context_header + item.text
        chunks = chunk_text(full_text)

        for ci, chunk in enumerate(chunks):
            all_chunks.append({
                "text": chunk,
                "date": item.date,
                "doc_type": qdrant_doc_type,
                "filename": item.filepath.name,
                "chunk_index": ci,
            })

        print(f"  {item.filepath.name[:50]:50s} -> {len(chunks)} chunks")

    if not all_chunks:
        print("  No chunks to ingest (all items skipped)")
        return None

    print(f"  Total chunks: {len(all_chunks)}")

    # Embed
    print(f"  Embedding...")
    texts = [c["text"] for c in all_chunks]
    embeddings = []
    for i in range(0, len(texts), 100):
        batch_texts = texts[i:i+100]
        embeddings.extend(embed_texts(batch_texts))
        if i + 100 < len(texts):
            time.sleep(0.3)

    for i, emb in enumerate(embeddings):
        all_chunks[i]["embedding"] = emb

    # Write to Qdrant
    print(f"  Writing to Qdrant...")
    n = write_to_qdrant(deal_config, all_chunks)
    print(f"  -> {n} vectors written")

    # Write to Postgres
    print(f"  Writing to Postgres ingestion_log...")
    write_to_postgres(deal_config, all_chunks)
    print(f"  -> ingestion_log updated")

    # Backdate ingestion_log entries to milestone date
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=POSTGRES_HOST, port=int(POSTGRES_PORT),
            dbname=POSTGRES_DB, user=POSTGRES_USER, password=POSTGRES_PASSWORD
        )
        cur = conn.cursor()
        # Update ingested_at for all chunks just inserted for this milestone
        # They share the same deal_id and subject matches the filename
        for item in milestone.items:
            cur.execute("""
                UPDATE ingestion_log SET ingested_at = %s
                WHERE deal_id = %s AND subject = %s
            """, (milestone.date, deal_config["deal_id"], item.filepath.name))
        conn.commit()
        backdated_count = sum(1 for _ in milestone.items)
        print(f"  Backdated {backdated_count} ingestion_log entries to {milestone.date.strftime('%Y-%m-%d')}")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"  [warn] Could not backdate ingestion_log: {e}")

    # Score
    if milestone.should_score and not skip_scoring:
        print(f"  Firing CW-02 health scoring...")
        fire_cw02(deal_config["deal_id"], milestone.label)

        print(f"  Waiting {SCORE_WAIT_SECS}s for CW-02...", end="", flush=True)
        for _ in range(SCORE_WAIT_SECS // 10):
            time.sleep(10)
            print(".", end="", flush=True)
        print()

        row = fetch_latest_score(deal_config["deal_id"])
        if row:
            total, pain, power, vision, value, change, control, cas, scored_at = row
            print(f"\n  Score: {total}/30  CAS: {cas}")
            print(f"  P={pain} Po={power} V={vision} Va={value} Ch={change} Co={control}")

            # Backdate the scored_at to the milestone date
            milestone_date = milestone.date
            try:
                import psycopg2
                conn = psycopg2.connect(
                    host=POSTGRES_HOST, port=int(POSTGRES_PORT),
                    dbname=POSTGRES_DB, user=POSTGRES_USER, password=POSTGRES_PASSWORD
                )
                cur = conn.cursor()
                cur.execute("""
                    UPDATE deal_health SET scored_at = %s
                    WHERE deal_id = %s AND scored_at = (
                        SELECT MAX(scored_at) FROM deal_health WHERE deal_id = %s
                    )
                """, (milestone_date, deal_config["deal_id"], deal_config["deal_id"]))
                conn.commit()
                cur.close()
                conn.close()
                print(f"  Backdated score to {milestone_date.strftime('%Y-%m-%d')}")
            except Exception as e:
                print(f"  [!] Failed to backdate score: {e}")

            return {
                "milestone": milestone.label,
                "total": total, "cas": cas,
                "pain": pain, "power": power, "vision": vision,
                "value": value, "change": change, "control": control,
            }
        else:
            print(f"  [!] No score found yet (CW-02 may still be running)")
    elif skip_scoring:
        print(f"  Scoring skipped (--skip-scoring)")
    else:
        print(f"  No scoring trigger for this milestone")

    return None


# ── Clean existing data for a deal ───────────────────────────────────────────

def clean_deal_data(deal_name: str, deal_config: dict):
    """Delete all existing backfill-related data for a deal so it can be re-ingested cleanly.

    Preserves: deals row, calendar_events, outputs_log.
    Deletes: Qdrant points, ingestion_log, deal_health, stakeholders, deal_notifications.
    Clears: smart_progress for this deal.
    """
    deal_id = deal_config["deal_id"]
    print(f"\nCLEANING existing data for {deal_config['company_name']} ({deal_id})...")

    # ── a) Delete Qdrant points ──────────────────────────────────────────────
    try:
        # Count points before deleting
        count_resp = requests.post("http://localhost:6333/collections/deals/points/count", json={
            "filter": {
                "must": [{"key": "deal_id", "match": {"value": deal_id}}]
            },
            "exact": True
        })
        qdrant_count = 0
        if count_resp.ok:
            qdrant_count = count_resp.json().get("result", {}).get("count", 0)

        resp = requests.post("http://localhost:6333/collections/deals/points/delete", json={
            "filter": {
                "must": [{"key": "deal_id", "match": {"value": deal_id}}]
            }
        })
        resp.raise_for_status()
        print(f"  Qdrant: deleted {qdrant_count} points")
    except Exception as e:
        print(f"  Qdrant: error deleting points: {e}")

    # ── b) Delete Postgres rows ──────────────────────────────────────────────
    import psycopg2
    try:
        conn = psycopg2.connect(
            host=POSTGRES_HOST, port=int(POSTGRES_PORT),
            dbname=POSTGRES_DB, user=POSTGRES_USER, password=POSTGRES_PASSWORD
        )
        cur = conn.cursor()

        cur.execute("DELETE FROM ingestion_log WHERE deal_id = %s", (deal_id,))
        ingestion_count = cur.rowcount
        cur.execute("DELETE FROM deal_health WHERE deal_id = %s", (deal_id,))
        health_count = cur.rowcount
        cur.execute("DELETE FROM deal_stakeholders WHERE deal_id = %s", (deal_id,))
        stakeholder_count = cur.rowcount
        cur.execute("DELETE FROM deal_notifications WHERE deal_id = %s", (deal_id,))
        notification_count = cur.rowcount
        cur.execute("DELETE FROM outputs_log WHERE deal_id = %s AND status = 'draft'", (deal_id,))
        draft_count = cur.rowcount

        conn.commit()
        cur.close()
        conn.close()

        print(f"  ingestion_log: deleted {ingestion_count} rows")
        print(f"  deal_health: deleted {health_count} rows")
        print(f"  stakeholders: deleted {stakeholder_count} rows")
        print(f"  deal_notifications: deleted {notification_count} rows")
        print(f"  draft outputs: deleted {draft_count} rows")
    except Exception as e:
        print(f"  Postgres: error deleting rows: {e}")

    # ── c) Clear smart_progress for this deal ────────────────────────────────
    progress = load_progress()
    changed = False
    if deal_name in progress.get("deal_milestones", {}):
        del progress["deal_milestones"][deal_name]
        changed = True
    if deal_name in progress.get("completed_deals", []):
        progress["completed_deals"].remove(deal_name)
        changed = True
    if changed:
        save_progress(progress)
    print(f"  smart_progress: cleared")
    print()


# ── Main processing per deal ─────────────────────────────────────────────────

def process_deal(deal_name: str, dry_run: bool = False,
                 skip_scoring: bool = False, resume: bool = True,
                 clean: bool = False) -> bool:
    """Process a single deal. Returns True on success."""

    if deal_name not in DEAL_CONFIG:
        print(f"Unknown deal '{deal_name}'. Available: {sorted(DEAL_CONFIG.keys())}")
        return False

    deal_config = DEAL_CONFIG[deal_name]
    deal_dir = BACKFILL_DIR / deal_name

    # Run clean before anything else if requested (but NOT during dry-run)
    if clean and not dry_run:
        clean_deal_data(deal_name, deal_config)
    elif clean and dry_run:
        print(f"  [dry-run] --clean flag set but skipped (dry-run mode)")

    if not deal_dir.exists():
        print(f"No backfill directory: {deal_dir}")
        return False

    files = sorted([f for f in deal_dir.iterdir()
                    if f.is_file()
                    and f.suffix.lower() in {".txt", ".pdf", ".pptx", ".csv", ".eml"}
                    and not f.name.startswith(".")])

    if not files:
        print(f"No files in {deal_dir}")
        return False

    # Check resume state
    progress = load_progress()
    completed_milestones = set()
    if resume and deal_name in progress.get("deal_milestones", {}):
        completed_milestones = set(progress["deal_milestones"][deal_name])
        if completed_milestones:
            print(f"  Resuming: {len(completed_milestones)} milestones already completed")

    print(f"\n{'='*60}")
    print(f"SMART BACKFILL: {deal_config['company_name']}")
    print(f"Deal ID: {deal_config['deal_id']}")
    print(f"Files: {len(files)}")
    print(f"{'='*60}")

    # ── Step 1: Pull calendar events ─────────────────────────────────────────
    calendar_events = get_calendar_events(deal_config["deal_id"])
    if calendar_events:
        print(f"\nCalendar events found: {len(calendar_events)}")
    else:
        print(f"\nNo calendar events in Postgres for this deal")

    # ── Step 2: Parse all files ──────────────────────────────────────────────
    print(f"\nParsing files...")

    eml_entries = []
    non_eml_items = []
    total_skipped_eml = 0

    for f in files:
        classification = classify_file(f, "")

        if f.suffix.lower() == ".eml":
            parsed = parse_eml_enhanced(f)
            eml_entries.append({**parsed, "filepath": f, "classification": classification})
            print(f"  {f.name[:50]:50s} -> eml ({parsed['normalized_subject'][:30]})")
        else:
            text = f.read_text(encoding="utf-8", errors="ignore")
            text = text.replace('\u2028', '\n').replace('\u2029', '\n')

            # Re-classify with actual content
            classification = classify_file(f, text)

            # Internal excerpts = Austin's voice memos/notes about the deal
            # Classify as voice_memo and bundle with nearest milestone (no scoring)
            if "Call Type: internal excerpt" in text[:500]:
                classification = {"type": "voice_memo", "score_worthy": False, "priority": "low"}

            # Extract date
            from backfill import extract_date
            date = extract_date(text, f.name)

            # Check for voice memo date override
            if classification["type"] == "voice_memo":
                date_match = re.search(r'^Date:\s*(\d{4}-\d{2}-\d{2})', text[:500], re.MULTILINE)
                if date_match:
                    try:
                        date = datetime.strptime(date_match.group(1), "%Y-%m-%d")
                    except ValueError:
                        pass

            # Calendar cross-reference
            cal_match = match_to_calendar(date, calendar_events)

            # For call transcripts, snap date to the calendar event date
            # (the transcript happened ON the call, not whenever the file was created)
            has_date_in_name = bool(re.search(r'\d{4}-\d{2}-\d{2}', f.name))
            if classification["type"] == "call_transcript" and cal_match:
                evt_date = cal_match["start_time"]
                if hasattr(evt_date, 'tzinfo') and evt_date.tzinfo:
                    evt_date = evt_date.replace(tzinfo=None)
                date = evt_date.replace(hour=0, minute=0, second=0, microsecond=0)

            # For call transcripts without a date in filename and no calendar match,
            # try harder by checking content for attendee names
            if classification["type"] == "call_transcript" and not has_date_in_name and not cal_match:
                # Try matching to each calendar event — pick the one where
                # attendee names appear most in the transcript text
                best_match = None
                best_score = 0
                text_lower = text[:5000].lower()
                for evt in calendar_events:
                    attendees = evt.get("attendees") or []
                    score = 0
                    for att in attendees:
                        att_str = att if isinstance(att, str) else str(att)
                        # Extract first names from email addresses
                        for email_addr in re.findall(r'[\w.]+@[\w.]+', att_str):
                            first = email_addr.split('@')[0].split('.')[0].lower()
                            if len(first) > 2 and first in text_lower:
                                score += 1
                    if score > best_score:
                        best_score = score
                        best_match = evt
                if best_match and best_score >= 2:
                    evt_date = best_match["start_time"]
                    if hasattr(evt_date, 'tzinfo') and evt_date.tzinfo:
                        evt_date = evt_date.replace(tzinfo=None)
                    date = evt_date.replace(hour=0, minute=0, second=0, microsecond=0)
                    cal_match = best_match

            item = ContentItem(
                filepath=f,
                text=text,
                date=date,
                file_type=classification["type"],
                doc_type=classification["type"],
                score_worthy=classification["score_worthy"],
                priority=classification["priority"],
                calendar_match=cal_match,
            )
            non_eml_items.append(item)
            cal_note = f" <- calendar: {cal_match['title']}" if cal_match else ""
            print(f"  {f.name[:50]:50s} -> {classification['type']:18s} "
                  f"| {date.strftime('%Y-%m-%d')}{cal_note}")

    # ── Step 3: Thread-dedup emails ──────────────────────────────────────────
    threads = group_emails_by_thread(eml_entries)

    eml_items = []
    for thread in threads:
        for em in thread["emails"]:
            cal_match = match_to_calendar(em["date"], calendar_events)
            item = ContentItem(
                filepath=em["filepath"],
                text=em["net_new_text"],
                date=em["date"],
                file_type="eml",
                doc_type="email_thread",
                score_worthy=False,  # determined at milestone level
                priority="medium",
                calendar_match=cal_match,
                thread_subject=thread["thread_subject"],
                is_client_response=em["is_client_response"],
            )
            eml_items.append(item)
        total_skipped_eml += thread["skipped_count"]

    if eml_entries:
        total_eml = len(eml_entries)
        kept = len(eml_items)
        print(f"\n  Email dedup: {total_eml} .eml files -> {kept} with unique content, "
              f"{total_skipped_eml} skipped (<50 chars)")

    # ── Step 4: Combine and build milestones ─────────────────────────────────
    all_items = non_eml_items + eml_items
    milestones = build_milestones(all_items, calendar_events)

    # Thread info for dry run display
    thread_info = [t for t in threads if t["unique_content_count"] > 0 or t["skipped_count"] > 0]

    # ── Step 4b: Extract outbound emails for Prior Outputs ──────────────────
    outbound = extract_outbound_emails(eml_entries, deal_config)
    if outbound:
        print(f"\n  Outbound emails found: {len(outbound)} (will insert to outputs_log)")

    # ── Dry run ──────────────────────────────────────────────────────────────
    if dry_run:
        print_dry_run(deal_config, milestones, calendar_events,
                      thread_info, total_skipped_eml, outbound_emails=outbound)
        return True

    # ── Step 5: Ingest milestones ────────────────────────────────────────────
    print(f"\nMilestones to process: {len(milestones)}")
    score_history = []

    for idx, milestone in enumerate(milestones, 1):
        # Check if already completed (resume support)
        if milestone.label in completed_milestones:
            print(f"\n  [resume] Skipping completed milestone: {milestone.label}")
            continue

        result = ingest_milestone(
            deal_config, milestone, idx, len(milestones),
            calendar_events, skip_scoring=skip_scoring,
        )
        if result:
            score_history.append(result)

        # Save progress after each milestone
        if deal_name not in progress.get("deal_milestones", {}):
            progress.setdefault("deal_milestones", {})[deal_name] = []
        progress["deal_milestones"][deal_name].append(milestone.label)
        save_progress(progress)

    # ── Summary ──────────────────────────────────────────────────────────────
    if score_history:
        print(f"\n{'='*60}")
        print(f"SCORE HISTORY -- {deal_config['company_name']}")
        print(f"{'='*60}")
        for s in score_history:
            print(f"  {s['milestone']:50s} -> {s['total']:2d}/30  CAS: {s['cas']}")
        print()

    # ── Step 6: Extract outbound emails as Prior Outputs ─────────────────
    if outbound:
        print(f"\nExtracting {len(outbound)} outbound emails as Prior Outputs...")
        inserted = insert_outbound_emails(outbound, deal_config)
        print(f"  -> {inserted} outbound emails written to outputs_log")

    # Mark deal complete
    if deal_name not in progress.get("completed_deals", []):
        progress.setdefault("completed_deals", []).append(deal_name)
    save_progress(progress)

    print(f"Done: {deal_config['company_name']}")
    return True


# ── CLI ──────────────────────────────────────────────────────────────────────

def find_deals_with_gaps() -> list:
    """Find deals that have backfill directories but haven't been smart-backfilled."""
    progress = load_progress()
    completed = set(progress.get("completed_deals", []))

    available = []
    for name in sorted(DEAL_CONFIG.keys()):
        deal_dir = BACKFILL_DIR / name
        if deal_dir.exists() and name not in completed:
            files = [f for f in deal_dir.iterdir()
                     if f.is_file() and f.suffix.lower() in {".txt", ".pdf", ".pptx", ".csv", ".eml"}
                     and not f.name.startswith(".")]
            if files:
                available.append(name)
    return available


def main():
    parser = argparse.ArgumentParser(
        description="Smart backfill with timeline reconstruction and email dedup"
    )
    parser.add_argument("--deal", required=True,
                        help="Deal folder name (e.g. 'velentium') or 'all'")
    parser.add_argument("--dry-run", action="store_true",
                        help="Analyze and show plan without writing anything")
    parser.add_argument("--skip-scoring", action="store_true",
                        help="Ingest content but don't trigger CW-02 scoring")
    parser.add_argument("--no-resume", action="store_true",
                        help="Start fresh, ignore previous progress")
    parser.add_argument("--reset-progress", action="store_true",
                        help="Clear all progress tracking and exit")
    parser.add_argument("--clean", action="store_true",
                        help="Wipe existing data (Qdrant, ingestion_log, deal_health, "
                             "stakeholders, deal_notifications) before backfilling")
    args = parser.parse_args()

    if args.reset_progress:
        progress_file = STATE_DIR / "smart_progress.json"
        if progress_file.exists():
            progress_file.unlink()
            print("Progress reset.")
        else:
            print("No progress file found.")
        return

    if args.deal.lower() == "all":
        deals = find_deals_with_gaps()
        if not deals:
            print("All deals with backfill directories have been processed.")
            print("Use --reset-progress to start over, or --no-resume to reprocess.")
            if args.no_resume:
                deals = sorted([n for n in DEAL_CONFIG.keys()
                               if (BACKFILL_DIR / n).exists()])
        if not deals:
            return

        print(f"\nDeals to process: {len(deals)}")
        for d in deals:
            print(f"  - {d}")
        print()

        for deal_name in deals:
            try:
                process_deal(deal_name, dry_run=args.dry_run,
                           skip_scoring=args.skip_scoring,
                           resume=not args.no_resume,
                           clean=args.clean)
            except Exception as e:
                print(f"\n[ERROR] {deal_name}: {e}")
                import traceback
                traceback.print_exc()
                continue
    else:
        deal_name = args.deal.lower()
        if deal_name not in DEAL_CONFIG:
            # Try partial match
            matches = [k for k in DEAL_CONFIG.keys() if deal_name in k]
            if len(matches) == 1:
                deal_name = matches[0]
                print(f"Matched: {deal_name}")
            elif len(matches) > 1:
                print(f"Ambiguous deal '{args.deal}'. Matches: {matches}")
                sys.exit(1)
            else:
                print(f"Unknown deal '{args.deal}'.")
                print(f"Available: {sorted(DEAL_CONFIG.keys())}")
                sys.exit(1)

        success = process_deal(deal_name, dry_run=args.dry_run,
                              skip_scoring=args.skip_scoring,
                              resume=not args.no_resume,
                              clean=args.clean)
        if not success:
            sys.exit(1)


if __name__ == "__main__":
    main()
