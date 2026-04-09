# Wiki Schema — Personal Knowledge Base

This document defines how the wiki is built and maintained. It is the authoritative reference for the compiler (which builds the wiki from raw inputs) and the query layer (which reads the wiki to produce analysis and outputs).

---

## What This Is

A personal knowledge base for a B2B sales executive managing a large, multi-deal pipeline in healthcare cybersecurity, compliance, and risk management. The wiki captures everything the user encounters professionally: deals, people, internal projects, competitive intelligence, product knowledge, coaching themes, industry trends, and operational patterns.

The system has three layers:

1. **Raw inputs** (`raw/`) — verbatim daily logs of everything that came in. Never modified.
2. **Wiki articles** (`wiki/`) — the compiler's synthesis of raw inputs into durable, cross-referenced knowledge. Flat directory of markdown files.
3. **Query/analysis layer** — separate prompts that read from the wiki to produce scored outputs, drafted emails, call prep, pipeline reviews, and Salesforce updates. These apply methodology; the wiki stores knowledge.

The compiler is the only process that writes to the wiki. It runs periodically, reads new raw inputs alongside the existing wiki, and decides what to create, update, or connect.

---

## Raw Inputs

### Format

Daily log files at `raw/YYYY-MM-DD.md`. Each file is an append-only chronological record of everything received that day.

### Input Channels

Inputs arrive through four channels. Each entry in the daily log is tagged with its source:

```markdown
---
[email] 12:43 PM
from: Brian Chao <brian.chao@exerurgentcare.com>
to: Austin Holland <austin.holland@clearwatersecurity.com>
cc: Marie Lange
subject: Re: Clearwater - Risk Analysis, Pen Test & Phishing
---

[verbatim email body, including signatures and disclaimers]

---
[teams] 2:15 PM
from: David Kolb
chat: PPM Pipeline
---

[verbatim Teams message]

---
[call] 3:30 PM
participants: Austin Holland, Rick Fincham (PantherRx), Jessica (PantherRx)
duration: 28 min
source: voice-to-text
---

[verbatim transcript, including speaker labels where available]

---
[calendar] 4:00 PM
event: Exer Catch-Up Call
time: 2026-04-09 11:30 AM PT
attendees: Austin Holland, Brian Chao, Marie Lange
---

[any notes or agenda attached]
```

### Rules

- Raw files are never modified after the day ends. During the day, new entries are appended.
- Preserve everything verbatim: email signatures, disclaimers, transcript filler, typos. The compiler decides what matters.
- If the same email thread appears multiple times (forwarded at different points), log each instance. The compiler handles deduplication.

---

## Wiki Articles

### File Format

Every wiki article is a markdown file with YAML frontmatter, stored flat in `wiki/`. No subdirectories.

```markdown
---
title: [Human-readable title]
type: [deal | person | org | project | concept | product | pattern | event]
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources: [list of raw input dates and entries that contributed]
related: [list of other wiki article filenames]
tags: [freeform tags for discoverability]
status: [active | closed | historical | stub]
---

# Title

[Article body — structured markdown. No prescribed internal structure.
The compiler decides how to organize each article based on what
the knowledge requires.]
```

### Frontmatter Fields

| Field | Required | Description |
|-------|----------|-------------|
| `title` | yes | Human-readable name |
| `type` | yes | Article type (see below) |
| `created` | yes | Date first created |
| `updated` | yes | Date last modified |
| `sources` | yes | Which raw inputs contributed to this article |
| `related` | yes | Filenames of connected articles (bidirectional — both sides should list each other) |
| `tags` | no | Freeform tags. Use for discoverability, not taxonomy. |
| `status` | yes | `active` (current, maintained), `closed` (terminal state reached — deal won/lost, project complete), `historical` (kept for pattern value), `stub` (exists but thin — needs more inputs) |

### Article Types

