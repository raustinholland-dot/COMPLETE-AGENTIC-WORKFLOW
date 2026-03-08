"""
Calendar Import Script — Clearwater Deal Intelligence Engine

Parses calendar_events.csv (Outlook export) and inserts external meetings
into the Postgres calendar_events table, matched to deals by attendee domain.

Usage:
    python3 scripts/import_calendar.py                    # full import
    python3 scripts/import_calendar.py --dry-run          # show matches, don't insert
    python3 scripts/import_calendar.py --deal velentium   # only import for one deal

Requirements:
    pip3 install psycopg2-binary python-dotenv
"""

import argparse
import csv
import hashlib
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

# ── Load env ─────────────────────────────────────────────────────────────────
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

POSTGRES_HOST     = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT     = os.getenv("POSTGRES_PORT", "5433")
POSTGRES_DB       = os.getenv("POSTGRES_DB", "clearwater_deals")
POSTGRES_USER     = os.getenv("POSTGRES_USER", "clearwater")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")

CSV_PATH = Path(__file__).parent.parent.parent / "calendar_events.csv"

# Domains to ignore when matching attendees to deals
NOISE_DOMAINS = {
    "clearwatersecurity.com",
    "clearwatercompliance.com",
    "clearwatercompliance.llc",
    "clearwatercompliancellc.onmicrosoft.com",
    "redspin.com",
    "zoom.us",
    "microsoft.com",
    "gmail.com",
    "outlook.com",
    "hotmail.com",
    "yahoo.com",
    "salesforce.com",
    "paylocity.com",
    "teams.microsoft.com",
}


def get_pg_connection():
    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
    )


def build_domain_lookup(conn):
    """Build a domain -> deal_id map from the deals table."""
    cur = conn.cursor()
    cur.execute(
        "SELECT deal_id, company_name, sender_domains FROM deals WHERE status != 'archived'"
    )
    rows = cur.fetchall()
    cur.close()

    domain_map = {}      # domain -> deal_id
    company_map = {}     # deal_id -> company_name
    name_to_deal = {}    # lowercase company_name -> deal_id

    for deal_id, company_name, sender_domains in rows:
        company_map[deal_id] = company_name
        if company_name:
            name_to_deal[company_name.lower()] = deal_id
        if sender_domains:
            for domain in sender_domains:
                domain_map[domain.lower().strip()] = deal_id

    return domain_map, company_map, name_to_deal


def extract_email(attendee_str):
    """Extract email from 'Name <email>' or bare email format."""
    m = re.search(r'<([^>]+)>', attendee_str)
    if m:
        return m.group(1).lower().strip()
    # Bare email
    cleaned = attendee_str.strip().lower()
    if "@" in cleaned:
        return cleaned
    return None


def extract_domain(email_addr):
    """Get domain from an email address."""
    if not email_addr or "@" not in email_addr:
        return None
    return email_addr.split("@", 1)[1].lower().strip()


def parse_attendees(attendees_str):
    """Parse pipe-delimited attendee string into list of emails."""
    if not attendees_str or not attendees_str.strip():
        return []
    parts = attendees_str.split("|")
    emails = []
    for part in parts:
        email = extract_email(part.strip())
        if email:
            emails.append(email)
    return emails


