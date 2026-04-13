#!/bin/bash
# write-metrics.sh — Collect pipeline metrics and write a run file for Obsidian.
#
# Gathers:
#   - Triage: from .tmp-metrics-triage.json + openclaw sessions (Opus tokens)
#   - Select: from .tmp-metrics-select.json (Gemini tokens + timing)
#   - Compile: from cron list lastDurationMs + openclaw sessions (Opus tokens)
#   - Analysis: from .tmp-metrics-analysis.json (Gemini tokens + timing)
#   - Output: from cron list lastDurationMs + openclaw sessions (Opus tokens)
#
# Writes: wiki/metrics/run-YYYY-MM-DD-HHMM.md with all frontmatter fields.
#
# Usage: write-metrics.sh <channel> <sender> <subject>

set -e

WORKSPACE="${WORKSPACE:-/Users/austinholland/.openclaw/workspace}"
CHANNEL="${1:-unknown}"
SENDER="${2:-}"
SUBJECT="${3:-}"

# ─── Pricing (USD per million tokens) ───
OPUS_IN=15
OPUS_OUT=75
SONNET_IN=3
SONNET_OUT=15
FLASH_IN="0.15"
FLASH_OUT="0.60"

# ─── Helpers ───
read_json() {
  # read_json <file> <jq-expression> <default>
  local file="$1" expr="$2" default="$3"
  if [ -f "$file" ]; then
    jq -r "$expr // \"$default\"" "$file" 2>/dev/null || echo "$default"
  else
    echo "$default"
  fi
}

ms_to_s() {
  python3 -c "print(round($1/1000))"
}

calc() {
  python3 -c "print(round($1, 6))"
}

# ─── Pull Gemini metrics from temp files ───
SELECT_FILE="$WORKSPACE/.tmp-metrics-select.json"
ANALYSIS_FILE="$WORKSPACE/.tmp-metrics-analysis.json"
TRIAGE_FILE="$WORKSPACE/.tmp-metrics-triage.json"

SELECT_IN=$(read_json "$SELECT_FILE" '.promptTokenCount' 0)
SELECT_OUT=$(read_json "$SELECT_FILE" '.candidatesTokenCount' 0)
SELECT_MS=$(read_json "$SELECT_FILE" '.durationMs' 0)
SELECT_S=$(ms_to_s "$SELECT_MS")

ANALYSIS_IN=$(read_json "$ANALYSIS_FILE" '.promptTokenCount' 0)
ANALYSIS_OUT=$(read_json "$ANALYSIS_FILE" '.candidatesTokenCount' 0)
ANALYSIS_MS=$(read_json "$ANALYSIS_FILE" '.durationMs' 0)
ANALYSIS_S=$(ms_to_s "$ANALYSIS_MS")

TRIAGE_MS=$(read_json "$TRIAGE_FILE" '.durationMs' 0)
TRIAGE_S=$(ms_to_s "$TRIAGE_MS")

# ─── Pull Opus session tokens from openclaw sessions ───
SESSIONS_JSON=$(openclaw sessions --json 2>/dev/null || echo '{"sessions":[]}')

# Triage: the main agent session (where llm-task runs)
TRIAGE_SESSION=$(echo "$SESSIONS_JSON" | jq '.sessions[] | select(.key == "agent:main:main")' 2>/dev/null | head -100)
TRIAGE_TOTAL=$(echo "$TRIAGE_SESSION" | jq -r '.totalTokens // 0')
TRIAGE_OUT_TOKENS=$(echo "$TRIAGE_SESSION" | jq -r '.outputTokens // 0')
TRIAGE_IN=$((TRIAGE_TOTAL - TRIAGE_OUT_TOKENS))
[ "$TRIAGE_IN" -lt 0 ] && TRIAGE_IN=0

# Compile: look at the compile-trigger session
COMPILE_SESSION=$(echo "$SESSIONS_JSON" | jq '[.sessions[] | select(.key | contains("compile-trigger-001"))] | sort_by(.updatedAt) | reverse | .[0]' 2>/dev/null)
COMPILE_TOTAL=$(echo "$COMPILE_SESSION" | jq -r '.totalTokens // 0')
COMPILE_OUT_TOKENS=$(echo "$COMPILE_SESSION" | jq -r '.outputTokens // 0')
COMPILE_IN=$((COMPILE_TOTAL - COMPILE_OUT_TOKENS))
[ "$COMPILE_IN" -lt 0 ] && COMPILE_IN=0

# Output: look at the output-trigger session
OUTPUT_SESSION=$(echo "$SESSIONS_JSON" | jq '[.sessions[] | select(.key | contains("output-trigger-001"))] | sort_by(.updatedAt) | reverse | .[0]' 2>/dev/null)
OUTPUT_TOTAL=$(echo "$OUTPUT_SESSION" | jq -r '.totalTokens // 0')
OUTPUT_OUT_TOKENS=$(echo "$OUTPUT_SESSION" | jq -r '.outputTokens // 0')
OUTPUT_IN=$((OUTPUT_TOTAL - OUTPUT_OUT_TOKENS))
[ "$OUTPUT_IN" -lt 0 ] && OUTPUT_IN=0

