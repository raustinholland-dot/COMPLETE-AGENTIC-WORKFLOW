# Wiki Architecture Plan — Karpathy-Inspired Knowledge Base for Johnny Forsyth

Created: 2026-04-08
Status: DEPLOYED, TESTING PHASE

---

## What This Is

A complete architectural overhaul of Johnny Forsyth's knowledge system, inspired by Andrej Karpathy's LLM Wiki pattern and Cole Medin's claude-memory-compiler. Replaces the per-input processing pipeline (classify → read → rescore → Writer → Verifier → notify) with a three-layer architecture: capture → compile → query/act.

## Why We Did This

The previous system had fundamental problems:
- **Sealed rooms** — Writer and Verifier sub-agents operated in sandboxed contexts with no visibility into the full picture. Johnny had to compress everything into "sticky notes" (task briefs) that frequently lost information.
- **Too much per input** — Every single feed input triggered a full pipeline: classification, P2V2C2 rescoring, Writer spawn, Verifier spawn, index/hot updates. Token-heavy, time-consuming, fragile.
- **Siloed knowledge** — Deals analyzed in isolation. No cross-deal intelligence, no pattern recognition, no compounding knowledge.
- **Methodology baked into storage** — P2V2C2 scores, CAS stages, DAP timelines, communication log numbering all embedded into rigid deal-state templates. The Writer had to know exact formats, which is why rules kept needing fixes.

## The New Architecture

### Three Layers

```
raw/                    → Immutable daily input logs (verbatim capture)
   ↓ [compiler]
wiki/                   → LLM-owned compiled knowledge (flat markdown, wikilinks)
   ↓ [query/analysis]
Outputs                 → Drafts, scores, briefings, SF updates
```

### Key Design Decisions

1. **Methodology-agnostic storage.** The wiki stores knowledge. P2V2C2, CAS, DAP — all applied at the query/analysis layer, not baked into article structure.
2. **Scoring stored separately.** `scores.jsonl` holds scoring results with cited evidence. Not in wiki articles.
3. **Compiler decides what matters.** No prescribed article types. The compiler creates whatever structure the knowledge requires.
4. **Bias toward creating.** When in doubt, capture it. Stubs are cheap. The wiki self-prunes through usage — articles that get referenced survive, orphans get flagged by lint and archived.
5. **Connections are the most valuable layer.** Cross-deal patterns, coaching themes, pricing behaviors, industry playbooks emerge from the compiler seeing across many inputs.
6. **Knowledge compounds.** Questions filed back as articles. Won/lost deals teach patterns. The system gets smarter over time.
7. **Gemini Gem model for outputs.** Dedicated, well-tuned prompts per output type (email draft, call prep, pipeline review, scoring) read from the wiki. Like the existing Gemini Gem that works well for transcript analysis.

### What Was Retired
- **Writer sub-agent** — compiler handles all wiki writes
- **Verifier sub-agent** — lint cron handles integrity checks
- **WRITER-RULES.md** — archived
- **VERIFIER-RULES.md** — archived
- **Per-input pipeline** (classify → rescore → bundle → verify → notify) — replaced by capture + compile

### What Was Kept
- **Researcher sub-agent** — on-demand web research
- **Meeting Prep sub-agent** — optional, can also be done via wiki query
- **Ops Log** — still the audit trail
- **Dedup** — .processed-inputs.jsonl still checked on every input
- **Outbound tracking** — outbound-tracking.jsonl still maintained
- **Session resets** — 5-min idle reset still active
- **All existing deal-state files** — untouched in clearwater/deals/, wiki seeded FROM them

---

## What's Deployed (on Johnny's MBP)

### New Files at `~/.openclaw/workspace/`

| File | Purpose |
|------|---------|
| `SOUL.md` | Updated identity — wiki-centric foundational rule |
| `FEED-RULES.md` | Simplified — capture + triage only (no Writer/Verifier) |
| `AGENTS.md` | New architecture — compile crons, retired Writer/Verifier |
| `HEARTBEAT.md` | Updated cron schedule with compile + lint |
| `wiki-schema.md` | Full compilation schema — loaded when compile runs |
| `scores.jsonl` | Empty scoring table |
| `wiki/index.md` | Master catalog — 100 articles indexed |
| `wiki/log.md` | Compiler changelog |
| `wiki/[100 articles]` | Seeded from 33 deal-state files + knowledge base |
| `raw/2026-04-08.md` | Placeholder for first real raw capture |

### Wiki Seed Summary (Pass 2 — from actual deal-state files)

- 29 active deals, 6 closed deals
- 25 external people, 22 internal people
- 4 organizations, 3 projects, 3 events
- 8 concepts/products
- **Total: 100 articles + index + log**

### Old Files (Still Present, Untouched)

- `clearwater/deals/` — all 33 deal-state files still there
- `clearwater/knowledge/` — old index.md, hot.md still there
- `MEMORY.md`, `USER.md`, `TOOLS.md` — still there
- Writer/Verifier agent configs in `~/.openclaw/agents/` — still there but not referenced