| Type | What it represents | Examples |
|------|--------------------|----------|
| `deal` | An external sales opportunity with a customer or prospect | `exer-urgent-care.md`, `paradigm-health-pp.md` |
| `person` | An individual the user interacts with professionally | `brian-chao.md`, `david-kolb.md` |
| `org` | A company, PE firm, or organizational entity | `pantherrx.md`, `cressey-co.md` |
| `project` | An internal initiative with a lifecycle | `nashville-strategy.md`, `pe-targeting-refresh.md` |
| `concept` | Persistent knowledge about a topic, product, framework, or market | `knowbe4-aida.md`, `hipaa-enforcement-trends.md` |
| `product` | A Clearwater product or service offering | `managed-security-services.md`, `vciso.md` |
| `pattern` | A cross-cutting insight drawn from multiple sources | `champion-access-patterns.md`, `sow-redline-delays.md` |
| `event` | A conference, meeting series, or calendar-anchored occurrence | `mcguire-woods-event.md` |

The compiler is not limited to these types. If a new type is warranted, use it and document it in the index.

### Wikilinks

Use `[[filename]]` (without `.md` extension) to link between articles. These are Obsidian-compatible.

```markdown
Discussed pricing with [[brian-chao]] on the [[exer-urgent-care]] deal.
[[david-kolb]] flagged this during the Tuesday pipeline call.
See [[managed-security-services]] for the current tier breakdown.
```

Every wikilink should be reciprocal: if article A links to article B, article B's `related` frontmatter should include A (and vice versa). The compiler maintains this.

### Filenames

- Lowercase, hyphenated: `brian-chao.md`, `exer-urgent-care.md`
- Descriptive enough to identify without opening: `paradigm-health-mss.md` not `deal-47.md`
- Stable: once created, a filename does not change (wikilinks depend on it)

---

## Index

`wiki/index.md` is the master catalog. The compiler updates it on every pass.

```markdown
---
title: Index
updated: YYYY-MM-DD
---

# Index

## Deals — Active
| Article | Status | Key Contact | Last Touched |
|---------|--------|-------------|--------------|
| [[exer-urgent-care]] | budget confirmed | [[brian-chao]] | 2026-04-08 |

## Deals — Closed
| Article | Outcome | Close Date |
|---------|---------|------------|
| [[dedicated-sleep]] | lost — no contact | 2026-04-06 |

## People
| Article | Org | Role |
|---------|-----|------|
| [[david-kolb]] | Clearwater | VP Sales (PPM) |
| [[brian-chao]] | Exer Urgent Care | Primary contact |

## Organizations
| Article | Sector | Deals |
|---------|--------|-------|
| [[pantherrx]] | Specialty Pharmacy | [[pantherrx-rare]] |

## Projects
| Article | Status | Owner |
|---------|--------|-------|
| [[nashville-strategy]] | in progress | Austin + David A |

## Concepts & Products
| Article | Tags |
|---------|------|
| [[managed-security-services]] | mss, azure, endpoint |
| [[knowbe4-aida]] | phishing, training |

## Patterns
| Article | Derived From |
|---------|-------------|
| [[champion-access-patterns]] | multiple deals |
```

The index uses wikilinks so it functions as a clickable navigation surface. The compiler adds new articles, updates statuses, and removes nothing (closed items move to the appropriate closed/historical section).

---

## Log

`wiki/log.md` is a reverse-chronological record of what the compiler did. **New entries go at the top**, immediately below the frontmatter and `# Compiler Log` heading. Newest first.

**Every log entry must use this exact format:**

```markdown
## YYYY-MM-DD HH:MM — [Label]

**Inputs processed:** [source description]

- UPDATED [[article]] — what changed
- CREATED [[article]] — why
- ENRICHED [[article]] — what was added
- CONNECTED [[article-a]] <-> [[article-b]] — why
- INDEX updated — what changed

---
```

Rules:
- Always `##` heading level (never `###`, never bold text as heading)
- Always a `---` separator after each entry
- New entries inserted at the top, below the `# Compiler Log` heading
- Never append to the bottom of the log