# ─── Pull cron durations ───
CRONS_JSON=$(openclaw.invoke --tool cron --action list --args-json '{}' 2>/dev/null || echo '{}')
# The cron tool returns [{content:[{type:text,text:"..."}],details:{...}}]
# Extract the details.jobs array
COMPILE_CRON=$(echo "$CRONS_JSON" | jq '.[0].details.jobs[] | select(.id == "compile-trigger-001")' 2>/dev/null)
COMPILE_CRON_MS=$(echo "$COMPILE_CRON" | jq -r '.state.lastDurationMs // 0')
COMPILE_S=$(ms_to_s "$COMPILE_CRON_MS")

OUTPUT_CRON=$(echo "$CRONS_JSON" | jq '.[0].details.jobs[] | select(.id == "output-trigger-001")' 2>/dev/null)
OUTPUT_CRON_MS=$(echo "$OUTPUT_CRON" | jq -r '.state.lastDurationMs // 0')
OUTPUT_S=$(ms_to_s "$OUTPUT_CRON_MS")

# ─── Cost calculations ───
# Opus (triage, compile, output)
TRIAGE_IN_COST=$(calc "$TRIAGE_IN/1000000*$OPUS_IN")
TRIAGE_OUT_COST=$(calc "$TRIAGE_OUT_TOKENS/1000000*$OPUS_OUT")
COMPILE_IN_COST=$(calc "$COMPILE_IN/1000000*$OPUS_IN")
COMPILE_OUT_COST=$(calc "$COMPILE_OUT_TOKENS/1000000*$OPUS_OUT")
OUTPUT_IN_COST=$(calc "$OUTPUT_IN/1000000*$OPUS_IN")
OUTPUT_OUT_COST=$(calc "$OUTPUT_OUT_TOKENS/1000000*$OPUS_OUT")

OPUS_INPUT_COST=$(calc "$TRIAGE_IN_COST+$COMPILE_IN_COST+$OUTPUT_IN_COST")
OPUS_OUTPUT_COST=$(calc "$TRIAGE_OUT_COST+$COMPILE_OUT_COST+$OUTPUT_OUT_COST")

# Gemini (select, analysis)
GEMINI_INPUT_COST=$(calc "($SELECT_IN+$ANALYSIS_IN)/1000000*$FLASH_IN")
GEMINI_OUTPUT_COST=$(calc "($SELECT_OUT+$ANALYSIS_OUT)/1000000*$FLASH_OUT")

TOTAL_COST=$(calc "$OPUS_INPUT_COST+$OPUS_OUTPUT_COST+$GEMINI_INPUT_COST+$GEMINI_OUTPUT_COST")

# ─── Totals ───
TOTAL_OPUS_TOKENS=$((TRIAGE_TOTAL + COMPILE_TOTAL + OUTPUT_TOTAL))
TOTAL_GEMINI_TOKENS=$((SELECT_IN + SELECT_OUT + ANALYSIS_IN + ANALYSIS_OUT))
TOTAL_SECONDS=$((TRIAGE_S + SELECT_S + COMPILE_S + ANALYSIS_S + OUTPUT_S))

# Pull deals touched from the most recent compile log entry
DEALS_TOUCHED=$(grep -o 'UPDATED \[\[[^]]*\]\]' "$WORKSPACE/wiki/log.md" 2>/dev/null | head -20 | wc -l | tr -d ' ')
[ -z "$DEALS_TOUCHED" ] && DEALS_TOUCHED=0

# Pull deal wikilinks for the body
DEAL_LINKS=$(grep -o 'UPDATED \[\[[^]]*\]\]' "$WORKSPACE/wiki/log.md" 2>/dev/null | head -10 | sed 's/UPDATED //' | sort -u)

# Outputs produced — approximate from analysis result
OUTPUTS_PRODUCED=0
if [ -f "$WORKSPACE/.tmp-analysis-result.json" ]; then
  OUTPUTS_PRODUCED=$(jq '[.deals[] | select(.output_needed != "none")] | length' "$WORKSPACE/.tmp-analysis-result.json" 2>/dev/null || echo 0)
fi

# ─── Write the metrics file ───
TODAY=$(TZ=America/Chicago date "+%Y-%m-%d")
HHMM=$(TZ=America/Chicago date "+%H%M")
METRICS_DIR="$WORKSPACE/wiki/metrics"
mkdir -p "$METRICS_DIR"
METRICS_FILE="$METRICS_DIR/run-${TODAY}-${HHMM}.md"

# Escape subject/sender for YAML
SENDER_ESC=$(echo "$SENDER" | sed 's/"/\\"/g')
SUBJECT_ESC=$(echo "$SUBJECT" | sed 's/"/\\"/g')