---

## Git Save Point

**Tag:** `10-10-baseline`
**Commit:** `8e1add3`
**What it contains:** Full pre-wiki state — all files, audit data, schema prompt, everything

**To restore:** `rollback` (alias configured in ~/.zshrc) or `git checkout 10-10-baseline`

**Note:** GitHub push failed (auth token expired). Save point is LOCAL only. Johnny's nightly GitHub backup is a separate safety net.

---

## Source Material

- **Karpathy's LLM Wiki gist:** https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
- **Cole Medin's claude-memory-compiler:** https://github.com/coleam00/claude-memory-compiler
- **Cole Medin video walkthrough:** https://www.youtube.com/watch?v=7huCP6RkcY4
- **Meta-Harness paper (Stanford):** `Meta-harness end-to-end optimization of model harnesses.pdf` in sales-tools/
- **Wiki schema prompt:** `wiki-schema-prompt.md` in sales-tools/
- **Generated schema:** `wiki-schema.md` in sales-tools/ and deployed to Johnny's MBP

---

## Testing Plan

### Phase 1: Capture-Compile Loop (Current Phase)

Test that inputs get captured to raw/ and the compiler correctly updates the wiki.

**Test 1: Simple email input**
- Send a straightforward deal email to Email Feed
- Verify Johnny captures it verbatim to raw/2026-04-08.md (or next day)
- Verify triage (urgent vs normal) and ack to DM
- Trigger compile manually
- Verify the wiki article for that deal got updated with the new info
- Verify index.md reflects the change

**Test 2: Multi-deal transcript**
- Send a call transcript that covers 2-3 deals (like a DK 1:1)
- Verify raw capture
- Trigger compile
- Verify multiple wiki articles updated from one input
- Verify cross-references/wikilinks created between the deals
- Check if a connection article was created (DK coaching themes, shared patterns)

**Test 3: New entity (person/org/concept)**
- Send an input that mentions someone not in the wiki yet
- Trigger compile
- Verify a new person article was created (even as stub)
- Verify the deal article links to the new person
- Verify index updated with the new person

**Test 4: Urgent triage path**
- Send an input that should be flagged urgent (client asking a question)
- Verify Johnny reads wiki articles for context
- Verify Johnny produces an inline draft in DM WITHOUT waiting for compile
- Verify raw capture still happened
- Trigger compile and verify wiki updated

**Test 5: Dedup**
- Send the same input again
- Verify Johnny recognizes it as duplicate and skips

### Phase 2: Query/Analysis Layer

Test that the wiki enables better outputs than the old system.

**Test 6: Deal scoring**
- Ask Johnny to score a deal using P2V2C2 based on wiki evidence
- Verify the score cites specific evidence from wiki articles
- Verify the score gets written to scores.jsonl
- Compare quality against previous scoring (should be more evidence-based)

**Test 7: Email draft from wiki context**
- Ask Johnny to draft an email for a specific deal
- Verify the draft pulls from the wiki deal article + person article
- Verify the draft matches Austin's actual communication style
- Compare quality against previous drafts

**Test 8: Cross-deal intelligence**
- Ask a question that spans multiple deals (e.g., "what's my pipeline look like for deals over $100K?")
- Verify Johnny reads the index, pulls multiple deal articles, and synthesizes
- Verify the answer includes cross-deal patterns or connections
- This is the capability that didn't exist before

### Phase 3: Cron + Automation

**After Phases 1-2 pass:**
- Set up the compile cron (every 30 min, 8 AM - 6 PM CT)
- Set up the lint cron (daily 8 PM CT)
- Monitor for 1-2 days
- Verify compile logs in wiki/log.md
- Verify lint reports catching any issues

---

## Future (Not Yet Implemented)

- **Obsidian visualization** — install on Austin's MBP, sync wiki via GitHub backup, browse the graph
- **Graph API automation** — Microsoft Graph API to auto-ingest emails, Teams, calendar (weeks out)
- **Pattern articles** — will emerge naturally from compile cycles as cross-deal themes surface
- **Scoring agent** — dedicated Gem-like prompt for P2V2C2 scoring from wiki evidence
- **Output templates** — dedicated prompts per output type (email draft, Teams message, call prep, pipeline review)
- **GitHub auth fix** — re-authenticate to push to remote

---

## Key Files Reference

| File | Location | Purpose |
|------|----------|---------|
| `wiki-architecture-plan.md` | sales-tools/ | This file — full plan and context |
| `wiki-schema.md` | sales-tools/ + Johnny's MBP | The compilation schema |
| `wiki-schema-prompt.md` | sales-tools/ | The prompt that generated the schema |
| `wiki-deploy/` | sales-tools/ | Local copies of all deployed files |
| `audits/audit-2026-04-08.json` | sales-tools/ | Today's audit data (used for analysis) |
| `Gemini Gem Description and Instructions.txt` | sales-tools/ | The proven analysis tool — informs query layer design |
| `johnny-rebuild-2026-04-06.md` | sales-tools/ | Previous architecture (reference for what changed) |
