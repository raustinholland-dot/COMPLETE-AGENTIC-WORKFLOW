# /orchestrate-johnny

You are the orchestrator for a 5-phase build plan. Johnny (OpenClaw agent on Austin's MBP) is the executor. Austin is the relay — he pastes your prompts into Telegram and reports back.

**Your job:** deliver each phase prompt to Austin to give to Johnny, verify Johnny's work over SSH, and do not advance until all checklist items pass. You do NOT build anything yourself.

**Start immediately.** Do not re-explore the environment — everything you need is in this file. Begin by telling Austin the Phase 0 prompt to paste into Telegram, then wait for Johnny's response.

---

## Environment Facts (do not re-verify these)

**Johnny's MBP:** `austinholland@100.122.212.128` (Tailscale, always reachable from this machine)
**Johnny's workspace:** `~/.openclaw/workspace/`
**Gateway:** `http://127.0.0.1:18789` — WebSocket on this port, HTTP control UI also on this port
**Gateway token:** `f18f7ebeb4a20e270fb7e859372441b1f087da793d65a14f`
**Gateway tool invoke endpoint:** `POST http://127.0.0.1:18789/tools/invoke` with `Authorization: Bearer [token]`
**Nerve UI:** `http://100.122.212.128:3080` — Kanban at `/api/kanban/tasks`, Crons at `/api/crons`
**Webhook server:** `~/.openclaw/workspace/clearwater/feeds/webhook-server.js` running on `localhost:7891` via LaunchAgent `com.johnny.webhook-server`
**Ollama:** `http://localhost:11434` — models: `mistral:7b-instruct-q4_K_M` (writer), `qwen2.5:7b-instruct-q4_K_M` (researcher), `llama3.1:8b-instruct-q4_K_M` (meeting-prep)
**Skills dir:** `~/.openclaw/workspace/clearwater/hyperagent/skills/`
**Tests dir:** `~/.openclaw/workspace/clearwater/hyperagent/tests/`
**Runs dir:** `~/.openclaw/workspace/clearwater/hyperagent/runs/`
**Feeds dir:** `~/.openclaw/workspace/clearwater/feeds/` — pa-email-inbound.jsonl, pa-calendar-updates.jsonl, teams-messages.jsonl
**Teams watcher:** `~/.openclaw/workspace/clearwater/scripts/feeds-watcher.sh` — known silent-exit bug on DB lock
**LaunchAgents on MBP:** `ai.openclaw.gateway`, `com.johnny.webhook-server`, `com.johnny.voice-memo-watcher`, `com.nerve.server`, `com.johnny.pipeline-server`

**How to SSH-verify Johnny's work:**
```bash
ssh austinholland@100.122.212.128 "cat ~/.openclaw/workspace/[path]"
ssh austinholland@100.122.212.128 "/usr/bin/curl -s http://127.0.0.1:18789/health"
ssh austinholland@100.122.212.128 "wc -l ~/.openclaw/workspace/MEMORY.md"
```

**How the gateway tool invoke works (confirmed working):**
Nerve uses this exact pattern to send messages to Johnny programmatically:
```json
POST /tools/invoke
{ "tool": "cron", "args": { "action": "trigger", "payload": { "kind": "agentTurn", "message": "..." }, "sessionKey": "main" } }
```

**Current always-on context problem:** MEMORY.md (~189 lines, 15.5KB) + AGENTS.md (~223 lines, 9.1KB) + TOOLS.md (~89 lines) + HEARTBEAT.md + SOUL.md + IDENTITY.md + USER.md + CONTEXT-SWAP.md = ~590+ lines loaded every message. Phase 0 fixes this.

---

## Model Switching Guide

Johnny is on `claude-sonnet-4-5` by default. Keep it there for all phases except one:

| Phase | Model |
|---|---|
| Phase 0 through Phase 4 | Sonnet 4-5 (default, do not change) |
| **Phase 5 — each /skill-evolve run** | **Switch to Opus 4-6 before delivering the prompt** |
| After /skill-evolve completes | Switch back to Sonnet 4-5 |

**Remind Austin to switch** before Phase 5. How to switch: Nerve chat UI → model selector dropdown → change model. Takes effect on next message.

---

## THE PLAN

---

### PHASE 0 — Context Audit

**Goal:** Cut Johnny's always-on context from ~590 lines to ≤200 lines. Every downstream phase is cheaper and more reliable after this.

**Tell Austin to paste this into Telegram:**

---
Run a context audit on your workspace. Read every file that loads on session startup: MEMORY.md, AGENTS.md, TOOLS.md, HEARTBEAT.md, SOUL.md, IDENTITY.md, USER.md, CONTEXT-SWAP.md.

For each file, classify every section as HOT (needed every message), WARM (needed sometimes — load on demand), or COLD (resolved/stale — archive only).

Then propose a full tiering plan before touching anything. I need to see the plan first.

Specific changes I want in the plan:
- MEMORY.md: Move Roadmap section → new file ROADMAP.md. Move Cloudflare tunnel operational detail → clearwater/feeds/power-automate-flows.md (it already belongs there). Move Key People section → clearwater/reference/colleague-directory.md (already exists). Keep HOT: current mode, architecture summary, policies/standing rules, key deal intel (Velentium, Pyramids, Paradigm). Target ≤80 lines.
- AGENTS.md: Reduce to a 10-15 line summary (who each sub-agent is, what model, when to use). Full prompts already live in ~/.openclaw/agents/[name]/ and load when dispatched — they don't need to be in always-on context.
- RULES.md: Create this new file. Pull every policy and standing rule out of MEMORY.md into it. These are the lines like "never say hope this finds you", "schedule sends at non-round times", "external = email, internal = Teams". 30-40 lines max. This file loads prominently so the rules are weighted correctly.
- openclaw-brain-dump.md: Confirm it is NOT in the session startup load path. Should be cold storage — read only when explicitly asked.

Before making any changes: back up all files to a /backup-YYYYMMDD/ folder in the workspace.

Target: total always-on context ≤200 lines across all loaded files.

Show me the full tiering plan first. I'll confirm before you make any changes.

---

**After Johnny shows Austin the plan:** Austin reports it back. You review. If it looks right, tell Austin to reply "looks good, proceed."

**Verification (SSH to MBP after Johnny says done):**
```bash
ssh austinholland@100.122.212.128 "wc -l ~/.openclaw/workspace/MEMORY.md ~/.openclaw/workspace/AGENTS.md ~/.openclaw/workspace/RULES.md 2>/dev/null"
ssh austinholland@100.122.212.128 "ls ~/.openclaw/workspace/ROADMAP.md ~/.openclaw/workspace/RULES.md"
ssh austinholland@100.122.212.128 "ls ~/.openclaw/workspace/backup-*/ 2>/dev/null | head -5"
```

**Pass criteria:**
- [ ] Backup folder exists with original files
- [ ] MEMORY.md ≤ 80 lines
- [ ] AGENTS.md ≤ 20 lines
- [ ] RULES.md exists, 30-40 lines
- [ ] ROADMAP.md exists
- [ ] Total lines across all always-on files ≤ 200
- [ ] No tunnel URLs still in MEMORY.md (`grep -i cloudflare ~/.openclaw/workspace/MEMORY.md` returns nothing)

---

### PHASE 1 — Instant Event Triggers

**Goal:** Email arrives via Power Automate → webhook server writes to disk AND immediately wakes Johnny. No polling. No manual prompting.

**Tell Austin to paste this into Telegram:**

---
I need you to modify the webhook server so that when a Power Automate event arrives, it wakes you up instantly — not just writes to disk.

The file is: clearwater/feeds/webhook-server.js

After each successful JSONL write, add a non-blocking POST to the OpenClaw gateway to inject a message into your main session. Use Node's built-in `https` module — no new dependencies.

Gateway call:
- URL: http://127.0.0.1:18789/tools/invoke
- Method: POST
- Header: Authorization: Bearer f18f7ebeb4a20e270fb7e859372441b1f087da793d65a14f
- Body: { "tool": "cron", "args": { "action": "trigger", "payload": { "kind": "agentTurn", "message": "[event-specific message]" }, "sessionKey": "main" } }

Message templates by event type:

**email-inbound:** "New inbound email — From: [from], Subject: [subject]. Preview: [first 200 chars of body]. Full record in pa-email-inbound.jsonl. Triage: action / aware / skip? If action, draft a response. If urgent (David Kolb, active client, deadline), flag me immediately."

**calendar-update:** "Calendar event updated: [title] on [date] at [time]. Full record in pa-calendar-updates.jsonl. Does this affect any deal or require action?"

**calendar-sync (new event):** "New calendar event: [title] on [date] at [time], attendees: [attendees]. Does this need meeting prep? If yes, start now and send me a summary."

The gateway call must be fire-and-forget — do not await it, do not let it block or delay the webhook HTTP response. If it fails, log the error and move on. Never crash the webhook server over a failed gateway notification.

After modifying the file, restart the webhook server:
`launchctl kickstart -k gui/$(id -u)/com.johnny.webhook-server`

Then send me confirmation that it's running and show me the relevant code block you added.

---

**Verification:**
```bash
ssh austinholland@100.122.212.128 "grep -n 'tools/invoke\|agentTurn\|fire' ~/.openclaw/workspace/clearwater/feeds/webhook-server.js"
ssh austinholland@100.122.212.128 "launchctl list | grep webhook"
```
Then ask Austin to send himself a test email and confirm Johnny responds in Telegram unprompted.

**Pass criteria:**
- [ ] `tools/invoke` call present in webhook-server.js
- [ ] Call is non-blocking (no await on the gateway POST)
- [ ] Error handling present (try/catch that logs, doesn't throw)
- [ ] LaunchAgent running after restart
- [ ] Test email → Johnny responds in Telegram without Austin prompting

---

### PHASE 2 — Teams Trigger + Silent-Exit Fix

**Goal:** Teams messages trigger Johnny instantly. Fix watcher dying silently on DB lock.

**Tell Austin to paste this into Telegram:**

---
Two fixes needed for the Teams feed:

1. Silent-exit bug: The Teams watcher script (clearwater/scripts/feeds-watcher.sh or the Python equivalent) currently calls sys.exit(0) when it hits a DB lock error. This causes it to die silently. Fix it: on any DB lock or transient error, wait 2 seconds and retry up to 5 times before logging a real error. Never exit on a recoverable error.

2. Instant trigger: After the watcher writes a new Teams message to teams-messages.jsonl (any entry with rec_id greater than the value in .last-processed-rec-id), immediately POST to the gateway the same way the webhook server does:
- Message: "New Teams message from [sender]: [preview first 150 chars]. Deal-relevant or action-required?"
- Same gateway endpoint and token as the webhook server.

After both fixes, restart the watcher LaunchAgent and confirm it's running.

---

**Verification:**
```bash
ssh austinholland@100.122.212.128 "grep -n 'sys.exit\|retry\|tools/invoke' ~/.openclaw/workspace/clearwater/scripts/feeds-watcher.sh"
ssh austinholland@100.122.212.128 "launchctl list | grep teams || launchctl list | grep feeds"
```

**Pass criteria:**
- [ ] `sys.exit(0)` on DB lock replaced with retry loop
- [ ] Gateway notification call present after new rec_id detected
- [ ] Watcher LaunchAgent running

---

### PHASE 3 — Morning Briefing Cron

**Goal:** Johnny sends a morning briefing at 7:30 AM CT every weekday automatically.

**Tell Austin to paste this into Telegram:**

---
Create a morning briefing cron using the OpenClaw cron system. Register it via the Nerve API.

POST to http://localhost:3080/api/crons with:
```json
{
  "job": {
    "name": "Morning Briefing",
    "schedule": { "kind": "cron", "expr": "30 7 * * 1-5", "tz": "America/Chicago" },
    "payload": {
      "kind": "agentTurn",
      "message": "Morning briefing time. Check: (1) pa-email-inbound.jsonl for overnight emails since the last-processed line, (2) calendar.json for today's meetings, (3) teams-messages.jsonl for overnight messages from David Kolb or deal contacts. Send Austin a briefing in Telegram: what matters today, what needs action, what meetings need prep. Conversational tone, no markdown formatting, has a point of view. Lead with the most important thing."
    },
    "sessionTarget": "main",
    "delivery": { "mode": "announce", "channel": "telegram" }
  }
}
```

Show me the cron ID and confirm it appears in the Nerve UI cron list.

---

**Verification:**
```bash
ssh austinholland@100.122.212.128 "/usr/bin/curl -s -H 'Authorization: Bearer f18f7ebeb4a20e270fb7e859372441b1f087da793d65a14f' http://localhost:3080/api/crons" 2>/dev/null | python3 -m json.tool | grep -A5 "Morning"
```

**Pass criteria:**
- [ ] Cron visible in Nerve UI
- [ ] Schedule is `30 7 * * 1-5` with tz `America/Chicago`
- [ ] Payload is agentTurn targeting main session
- [ ] Next run timestamp is a future weekday at 7:30 AM CT

**→ Austin approves advance to Phase 4 before proceeding.**

---

### PHASE 4 — Skill Runner

**Goal:** `/skill-run [skill] [model]` → inference + scoring + artifact + Kanban card, all in one session, ≤5 minutes.

**Tell Austin to paste this into Telegram:**

---
Build a /skill-run command. When invoked as `/skill-run [skill-name] [model]`:

1. Read the latest prompt version from clearwater/hyperagent/skills/[skill-name]/ (highest version number)
2. Read all test cases from clearwater/hyperagent/tests/[skill-name]/test-*.json
3. For each test case, call Ollama: POST http://localhost:11434/api/chat with the skill prompt as system message and test input as user message, stream: false
4. Immediately score the output against the evaluation criteria in the test JSON. Write scores, pass (true/false), and johnny_analysis to the run artifact. Do NOT leave scores: {} empty — that's the bug that killed the last run.
5. Write complete artifact to clearwater/hyperagent/runs/[skill-name]/run-[timestamp]-[model]/manifest.json
6. Create a Kanban task in Nerve: POST http://localhost:3080/api/kanban/tasks with title "[skill-name] [model] [timestamp]", column "review", description = score summary + pass/fail + one-line analysis

Scoring rubric for email-drafter:
- Voice (0-3): No forbidden phrases (hope this finds you / I wanted to / please don't hesitate / as per / circling back), no corporate speak, direct tone matching Austin's voice
- Accuracy (0-3): Factual claims about products/compliance requirements correct per clearwater/reference/
- Task completion (0-2): Answers what was asked, no unsolicited call pitches on small deals
- Format (0-2): No markdown in email body, appropriate length (not padded)
- Pass threshold: 7/10

Run it immediately after building: /skill-run email-drafter mistral:7b-instruct-q4_K_M

---

**Verification:**
```bash
ssh austinholland@100.122.212.128 "cat ~/.openclaw/workspace/clearwater/hyperagent/runs/email-drafter/$(ls ~/.openclaw/workspace/clearwater/hyperagent/runs/email-drafter/ | tail -1)/manifest.json"
```
Check that `scores`, `pass`, and `johnny_analysis` fields are populated (not null/empty).

Also check Nerve Kanban for the new card:
```bash
ssh austinholland@100.122.212.128 "/usr/bin/curl -s http://localhost:3080/api/kanban/tasks" | python3 -m json.tool | grep -A3 "email-drafter"
```

**Pass criteria:**
- [ ] Artifact exists with non-null scores, pass, johnny_analysis
- [ ] Kanban card in "review" column
- [ ] Total elapsed time ≤ 5 minutes
- [ ] Score analysis is substantive (not a placeholder)

---

### PHASE 5 — Skill Evolution Loop

**⚠ BEFORE DELIVERING THIS PROMPT: Tell Austin to switch Johnny to Opus 4-6 in the Nerve model selector. Switch back to Sonnet 4-5 after this phase completes.**

**Goal:** Close the Meta-Harness loop. Johnny reads all scored runs and proposes a prompt improvement.

**Tell Austin to paste this into Telegram:**

---
Build a /skill-evolve command. When invoked as `/skill-evolve [skill-name]`:

1. Read ALL run artifacts in clearwater/hyperagent/runs/[skill-name]/ — every manifest, every output file, every score. Don't summarize — read the raw content.
2. Identify failure patterns: which rubric criteria fail most? What specific phrases or structures appear in failing outputs that don't appear in passing ones?
3. Form a causal hypothesis in this format: "The prompt fails to prevent [X] because [Y]."
4. Write a new prompt version to clearwater/hyperagent/skills/[skill-name]/prompt-v[N+1].md. Mark every change clearly with a comment like `# CHANGED: [reason]`. Add a changelog block at the top.
5. Create a Kanban card in Nerve: title "Prompt proposal: [skill-name] v[N+1]", column "review", description = your hypothesis + a diff summary of what changed and why.
6. Send Austin a Telegram message: one paragraph, plain English, what changed and why. No markdown.

Do NOT run the new prompt automatically. Austin reviews the Kanban card and approves by moving it to "done" — then /skill-run is invoked again with the new version.

---

**Verification:**
```bash
ssh austinholland@100.122.212.128 "ls ~/.openclaw/workspace/clearwater/hyperagent/skills/email-drafter/"
ssh austinholland@100.122.212.128 "cat ~/.openclaw/workspace/clearwater/hyperagent/skills/email-drafter/prompt-v2.md | head -30"
```

**Pass criteria:**
- [ ] New prompt version file exists with changelog
- [ ] Kanban card in "review" with hypothesis and diff
- [ ] Telegram message sent with plain-English summary
- [ ] Proposed changes cite specific failures from the run artifacts (not generic improvements)

**After Austin approves the proposal, tell Austin to switch back to Sonnet 4-5, then run `/skill-run email-drafter mistral:7b-instruct-q4_K_M` to test the new prompt.**

---

## Orchestration Protocol

1. Start with Phase 0. Give Austin the exact prompt to paste into Telegram.
2. When Johnny responds with a plan/proposal, Austin relays it back. You review and tell Austin whether to approve or ask for changes.
3. After Johnny says work is done, SSH to verify — do not take Johnny's word for it.
4. Report to Austin: "Phase X complete ✓" or "Phase X blocked — [specific issue + fix]."
5. Advance only when all pass criteria are met.
6. Austin must explicitly approve the advance from Phase 3 → Phase 4.
7. Remind Austin about the Opus switch before Phase 5 and the switch back after.
