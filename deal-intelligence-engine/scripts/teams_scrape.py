#!/usr/bin/env python3
"""
teams_scrape.py — Playwright-based Teams chat scraper

Scrapes all chats and channels from Teams web app and saves them as text files
in deal-intelligence-engine/backfill/teams-raw/ for later processing.

First run: opens a visible browser for MFA login, saves session.
Subsequent runs: headless, uses saved session.

Usage:
    pip3 install playwright anthropic
    playwright install chromium

    # First run (interactive login):
    python3 scripts/teams_scrape.py --login

    # Subsequent runs (headless):
    python3 scripts/teams_scrape.py

    # Dry run (list chats without scraping):
    python3 scripts/teams_scrape.py --dry-run

    # Identify deals from raw files after scraping:
    python3 scripts/teams_scrape.py --identify
"""

import argparse
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

SCRIPT_DIR    = Path(__file__).parent
PROJECT_DIR   = SCRIPT_DIR.parent
RAW_DIR       = PROJECT_DIR / "backfill" / "teams-raw"
SESSION_FILE  = SCRIPT_DIR / ".teams-session.json"
TEAMS_URL     = "https://teams.cloud.microsoft"

# Deal list for Claude identification (same as backfill.py)
DEALS = [
    "American Medical Staffing",
    "Exer Urgent Care",
    "Mississippi State University",
    "PANTHERx Rare",
    "Pyramids Pharmacy",
    "Velentium Medical",
    "Minaris Advanced Therapies",
    "Ephicacy",
    "Partnership HealthPlan of California",
    "Trustwell Living",
    "Dedicated Sleep",
    "RISE Services",
    "Family Resource Home Care",
    "Primary Health Partners Oklahoma",
    "Royal Community Support",
    "Paradigm Health",
    "MedElite",
    "Atlas Clinical Research",
    "Fella Health",
    "SCA Pharma",
    "Advanced Dermatology PC",
    "Life Care Home Health",
    "Gavin Foundation",
    "Daniel Island",
]

