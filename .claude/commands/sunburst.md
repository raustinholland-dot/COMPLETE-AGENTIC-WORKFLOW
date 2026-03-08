---
name: sunburst
description: >
  Load design specs and prototypes for the deal lifecycle visualization (Mandala and
  Depth Circle tracks). Use when Austin wants to work on the sunburst/mandala/depth
  circle visualization or the deal health visual in the left panel.
---

# /sunburst — Prime session for Deal Lifecycle Visualization

Load design spec and context for both visualization tracks.

## What this command does

Read the following files and internalize their contents:

1. Read `deal-intelligence-engine/prototypes/DESIGN-SPEC.md` — Full design spec covering both tracks, encoding scheme, data requirements
2. Read `deal-intelligence-engine/prototypes/depth-circle-v2.html` — CURRENT preferred prototype (Depth Circle track)
3. Read `deal-intelligence-engine/prototypes/mandala-v3a.html` — CURRENT mandala prototype
4. Read `deal-intelligence-engine/ui/index.html` lines 1370-1650 — Current left panel rendering that the visualization will replace
5. List `deal-intelligence-engine/prototypes/` to see all prototype files

## After reading

Confirm to Austin:
- Current status of both visualization tracks
- What the open items / next steps are
- What needs to happen before integration into the Deal Room UI

## Two Visualization Tracks

### Track 1: Mandala (deal health overview)
- `mandala-v3a.html` is CURRENT — enhanced fractal contrast, color saturation bloom, organic branch curves
- `mandala-v4.html` was REJECTED (tried to merge too many concepts into one viz)
- Next: accentuate simple vs complex deal differences further

### Track 2: Depth Circle (ALIS-style relationship topology) — PREFERRED DIRECTION
- `depth-circle-v2.html` is CURRENT — same deal (Acme Health) at 6 time points showing full progression
- Connections always visible (alpha 0.25), bezier curves pulled toward center
- Concentric rings: center deal node, Ring 1 dimension nodes, Ring 2 evidence clusters, Ring 3 stakeholders
- Austin said "these are better, especially the depth circle one, very much better"

## Key context
- Prototypes are standalone HTML files served via `python3 -m http.server 8888` from the prototypes directory
- Canvas-based rendering (not SVG) for compositing support
- No external dependencies — pure vanilla JS
- The visualization replaces the existing radar chart in the Deal Room UI left panel
- Integration requires enriching CW-07 (get-deal-context) API response with additional fields
- Still in prototype phase — NOT integrating into the environment yet
