# /prompt-building — Input-Output Batch Mapper for Johnny

## Overview

This command sets up an interactive HTML-based batch mapper tool for mapping Johnny's inputs (emails, Teams messages, calendar events) to their corresponding outputs (files to update, tasks to create, etc.).

The tool helps build ground-truth training data for creating intelligent prompts that automate Johnny's response generation.

## What It Does

1. **Displays inputs chronologically** — All inputs sorted by time (earliest first)
2. **Shows full input details** — When you click an input, see all the information Johnny would see
3. **Maps inputs to outputs** — For each input, view/edit what files should be updated
4. **Batch selection** — Group multiple inputs together and map them as a unit
5. **Refresh function** — Reset to the earliest input anytime

## Files Involved

```
/Users/austinhollsnd/Desktop/johnny-ops/
├── batch-mapper.html           (Main HTML app)
├── input-output-chronological.html  (Alternative chronological view)
├── input-output-map.md         (Ground truth data file)
└── scoreboard.html             (Stats dashboard)
```

## How to Run

### Start the HTTP Server

```bash
cd /Users/austinhollsnd/Desktop/johnny-ops/
python3 -m http.server 8889 > /tmp/local-server.log 2>&1 &
```

### Open in Browser

```
http://localhost:8889/batch-mapper.html
```

## Architecture

### Data Structure

The batch mapper uses:

1. **Inputs Array** — Each input has:
   - `id` — unique identifier (INPUT-001, etc.)
   - `time` — timestamp (format: "2026-04-01 08:32 AM CT")
   - `from` — sender
   - `type` — "email", "teams", or "calendar"
   - `subject` — subject line
   - `preview` — body content preview

2. **Input-Output Map** — Dictionary mapping input IDs to outputs:
   ```javascript
   inputOutputMap["INPUT-001"] = [
       { desc: "Update memory", file: "memory/2026-04-01.md", condition: "always" },
       { desc: "Create event", file: "ops/events/index.md", condition: "always" }
   ]
   ```

### Key Functions

- **resetToEarliest()** — Load earliest input, clear selection
- **toggleInputSelection(inputId)** — Select/deselect input and show details
- **showFullInputDetails(inputId)** — Display all input metadata
- **showInputOutputs(inputId)** — Show outputs for that input
- **createNewBatch()** — Group selected inputs as a batch
- **saveBatch()** — Save batch mapping to local storage
- **exportAllMappings()** — Export all batches as markdown

## Workflow

1. **Page loads** → Shows earliest input + outputs
2. **Click an input** → See full details + corresponding outputs
3. **Select multiple inputs** → Create a batch
4. **Edit outputs** → Add/remove/modify output mappings
5. **Save batch** → Store the input-output mapping
6. **Refresh** → Reset to earliest, start over

## Adding New Inputs

To add new inputs/outputs, edit the JavaScript section in batch-mapper.html:

```javascript
// Add to inputOutputMap
inputOutputMap["INPUT-NEW"] = [
    { desc: "...", file: "...", condition: "always" }
];

// Add to inputs array
inputs.push({
    id: "INPUT-NEW",
    time: "2026-04-01 02:00 PM CT",
    from: "Sender Name",
    type: "email",
    subject: "Subject here",
    preview: "Body preview"
});
```

## Data Flow

```
Johnny's Environment (MBP)
    ↓
Feeds (pa-email-inbound.jsonl, teams-messages.jsonl, etc.)
    ↓
Claude Code (daily driver)
    ↓
batch-mapper.html (HTML app)
    ↓
You (Austin) map inputs → outputs
    ↓
input-output-map.md (ground truth)
    ↓
Build prompts from ground truth
```

## Use Cases

1. **Training data collection** — Capture real input-output pairs from a day's work
2. **Prompt engineering** — Build prompts that can replicate the mappings you define
3. **Skill development** — Create skills/workflows based on observed patterns
4. **Audit trail** — Document what Johnny should do for each input type

## Next Steps (From Here)

1. Load real inputs from Johnny's feeds (pa-email-inbound.jsonl, teams-messages.jsonl, etc.)
2. Map them to actual outputs you want Johnny to perform
3. Export mappings as markdown to input-output-map.md
4. Use those mappings to write/refine prompts
5. Iterate with feedback loops

## Related Files

- `/Users/austinhollsnd/.claude/commands/orchestrate-johnny.md` — Main build plan for Johnny
- `/Users/austinhollsnd/Desktop/johnny-ops/input-output-map.md` — Ground truth mappings
- `~/.openclaw/workspace/HEARTBEAT.md` — Johnny's heartbeat/cron config
- `~/.openclaw/workspace/clearwater/hyperagent/skills/` — Skill definitions

## Browser Console Debugging

If inputs don't load or refresh doesn't work:

1. Open browser DevTools (F12)
2. Go to Console tab
3. Look for `console.log()` output
4. Check for JavaScript errors (red text)

## Session State

The batch mapper stores state in browser memory only. To persist:

- Click "Export All Mappings" to copy to clipboard
- Paste into `input-output-map.md` or save elsewhere
- Refresh page = clears all unsaved batches

## Technical Notes

- Uses vanilla JavaScript (no frameworks)
- Runs client-side only (no server backend)
- Time parsing: "2026-04-01 08:32 AM CT" format
- Sorting by time: converts to ISO for comparison
- Responsive grid layout (HTML5/CSS3)

---

**Created:** 2026-04-02
**Status:** Active development
**Owner:** Claude Code on Austin's daily driver
