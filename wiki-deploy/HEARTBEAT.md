# HEARTBEAT.md — Cron Schedules + Routines

## Compile Cycle (NEW — Primary)

**Schedule:** Every 30 minutes, 8 AM – 6 PM CT, weekdays
**What:** Check raw/ for new inputs since last compile. If new inputs exist, load wiki-schema.md and compile them into the wiki. Post summary to Ops Log and DM Austin.
**If no new inputs:** Skip. Log "no new inputs" to wiki/log.md.

## Lint (NEW)

**Schedule:** Daily 8 PM CT
**What:** Run 7 health checks on the wiki:
1. Broken wikilinks — links pointing to non-existent articles
2. Orphan pages — articles with no inbound links (candidates for archival)
3. Uncompiled inputs — raw/ entries not reflected in wiki/
4. Stale articles — active articles with no updates in 30+ days
5. Missing backlinks — A links to B but B doesn't link back
6. Sparse articles — under 200 words (stubs that need enrichment)
7. Contradictions — conflicting claims across articles (requires reading the wiki)

Post report to Johnny Alerts. Fix broken links and missing backlinks automatically. Flag everything else for review.

## Tomorrow's Briefing

**Schedule:** 9 PM CT Sunday through Thursday
**What:** Read wiki/index.md → filter for tomorrow's meetings and active deals → read relevant wiki articles → produce briefing for Austin's DM.

Sources: wiki deal articles, wiki people articles, calendar data, connection/pattern articles.

## SF Pipeline Sync

**Schedule:** 9:45 PM CT Sunday, 10 PM CT Tuesday
**What:** Read wiki deal articles for all active deals → query SF for current field values → identify deltas → present proposed updates to Austin's DM for approval.

Scoring data comes from scores.jsonl, not from wiki articles.

## Skill Evolution

**Schedule:** Wednesday 9 PM CT
**What:** Analyze wiki patterns, review lint reports, review scores.jsonl trends, identify improvements to the compilation schema or analysis prompts. Report to Johnny Alerts.

## Daily Backup

**Schedule:** 11 PM CT daily
**What:** Git commit raw/ + wiki/ + scores.jsonl → push to GitHub backup repo.
Only commits if there are changes.