def fuzzy_match_subject(subject, name_to_deal):
    """Try to match subject line against deal company names.

    Strict matching rules:
    - Company name words must appear as whole words (word boundaries) in the subject
    - Skip words shorter than 5 characters to avoid false positives
    - Single-word company names must match exactly as a whole word
    - Multi-word names require >= 75% of significant words to match
    """
    subj_lower = subject.lower()
    best_match = None
    best_len = 0
    for company_name, deal_id in name_to_deal.items():
        # Extract significant words (>= 5 chars) from company name
        words = [w for w in company_name.split() if len(w) >= 5]

        if not words:
            # Company name has no words >= 5 chars (e.g. "RISE", "Popl")
            # Require the full company name to appear as a whole word
            if len(company_name) < 3:
                continue
            pattern = r'\b' + re.escape(company_name) + r'\b'
            if re.search(pattern, subj_lower, re.IGNORECASE):
                if len(company_name) > best_len:
                    best_len = len(company_name)
                    best_match = deal_id
            continue

        # Check each significant word as a whole-word match (word boundaries)
        matches = 0
        for w in words:
            pattern = r'\b' + re.escape(w) + r'\b'
            if re.search(pattern, subj_lower, re.IGNORECASE):
                matches += 1

        # Require >= 75% of significant words to match (stricter than 50%)
        if matches > 0 and matches >= len(words) * 0.75:
            if len(company_name) > best_len:
                best_len = len(company_name)
                best_match = deal_id
    return best_match


def generate_event_id(subject, start):
    """Deterministic event ID from subject + start time."""
    raw = f"{subject}{start}"
    return f"cal_import_{hashlib.md5(raw.encode()).hexdigest()}"


def classify_meeting_type(subject):
    """Infer meeting type from subject line."""
    subj = subject.lower()
    if any(w in subj for w in ["discovery", "discover", "overview", "introduction", "intro"]):
        return "discovery"
    if any(w in subj for w in ["qualify", "qualification"]):
        return "qualify"
    if any(w in subj for w in ["prove", "demo", "presentation", "approach"]):
        return "prove"
    if any(w in subj for w in ["debrief", "review", "sync", "check-in", "check in"]):
        return "debrief"
    if any(w in subj for w in ["kickoff", "kick-off", "kick off", "onboarding"]):
        return "kickoff"
    if any(w in subj for w in ["negotiate", "contract", "msa", "sow", "pricing"]):
        return "negotiate"
    return "other"


def get_existing_event_ids(conn):
    """Fetch all google_event_ids already in calendar_events."""
    cur = conn.cursor()
    cur.execute("SELECT google_event_id FROM calendar_events")
    ids = {row[0] for row in cur.fetchall()}
    cur.close()
    return ids