cat > "$METRICS_FILE" <<EOF
---
type: pipeline-run
date: $TODAY
trigger: feed-pipeline
channel: $CHANNEL
sender: "$SENDER_ESC"
subject: "$SUBJECT_ESC"
deals_touched: $DEALS_TOUCHED
outputs_produced: $OUTPUTS_PRODUCED
total_seconds: $TOTAL_SECONDS
triage_seconds: $TRIAGE_S
triage_input_tokens: $TRIAGE_IN
triage_output_tokens: $TRIAGE_OUT_TOKENS
select_seconds: $SELECT_S
select_input_tokens: $SELECT_IN
select_output_tokens: $SELECT_OUT
compile_seconds: $COMPILE_S
compile_input_tokens: $COMPILE_IN
compile_output_tokens: $COMPILE_OUT_TOKENS
compile_session_tokens: $COMPILE_TOTAL
analysis_seconds: $ANALYSIS_S
analysis_input_tokens: $ANALYSIS_IN
analysis_output_tokens: $ANALYSIS_OUT
output_seconds: $OUTPUT_S
output_input_tokens: $OUTPUT_IN
output_output_tokens: $OUTPUT_OUT_TOKENS
output_session_tokens: $OUTPUT_TOTAL
total_opus_tokens: $TOTAL_OPUS_TOKENS
total_gemini_tokens: $TOTAL_GEMINI_TOKENS
opus_input_cost: $OPUS_INPUT_COST
opus_output_cost: $OPUS_OUTPUT_COST
gemini_input_cost: $GEMINI_INPUT_COST
gemini_output_cost: $GEMINI_OUTPUT_COST
total_cost_usd: $TOTAL_COST
---

# Pipeline Run — $TODAY $HHMM ($SENDER_ESC)

## Deals Touched
$(echo "$DEAL_LINKS" | sed 's/^/- /')

## Step Detail

### 1. Triage (Opus via llm-task)
| | |
|---|---|
| Seconds | $TRIAGE_S |
| Input tokens | $TRIAGE_IN |
| Output tokens | $TRIAGE_OUT_TOKENS |
| Cost | \$$(calc "$TRIAGE_IN_COST+$TRIAGE_OUT_COST") |

**In:** triage prompt + classification rules + channel/sender/subject + raw input.
**Out:** JSON — urgency, is_transcript, updates_deal, summary.

### 2. Article Selection (Gemini Flash)
| | |
|---|---|
| Seconds | $SELECT_S |
| Input tokens | $SELECT_IN |
| Output tokens | $SELECT_OUT |
| Cost | \$$(calc "$SELECT_IN/1000000*$FLASH_IN+$SELECT_OUT/1000000*$FLASH_OUT") |

**In:** selection prompt + schema + wiki-schema.md + wiki/index.md + raw input.
**Out:** JSON — list of articles to read, new entities, reasoning.

### 3. Compile — Johnny #1 (Opus, full agent turn)
| | |
|---|---|
| Seconds | $COMPILE_S |
| Input tokens | $COMPILE_IN |
| Output tokens | $COMPILE_OUT_TOKENS |
| Session total | $COMPILE_TOTAL |
| Cost | \$$(calc "$COMPILE_IN_COST+$COMPILE_OUT_COST") |

**In:** compile-prompt.md + .tmp-compile-articles.txt (assembled context) + always-on context.
**Out:** wiki article updates + new articles + updated index + new log entry + Telegram DM.

### 4. Gap Analysis (Gemini Flash)
| | |
|---|---|
| Seconds | $ANALYSIS_S |
| Input tokens | $ANALYSIS_IN |
| Output tokens | $ANALYSIS_OUT |
| Cost | \$$(calc "$ANALYSIS_IN/1000000*$FLASH_IN+$ANALYSIS_OUT/1000000*$FLASH_OUT") |

**In:** analysis prompt + scoring-methodology.md + scoring-services.md + scores.jsonl + deal articles.
**Out:** JSON — per-deal gaps, next_actions, urgency, output_needed.

### 5. Output — Johnny #2 (Opus, full agent turn)
| | |
|---|---|
| Seconds | $OUTPUT_S |
| Input tokens | $OUTPUT_IN |
| Output tokens | $OUTPUT_OUT_TOKENS |
| Session total | $OUTPUT_TOTAL |
| Cost | \$$(calc "$OUTPUT_IN_COST+$OUTPUT_OUT_COST") |

**In:** output-prompt.md + Gemini analysis JSON + full deal context + always-on context.
**Out:** email drafts, call prep, action reminders, deal updates — each to Austin's DM.

## Totals
| | |
|---|---|
| Total seconds | $TOTAL_SECONDS |
| Total Opus tokens | $TOTAL_OPUS_TOKENS |
| Total Gemini tokens | $TOTAL_GEMINI_TOKENS |
| Opus cost | \$$(calc "$OPUS_INPUT_COST+$OPUS_OUTPUT_COST") |
| Gemini cost | \$$(calc "$GEMINI_INPUT_COST+$GEMINI_OUTPUT_COST") |
| **Total cost** | **\$$TOTAL_COST** |
EOF

echo "{\"metrics_file\": \"$METRICS_FILE\", \"cost\": $TOTAL_COST}"
