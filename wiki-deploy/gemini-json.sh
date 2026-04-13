#!/bin/bash
# Calls Gemini 2.5 Flash with JSON mode, reading args from a file.
# Usage: gemini-json.sh <prompt> <schema-json> <input-file> [usage-out-file]
# The input-file content is appended to the prompt.
# Outputs parsed JSON to stdout.
# If usage-out-file is provided, writes usageMetadata to that file as JSON.

PROMPT="$1"
SCHEMA="$2"
INPUT_FILE="$3"
USAGE_OUT="$4"
API_KEY="${GEMINI_API_KEY:-AIzaSyAnJnn_N_IvSGVsCzo7T2lSs-H73ej4ccE}"

INPUT_TEXT=$(cat "$INPUT_FILE")

# Build the request using jq with env vars (no shell expansion issues)
export G_PROMPT="$PROMPT"
export G_INPUT="$INPUT_TEXT"
export G_SCHEMA="$SCHEMA"

jq -n '{
  contents: [{parts: [{text: (env.G_PROMPT + "\n\n" + env.G_INPUT)}]}],
  generationConfig: {
    responseMimeType: "application/json",
    responseSchema: (env.G_SCHEMA | fromjson)
  }
}' > /tmp/gemini-request.json

# Time the API call
START_MS=$(python3 -c 'import time; print(int(time.time()*1000))')

RESPONSE=$(curl -s -X POST \
  "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=$API_KEY" \
  -H "Content-Type: application/json" \
  -d @/tmp/gemini-request.json)

END_MS=$(python3 -c 'import time; print(int(time.time()*1000))')
DURATION_MS=$((END_MS - START_MS))

# Write usage metadata to file if requested
if [ -n "$USAGE_OUT" ]; then
  echo "$RESPONSE" | jq --argjson dur "$DURATION_MS" '{
    promptTokenCount: (.usageMetadata.promptTokenCount // 0),
    candidatesTokenCount: (.usageMetadata.candidatesTokenCount // 0),
    totalTokenCount: (.usageMetadata.totalTokenCount // 0),
    thoughtsTokenCount: (.usageMetadata.thoughtsTokenCount // 0),
    durationMs: $dur,
    model: "gemini-2.5-flash"
  }' > "$USAGE_OUT"
fi

# Extract the text from the response (unchanged behavior)
echo "$RESPONSE" | jq -r '.candidates[0].content.parts[0].text // empty'
