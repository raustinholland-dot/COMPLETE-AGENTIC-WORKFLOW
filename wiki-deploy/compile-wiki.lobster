name: compile-wiki
# Sub-lobster: assembles context (schema + index + relevant articles + input),
# writes debug logs for visibility, then triggers Johnny via cron.run.
# Lobster owns the conveyor belt. Johnny owns the workbench.

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
  # ── 5a. READ CONTEXT ──
  # Read wiki-schema.md and index. No compile log (wiki articles are the source of truth).
  - id: read_context
    command: |
      {
        echo "=== WIKI SCHEMA (MANDATORY — follow exactly) ==="
        cat "$WORKSPACE/wiki-schema.md"
        echo ""
        echo "=== END WIKI SCHEMA ==="
        echo ""
        echo "=== CURRENT WIKI INDEX ==="
        cat "$WORKSPACE/wiki/index.md"
        echo ""
        echo "=== END WIKI INDEX ==="
        echo ""
        echo "=== NEW INPUT [$LOBSTER_ARG_CHANNEL] ==="
        if [ -n "$LOBSTER_ARG_SENDER" ]; then echo "from: $LOBSTER_ARG_SENDER"; fi
        if [ -n "$LOBSTER_ARG_SUBJECT" ]; then echo "subject: $LOBSTER_ARG_SUBJECT"; fi
        echo ""
        printf '%s\n' "$LOBSTER_ARG_INPUT_TEXT"
        echo ""
        echo "=== END INPUT ==="
      } | tee "$WORKSPACE/.tmp-compile-context.txt"

  # ── 5b. IDENTIFY ARTICLES ──
  # Quick Gemini Flash call: given the index + input, which articles to read?
  - id: identify_articles
    command: |
      SCHEMA='{"type":"object","properties":{"articles":{"type":"array","items":{"type":"string"}},"new_entities":{"type":"array","items":{"type":"string"}},"reasoning":{"type":"string"}},"required":["articles","new_entities","reasoning"]}'
      CONTEXT_FILE="$WORKSPACE/.tmp-compile-context.txt"
      RESULT=$("$WORKSPACE/gemini-json.sh" \
        "Identify wiki articles to read for compiling this input. Return JSON with: articles (array of filenames from the index that this input relates to), new_entities (array of new people/deals/orgs not in the index), reasoning (brief explanation of why you chose these articles). Only return filenames that appear in the index. Empty arrays if all new." \
        "$SCHEMA" \
        "$CONTEXT_FILE" \
        "$WORKSPACE/.tmp-metrics-select.json")
      echo "$RESULT" > "$WORKSPACE/.tmp-identify-result.json"
      echo "$RESULT"

  # ── 5c. READ ARTICLES ──
  # Read each identified article + related articles (one degree out).
  - id: read_articles
    command: |
      IDENTIFY_FILE="$WORKSPACE/.tmp-identify-result.json"
      ARTICLES=$(cat "$IDENTIFY_FILE" | jq -r '.articles[]' 2>/dev/null)
      ALL_FILES=""
      OUTFILE="$WORKSPACE/.tmp-compile-articles.txt"
      : > "$OUTFILE"

      # Include the original context
      cat "$WORKSPACE/.tmp-compile-context.txt" >> "$OUTFILE"

      # First pass: read identified articles, collect related filenames
      RELATED=""
      for article in $ARTICLES; do
        FILEPATH="$WORKSPACE/wiki/$article"
        if [ -f "$FILEPATH" ]; then
          printf '\n=== ARTICLE: %s ===\n' "$article" >> "$OUTFILE"
          cat "$FILEPATH" >> "$OUTFILE"
          printf '\n=== END %s ===\n' "$article" >> "$OUTFILE"
          ALL_FILES="$ALL_FILES $article"
          REL=$(grep -A 50 '^related:' "$FILEPATH" 2>/dev/null | grep '^ *- ' | sed 's/^ *- //' | head -20)
          RELATED="$RELATED $REL"
        fi
      done

      # Second pass: read related articles not already read
      for rel in $RELATED; do
        case "$rel" in
          *.md) RELFILE="$rel" ;;
          *) RELFILE="${rel}.md" ;;
        esac
        case "$ALL_FILES" in
          *"$RELFILE"*) continue ;;
        esac
        FILEPATH="$WORKSPACE/wiki/$RELFILE"
        if [ -f "$FILEPATH" ]; then
          printf '\n=== RELATED ARTICLE: %s ===\n' "$RELFILE" >> "$OUTFILE"
          cat "$FILEPATH" >> "$OUTFILE"
          printf '\n=== END %s ===\n' "$RELFILE" >> "$OUTFILE"
          ALL_FILES="$ALL_FILES $RELFILE"
        fi
      done

      if [ -z "$ALL_FILES" ]; then
        echo "(No existing articles found — this may be a new entity.)" >> "$OUTFILE"
      fi

      echo '{"articles_read": true}'

  # ── 5d. WRITE DEBUG LOG ──
  # Write .last-compile-prompt.md so Austin can see exactly what Johnny gets.
  - id: write_debug
    command: |
      IDENTIFY=$(cat "$WORKSPACE/.tmp-identify-result.json" 2>/dev/null)
      ARTICLES_CHOSEN=$(echo "$IDENTIFY" | jq -r '.articles[]' 2>/dev/null | tr '\n' ', ' | sed 's/,$//')
      NEW_ENTITIES=$(echo "$IDENTIFY" | jq -r '.new_entities[]' 2>/dev/null | tr '\n' ', ' | sed 's/,$//')
      REASONING=$(echo "$IDENTIFY" | jq -r '.reasoning // "none"' 2>/dev/null)
      CONTEXT_SIZE=$(wc -c < "$WORKSPACE/.tmp-compile-articles.txt" | tr -d ' ')
      TIMESTAMP=$(TZ=America/Chicago date "+%Y-%m-%d %I:%M %p CT")

      {
        echo "# Compile Debug Log"
        echo ""
        echo "**Timestamp:** $TIMESTAMP"
        echo "**Channel:** $LOBSTER_ARG_CHANNEL"
        echo "**Sender:** $LOBSTER_ARG_SENDER"
        echo "**Subject:** $LOBSTER_ARG_SUBJECT"
        echo ""
        echo "## Article Selection (Gemini Flash)"
        echo ""
        echo "**Articles chosen:** $ARTICLES_CHOSEN"
        echo "**New entities detected:** ${NEW_ENTITIES:-none}"
        echo "**Reasoning:** $REASONING"
        echo ""
        echo "## Context Assembly"
        echo ""
        echo "**Total context size:** ${CONTEXT_SIZE} bytes"
        echo "**Files pulled:**"
        echo "- wiki-schema.md (always)"
        echo "- wiki/index.md (always)"
        for a in $(echo "$IDENTIFY" | jq -r '.articles[]' 2>/dev/null); do
          echo "- wiki/$a (primary)"
        done
        grep -o 'RELATED ARTICLE: [^ ]*' "$WORKSPACE/.tmp-compile-articles.txt" 2>/dev/null | while read line; do
          echo "- wiki/$(echo "$line" | sed 's/RELATED ARTICLE: //') (related)"
        done
        echo ""
        echo "## Prompt Sent to Johnny"
        echo ""
        echo "Cron job: compile-trigger-001"
        echo "Johnny reads: compile-prompt.md + .tmp-compile-articles.txt"
        echo ""
        echo "---"
        echo ""
        echo "## compile-prompt.md contents:"
        echo ""
        cat "$WORKSPACE/compile-prompt.md" 2>/dev/null || echo "(not found)"
      } > "$WORKSPACE/.last-compile-prompt.md"

      echo '{"debug_written": true}'

  # ── 5e. TRIGGER JOHNNY ──
  # Fire the compile-trigger cron job to wake Johnny with the assembled context.
  - id: trigger_johnny
    command: |
      ARGS=$(jq -n '{id: "compile-trigger-001"}')
      openclaw.invoke --tool cron --action run --args-json "$ARGS"