Each log entry records: what raw inputs were processed, what articles were created/updated/connected, and what changed in the index.

---

## Compilation

### When It Runs

Every 30 minutes during business hours (8 AM - 8 PM CT weekdays), or on demand. Each run processes all raw input entries since the last logged compilation timestamp.

### What the Compiler Sees

On every pass, the compiler reads:
1. New raw input entries (since last compile)
2. `wiki/index.md` (full)
3. Any existing wiki articles that are relevant to the new inputs
4. `wiki/log.md` (recent entries, for continuity)

At current scale, the full wiki fits in context. As it grows, the index serves as the navigation layer — the compiler reads the index first, then loads only the articles it needs.

### What the Compiler Does

For each new raw input entry:

1. **Identify what this is about.** People, deals, orgs, projects, concepts. An input can touch multiple articles.

2. **Read existing articles.** Before writing anything, read the current state of every article this input touches. The update must be additive and current.

3. **Update or create articles.** For each distinct piece of new information:
   - If an article exists: update it with the new information, update `sources` and `updated` in frontmatter.
   - If no article exists: **create one.** Bias toward creating. A stub with three lines is cheap; a missed connection six months later is expensive. If it turns out to be noise, the lint process will flag it as an orphan and it gets pruned naturally. If it matters, future inputs will reference it and it becomes a hub. Let the information flow decide what's important — don't try to decide upfront.

4. **Maintain connections.** Add wikilinks between articles that are now related. Update `related` frontmatter on both sides. This is where compound value is created — a pricing email about Exer should link to the Exer deal, the person who sent it, the product being priced, and any competing deal where the same product was discussed.

   **Backlink verification (mandatory):** After creating or updating any article, check every article listed in its `related` field. If the backlink does not exist in that article's `related` field, add it now. Do not defer this to lint. Every compile pass must leave all backlinks consistent.

5. **Update the index.** Add new articles, update statuses, move closed items.

6. **Log what happened.** Append to `wiki/log.md`.

7. **Ledger check.** If you updated a deal article, check whether the change affects any field in the deal's last `scores.jsonl` entry. If so, update that field. If a P2V2C2 dimension may have shifted, note it in the DM compile summary.

### Compiler Judgment Calls

The compiler uses judgment on these questions. The schema does not prescribe answers — it identifies the questions.

**When to create a new article vs. update an existing one:**
- A new person, deal, org, concept, idea, or project mentioned for the first time gets its own article — even as a stub. Capture it. The wiki self-prunes through usage: articles that get referenced and updated survive; articles that don't get flagged by lint and archived.
- The only things that don't warrant an article: purely logistical noise (meeting moved by 15 minutes, email signature blocks, "sounds good" acknowledgments).

**When to merge articles:**
- If two articles are clearly about the same entity (duplicates, name variations), merge into one and update all wikilinks.

**What to extract from messy inputs:**
- Call transcripts are noisy. Extract: decisions made, commitments given, new information revealed, action items, emotional/political signals. Discard filler.
- Email threads contain old messages. Only extract what is new relative to what the wiki already contains.
- Teams messages are brief. Small messages may not warrant any wiki update. Context and judgment.

**How much to write:**
- Articles should be as long as they need to be and no longer. A person article for someone mentioned once might be three lines. A deal article for a $188K opportunity in active negotiation might be a page.
- Prefer facts over summaries. "Brian confirmed budget on 4/6 and requested Gold vs Diamond pricing breakout" is better than "positive momentum on Exer."

---

## Quality Standards

### Minimum Bar for an Article

An article must have:
- Complete, accurate frontmatter
- At least one sentence of substantive content (not just a title)
- At least one wikilink to another article (nothing should be orphaned)
- Accurate `sources` listing

If an article cannot meet this bar, it should be a stub (frontmatter + one-line description) with `status: stub`.

### Factual Accuracy

