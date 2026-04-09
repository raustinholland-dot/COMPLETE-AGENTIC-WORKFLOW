# FEED-RULES.md — Capture + Triage

This file governs how feed channel inputs are handled. The wiki schema (`wiki-schema.md`) governs how knowledge is compiled.

---

## When an Input Arrives in Any Feed Channel

### 1. DEDUP CHECK
- Hash the input, check `clearwater/feeds/.processed-inputs.jsonl`
- If duplicate → DM Austin "Already processed" + `NO_REPLY` in feed. Stop.

### 2. CAPTURE
- Append to `raw/YYYY-MM-DD.md` in this format:

```
---
[channel] HH:MM CT
from: [sender]
to: [recipient if applicable]
subject: [if email]
---

[full verbatim text — preserve everything including signatures, disclaimers, typos]
```

- Log hash to `.processed-inputs.jsonl`

### 3. TRIAGE

**URGENT** if ANY of:
- Client or prospect asking a direct question or requesting action
- Meeting in less than 24 hours that needs prep
- Deal status change (budget approved, SOW signed, close, loss)
- Austin explicitly says "need this now" or "urgent"

**NORMAL** — everything else.

### 4. IF URGENT
- Read relevant `wiki/` articles (check `wiki/index.md` first)
- If there are uncompiled raw inputs relevant to this topic, compile them into the wiki first (quick targeted compile)
- Draft response or action inline in Austin's DM
- Post to Ops Log: `CAPTURE + TRIAGE: URGENT + DRAFT`

### 5. IF NORMAL
- One-line ack to Austin's DM: "Captured [brief summary]. Will compile."
- Post to Ops Log: `CAPTURE + TRIAGE: NORMAL`

---

## Email Thread Parsing

When an email thread arrives:
1. Read the newest message first — that's usually the new information
2. Skip boilerplate: signatures, disclaimers, legal footers, forwarding headers
3. Check wiki for existing deal/person articles before re-analyzing older messages in the thread
4. Only capture genuinely new information — don't re-capture what the wiki already knows

---

## What This File Does NOT Cover

- **Compilation** — handled by the compile cron using `wiki-schema.md`
- **Scoring** — handled by the analysis/query layer on demand
- **Drafting** — handled on demand when Austin asks or when triage flags urgent
- **Salesforce updates** — handled by the SF sync cron reading from the wiki
- **Verification** — the compile step is self-verifying; the lint cron checks wiki integrity

The pipeline is: **capture → compile → query/act**. This file handles capture only.
