"""
run_backfill_all.py — Orchestrate full backfill across all deals.

Runs backfill.py for each deal sequentially (CW-02 is a shared resource).
Logs progress so you can resume after a crash.

Usage:
    python3 scripts/run_backfill_all.py              # full run (skips already-done deals)
    python3 scripts/run_backfill_all.py --dry-run    # show batch plan for all deals, no writes
    python3 scripts/run_backfill_all.py --deal velentium  # single deal only
    python3 scripts/run_backfill_all.py --from ephicacy   # resume from a specific deal
    python3 scripts/run_backfill_all.py --reset            # clear progress log, start fresh

Progress is saved to: backfill/_state/progress.json
A deal is marked done only after ALL its batches complete successfully.
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BACKFILL_DIR  = Path(__file__).parent.parent / "backfill"
STATE_DIR     = BACKFILL_DIR / "_state"
PROGRESS_FILE = STATE_DIR / "progress.json"
BACKFILL_SCRIPT = Path(__file__).parent / "backfill.py"

# Ordered list — runs in this sequence.
# Velentium first (already has data), then by file count descending.
DEAL_ORDER = [
    "velentium",
    "family-resource-home-care",
    "exer-urgent-care",
    "minaris",
    "mississippi-state",
    "sca-pharma",
    "partnership-healthplan",
    "american-medical-staffing",
    "ephicacy",
    "paradigm-health",
    "auch-utech",
    "sandstone",
    "pyramids-pharmacy",
    "st-croix-hospice",
    "trustwell-living",
    "personal-physicians-healthcare",
    "pantherx",
    "royal-community-support",
    "carehospice",
    "atlas-clinical",
    "primary-health-partners",
    "life-care-home-health",
    "dedicated-sleep",
    "project-wellness",
]


def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text())
    return {"completed": [], "started_at": None, "last_updated": None}


def save_progress(state: dict):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state["last_updated"] = datetime.now().isoformat()
    PROGRESS_FILE.write_text(json.dumps(state, indent=2))


def get_deals_with_files() -> list[str]:
    """Return deal slugs from DEAL_ORDER that have at least one file in their folder."""
    result = []
    for slug in DEAL_ORDER:
        deal_dir = BACKFILL_DIR / slug
        if not deal_dir.exists():
            continue
        files = [f for f in deal_dir.iterdir()
                 if f.is_file() and f.suffix in {".txt", ".eml", ".pdf", ".csv"}
                 and not f.name.startswith(".")]
        if files:
            result.append((slug, len(files)))
    return result


def run_dry_run(slug: str) -> bool:
    """Run backfill.py --dry-run for a deal. Returns True on success."""
    result = subprocess.run(
        [sys.executable, str(BACKFILL_SCRIPT), "--deal", slug, "--dry-run"],
        capture_output=False,  # stream to stdout
    )
    return result.returncode == 0


def run_backfill(slug: str, score_once: bool = False) -> bool:
    """Run backfill.py for a deal. Returns True on success."""
    cmd = [sys.executable, str(BACKFILL_SCRIPT), "--deal", slug]
    if score_once:
        cmd.append("--score-once")
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Orchestrate full backfill across all deals")
    parser.add_argument("--dry-run",    action="store_true", help="Show batch plan for all deals, no writes")
    parser.add_argument("--deal",       help="Run a single deal only")
    parser.add_argument("--from",       dest="from_deal", help="Resume from this deal slug")
    parser.add_argument("--reset",      action="store_true", help="Clear progress log and start fresh")
    parser.add_argument("--score-once", action="store_true", help="Fire CW-02 once per deal after all batches (faster)")
    args = parser.parse_args()

    # ── Reset ──────────────────────────────────────────────────────────────────
    if args.reset:
        if PROGRESS_FILE.exists():
            PROGRESS_FILE.unlink()
        print("Progress log cleared. Run again without --reset to start.")
        return

    # ── Single deal ────────────────────────────────────────────────────────────
    if args.deal:
        slug = args.deal.lower()
        deal_dir = BACKFILL_DIR / slug
        if not deal_dir.exists():
            print(f"No folder found for deal '{slug}'")
            sys.exit(1)
        if args.dry_run:
            run_dry_run(slug)
        else:
            ok = run_backfill(slug, score_once=args.score_once)
            sys.exit(0 if ok else 1)
        return

    # ── Full run ───────────────────────────────────────────────────────────────
    deals = get_deals_with_files()

    if not deals:
        print("No deal folders with files found.")
        return

    state = load_progress()
    if args.reset or state["started_at"] is None:
        state["started_at"] = datetime.now().isoformat()
        state["completed"] = []

    print("=" * 70)
    print(f"{'[DRY RUN] ' if args.dry_run else ''}Backfill Orchestrator")
    print(f"Deals with files: {len(deals)}")
    print(f"Already completed: {len(state['completed'])}")
    print("=" * 70)
    print()

    # Print full schedule table
    print(f"{'#':>3}  {'Deal':35}  {'Files':>5}  {'Status'}")
    print(f"{'─'*3}  {'─'*35}  {'─'*5}  {'─'*10}")
    for i, (slug, file_count) in enumerate(deals, 1):
        status = "done ✓" if slug in state["completed"] else "pending"
        if args.from_deal and slug == args.from_deal:
            status = "← start here"
        print(f"{i:>3}  {slug:35}  {file_count:>5}  {status}")
    print()

    if args.dry_run:
        print("─" * 70)
        print("DRY RUN — Batch plan for each deal:")
        print("─" * 70)
        for slug, file_count in deals:
            print(f"\n{'━'*70}")
            print(f"  {slug}  ({file_count} files)")
            print(f"{'━'*70}")
            run_dry_run(slug)
        return

    # ── Execute sequentially ───────────────────────────────────────────────────
    # Optionally skip to --from deal
    skip_until = args.from_deal.lower() if args.from_deal else None
    reached_start = skip_until is None

    for slug, file_count in deals:
        if not reached_start:
            if slug == skip_until:
                reached_start = True
            else:
                print(f"  Skipping {slug} (before --from point)")
                continue

        if slug in state["completed"]:
            print(f"  Skipping {slug} — already completed ✓")
            continue

        print(f"\n{'━'*70}")
        print(f"  Starting: {slug}  ({file_count} files)")
        print(f"  Time: {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'━'*70}")

        ok = run_backfill(slug, score_once=args.score_once)

        if ok:
            state["completed"].append(slug)
            save_progress(state)
            print(f"\n  ✅ {slug} complete")
        else:
            save_progress(state)
            print(f"\n  ❌ {slug} failed — stopping. Fix the issue and re-run to resume.")
            print(f"     (Completed deals saved to {PROGRESS_FILE})")
            sys.exit(1)

        # Brief pause between deals so CW-02 fully settles
        if deals.index((slug, file_count)) < len(deals) - 1:
            print(f"  Pausing 15s before next deal...")
            time.sleep(15)

    print()
    print("=" * 70)
    print(f"ALL DEALS COMPLETE — {len(state['completed'])} deals backfilled")
    print("=" * 70)


if __name__ == "__main__":
    main()