- Every claim in a wiki article should be traceable to a raw input via the `sources` field.
- When the compiler notices a contradiction between a new input and existing wiki content, it should update the article to reflect the most recent information and note the change. Do not silently overwrite — record what changed and why.
- When information is uncertain or inferred (not stated directly in a raw input), mark it as such: "likely", "appears to be", "based on [context]".

### Staleness

- `updated` in frontmatter tracks when an article was last touched by the compiler.
- The compiler should flag (in the log) any article that is:
  - Referenced by a new input but has not been updated in 30+ days
  - Listed as `active` but has no recent raw input sources
  - A stub that has been a stub for 14+ days
- Flagging is informational. The user or a lint process decides what to do.

### Wikilink Integrity

- Every wikilink must point to an existing article. If the compiler creates a link to something that does not yet exist, it must also create at least a stub for that article.
- The `related` list in frontmatter must be kept in sync with the wikilinks in the body. The compiler maintains this.

---

## Lifecycle

### Active Knowledge

Most articles start as `active`. They are updated as new inputs arrive. Deals, people, projects, concepts — all active while relevant.

### Closing

When a deal is won or lost, or a project completes:
- Update `status` to `closed`
- Add a final entry summarizing outcome, lessons, and key dates
- Move to the closed section of the index
- Do not delete. Closed articles retain their wikilinks and remain searchable.

### Historical Value

Closed articles become historical knowledge:
- Won deals teach what worked: which patterns, which people, which timelines.
- Lost deals teach what broke: where access was lost, what signals were missed.
- Completed projects record what was decided and why.

The compiler may create `pattern` articles that synthesize lessons across multiple closed deals or projects. These are some of the most valuable articles in the wiki.

### Archival

Articles with `status: historical` are never deleted. They may be flagged by lint if they contain stale wikilinks to articles that have changed significantly.

### Evolution

People change roles. Companies get acquired. Products get renamed. The compiler updates articles to reflect current reality. It does not delete the history — it adds to it.

---

## Query Layer Reference

The query/analysis layer is separate from compilation. It reads from the wiki to produce outputs. The schema does not define query prompts, but it defines what the query layer can expect from the wiki.

### What the Query Layer Can Assume

- `wiki/index.md` is a complete, current catalog of all articles with statuses.
- Every article has accurate frontmatter.
- Wikilinks are valid and bidirectional.
- `sources` in frontmatter trace back to specific raw input entries.
- The wiki contains the compiler's best synthesis of all raw inputs to date.
- Raw inputs in `raw/` are available for deeper analysis when wiki articles are insufficient.

### What the Query Layer Should NOT Assume

- That the wiki contains everything from every raw input. The compiler exercises judgment.
- That any particular article structure exists. Articles are free-form below the frontmatter.
- That methodology or scoring is embedded in articles. The query layer applies its own analytical frameworks.

### Common Query Patterns

These are examples of what the query layer does, not prescriptions for how:

- **Deal scoring:** Read a deal article + related person/org articles. Apply a scoring methodology. Cite evidence from the articles.
- **Email drafting:** Read relevant deal/person articles + recent raw inputs. Match the user's actual communication style (short, direct, professional, no corporate filler, "Best," sign-off, uses em dashes, names people directly).
- **Call prep:** Read deal article + attendee person articles + related concept articles. Synthesize into a briefing.
- **Pipeline review:** Read the index for all active deals. Load each deal article. Produce a comparative view.
- **Pattern recognition:** Read multiple deal or person articles. Identify cross-cutting themes.

---

## File Tree

```
raw/
  2026-04-07.md
  2026-04-08.md
  ...

wiki/
  index.md          # master catalog
  log.md            # compiler changelog
  exer-urgent-care.md
  brian-chao.md
  david-kolb.md
  paradigm-health-pp.md
  paradigm-health-mss.md
  pantherrx-rare.md
  managed-security-services.md
  nashville-strategy.md
  ...
```

No subdirectories within `wiki/`. The index and wikilinks provide all the structure needed.
