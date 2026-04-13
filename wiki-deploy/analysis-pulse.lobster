name: analysis-pulse
# Runs every 5 minutes. Checks for wiki compiles that haven't been analyzed yet.
# If found: reads updated deal articles, runs Gemini gap analysis, triggers Johnny #2
# for the strategic work product.
#
# This is the "deterministic brain" — it tells Johnny what's missing and what to produce.

env:
  OPENCLAW_URL: "http://127.0.0.1:18789"
  OPENCLAW_TOKEN: "f18f7ebeb4a20e270fb7e859372441b1f087da793d65a14f"
  WORKSPACE: "/Users/austinholland/.openclaw/workspace"

steps:
  # ── 1. CHECK FOR UNANALYZED COMPILES ──
  # Compare wiki/log.md timestamps against .last-analysis-ts
  - id: check_pending
    command: |
      LAST_TS_FILE="$WORKSPACE/.last-analysis-ts"
      LAST_TS=$(cat "$LAST_TS_FILE" 2>/dev/null || echo "1970-01-01")

      # Extract compile timestamps from log.md (format: ## YYYY-MM-DD HH:MM — Label)
      LATEST_COMPILE=$(grep '^## [0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}' "$WORKSPACE/wiki/log.md" 2>/dev/null | head -1 | sed 's/^## //' | cut -d' ' -f1-2)

      if [ -z "$LATEST_COMPILE" ]; then
        echo '{"has_pending": false, "reason": "no compiles in log"}'
        exit 0
      fi

      if [ "$LATEST_COMPILE" = "$LAST_TS" ]; then
        echo '{"has_pending": false, "reason": "already analyzed"}'
        exit 0
      fi

      # Find which deals were updated in recent compiles (since last analysis)
      # Extract deal article names from log entries between last analysis and now
      UPDATED_DEALS=$(awk -v last="$LAST_TS" '
        /^## [0-9]{4}-[0-9]{2}-[0-9]{2}/ {
          ts = substr($0, 4, 16)
          if (ts <= last) exit
        }
        /UPDATED \[\[/ { gsub(/.*UPDATED \[\[/, ""); gsub(/\]\].*/, ""); print }
        /CREATED \[\[/ { gsub(/.*CREATED \[\[/, ""); gsub(/\]\].*/, ""); print }
      ' "$WORKSPACE/wiki/log.md" | sort -u | tr '\n' ',' | sed 's/,$//')

      echo "{\"has_pending\": true, \"latest_compile\": \"$LATEST_COMPILE\", \"updated_deals\": \"$UPDATED_DEALS\"}"

  # ── 2. READ DEAL CONTEXT FOR ANALYSIS ──
  # Pull the updated deal articles + scoring files
  - id: read_analysis_context
    command: |
      PENDING='$PENDING_OUT'
      UPDATED=$(echo "$PENDING" | jq -r '.updated_deals // ""')
      OUTFILE="$WORKSPACE/.tmp-analysis-context.txt"
      : > "$OUTFILE"

      # Scoring methodology
      {
        echo "=== SCORING METHODOLOGY (MANDATORY) ==="
        cat "$WORKSPACE/scoring-methodology.md"
        echo ""
        echo "=== END SCORING METHODOLOGY ==="
        echo ""
        echo "=== SCORING SERVICES REFERENCE ==="
        cat "$WORKSPACE/scoring-services.md"
        echo ""
        echo "=== END SCORING SERVICES ==="
        echo ""
        echo "=== RECENT SCORES ==="
        tail -5 "$WORKSPACE/scores.jsonl" 2>/dev/null || echo "No scores yet."
        echo ""
        echo "=== END RECENT SCORES ==="
        echo ""
        echo "=== WIKI INDEX ==="
        cat "$WORKSPACE/wiki/index.md"
        echo ""
        echo "=== END WIKI INDEX ==="
        echo ""
      } >> "$OUTFILE"

      # Read each updated deal article
      DEAL_LIST=""
      IFS=',' read -ra DEALS <<< "$UPDATED"
      for deal in "${DEALS[@]}"; do
        deal=$(echo "$deal" | tr -d ' ')
        [ -z "$deal" ] && continue
        FILEPATH="$WORKSPACE/wiki/${deal}.md"
        if [ -f "$FILEPATH" ]; then
          printf '\n=== DEAL ARTICLE: %s ===\n' "$deal" >> "$OUTFILE"
          cat "$FILEPATH" >> "$OUTFILE"
          printf '\n=== END %s ===\n' "$deal" >> "$OUTFILE"
          DEAL_LIST="$DEAL_LIST $deal"
        fi
      done

      # Read recent compile log entries for context on what changed
      {
        echo ""
        echo "=== RECENT COMPILE LOG (what just changed) ==="
        head -40 "$WORKSPACE/wiki/log.md"
        echo ""
        echo "=== END COMPILE LOG ==="
      } >> "$OUTFILE"

      CONTEXT_SIZE=$(wc -c < "$OUTFILE" | tr -d ' ')
      echo "{\"context_ready\": true, \"deals_read\": \"$(echo $DEAL_LIST | tr ' ' ',')\", \"context_size\": $CONTEXT_SIZE}"
    env:
      PENDING_OUT: $check_pending.stdout
    when: $check_pending.json.has_pending

  # ── 3. GEMINI GAP ANALYSIS ──
  # Deterministic analysis: what's missing, what does Austin need to do next?
  - id: gap_analysis
    command: |
      SCHEMA='{"type":"object","properties":{"deals":{"type":"array","items":{"type":"object","properties":{"deal":{"type":"string"},"current_stage":{"type":"string"},"gaps":{"type":"array","items":{"type":"string"}},"next_actions":{"type":"array","items":{"type":"string"}},"urgency":{"type":"string","enum":["HIGH","MEDIUM","LOW"]},"output_needed":{"type":"string","enum":["email_draft","call_prep","action_reminder","deal_update","none"]},"output_context":{"type":"string"}},"required":["deal","gaps","next_actions","urgency","output_needed"]}},"summary":{"type":"string"}},"required":["deals","summary"]}'

      "$WORKSPACE/gemini-json.sh" \
        "You are a deal operations analyst. For each deal article provided, analyze: (1) What components are missing to move the deal forward? (2) What specific actions does Austin need to take? (3) How urgent is it? (4) What output does Austin need — an email draft, call prep, action reminder, or just a deal status update? Be specific and cite what you see in the wiki articles. If a deal just had informational input with no required action, set output_needed to none. Provide a one-sentence summary of the overall state." \
        "$SCHEMA" \
        "$WORKSPACE/.tmp-analysis-context.txt" \
        "$WORKSPACE/.tmp-metrics-analysis.json" \
        > "$WORKSPACE/.tmp-analysis-result.json"

      cat "$WORKSPACE/.tmp-analysis-result.json"
    when: $check_pending.json.has_pending

  # ── 4. WRITE DEBUG LOG ──
  - id: write_analysis_debug
    command: |
      PENDING='$PENDING_OUT'
      ANALYSIS=$(cat "$WORKSPACE/.tmp-analysis-result.json" 2>/dev/null)
      CONTEXT_INFO='$CONTEXT_OUT'
      TIMESTAMP=$(TZ=America/Chicago date "+%Y-%m-%d %I:%M %p CT")

      {
        echo "# Analysis Pulse Debug Log"
        echo ""
        echo "**Timestamp:** $TIMESTAMP"
        echo "**Latest compile:** $(echo "$PENDING" | jq -r '.latest_compile')"
        echo "**Deals analyzed:** $(echo "$PENDING" | jq -r '.updated_deals')"
        echo "**Context size:** $(echo "$CONTEXT_INFO" | jq -r '.context_size') bytes"
        echo ""
        echo "## Gemini Analysis Result"
        echo ""
        echo '```json'
        echo "$ANALYSIS" | jq '.' 2>/dev/null || echo "$ANALYSIS"
        echo '```'
        echo ""
        echo "## Files Pulled"
        echo "- scoring-methodology.md"
        echo "- scoring-services.md"
        echo "- scores.jsonl (last 5 entries)"
        echo "- wiki/index.md"
        echo "- Deal articles: $(echo "$PENDING" | jq -r '.updated_deals')"
        echo "- wiki/log.md (last 40 lines)"
      } > "$WORKSPACE/.last-analysis-prompt.md"

      echo '{"debug_written": true}'
    env:
      PENDING_OUT: $check_pending.stdout
      CONTEXT_OUT: $read_analysis_context.stdout
    when: $check_pending.json.has_pending

  # ── 5. CHECK IF OUTPUT NEEDED ──
  # Only trigger Johnny #2 if Gemini says Austin needs something
  - id: check_output_needed
    command: |
      ANALYSIS=$(cat "$WORKSPACE/.tmp-analysis-result.json" 2>/dev/null)
      NEEDS_OUTPUT=$(echo "$ANALYSIS" | jq '[.deals[] | select(.output_needed != "none")] | length')

      if [ "$NEEDS_OUTPUT" -gt 0 ]; then
        # Write the analysis result for Johnny #2 to read
        echo "$ANALYSIS" | jq '.' > "$WORKSPACE/.tmp-output-context.json"
        echo '{"needs_output": true, "deals_needing_output": '$NEEDS_OUTPUT'}'
      else
        echo '{"needs_output": false}'
      fi
    when: $check_pending.json.has_pending

  # ── 6. TRIGGER JOHNNY #2 ──
  # Fire the output-trigger cron job for strategic work product
  - id: trigger_output
    command: |
      ARGS=$(jq -n '{id: "output-trigger-001"}')
      openclaw.invoke --tool cron --action run --args-json "$ARGS"
    when: $check_output_needed.json.needs_output

  # ── 7. UPDATE TIMESTAMP ──
  # Mark this analysis as done so we don't re-run it
  - id: update_timestamp
    command: |
      PENDING='$PENDING_OUT'
      LATEST=$(echo "$PENDING" | jq -r '.latest_compile')
      echo "$LATEST" > "$WORKSPACE/.last-analysis-ts"
      echo '{"timestamp_updated": true}'
    env:
      PENDING_OUT: $check_pending.stdout
    when: $check_pending.json.has_pending

  # ── 8. OPS LOG ──
  - id: ops_log
    command: |
      PENDING='$PENDING_OUT'
      HAS_PENDING=$(echo "$PENDING" | jq -r '.has_pending')

      if [ "$HAS_PENDING" = "true" ]; then
        DEALS=$(echo "$PENDING" | jq -r '.updated_deals')
        ANALYSIS=$(cat "$WORKSPACE/.tmp-analysis-result.json" 2>/dev/null)
        SUMMARY=$(echo "$ANALYSIS" | jq -r '.summary // "analysis complete"')
        NEEDS=$(echo '$CHECK_OUT' | jq -r '.needs_output // false')

        MSG="ANALYSIS PULSE: ${DEALS}"
        MSG="${MSG}$(printf '\n')${SUMMARY}"
        if [ "$NEEDS" = "true" ]; then
          MSG="${MSG}$(printf '\n')OUTPUT: triggered Johnny #2"
        else
          MSG="${MSG}$(printf '\n')OUTPUT: none needed"
        fi
      else
        MSG="ANALYSIS PULSE: no pending compiles"
      fi

      openclaw.invoke --tool message --action send \
        --args-json "$(jq -n --arg msg "$MSG" '{"provider":"telegram","to":"-5205161230","message":$msg}')"

      echo '{"ops_logged": true}'
    env:
      PENDING_OUT: $check_pending.stdout
      CHECK_OUT: $check_output_needed.stdout
