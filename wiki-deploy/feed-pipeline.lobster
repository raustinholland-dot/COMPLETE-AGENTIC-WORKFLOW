name: feed-pipeline
# Johnny Forsyth Feed Pipeline — Lobster Workflow
#
# Triggered when a feed channel input arrives (email, transcript, calendar, Teams).
# Lobster owns the conveyor belt (logistics). Johnny owns the workbench (creative work).
#
# Flow: dedup → capture → triage → assemble context → trigger Johnny → notify Austin → ops log
# Scoring and needs assessment run on a separate 5-minute pulse (analysis-pulse.lobster).

args:
  INPUT_TEXT:
    default: ""
  CHANNEL:
    default: ""
  SENDER:
    default: ""
  SUBJECT:
    default: ""

env:
  OPENCLAW_URL: "http://127.0.0.1:18789"
  OPENCLAW_TOKEN: "f18f7ebeb4a20e270fb7e859372441b1f087da793d65a14f"
  WORKSPACE: "/Users/austinholland/.openclaw/workspace"

steps:
  # ════════════════════════════════════════
  # STEP 0: INIT METRICS (shell)
  # Wipe any previous metrics state and record pipeline start time
  # ════════════════════════════════════════
  - id: init_metrics
    command: |
      rm -f "$WORKSPACE/.tmp-metrics-select.json" \
            "$WORKSPACE/.tmp-metrics-analysis.json" \
            "$WORKSPACE/.tmp-metrics-triage.json" \
            "$WORKSPACE/.tmp-metrics-run.json"
      START_MS=$(python3 -c 'import time; print(int(time.time()*1000))')
      echo "{\"pipeline_start_ms\": $START_MS}" > "$WORKSPACE/.tmp-metrics-run.json"
      echo "{\"initialized\": true}"

  # ════════════════════════════════════════
  # STEP 1: DEDUP CHECK (shell)
  # ════════════════════════════════════════
  - id: dedup
    command: |
      HASH=$(printf '%s' "$LOBSTER_ARG_INPUT_TEXT" | shasum -a 256 | cut -d' ' -f1)
      DEDUP_FILE="$WORKSPACE/clearwater/feeds/.processed-inputs.jsonl"
      if [ -f "$DEDUP_FILE" ] && grep -q "$HASH" "$DEDUP_FILE" 2>/dev/null; then
        echo '{"is_new": false}'
      else
        echo "{\"is_new\": true, \"hash\": \"$HASH\"}"
      fi

  # ════════════════════════════════════════
  # STEP 2: DUPLICATE EXIT (shell, conditional)
  # ════════════════════════════════════════
  - id: dup_notify
    command: |
      openclaw.invoke --tool message --action send \
        --args-json "{\"provider\":\"telegram\",\"to\":\"6461072413\",\"message\":\"Already processed this input (duplicate). Skipping.\"}"
      echo '{"status": "duplicate_exit"}'
    when: $dedup.json.is_new == false

  # ════════════════════════════════════════
  # STEP 3: CAPTURE TO RAW (shell)
  # ════════════════════════════════════════
  - id: capture
    command: |
      TODAY=$(date +%Y-%m-%d)
      TIMESTAMP=$(TZ=America/Chicago date "+%I:%M %p CT")
      RAW_FILE="$WORKSPACE/raw/${TODAY}.md"

      # Write capture block
      {
        printf '\n---\n'
        printf '[%s] %s\n' "$LOBSTER_ARG_CHANNEL" "$TIMESTAMP"
        [ -n "$LOBSTER_ARG_SENDER" ] && printf 'from: %s\n' "$LOBSTER_ARG_SENDER"
        [ -n "$LOBSTER_ARG_SUBJECT" ] && printf 'subject: %s\n' "$LOBSTER_ARG_SUBJECT"
        printf '---\n\n'
        printf '%s\n' "$LOBSTER_ARG_INPUT_TEXT"
      } >> "$RAW_FILE"

      # Log hash
      HASH=$(printf '%s' "$LOBSTER_ARG_INPUT_TEXT" | shasum -a 256 | cut -d' ' -f1)
      printf '{"hash":"%s","date":"%s","channel":"%s","ts":"%s"}\n' \
        "$HASH" "$TODAY" "$LOBSTER_ARG_CHANNEL" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        >> "$WORKSPACE/clearwater/feeds/.processed-inputs.jsonl"

      echo "{\"captured\": true, \"date\": \"$TODAY\", \"raw_file\": \"$RAW_FILE\"}"
    when: $dedup.json.is_new

  # ════════════════════════════════════════
  # STEP 4: TRIAGE (llm_task.invoke) — timed
  # ════════════════════════════════════════
  - id: triage
    command: |
      SCHEMA='{"type":"object","properties":{"urgency":{"type":"string","enum":["URGENT","NORMAL"]},"is_transcript":{"type":"boolean"},"updates_deal":{"type":"boolean"},"summary":{"type":"string"}},"required":["urgency","is_transcript","updates_deal","summary"]}'
      export TRIAGE_INPUT="$LOBSTER_ARG_INPUT_TEXT"
      export TRIAGE_CHANNEL="$LOBSTER_ARG_CHANNEL"
      export TRIAGE_SENDER="$LOBSTER_ARG_SENDER"
      export TRIAGE_SUBJECT="$LOBSTER_ARG_SUBJECT"

      START_MS=$(python3 -c 'import time; print(int(time.time()*1000))')
      RESULT=$(openclaw.invoke --tool llm-task --action json --args-json "$(jq -n \
        --argjson schema "$SCHEMA" \
        '{prompt: ("Return ONLY a JSON object with these exact keys: urgency (URGENT or NORMAL), is_transcript (boolean), updates_deal (boolean), summary (string, max 100 chars). URGENT if: client asking a question, meeting within 24h, deal status change, or explicitly urgent. NORMAL otherwise. is_transcript: true only if this is a call/meeting transcript. updates_deal: true if it mentions a specific client, prospect, or deal by name. No explanation, no markdown, just the JSON object. Channel: " + env.TRIAGE_CHANNEL + ". Sender: " + env.TRIAGE_SENDER + ". Subject: " + env.TRIAGE_SUBJECT + ". Input: " + env.TRIAGE_INPUT), schema: $schema}')")
      END_MS=$(python3 -c 'import time; print(int(time.time()*1000))')
      DURATION_MS=$((END_MS - START_MS))

      # Log triage timing + model (tokens will be pulled from openclaw sessions in write_metrics)
      MODEL=$(echo "$RESULT" | jq -r '.[0].details.model // "claude-opus-4-6"' 2>/dev/null)
      echo "{\"durationMs\": $DURATION_MS, \"model\": \"$MODEL\"}" > "$WORKSPACE/.tmp-metrics-triage.json"

      echo "$RESULT"
    when: $dedup.json.is_new

  # ════════════════════════════════════════
  # STEP 5: NOTIFY AUSTIN (shell)
  # ════════════════════════════════════════
  - id: notify
    command: |
      URGENCY=$(echo '$TRIAGE_OUT' | jq -r '.urgency // "NORMAL"')
      SUMMARY=$(echo '$TRIAGE_OUT' | jq -r '.summary // "new input"')

      if [ "$URGENCY" = "URGENT" ]; then
        MSG="URGENT: ${SUMMARY}. Processing now."
      else
        MSG="Captured: ${SUMMARY}. Compiling."
      fi

      openclaw.invoke --tool message --action send \
        --args-json "$(jq -n --arg msg "$MSG" '{"provider":"telegram","to":"6461072413","message":$msg}')"

      echo '{"notified": true}'
    env:
      TRIAGE_OUT: $triage.stdout
    when: $dedup.json.is_new

  # ════════════════════════════════════════
  # STEP 6: COMPILE (sub-lobster — assembles context + triggers Johnny)
  # ════════════════════════════════════════
  - id: compile
    command: |
      export COMPILE_INPUT="$LOBSTER_ARG_INPUT_TEXT"
      export COMPILE_CHANNEL="$LOBSTER_ARG_CHANNEL"
      export COMPILE_SENDER="$LOBSTER_ARG_SENDER"
      export COMPILE_SUBJECT="$LOBSTER_ARG_SUBJECT"
      ARGS_JSON=$(jq -n '{INPUT_TEXT: env.COMPILE_INPUT, CHANNEL: env.COMPILE_CHANNEL, SENDER: env.COMPILE_SENDER, SUBJECT: env.COMPILE_SUBJECT}')
      lobster run --mode tool --file "$WORKSPACE/compile-wiki.lobster" --args-json "$ARGS_JSON"
    when: $dedup.json.is_new

  # ════════════════════════════════════════
  # STEP 7: WRITE METRICS (shell)
  # Collect all per-step metrics + Opus session tokens from openclaw sessions
  # and write a metrics/run-*.md file to the wiki for Obsidian/Dataview.
  # ════════════════════════════════════════
  - id: write_metrics
    command: |
      bash "$WORKSPACE/write-metrics.sh" \
        "$LOBSTER_ARG_CHANNEL" \
        "$LOBSTER_ARG_SENDER" \
        "$LOBSTER_ARG_SUBJECT" || echo '{"metrics_error": true}'
      echo '{"metrics_written": true}'
    when: $dedup.json.is_new

  # ════════════════════════════════════════
  # STEP 8: OPS LOG (shell)
  # ════════════════════════════════════════
  - id: ops_log
    command: |
      SUMMARY=$(echo '$TRIAGE_OUT' | jq -r '.summary // "input processed"')
      URGENCY=$(echo '$TRIAGE_OUT' | jq -r '.urgency // "NORMAL"')

      MSG="PIPELINE: ${URGENCY} -- ${SUMMARY}"
      MSG="${MSG}$(printf '\n')CONTEXT ASSEMBLED: wiki-schema.md + index + relevant articles"
      MSG="${MSG}$(printf '\n')COMPILE: triggered Johnny via cron"

      openclaw.invoke --tool message --action send \
        --args-json "$(jq -n --arg msg "$MSG" '{"provider":"telegram","to":"-5205161230","message":$msg}')"

      echo '{"pipeline_complete": true}'
    env:
      TRIAGE_OUT: $triage.stdout
    when: $dedup.json.is_new
