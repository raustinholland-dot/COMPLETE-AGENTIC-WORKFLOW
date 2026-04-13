# Decision: Feed-Lobster Hook Routing Fix

**Date:** April 12, 2026
**Context:** Real emails pasted into the Telegram Email Feed channel were being silently routed to the `feed-sink` Ollama agent instead of triggering the Lobster pipeline. The metrics testing was blocked because no inputs were reaching `feed-pipeline.lobster`.

## Root Cause

There are **two separate implementations** of feed-lobster on the MBP, and we discovered the wrong one was disabled.

| Implementation | Path | Hook System | Event | Status |
|----------------|------|-------------|-------|--------|
| Old | `~/.openclaw/hooks/feed-lobster/` | Hooks loader (`hooks.internal.entries`) | `message:received` | **Was disabled** in config |
| New | `~/.openclaw/plugins/feed-lobster/` | Plugin SDK (`plugins.entries`) | `inbound_claim` | Loads but events never fire |

The new plugin's `api.on("inbound_claim", ...)` registration appears to succeed (the plugin's `register()` function runs and logs "Feed Lobster plugin registered") but the gateway never actually dispatches `inbound_claim` events to it. Silent failure — no errors, just no events.

Meanwhile, the `feed-sink` agent has an `accountId=feeds` binding that catches all messages routed through the `feeds` account, so it was claiming every email feed message and processing it through Ollama qwen2.5 (silently — its SOUL is `Reply only: NO_REPLY`).

The smoking gun: gateway log showed `[hooks:loader] Registered hook: feed-lobster -> message:received` last on 2026-04-09, then `hooks.internal.entries.feed-lobster.enabled` got set to `false` (probably during the rewrite to plugin SDK), and no `inbound_claim` registration ever appeared.

## Fix

1. Re-enabled the old hook: `hooks.internal.entries.feed-lobster.enabled = true`
2. Disabled the duplicate plugin: `plugins.entries.feed-lobster.enabled = false`
3. Restarted the gateway (`openclaw gateway restart`)
4. Verified hook registered: `[hooks:loader] Registered hook: feed-lobster -> message:received` at 02:07:25 CDT

## Caveat

The old hook uses `message:received`, which is a passive notification — it does NOT claim the message. So `feed-sink` still runs in parallel on every email feed message (no user-visible effect because of NO_REPLY, but Ollama burns cycles). 

The proper fix is to make `inbound_claim` work in the plugin SDK so we can claim the message and skip routing entirely. That's a future task — file an issue against the plugin SDK or rewrite the new plugin's hook registration.

## Why Two Implementations Existed

The new plugin (`plugins/feed-lobster/`) was created on April 11 to add media extraction (PDF text via pdf-parse, image OCR via tesseract). The author intended to migrate from `message:received` to `inbound_claim` (a cleaner hook that fires before routing) but `inbound_claim` dispatch isn't actually wired in the version of OpenClaw running on the MBP. The old hook was disabled on April 9 in anticipation of the migration. Net result: nothing was firing.

## Files Touched

| File | Change |
|------|--------|
| `~/.openclaw/openclaw.json` | `hooks.internal.entries.feed-lobster.enabled` → `true`; `plugins.entries.feed-lobster.enabled` → `false` |
| (gateway restart) | Re-loaded all hooks fresh |

Backup of original config at `~/.openclaw/openclaw.json.bak-20260412-*`.

## Known Limitations

- Old hook is text-only — no PDF/image extraction (the new plugin had that, but we disabled it)
- Future: get the plugin SDK working and consolidate to one implementation

## Status

Fixed and verified April 12, 2026. The hook is registered, gateway is running. Ready to test with real Telegram email feed input.

## Credit

Diagnosed and fixed by Claude Code (daily driver session, Apr 12). Required deep dive into gateway logs, plugin SDK type definitions, and hook registration internals.