def main():
    parser = argparse.ArgumentParser(description="Import Outlook calendar events into Postgres")
    parser.add_argument("--dry-run", action="store_true", help="Show matches without inserting")
    parser.add_argument("--deal", type=str, help="Only import events for a specific deal (substring match on deal_id)")
    parser.add_argument("--csv", type=str, help="Path to CSV file (default: calendar_events.csv in project root)")
    args = parser.parse_args()

    csv_path = Path(args.csv) if args.csv else CSV_PATH
    if not csv_path.exists():
        print(f"CSV not found: {csv_path}")
        sys.exit(1)

    # ── Read CSV ──────────────────────────────────────────────────────────────
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    total_rows = len(rows)

    # Filter out internal-only meetings
    external_rows = [r for r in rows if int(r.get("external_count", 0)) > 0]
    total_external = len(external_rows)

    print(f"\nCALENDAR IMPORT PLAN")
    print(f"====================")
    print(f"Source: {csv_path.name} ({total_rows} rows, {total_external} external)\n")

    # ── Build domain lookup from Postgres ─────────────────────────────────────
    conn = get_pg_connection()
    domain_map, company_map, name_to_deal = build_domain_lookup(conn)
    existing_ids = get_existing_event_ids(conn)

    # ── Match each external meeting to a deal ────────────────────────────────
    matched = []     # (row, deal_id, match_domain)
    unmatched = []   # (row, domains_found)

    for row in external_rows:
        ext_attendees_str = row.get("external_attendees", "")
        ext_emails = parse_attendees(ext_attendees_str)

        # Extract external domains (skip noise)
        ext_domains = set()
        for email in ext_emails:
            domain = extract_domain(email)
            if domain and domain not in NOISE_DOMAINS:
                ext_domains.add(domain)

        if not ext_domains:
            # All "external" attendees were noise domains — skip
            continue

        # Try domain match
        found_deal = None
        match_domain = None
        for domain in ext_domains:
            if domain in domain_map:
                found_deal = domain_map[domain]
                match_domain = domain
                break

        # Fuzzy subject match fallback
        if not found_deal:
            found_deal = fuzzy_match_subject(row["subject"], name_to_deal)
            if found_deal:
                match_domain = f"subject match: {company_map.get(found_deal, '?')}"

        if found_deal:
            # Apply deal filter if specified
            if args.deal and args.deal.lower() not in found_deal.lower():
                continue
            matched.append((row, found_deal, match_domain))
        else:
            if not args.deal:  # Only show unmatched if not filtering
                unmatched.append((row, ext_domains))

    # ── Display matches ──────────────────────────────────────────────────────
    print("Matched to deals:")
    if not matched:
        print("  (none)")
    else:
        # Group by deal for cleaner output
        by_deal = defaultdict(list)
        for row, deal_id, match_domain in matched:
            by_deal[deal_id].append((row, match_domain))

        for deal_id in sorted(by_deal.keys()):
            company = company_map.get(deal_id, deal_id)
            events = by_deal[deal_id]
            print(f"\n  {company} ({deal_id}) — {len(events)} event(s):")
            for row, match_domain in sorted(events, key=lambda x: x[0]["start"]):
                start_dt = datetime.fromisoformat(row["start"])
                date_str = start_dt.strftime("%b %d")
                subj = row["subject"][:60]
                event_id = generate_event_id(row["subject"], row["start"])
                already = " [ALREADY IN DB]" if event_id in existing_ids else ""
                print(f"    {date_str:6s}  {subj:60s}  ({match_domain}){already}")

    if unmatched:
        print(f"\nUnmatched (no deal found) — {len(unmatched)} event(s):")
        for row, domains in sorted(unmatched, key=lambda x: x[0]["start"]):
            start_dt = datetime.fromisoformat(row["start"])
            date_str = start_dt.strftime("%b %d")
            subj = row["subject"][:60]
            domain_list = ", ".join(sorted(domains))
            print(f"  {date_str:6s}  {subj:60s}  ({domain_list})")

    # ── Summary ──────────────────────────────────────────────────────────────
    already_count = sum(
        1 for row, deal_id, _ in matched
        if generate_event_id(row["subject"], row["start"]) in existing_ids
    )
    new_count = len(matched) - already_count
    print(f"\nSummary: {len(matched)} matched, {len(unmatched)} unmatched, {already_count} already in DB, {new_count} new to insert")

    if args.dry_run:
        print("\nDry run complete — no writes.")
        conn.close()
        return

    if new_count == 0:
        print("\nNothing new to insert.")
        conn.close()
        return

    # ── Insert into calendar_events ──────────────────────────────────────────
    cur = conn.cursor()
    inserted = 0

    for row, deal_id, match_domain in matched:
        event_id = generate_event_id(row["subject"], row["start"])
        if event_id in existing_ids:
            continue

        # Parse all attendees (not just external) for the attendees column
        all_emails = parse_attendees(row.get("attendees", ""))
        meeting_type = classify_meeting_type(row["subject"])

        try:
            cur.execute("""
                INSERT INTO calendar_events
                    (google_event_id, title, start_time, end_time,
                     attendees, location, deal_id, meeting_type, organizer, synced_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (google_event_id) DO NOTHING
            """, (
                event_id,
                row["subject"],
                row["start"],
                row["end"],
                all_emails,   # TEXT[] — psycopg2 handles list -> array
                row.get("location", ""),
                deal_id,
                meeting_type,
                row.get("organizer", ""),
            ))
            inserted += 1
        except Exception as e:
            print(f"  ERROR inserting {event_id}: {e}")
            conn.rollback()
            continue

    conn.commit()
    cur.close()
    conn.close()

    print(f"\nInserted {inserted} calendar events.")


if __name__ == "__main__":
    main()
