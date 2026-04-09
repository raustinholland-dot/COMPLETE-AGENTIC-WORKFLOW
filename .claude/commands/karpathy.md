# /karpathy — Wiki Knowledge Base Architecture

## Context

On 2026-04-08, Austin and Claude Code redesigned Johnny Forsyth's entire knowledge system, moving from a per-input processing pipeline to a Karpathy-inspired wiki architecture. This was a major architectural shift informed by Andrej Karpathy's LLM Wiki pattern, Cole Medin's claude-memory-compiler, and the Stanford Meta-Harness paper.

## What Happened

- Ran the daily audit (`/johnny-audit`) — scored 9.6/10 overall but identified a recurring "sealed rooms" problem: Writer sub-agent in a sandboxed context kept missing index/hot updates because it couldn't see the full picture
- Researched Karpathy's LLM Wiki architecture and Cole Medin's implementation
- Designed a three-layer system: raw/ (capture) → wiki/ (compiled knowledge) → query/analysis (outputs)
- Key decision: methodology-agnostic storage. P2V2C2, CAS, DAP are applied at query time, not embedded in article structure. Scoring goes to scores.jsonl, not wiki articles.
- Built schema document, new context files (SOUL, FEED-RULES, AGENTS, HEARTBEAT)
- Deployed to Johnny's MBP via SSH
- Johnny seeded the wiki: 100 articles from 33 deal-state files
- Gateway restarted with new context

## Current State

**DEPLOYED. IN TESTING PHASE.**

The wiki is live on Johnny's MBP with 100 seeded articles. The compile cron is NOT yet active — we're testing the capture→compile loop manually first.

## What to Do

1. Read the full plan: `~/Desktop/sales-tools/wiki-architecture-plan.md`
2. Read the wiki schema: `~/Desktop/sales-tools/wiki-schema.md`
3. Read the deployed context files in: `~/Desktop/sales-tools/wiki-deploy/`
4. SSH access to Johnny's MBP: `ssh austinholland@100.122.212.128`
5. Wiki lives at: `~/.openclaw/workspace/wiki/` on Johnny's MBP
6. Raw inputs at: `~/.openclaw/workspace/raw/` on Johnny's MBP

## Git Save Point

- **Tag:** `10-10-baseline` — the full pre-wiki state
- **Restore:** type `rollback` in terminal (alias configured)
- **Note:** local only, GitHub push failed (auth expired)

## Testing Sequence (8 tests)

We agreed to test manually before turning on crons:

1. **Simple email** — capture to raw/, compile, verify wiki update
2. **Multi-deal transcript** — verify cross-references and connection articles
3. **New entity** — verify stub creation for unknown person/concept
4. **Urgent triage** — verify instant draft from wiki + raw capture
5. **Dedup** — verify duplicate detection still works
6. **Deal scoring** — P2V2C2 from wiki evidence → scores.jsonl
7. **Email draft** — draft from wiki context, matching Austin's voice
8. **Cross-deal query** — pipeline review pulling from multiple articles

## Key Decisions Made

- Opus for compilation first, optimize to Gemini later once the process is proven
- Flat wiki (no subdirectories) — index + wikilinks provide all structure
- Bias toward creating articles — wiki self-prunes via lint (orphans flagged/archived)
- Compiler decides article types — not prescribed
- Connections are the most valuable layer — cross-deal intelligence
- Gemini Gem model for outputs — dedicated prompts per output type
- Lint runs daily during testing, weekly once stable
- Graph API integration coming (weeks out) — will increase input volume significantly

## Telegram Note

Bot auth was failing at end of session — may need reconfiguration. Austin sends messages to Johnny directly for now.
