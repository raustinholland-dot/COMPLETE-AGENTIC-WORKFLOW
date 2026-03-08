---
name: deploy
description: >
  Deploy a local workflow JSON file to the live n8n instance. Pulls live state first,
  diffs, pushes via push-workflow.sh, verifies deployment, and checks for escaping
  issues. Use when Austin says to deploy, push, or update a workflow.
argument-hint: "<workflow-filename.json>"
---

# /deploy — n8n Workflow Deploy Loop

Deploy a local workflow JSON to the live n8n instance. Argument: workflow filename (e.g. `workflow-01-ingestion.json`).

## Standing Rules
- **NEVER use n8n MCP tools.** Deploy loop only via push-workflow.sh or direct API calls.
- **Always pull live state BEFORE editing.** Never trust local JSON as source of truth.
- **Check for `\!` escaping issues** in Code node JavaScript after push. The shell can mangle `\!==` — use heredocs for future Code node edits.
- **If push-workflow.sh returns 404**, the workflow ID doesn't exist on the live instance. Use the creation pattern: POST empty workflow → get new ID → push → activate.

## Instructions

Use `$ARGUMENTS` as the workflow filename.

### Step 1: Read the local file

Read the local workflow JSON:
```
/Users/austinhollsnd/Desktop/COMPLETE AGENTIC WF/deal-intelligence-engine/n8n/workflows/$ARGUMENTS
```

Extract the workflow name from the JSON.

### Step 2: Identify the workflow ID

Look up the workflow ID using this mapping from MEMORY.md:

| File pattern | Workflow ID |
|---|---|
| workflow-01 | G6kZgyHCK0qHNhRj |
| workflow-02 | oOnzLBeQzu5M7nc4 |
| workflow-3a | ZS64jSadlOIPrert |
| workflow-3b | (check file) |
| workflow-3c | XDTSkxxWtZUBDECT |
| workflow-3d | bDE8s1e7bhPzvbpi |
| workflow-3e | K2i48dUP1MgYXQzA |
| workflow-04 | ZS64jSadlOIPrert |
| workflow-05-calendar | ZT0b4KVNggCp7XjX |
| workflow-06-salesforce | TBHuUQFya252wZXL |
| workflow-06-db-query | lLBrmwzHelkLW82x |
| workflow-06-get-deals | h2CrtDQx4fUp4c7v |
| workflow-07 | SYAQ4eVPyrp9XQMa |
| workflow-16 | 8ygX3a6Qr6fTsG8K |
| workflow-18 | 8CVEUtlemuihJhdA |
| workflow-19 | hiVtJY4I9UL82yKW |

If the file doesn't match any known pattern, check the JSON for an `id` field, or ask Austin.

### Step 3: Pull the LIVE workflow

```bash
N8N_API_KEY=$(grep N8N_API_KEY /Users/austinhollsnd/Desktop/COMPLETE\ AGENTIC\ WF/deal-intelligence-engine/.env | cut -d= -f2)
curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" http://localhost:5678/api/v1/workflows/<ID>
```

Compare local vs live:
- Node count difference
- List any nodes added, removed, or with changed parameters
- Report key differences concisely

### Step 4: Push the workflow

```bash
bash /Users/austinhollsnd/Desktop/COMPLETE\ AGENTIC\ WF/deal-intelligence-engine/scripts/push-workflow.sh /Users/austinhollsnd/Desktop/COMPLETE\ AGENTIC\ WF/deal-intelligence-engine/n8n/workflows/$ARGUMENTS
```

If push-workflow.sh returns a 404 error, use the creation pattern:
```bash
# Create empty workflow
curl -s -X POST -H "X-N8N-API-KEY: $N8N_API_KEY" -H "Content-Type: application/json" http://localhost:5678/api/v1/workflows -d '{"name":"<workflow-name>","nodes":[],"connections":{}}'
# Get the new ID from the response, then push again
```

### Step 5: Verify deployment

Wait 3 seconds for n8n to restart/reload, then re-pull the live workflow:

```bash
curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" http://localhost:5678/api/v1/workflows/<ID>
```

Verify:
- Node count matches local file
- Key changed nodes are present in live version
- Workflow is active

### Step 6: Check for escaping issues

After push, scan Code nodes in the live workflow for corrupted JavaScript — specifically `\!==` which should be `!==`. If found, report the affected node names.

### Step 7: Report

Confirm deployment with a one-line summary:
> Deployed **<workflow name>** (ID: <ID>). <N> nodes, verified live. [Active/Inactive]

If any issues were found (escaping, node count mismatch, inactive status), list them.
