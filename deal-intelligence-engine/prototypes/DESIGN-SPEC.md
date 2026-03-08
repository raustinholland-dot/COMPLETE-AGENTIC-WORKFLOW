# Sunburst Mandala — Deal Lifecycle Visualization Design Spec

## Vision

A single organic visualization that communicates a deal's entire lifecycle at a glance — inspired by looking at a tree and immediately sensing its age, health, and history. The "ideal form" is instantly recognizable by the brain, and deviations from that ideal carry meaning without explanation — the way a warped cube looks wrong because you know what a cube should look like.

All dimensions (P2V2C2 scores, stakeholder evolution, activity density, stage progression, DAP milestones, deal value, complexity) are encoded simultaneously into one integrated form.

## Chosen Form: Mandala

After prototyping 4 candidate forms (flower, gem, tree ring, mandala), the mandala won decisively:
- Strongest "I can immediately tell what's going on" feeling
- Most visceral deviation detection (broken symmetry = something's wrong)
- Stackable: layered mandalas show deal history as depth
- 6-fold radial symmetry maps perfectly to 6 P2V2C2 dimensions

## Current Prototype Status

### Visualization Track 1: Mandala
- `form-candidates.html` — 4 candidate forms side-by-side (flower, gem, tree ring, mandala)
- `mandala-full.html` — Full 5-zone mandala with hover tooltips
- `mandala-stacked.html` — Layered history view with timeline slider + play button
- `mandala-v2.html` — Added adaptive time rings, deal value encoding, complexity ring
- `mandala-v3.html` — Fractal edge texture + stakeholder branches
- `mandala-v3a.html` — Enhanced fractal contrast (bigger bump scale, sub-peak branching at L3+), color saturation bloom (inner rings muted, outer vivid), organic branch curves on all deals (CURRENT MANDALA)
- `mandala-v4.html` — Experimental: feather density + stakeholder network merged into mandala (REJECTED — too many things in one viz)

### Visualization Track 2: Depth Circle (ALIS-style)
Inspired by Nadieh Bremer's ALIS OS visualization + Olympic Feathers (visualcinnamon.com). Concentric rings: center deal node, Ring 1 dimension nodes, Ring 2 evidence artifact clusters, Ring 3 stakeholder nodes with bezier connection lines.
- `depth-circle-v1.html` — 3 different deals side-by-side (simple/moderate/complex)
- `depth-circle-v2.html` — Same deal (Acme Health) at 6 time points showing full progression. Connections always visible. (CURRENT DEPTH CIRCLE — Austin liked this direction)

### Supporting JS files (used by form-candidates.html):
- `flower.js`, `gem.js`, `treering.js`, `mandala.js`

### To view prototypes:
```bash
cd deal-intelligence-engine/prototypes
python3 -m http.server 8888
# Open http://localhost:8888/depth-circle-v2.html (latest)
```

---

## Complete Encoding Scheme (7 zones + 2 surface features)

### Zone 1: CENTER CIRCLE
- **Radius** scales with deal value: $50K = 18px, $1M+ = 34px
- **Fill color** = deal stage: discover=#cbd5e1, qualify=#a5b4fc, prove=#6366f1, negotiate=#4338ca, close=#ca8a04
- **Number** = P2V2C2 total (0-30), bold white text
- **Border animation** = trend: improving = rotating bright arc (2s), declining = pulsing red glow (1.5s), stable = static white

### Zone 2: PE SPONSOR HALO (thin ring around center)
- Score 0: no ring (visible gap)
- Score 1-2: dashed red (#b91c1c)
- Score 3: solid amber (#f59e0b)
- Score 4-5: solid green (#15803d), 4px wide

### Zone 3: RADIAL ARMS (6 arms, stacked time-bucketed rings)

**6 arms** at 60-degree intervals from 12 o'clock: Pain, Power, Vision, Value, Change, Control

**Adaptive time bucketing:**
- Last 8 weeks: one ring per week (8px thick)
- Weeks 9-26: one ring per 2-week period (5px thick)
- Beyond 26 weeks: one ring per month (3.5px thick)
- Dormant periods (14+ days no activity): gray dashed ring (1.5px) spanning full 360 degrees

**Per segment encoding:**
- Angular width proportional to score (0-5 maps to 5-55 degrees)
- Color: 0-1=#b91c1c (red), 2=#f59e0b (amber), 3=#eab308, 4=#22c55e, 5=#15803d (green)
- Opacity by activity: 0-1 docs=0.5, 2-4=0.75, 5+=1.0
- Outermost ring glow: green if delta >= +4, red if <= -4

### Zone 4: DAP BOUNDARY (outer circle)
- No DAP: thin dashed #cbd5e1
- DAP exists, not agreed: solid amber #b45309
- DAP agreed: solid green #15803d
- Milestone arc: solid portion = milestones_complete/total * 360 degrees
- 14-day gap: boundary flashes between its color and red (800ms)
- Days-in-stage compression: gap between arms and boundary shrinks as deal stalls (10px normal, 2px minimum)

### Zone 5: OUTER GLOW (deal value)
- glowAlpha = 0.05 + (value/1M) * 0.30
- glowRadius = 20 + (value/1M) * 40
- Indigo (#6366f1) radial glow behind the mandala

### Surface Feature: FRACTAL EDGE TEXTURE (complexity)
- Complexity score (0-15) derived from: stakeholder count, workstream count, doc volume, doc type variety, calendar density
- Level 0 (score 0-3): Smooth arcs — clean, minimal
- Level 1 (score 4-6): Single Koch-curve bumps — slightly jagged
- Level 2 (score 7-9): Two levels of recursive subdivision — visibly textured
- Level 3 (score 10-12): Three levels — intricate, snowflake-like
- Level 4 (score 13-15): Four levels — ornate lacework edges
- Applied to outer edges of all arm segments
- Simple deal = smooth silhouette. Complex deal = spiky/crystalline silhouette.

### Surface Feature: STAKEHOLDER BRANCHES (replaces dots)
- Each stakeholder = a curved branch growing outward from DAP boundary
- Grouped by position: Champion (30 degrees), ES (90), DM (210), Other (270)
- Branch length by role: DM=25px, ES=20px, C=18px, PES=15px, PC=12px, OTHER=10px
- Branch thickness by role: DM=3px, ES=2.5px, C=2px, PES=1.5px, PC=1px
- Line style: confirmed (C/ES/DM) = solid, potential (PC/PES) = dashed
- Color: PC=#94a3b8, C=#6366f1, PES=#f59e0b, ES=#ca8a04, DM=#15803d
- Tip: potential = open circle, confirmed = filled circle, DM = larger filled
- Slight bezier curve for organic feel

---

## Stacked/History View

Overlay 10+ semi-transparent mandalas (18% opacity each) on one canvas:
- Consistent strength = deep accumulated color
- Consistent weakness = deep red
- Volatility = muddy mixed colors
- Growth = inner outlines small, outer outlines large (blooming effect)
- Stall = last 3+ layers identical shape (dense band at edge)

Interactive: timeline slider (1-10), play button (1 layer/sec), opacity control.

---

## Pipeline/Forest View (not yet built)

Grid of mini mandalas (80-160px each) for all 20-25 deals:
- Mandala SIZE = deal age (older deals physically larger)
- At 80px: glow, arm colors, fractal texture, branch count all still readable
- Click navigates to full detail view
- Sort by: score, stage, alphabetical

---

## Next Steps / Open Items

1. **Accentuate differences** — Make simple vs complex deals even more visually distinct
2. **3D exploration** — Consider CSS 3D transforms or isometric SVG for height dimension (deal progress). Deals "rise" from flat disc (Discover) to tall structure (Close). Not yet prototyped.
3. **Pipeline forest view** — Build the mini-mandala grid
4. **Integration into Deal Room UI** — Replace radar chart in left panel with mandala
5. **Backend data queries** — Extend CW-07 (get-deal-context) to return enriched history, activity density, complexity factors
6. **Hover tooltips** — Refine for all zones (partially implemented in v2)

---

## Data Requirements (for backend integration)

### Already available in get-deal-context response:
- scores (6 P2V2C2 + total), deal_stage, trend_direction, score_vs_previous
- stakeholders (with cps_role), score_history, dap object, risks, next_step

### Needs to be added to API response:
- `pe_sponsor_score` (in deal_health, not currently returned)
- `days_in_stage` (in deal_health, not currently returned)
- `score_history[].all_6_dimension_scores` (currently only returns total)
- `score_history[].doc_count` (join ingestion_log, count between scoring runs)
- `deal_value_usd` (in deals table)
- `first_scored_at` (for deal age calculation)
- Complexity factors: stakeholder_count, workstream_count, doc_chunk_total, doc_type_count, calendar_event_count

### Files to modify for integration:
- `deal-intelligence-engine/ui/index.html` — Add mandala renderer, replace radar chart
- CW-07 workflow (SYAQ4eVPyrp9XQMa) — Enriched history + activity density queries
- CW-13 workflow (h2CrtDQx4fUp4c7v) — Pipeline summary with latest scores for forest view

---

## Technical Approach
- Canvas-based rendering (not SVG) for compositing in stacked view
- No external dependencies (pure vanilla JS, consistent with existing UI)
- requestAnimationFrame loop for animations (trend pulse, DAP flash)
- Polar coordinate hit detection for hover tooltips
- Adaptive time bucketing algorithm for variable-length deal histories
- Koch-curve recursive subdivision for fractal edge texture
