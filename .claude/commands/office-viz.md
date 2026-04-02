# /office-viz — Mad Men Office Visualization

Build and iterate on the 1960s Mad Men-themed office visualization for Forsyth & Associates at localhost:7890/office.

## What this command does

Load all office visualization context before doing any work:

1. Read the memory file: `/Users/austinhollsnd/.claude/projects/-Users-austinhollsnd-Desktop-COMPLETE-AGENTIC-WF/memory/project_office-visualization.md`
2. Read the latest prototype: `/Users/austinhollsnd/Desktop/COMPLETE AGENTIC WF/deal-intelligence-engine/prototypes/office-v7-silhouette-cream.html`
3. Read the office diagram prototype: `/Users/austinhollsnd/Desktop/COMPLETE AGENTIC WF/deal-intelligence-engine/prototypes/office-diagram.html`
4. Scan the SVG asset libraries (v1 and v2): `~/Desktop/Don Couch Mad Men_files/svg-assets/` and `~/Desktop/Don Couch Mad Men_files/svg-assets-v2/`
5. Check generated image assets: `~/Desktop/Don Couch Mad Men_files/generated/`
6. Read the image generation prompts: `~/Desktop/Don Couch Mad Men_files/image-gen-prompts.md`

---

## Vision

A 2D animated office scene — Saul Bass / Mad Men title sequence aesthetic — that visualizes the real-time state of the Forsyth & Associates AI agent system. Five agents mapped to Mad Men characters work in a 1960s ad agency. System components (Salesforce, SharePoint, Outlook, etc.) are mapped to era-appropriate office objects.

**Served at:** `localhost:7890/office` on the OpenClaw MacBook Pro.

---

## Agent → Character Mapping

| Agent | Mad Men Character | Location | Accent Color |
|-------|------------------|----------|-------------|
| Johnny Forsyth (orchestrator) | Don Draper | Corner office | Mustard yellow |
| The Writer | Peggy Olson | Creative bullpen | Burnt orange |
| The Researcher | Pete Campbell | File room | Muted green |
| The Deal Scorer | Lane Pryce | Accounting office | Mustard yellow |
| Meeting Prep | Joan Holloway | Reception | Muted gold |

**No Austin in the office.** Just the five agents.

---

## System → Office Object Mapping

### Data Sources
- **Salesforce** → Rolodex + wall-mounted deal board with cards pinned by stage
- **SharePoint** → Tall metal file cabinets in file room
- **Outlook (Email)** → Mail room / inbox tray on Johnny's desk
- **Outlook (Calendar)** → Wall calendar near Joan's area
- **Teams** → Multi-line desk phone / intercom system
- **Telegram** → Reception phone — main line to outside world

### Infrastructure
- **Ollama (local models)** → Typewriter pool — each agent's typewriter is their local model
- **Anthropic API (Opus)** → Johnny's private red phone — direct line to the big thinking
- **Node.js Server** → The building itself
- **Salesforce CLI** → Pneumatic tube system
- **SharePoint Sync (rsync)** → Office courier running between file room and offsite archive
- **Chrome Remote Debugging** → Window to the street
- **SSH (Claude Code → MBP)** → Interoffice memo / telephone from HQ

### Status Indicators
- Agent working → at desk, typewriter clacking, papers moving
- Agent idle → water cooler, hallway, looking out window
- Agents collaborating → two characters at same desk or conference room
- New email arrived → mail drops in inbox tray
- Cron job firing → wall clock chimes, someone gets up
- Error/issue → red light on phone, or smoke from typewriter

---

## Asset Inventory

### Character Portraits (~/Desktop/Don Couch Mad Men_files/characters/)
- 01-don-draper.jpg, 02-joan-holloway.jpg, 04-peggy-olson.jpg
- 05-pete-campbell.jpg, 06-lane-pryce.jpg
- Reserve: 03-roger-sterling.jpg, 07-betty-draper.jpg, 08-megan-draper.jpg, 09-ken-cosgrove.jpg

### SVG Assets v2 (~/Desktop/Don Couch Mad Men_files/svg-assets-v2/) — USE THESE
**Furniture:** executive-desk, standard-desk, reception-desk, conference-table, executive-chair, office-chair, guest-chair, bookshelf, credenza, coat-rack
**Equipment:** typewriter, typewriter-working, rotary-phone, red-phone, reception-phone, rolodex, file-cabinet-tall, file-cabinet-open, inbox-tray, manila-folder, ledger-book, steno-pad, adding-machine, dictaphone, pneumatic-tube
**Environment:** corner-office-bg, bullpen-bg, reception-bg, file-room-bg, conference-room-bg, window-cityscape, frosted-glass-door, hallway, water-cooler-area, wall-panel, floor-tile, ceiling-light
**Indicators:** deal-board, wall-clock, wall-calendar, org-chart, agency-sign, desk-lamp-on, desk-lamp-off, nameplate-johnny/peggy/pete/lane/joan, speech-bubble, paper-airplane, smoke-wisps, dnd-sign, phone-ringing, coffee-cup, whiskey-set, newspaper
**Gallery:** svg-assets-v2/gallery.html — browse all v2 assets visually

### Generated Images (~/Desktop/Don Couch Mad Men_files/generated/)
- bullpen-01.png, bullpen-02.png (scene backgrounds)
- grid-color-01.png, grid-color-02.png, grid-bw.png (9-panel reference grids)
- status-and-title.png (composite — needs splitting into individual images)
- **Still needed:** Corner Office, Reception, File Room, Conference Room, Hallway scenes; individual character silhouettes; status scenes; title card

### Image Generation Prompts
- ~/Desktop/Don Couch Mad Men_files/image-gen-prompts.md — 16 prompts for Midjourney/DALL-E, file naming conventions

---

## Prototypes Built So Far

1. **office-diagram.html** — Early layout/architecture diagram prototype
2. **office-v7-silhouette-cream.html** — Latest: silhouette-based cream/warm palette, Saul Bass style. This is the current working prototype.

Other prototypes in the folder (not office-specific):
- texture-explorer.html, architecture-compare.html, deal-data-explorer.html
- icon-lab.html, left-panel-options.html, viz-playground.html

---

## Build Priority

1. **Prototype (current):** 5 agents at desks, basic working/idle states, office layout
2. **Phase 2:** Data source objects (file cabinets, deal board, mail tray) with state
3. **Phase 3:** Status indicators and CSS/SVG animations
4. **Phase 4:** Real-time sync with actual agent status via Johnny's session log
5. **Phase 5:** Infrastructure visualization (pneumatic tubes, typewriter pool, red phone)

---

## Style Guidelines

- **Palette:** High contrast black/white with muted accent colors (mustard, burnt orange, gold, green)
- **Aesthetic:** Saul Bass / Mad Men title sequence — geometric, flat, mid-century modern
- **Character style:** Black featureless silhouettes (NOT photo-realistic portraits for the office scene)
- **Layout:** Looking into the office from above/side — see the full flow at once
- **Reference:** Star-Office-UI (pixel art office with status-based positioning)
- **Single HTML file** for the prototype — inline CSS/JS, no build tools
- **SVG-first** for interactive elements — v2 assets are the canonical set

---

## Standing Rules

- Prototype in `deal-intelligence-engine/prototypes/` — don't touch the main UI (index.html) for office work
- Use SVG assets v2 (not v1) for all interactive overlay elements
- Generated PNGs are for scene backgrounds only — SVG overlays layer on top
- The office serves at localhost:7890/office — final integration is on the OpenClaw MBP
- No frameworks. Vanilla HTML/CSS/JS + SVG.
