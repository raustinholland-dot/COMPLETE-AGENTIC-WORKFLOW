/**
 * Flower Visualization — 6-Petal P2V2C2 Bloom
 *
 * Each petal represents one CPS dimension (Pain, Power, Vision, Value, Change, Control).
 * Petal length encodes the score (0-5), color encodes health (red-to-green gradient).
 * A healthy deal is a full, vibrant bloom. A struggling deal is wilted and red.
 *
 * Usage:
 *   renderFlower('container-id', scoringRuns, { ideal: false, size: 220, label: 'Flower' });
 */

// ---------------------------------------------------------------------------
// Sample data (hardcoded for standalone testing)
// ---------------------------------------------------------------------------
const SAMPLE_RUNS = [
  { scored_at:'2026-01-15', pain:1, power:1, vision:2, value:1, change:1, control:1, total:7,  stage:'discover', activity:5 },
  { scored_at:'2026-01-22', pain:2, power:1, vision:2, value:2, change:1, control:1, total:9,  stage:'discover', activity:4 },
  { scored_at:'2026-01-29', pain:2, power:2, vision:3, value:2, change:2, control:2, total:13, stage:'qualify',   activity:6 },
  { scored_at:'2026-02-05', pain:3, power:2, vision:3, value:2, change:2, control:2, total:14, stage:'qualify',   activity:3 },
  { scored_at:'2026-02-12', pain:3, power:2, vision:3, value:3, change:2, control:2, total:15, stage:'qualify',   activity:2 },
  { scored_at:'2026-02-19', pain:2, power:1, vision:2, value:2, change:1, control:2, total:10, stage:'qualify',   activity:1 },
  { scored_at:'2026-02-26', pain:3, power:2, vision:3, value:3, change:2, control:3, total:16, stage:'prove',     activity:4 },
  { scored_at:'2026-03-05', pain:4, power:2, vision:4, value:3, change:3, control:3, total:19, stage:'prove',     activity:7 },
  { scored_at:'2026-03-12', pain:4, power:2, vision:4, value:4, change:3, control:3, total:20, stage:'prove',     activity:5 },
  { scored_at:'2026-03-19', pain:5, power:2, vision:5, value:4, change:3, control:3, total:22, stage:'prove',     activity:6 },
];

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const DIMENSIONS = [
  { key: 'pain',    label: 'P'  },
  { key: 'power',   label: 'Pw' },
  { key: 'vision',  label: 'V'  },
  { key: 'value',   label: 'Va' },
  { key: 'change',  label: 'Ch' },
  { key: 'control', label: 'Co' },
];

// Color stops for scores 0-5
const SCORE_COLORS = {
  0: '#b91c1c',  // red
  1: '#b91c1c',  // red
  2: '#f59e0b',  // amber
  3: '#eab308',  // yellow
  4: '#22c55e',  // green
  5: '#15803d',  // deep green
};

// Darker stroke variants for petal outlines
const STROKE_COLORS = {
  0: '#7f1d1d',
  1: '#7f1d1d',
  2: '#b45309',
  3: '#a16207',
  4: '#16a34a',
  5: '#166534',
};

// Center circle color based on total (0-30)
function centerColor(total) {
  if (total < 12) return '#b91c1c';
  if (total < 20) return '#f59e0b';
  return '#15803d';
}

// ---------------------------------------------------------------------------
// SVG helper — creates an SVG element with attributes
// ---------------------------------------------------------------------------
function svgEl(tag, attrs, parent) {
  const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    el.setAttribute(k, v);
  }
  if (parent) parent.appendChild(el);
  return el;
}

