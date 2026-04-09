# AGENTS.md — Session Startup + System Architecture

## Session Startup

**Always load:** SOUL.md, FEED-RULES.md, wiki/index.md

**On compile trigger:** wiki-schema.md (the full schema — loaded when the compile cron fires)

**On demand:** wiki articles (navigate via index), raw/ logs, USER.md, TOOLS.md

---

## System Architecture

### Three Layers

```
raw/                    → Immutable daily input logs (verbatim)
   ↓ [compiler]
wiki/                   → LLM-owned compiled knowledge (articles + index + log)
   ↓ [query/analysis]
Outputs                 → Drafts, scores, briefings, SF updates
```

### The Compiler

- **What:** Reads new raw inputs + existing wiki → creates/updates/connects wiki articles
- **When:** Every 30 minutes during business hours (8 AM - 6 PM CT), or on demand
- **How:** Johnny loads wiki-schema.md, reads raw/ entries since last compile, reads relevant wiki articles, and writes updates directly. No sub-agents needed.
- **Logs:** Every compile appends to wiki/log.md and posts summary to Ops Log.

### The Query/Analysis Layer

When Austin asks for something:
1. Read wiki/index.md to find relevant articles
2. Read those articles + follow wikilinks to connected articles
3. Synthesize the answer, draft, briefing, or score
4. Optionally file the answer back as a wiki article (compounding loop)

### Sub-Agents

| Agent | Model | Role |
|-------|-------|------|
| **Researcher** | google/gemini-2.5-pro | Web research, competitive intel. Spawned on demand. |
| **Meeting Prep** | google/gemini-2.5-pro | Call briefings. Spawned on demand. Optional — Johnny can do this from wiki. |

Writer and Verifier sub-agents are retired. The compiler handles all wiki writes. The lint cron handles verification.

---

## Cron Schedule

| Cron | Schedule | What |
|------|----------|------|
| **Compile** | Every 30 min, 8 AM – 6 PM CT weekdays | Process raw/ → update wiki/ |
| **Lint** | Daily 8 PM CT | 7 health checks on wiki integrity |
| **Tomorrow's Briefing** | 9 PM CT Sun–Thu | Read wiki → produce briefing |
| **SF Pipeline Sync** | 9:45 PM CT Sun, 10 PM Tue | Read wiki deal articles → diff against SF → push deltas |
| **Skill Evolution** | Wed 9 PM CT | Analyze wiki + patterns → propose improvements |
| **Daily Backup** | 11 PM CT | Git commit + push wiki + raw to GitHub |

---

## Workspace Structure

```
~/.openclaw/workspace/
├── raw/                    # Immutable daily input logs
│   ├── 2026-04-08.md
│   └── ...
├── wiki/                   # LLM-owned compiled knowledge
│   ├── index.md            # Master catalog — loaded every session
│   ├── log.md              # Compiler changelog
│   └── [flat .md files]    # Articles — deals, people, concepts, patterns, etc.
├── clearwater/
│   └── feeds/              # Dedup ledger + outbound tracking
│       ├── .processed-inputs.jsonl
│       └── outbound-tracking.jsonl
├── scores.jsonl            # Scoring results (P2V2C2, deal health, etc.)
├── SOUL.md
├── FEED-RULES.md
├── AGENTS.md
├── HEARTBEAT.md
├── wiki-schema.md          # Full compilation schema — loaded on compile
├── USER.md
├── TOOLS.md
└── MEMORY.md
```

---

## Key Technical Details

- Johnny bot: @johnny_forsyth_bot
- Johnny's MBP: austinholland@100.122.212.128 (Tailscale)
- Gateway: http://127.0.0.1:18789
- Gateway token: f18f7ebeb4a20e270fb7e859372441b1f087da793d65a14f
- Default model: anthropic/claude-opus-4-6
- Sub-agent model: google/gemini-2.5-pro
- Ops Log chat_id: -5205161230
- Austin DM chat_id: 6461072413
