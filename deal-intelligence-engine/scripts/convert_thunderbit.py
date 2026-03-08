#!/usr/bin/env python3
"""
convert_thunderbit.py — Convert Thunderbit CSV exports to backfill .txt format

Usage:
    python3 scripts/convert_thunderbit.py
"""

import csv
import glob
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
RAW_DIR = PROJECT_DIR / "backfill" / "teams-raw"
BACKFILL_DIR = PROJECT_DIR / "backfill"

# Map output files to deal slugs (None = keep in teams-raw as multi-deal)
CONVERSIONS = {
    "richmond_david_merged": None,  # multi-deal internal, goes to _internal
    "carter-richmond-wes": "project-wellness",
    "jacob-jaime-mikaela": "project-wellness",
    "david-and-melissa": "life-care-home-health",
}


def parse_date(date_str):
    """Parse Thunderbit date format MM/DD/YY or MM/DD/YYYY."""
    for fmt in ("%m/%d/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def csv_to_txt(rows, chat_name, out_path):
    """Convert CSV rows to our standard backfill text format."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "[TEAMS CHAT EXPORT]",
        f"Chat: {chat_name}",
        f"Scraped: {datetime.now().isoformat()}",
        f"Messages: {len(rows)}",
        "[END HEADER]",
        "",
    ]
    for row in rows:
        sender = row.get("Sender Name", "").strip()
        date = row.get("Message Date", "").strip()
        time = row.get("Message Time", "").strip()
        body = row.get("Message Content", "").strip()
        attachment = row.get("Attachment Name", "").strip()

        if not body and not attachment:
            continue

        timestamp = f"{date} {time}".strip()
        lines.append(f"[{timestamp}] {sender}:")
        if body:
            lines.append(body)
        if attachment:
            lines.append(f"[Attachment: {attachment}]")
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  → {out_path} ({len(rows)} messages)")


def merge_richmond_csvs():
    """Merge all Thunderbit CSVs (Richmond/David chat) and deduplicate."""
    csv_files = sorted(RAW_DIR.glob("Thunderbit_*.csv"))
    if not csv_files:
        print("No Thunderbit CSVs found.")
        return []

    seen = set()
    all_rows = []
    for f in csv_files:
        with open(f) as fp:
            for row in csv.DictReader(fp):
                key = (row.get("Sender Name"), row.get("Message Date"),
                       row.get("Message Time"), row.get("Message Content", "")[:50])
                if key not in seen:
                    seen.add(key)
                    all_rows.append(row)

    # Sort chronologically
    def sort_key(r):
        d = parse_date(r.get("Message Date", ""))
        t = r.get("Message Time", "")
        return (d or datetime.min, t)

    all_rows.sort(key=sort_key)
    print(f"Merged {len(csv_files)} Thunderbit CSVs → {len(all_rows)} unique messages")
    return all_rows


def main():
    # 1. Merge Richmond/David Thunderbit CSVs → _internal/
    richmond_rows = merge_richmond_csvs()
    if richmond_rows:
        out_dir = BACKFILL_DIR / "_internal"
        out_path = out_dir / "2026-03-03_teams-richmond-david.txt"
        csv_to_txt(richmond_rows, "Richmond Donnelly (David Kolb)", out_path)

    # 2. Convert Carter/Richmond/Wes → project-wellness/
    src = RAW_DIR / "2026-03-03_carter-richmond-and-wes.txt"
    if src.exists():
        dst_dir = BACKFILL_DIR / "project-wellness"
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / "2026-03-03_teams-carter-richmond-wes.txt"
        dst.write_text(src.read_text(), encoding="utf-8")
        print(f"  → {dst}")

    # 3. Convert Jacob/Jaime/Mikaela → project-wellness/
    src = RAW_DIR / "2026-03-03_jacob-jaime-mikaela-2.txt"
    if src.exists():
        dst_dir = BACKFILL_DIR / "project-wellness"
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / "2026-03-03_teams-jacob-jaime-mikaela.txt"
        dst.write_text(src.read_text(), encoding="utf-8")
        print(f"  → {dst}")

    # 4. Convert David/Melissa → life-care-home-health/
    src = RAW_DIR / "2026-03-03_david-and-melissa.txt"
    if src.exists():
        dst_dir = BACKFILL_DIR / "life-care-home-health"
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / "2026-03-03_teams-david-melissa.txt"
        dst.write_text(src.read_text(), encoding="utf-8")
        print(f"  → {dst}")

    print("\nDone. Review _internal/ for multi-deal Richmond/David context.")
    print("Run backfill.py --deal <slug> for each deal folder.")


if __name__ == "__main__":
    main()