// ---------------------------------------------------------------------------
// Build a single petal path (cubic bezier, organic elliptical shape)
//
// The petal points upward (toward -Y) and is then rotated into position.
// score: 0-5, controls length. angleDeg: rotation from 12-o'clock.
// ---------------------------------------------------------------------------
function petalPath(score, angleDeg, cx, cy) {
  // Length: score 5 = 80px, score 0 = 10px stub
  const length = 10 + (score / 5) * 70;

  // Width at widest point (scales slightly with length for organic feel)
  const halfWidth = 6 + (score / 5) * 9; // 6-15px half-width

  // Control point offsets for the cubic bezier (organic rounded shape)
  const cpLen1 = length * 0.35;  // first control point distance along axis
  const cpLen2 = length * 0.75;  // second control point distance along axis
  const cpW1   = halfWidth * 1.3; // first control point width spread
  const cpW2   = halfWidth * 0.6; // second control point width spread (narrowing toward tip)

  // Build path in local coords (tip at 0, -length; base at 0, 0)
  // Right side: base(0,0) -> tip(0,-length) via cubic bezier
  // Left side: tip(0,-length) -> base(0,0) via cubic bezier (mirrored)
  const d = [
    `M 0,0`,
    // Right side curve to tip
    `C ${cpW1},${-cpLen1}  ${cpW2},${-cpLen2}  0,${-length}`,
    // Left side curve back to base
    `C ${-cpW2},${-cpLen2}  ${-cpW1},${-cpLen1}  0,0`,
    `Z`
  ].join(' ');

  return { d, length, angleDeg, cx, cy };
}

