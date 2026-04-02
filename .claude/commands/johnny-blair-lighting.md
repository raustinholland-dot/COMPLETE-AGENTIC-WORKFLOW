# Johnny Blair Lighting

## Context

Austin is setting up full smart home light control via the **Tuya Cloud API / Smart Life app**, with **Johnny** (MBP at 100.122.212.128) owning and running the entire system.

## Where We Left Off

A complete, ready-to-paste implementation spec was written for Johnny. It covers:
- Tuya HMAC-SHA256 signing algorithm (exact, working)
- Token fetch + refresh lifecycle
- Device discovery via iot.tuya.com
- Light on/off/dim/color-temp control (DPS codes)
- `config.yaml` schema for rooms, groups, schedules
- node-cron scheduler
- Local REST API on port 7891
- macOS LaunchAgent for persistence
- Johnny chat integration (natural language → REST)
- End-to-end test plan + common error codes

## What Austin Still Needs to Do

Before pasting the spec to Johnny, Austin needs to gather these from **iot.tuya.com**:

1. **Access ID** (Client ID) — Cloud > Development > [project] > **Overview tab**
2. **Access Secret** (Client Secret) — same Overview tab
3. **UID** — Cloud > Development > [project] > **Devices tab** > Link Tuya App Account (scan QR with Smart Life app)
4. **Region** — shown on the Overview tab (likely `us`)
5. **Room groups** — names of rooms and which Smart Life lights go in each
6. **Schedule** — on/off times, weekday vs. weekend preferences
7. **Timezone confirm** — Central time (America/Chicago)?

Austin has already created his iot.tuya.com account and project.

## Next Step

Once Austin has all 7 items above, either:
- **Option A**: Give them to Claude Code here → Claude will bake them into the spec so Johnny gets zero-question, ready-to-run instructions
- **Option B**: Paste the raw spec to Johnny and have Johnny ask Austin for credentials interactively

## The Full Spec

The complete Johnny implementation prompt is saved in memory. To regenerate it, ask:
> "Regenerate the full Tuya lighting spec for Johnny"

Key technical notes for regeneration:
- Signing: `clientId + [accessToken if not token-request] + t + nonce + stringToSign`
- `stringToSign` = `METHOD\nSHA256_HEX(body)\n\nurlPath[?sorted_params]`
- Empty body hash = `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- Control endpoint: `POST /v1.0/iot-03/devices/{device_id}/commands`
- Discovery: `GET /v1.0/users/{uid}/devices?from=home&page_size=50`
- npm deps: `node-cron`, `js-yaml`, `express`
- LaunchAgent at `~/Library/LaunchAgents/com.johnny.tuya-lights.plist`
- REST API port: 7891