DEAL_SLUG_MAP = {
    "American Medical Staffing": "american-medical-staffing",
    "Exer Urgent Care": "exer-urgent-care",
    "Mississippi State University": "mississippi-state",
    "PANTHERx Rare": "pantherx",
    "Pyramids Pharmacy": "pyramids-pharmacy",
    "Velentium Medical": "velentium",
    "Minaris Advanced Therapies": "minaris",
    "Ephicacy": "ephicacy",
    "Partnership HealthPlan of California": "partnership-healthplan",
    "Trustwell Living": "trustwell-living",
    "Dedicated Sleep": "dedicated-sleep",
    "RISE Services": "rise-services",
    "Family Resource Home Care": "family-resource-home-care",
    "Primary Health Partners Oklahoma": "primary-health-partners",
    "Royal Community Support": "royal-community-support",
    "Paradigm Health": "paradigm-health",
    "MedElite": "medelite",
    "Atlas Clinical Research": "atlas-clinical",
    "Fella Health": "fella-health",
    "SCA Pharma": "sca-pharma",
    "Advanced Dermatology PC": "advanced-dermatology",
    "Life Care Home Health": "life-care-home-health",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def slugify(name: str) -> str:
    """Convert chat name to a safe filename."""
    name = re.sub(r"[^\w\s-]", "", name.lower())
    name = re.sub(r"[\s_]+", "-", name.strip())
    return name[:80]


def already_scraped(chat_name: str) -> bool:
    """Check if this chat has already been scraped today."""
    today = datetime.now().strftime("%Y-%m-%d")
    slug = slugify(chat_name)
    existing = list(RAW_DIR.glob(f"{today}_{slug}*.txt"))
    return len(existing) > 0


def save_chat(chat_name: str, messages: list[dict]) -> Path:
    """Save scraped messages to a text file."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    slug = slugify(chat_name)
    out_path = RAW_DIR / f"{today}_{slug}.txt"

    lines = [
        f"[TEAMS CHAT EXPORT]",
        f"Chat: {chat_name}",
        f"Scraped: {datetime.now().isoformat()}",
        f"Messages: {len(messages)}",
        "[END HEADER]",
        "",
    ]

    for msg in messages:
        sender = msg.get("sender", "Unknown")
        timestamp = msg.get("timestamp", "")
        body = msg.get("body", "").strip()
        if body:
            lines.append(f"[{timestamp}] {sender}:")
            lines.append(body)
            lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


# ── Scraper ───────────────────────────────────────────────────────────────────

def login(playwright):
    """Open visible browser for MFA login, save session."""
    from playwright.sync_api import sync_playwright

    print("Opening browser for login...")
    print("Log in with your Clearwater credentials + MFA, then press Enter here.")

    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto(TEAMS_URL)

    input("\n>>> Press Enter after you've logged in and Teams has fully loaded... ")

    # Save session state
    storage = context.storage_state()
    SESSION_FILE.write_text(json.dumps(storage), encoding="utf-8")
    print(f"Session saved to {SESSION_FILE}")

    browser.close()


def scrape_chats(playwright, dry_run=False):
    """Scrape all chats using saved session."""
    if not SESSION_FILE.exists():
        print("No session found. Run with --login first.")
        return []

    storage_state = json.loads(SESSION_FILE.read_text())

    headless = not dry_run
    browser = playwright.chromium.launch(headless=headless)
    context = browser.new_context(storage_state=storage_state)
    page = context.new_page()

    print("Loading Teams...")
    # Teams v2 is a SPA that never reaches networkidle — use domcontentloaded
    page.goto(TEAMS_URL, wait_until="domcontentloaded", timeout=60000)
    time.sleep(12)

    results = []

    try:
        # Chat list is in the simple-collab-dnd-rail — no need to click Chat nav
        # Items 6+ in [tabindex] children are individual chats (skip filter headers)
        rail = page.locator('[data-tid="simple-collab-dnd-rail"]').first
        all_items = rail.locator('[tabindex]').all()

        # Filter to just chat items (skip section headers like Copilot, Discover, Mentions etc.)
        SKIP_LABELS = {"Copilot", "Discover", "Mentions", "Followed threads", "Favorites",
                       "Teams and channels", "See more", "See all channels", "See your teams"}
        chat_items = []
        in_chats_section = False
        in_teams_section = False
        for item in all_items:
            text = item.inner_text().strip().split("\n")[0]
            if text == "Chats":
                in_chats_section = True
                continue
            if text in ("Teams and channels", "See all your teams"):
                in_teams_section = True
                continue
            if in_teams_section:
                continue
            if text in SKIP_LABELS or not text:
                continue
            if in_chats_section:
                chat_items.append((text, item))

        print(f"Found {len(chat_items)} chats")

        if dry_run:
            for name, item in chat_items:
                print(f"  CHAT: {name}")
            browser.close()
            return []

        # Scrape each chat
        for i, (chat_name, item) in enumerate(chat_items):
            try:
                if already_scraped(chat_name):
                    print(f"  [{i+1}/{len(chat_items)}] SKIP (already scraped): {chat_name}")
                    continue

                print(f"  [{i+1}/{len(chat_items)}] Scraping: {chat_name}")
                item.click()
                time.sleep(3)

                messages = extract_messages(page)
                if messages:
                    out_path = save_chat(chat_name, messages)
                    print(f"    → {len(messages)} messages → {out_path.name}")
                    results.append({"chat": chat_name, "file": str(out_path), "count": len(messages)})
                else:
                    print(f"    → No messages extracted")

            except Exception as e:
                print(f"    → Error: {e}")
                continue

    except Exception as e:
        print(f"Error navigating Teams: {e}")

    browser.close()
    return results


def extract_messages(page) -> list[dict]:
    """Extract messages from the currently open chat."""
    messages = []

    # Scroll up repeatedly to load older messages
    try:
        for _ in range(15):
            page.keyboard.press("Control+Home")
            time.sleep(0.4)
    except:
        pass

    # Extract message items — Teams v2 uses [data-tid="chat-pane-item"]
    try:
        msg_items = page.locator('[data-tid="chat-pane-item"]').all()

        for item in msg_items:
            try:
                # Get message body — [data-tid="chat-pane-message"]
                body_el = item.locator('[data-tid="chat-pane-message"]').first
                body = body_el.inner_text().strip()
                if not body or len(body) < 2:
                    continue

                # Get sender — [data-tid="message-author-name"]
                sender = ""
                try:
                    sender_el = item.locator('[data-tid="message-author-name"]').first
                    sender = sender_el.inner_text().strip()
                except:
                    pass

                # Get timestamp — <time> element with aria-label
                timestamp = ""
                try:
                    time_el = item.locator("time").first
                    timestamp = time_el.get_attribute("aria-label") or time_el.inner_text()
                except:
                    pass

                messages.append({"sender": sender, "timestamp": timestamp, "body": body})
            except:
                continue

    except Exception as e:
        print(f"      Warning: {e}")

    return messages


# ── Deal Identification ───────────────────────────────────────────────────────

def identify_deals(dry_run=False):
    """
    Use Claude to identify which deal each raw Teams chat belongs to.
    Moves identified files to backfill/<deal-slug>/ with a teams- prefix.
    """
    import anthropic

    raw_files = sorted(RAW_DIR.glob("*.txt"))
    if not raw_files:
        print("No raw files to identify.")
        return

    client = anthropic.Anthropic()
    deal_list = "\n".join(f"- {d}" for d in DEALS)

    print(f"Identifying deals for {len(raw_files)} raw Teams chat files...")

    for raw_file in raw_files:
        content = raw_file.read_text(encoding="utf-8")
        # Use first 3000 chars for identification
        snippet = content[:3000]

        prompt = f"""You are analyzing a Teams chat export to determine which sales deal it relates to.

Active deals:
{deal_list}

Teams chat content (first portion):
{snippet}

Instructions:
- If this chat clearly relates to one of the active deals, respond with JSON: {{"deal": "<exact deal name from list>", "confidence": "high|medium|low", "reasoning": "<1 sentence>"}}
- If it relates to an internal Clearwater topic (not a specific deal), respond with JSON: {{"deal": "internal", "confidence": "high", "reasoning": "<topic>"}}
- If unclear or unrelated to any deal, respond with JSON: {{"deal": "unknown", "confidence": "low", "reasoning": "<why unclear>"}}

Respond with JSON only."""

        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )
            raw_json = response.content[0].text.strip()
            raw_json = re.sub(r"```json\n?", "", raw_json)
            raw_json = re.sub(r"```\n?", "", raw_json).strip()
            result = json.loads(raw_json)

            deal = result.get("deal", "unknown")
            confidence = result.get("confidence", "low")
            reasoning = result.get("reasoning", "")

            print(f"\n  {raw_file.name}")
            print(f"    Deal: {deal} ({confidence})")
            print(f"    Reason: {reasoning}")

            if dry_run:
                continue

            if deal in ("unknown", "internal") or confidence == "low":
                # Move to _other/
                dest_dir = PROJECT_DIR / "backfill" / "_other"
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest = dest_dir / f"teams-{raw_file.name}"
                raw_file.rename(dest)
                print(f"    → Moved to _other/")

            else:
                slug = DEAL_SLUG_MAP.get(deal)
                if slug:
                    dest_dir = PROJECT_DIR / "backfill" / slug
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    dest = dest_dir / f"teams-{raw_file.name}"
                    raw_file.rename(dest)
                    print(f"    → Moved to backfill/{slug}/")
                else:
                    print(f"    → No slug mapping for '{deal}', leaving in teams-raw/")

        except Exception as e:
            print(f"    → Error: {e}")

    print("\nIdentification complete.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Teams chat scraper")
    parser.add_argument("--login", action="store_true", help="Interactive login (first run)")
    parser.add_argument("--dry-run", action="store_true", help="List chats without scraping")
    parser.add_argument("--identify", action="store_true", help="Identify deals from raw files")
    args = parser.parse_args()

    if args.identify:
        identify_deals(dry_run=args.dry_run)
        return

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright not installed. Run: pip3 install playwright && playwright install chromium")
        return

    with sync_playwright() as playwright:
        if args.login:
            login(playwright)
        else:
            results = scrape_chats(playwright, dry_run=args.dry_run)
            if results and not args.dry_run:
                print(f"\n{'='*50}")
                print(f"Scraped {len(results)} chats.")
                print(f"Raw files in: {RAW_DIR}")
                print(f"\nNext step: python3 scripts/teams_scrape.py --identify")


if __name__ == "__main__":
    main()