// ---------------------------------------------------------------------------
// Render the flower SVG
// ---------------------------------------------------------------------------
function renderFlower(containerId, scoringRuns, options) {
  const opts = Object.assign({ ideal: false, size: 220, label: 'Flower' }, options || {});
  const container = typeof containerId === 'string'
    ? document.getElementById(containerId)
    : containerId;

  if (!container) {
    console.error('renderFlower: container not found:', containerId);
    return;
  }

  const runs = scoringRuns && scoringRuns.length ? scoringRuns : SAMPLE_RUNS;
  const latest = runs[runs.length - 1];

  // If ideal mode, override all scores to 5
  const scores = {};
  DIMENSIONS.forEach(dim => {
    scores[dim.key] = opts.ideal ? 5 : (latest[dim.key] || 0);
  });
  const total = opts.ideal ? 30 : (latest.total || 0);

  // Center of the flower
  const cx = 110;
  const cy = 105;

  // Unique ID prefix for gradient definitions (support multiple flowers on one page)
  const uid = 'fl_' + Math.random().toString(36).slice(2, 8);

  // Create SVG root
  const svg = svgEl('svg', {
    viewBox: '0 0 220 240',
    width: opts.size,
    height: Math.round(opts.size * (240 / 220)),
    xmlns: 'http://www.w3.org/2000/svg',
    style: 'display:block;margin:auto;',
  });

  // --- Defs: radial gradients for each petal ---
  const defs = svgEl('defs', {}, svg);

  DIMENSIONS.forEach((dim, i) => {
    const score = scores[dim.key];
    const color = SCORE_COLORS[score];

    // Radial gradient: lighter center, saturated tip
    const grad = svgEl('radialGradient', {
      id: `${uid}_pg${i}`,
      cx: '50%', cy: '100%', r: '100%',
      fx: '50%', fy: '100%',
      gradientUnits: 'objectBoundingBox',
    }, defs);

    svgEl('stop', { offset: '0%',   'stop-color': color, 'stop-opacity': '0.45' }, grad);
    svgEl('stop', { offset: '55%',  'stop-color': color, 'stop-opacity': '0.75' }, grad);
    svgEl('stop', { offset: '100%', 'stop-color': color, 'stop-opacity': '1'    }, grad);
  });

  // --- Subtle stem line ---
  svgEl('line', {
    x1: cx, y1: cy + 18,
    x2: cx, y2: cy + 70,
    stroke: '#6b8e5a',
    'stroke-width': '2.5',
    'stroke-linecap': 'round',
    opacity: '0.35',
  }, svg);

  // Small leaf on stem
  const leafPath = `M ${cx},${cy + 45} C ${cx + 12},${cy + 38} ${cx + 16},${cy + 48} ${cx + 6},${cy + 55}`;
  svgEl('path', {
    d: leafPath,
    fill: '#6b8e5a',
    opacity: '0.25',
    stroke: 'none',
  }, svg);

  // --- Render petals ---
  DIMENSIONS.forEach((dim, i) => {
    const score = scores[dim.key];
    const angleDeg = i * 60 - 90; // start at 12-o'clock (-90), clockwise
    const petal = petalPath(score, angleDeg, cx, cy);
    const color = SCORE_COLORS[score];
    const strokeCol = STROKE_COLORS[score];

    // Petal group with rotation
    const g = svgEl('g', {
      transform: `translate(${cx}, ${cy}) rotate(${angleDeg + 90})`,
    }, svg);

    svgEl('path', {
      d: petal.d,
      fill: `url(#${uid}_pg${i})`,
      stroke: strokeCol,
      'stroke-width': '1',
      opacity: '0.85',
    }, g);

    // --- Dimension label at petal tip ---
    const angleRad = (angleDeg) * Math.PI / 180;
    const labelDist = petal.length + 12;
    const lx = cx + Math.cos(angleRad) * labelDist;
    const ly = cy + Math.sin(angleRad) * labelDist;

    svgEl('text', {
      x: lx, y: ly,
      'text-anchor': 'middle',
      'dominant-baseline': 'central',
      'font-size': '8',
      'font-family': 'system-ui, sans-serif',
      'font-weight': '600',
      fill: '#555',
      opacity: '0.8',
    }, svg).textContent = dim.label;
  });

  // --- Center circle ---
  const centerR = 16;

  // Outer ring (soft shadow)
  svgEl('circle', {
    cx, cy, r: centerR + 2,
    fill: 'none',
    stroke: '#00000015',
    'stroke-width': '3',
  }, svg);

  // Main center disc
  svgEl('circle', {
    cx, cy, r: centerR,
    fill: centerColor(total),
    stroke: '#fff',
    'stroke-width': '2',
  }, svg);

  // Stamen/pistil dots — tiny circles arranged in center
  const stamenAngles = [0, 60, 120, 180, 240, 300];
  stamenAngles.forEach(a => {
    const rad = a * Math.PI / 180;
    const sr = 5;
    svgEl('circle', {
      cx: cx + Math.cos(rad) * sr,
      cy: cy + Math.sin(rad) * sr,
      r: 1.5,
      fill: '#ffffff80',
      stroke: 'none',
    }, svg);
  });

  // Center dot
  svgEl('circle', {
    cx, cy, r: 2,
    fill: '#ffffff90',
    stroke: 'none',
  }, svg);

  // Total score text
  svgEl('text', {
    x: cx, y: cy + 1,
    'text-anchor': 'middle',
    'dominant-baseline': 'central',
    'font-size': '12',
    'font-weight': '700',
    'font-family': 'system-ui, sans-serif',
    fill: '#fff',
  }, svg).textContent = total;

  // --- Label below flower ---
  svgEl('text', {
    x: cx, y: 210,
    'text-anchor': 'middle',
    'dominant-baseline': 'central',
    'font-size': '11',
    'font-weight': '600',
    'font-family': 'system-ui, sans-serif',
    fill: '#333',
  }, svg).textContent = opts.label;

  svgEl('text', {
    x: cx, y: 225,
    'text-anchor': 'middle',
    'dominant-baseline': 'central',
    'font-size': '8',
    'font-family': 'system-ui, sans-serif',
    fill: '#888',
  }, svg).textContent = 'Ideal: full bloom, all petals equal';

  // Append to container
  container.appendChild(svg);

  return svg;
}

// ---------------------------------------------------------------------------
// Expose globally for cross-file usage
// ---------------------------------------------------------------------------
if (typeof window !== 'undefined') {
  window.renderFlower = renderFlower;
  window.FLOWER_SAMPLE_RUNS = SAMPLE_RUNS;
}
