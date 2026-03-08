/**
 * Tree Ring Visualization — Deal Health as a Cross-Section of Wood
 *
 * Each concentric ring = one scoring run (innermost = oldest).
 * Each ring is divided into 6 sectors (P2V2C2 dimensions).
 * Ring thickness = activity density. Sector color = dimension score.
 * Thick green rings = healthy growth. Thin dark rings = stress/drought.
 */

const SAMPLE_RUNS = [
  { scored_at:'2026-01-15', pain:1, power:1, vision:2, value:1, change:1, control:1, total:7, stage:'discover', activity:5 },
  { scored_at:'2026-01-22', pain:2, power:1, vision:2, value:2, change:1, control:1, total:9, stage:'discover', activity:4 },
  { scored_at:'2026-01-29', pain:2, power:2, vision:3, value:2, change:2, control:2, total:13, stage:'qualify', activity:6 },
  { scored_at:'2026-02-05', pain:3, power:2, vision:3, value:2, change:2, control:2, total:14, stage:'qualify', activity:3 },
  { scored_at:'2026-02-12', pain:3, power:2, vision:3, value:3, change:2, control:2, total:15, stage:'qualify', activity:2 },
  { scored_at:'2026-02-19', pain:2, power:1, vision:2, value:2, change:1, control:2, total:10, stage:'qualify', activity:1 },
  { scored_at:'2026-02-26', pain:3, power:2, vision:3, value:3, change:2, control:3, total:16, stage:'prove', activity:4 },
  { scored_at:'2026-03-05', pain:4, power:2, vision:4, value:3, change:3, control:3, total:19, stage:'prove', activity:7 },
  { scored_at:'2026-03-12', pain:4, power:2, vision:4, value:4, change:3, control:3, total:20, stage:'prove', activity:5 },
  { scored_at:'2026-03-19', pain:5, power:2, vision:5, value:4, change:3, control:3, total:22, stage:'prove', activity:6 },
];

// Dimension keys in sector order (clockwise from 12 o'clock)
const DIMS = ['pain', 'power', 'vision', 'value', 'change', 'control'];
const DIM_LABELS = ['P', 'Pw', 'V', 'Va', 'Ch', 'Co'];

// Score-to-wood-color mapping
function woodColor(score) {
  if (score <= 1) return '#92400e'; // dark stressed wood
  if (score === 2) return '#b45309'; // amber wood
  if (score === 3) return '#d97706'; // warm wood
  if (score === 4) return '#a3e635'; // light healthy wood
  return '#65a30d';                  // rich healthy heartwood
}

// Map activity (1-7) to ring thickness (3-10px)
function ringThickness(activity) {
  return 3 + ((activity - 1) / 6) * 7;
}

// SVG namespace
const SVG_NS = 'http://www.w3.org/2000/svg';

function svgEl(tag, attrs) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) el.setAttribute(k, v);
  return el;
}

/**
 * Build a wavy arc path for one sector of one ring.
 * Uses sine perturbation on inner/outer radii for organic feel.
 *
 * @param {number} cx - center x
 * @param {number} cy - center y
 * @param {number} rInner - inner radius
 * @param {number} rOuter - outer radius
 * @param {number} startAngle - in radians
 * @param {number} endAngle - in radians
 * @param {number} ringIdx - used to seed the waviness
 * @returns {string} SVG path d attribute
 */
function wavySectorPath(cx, cy, rInner, rOuter, startAngle, endAngle, ringIdx) {
  const steps = 20; // arc resolution
  const wobbleAmp = 0.8; // pixels of wobble
  const wobbleFreq = 3 + ringIdx * 0.7; // vary per ring for natural look

  // Generate points along outer arc (startAngle -> endAngle)
  const outerPts = [];
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    const angle = startAngle + t * (endAngle - startAngle);
    const wobble = Math.sin(angle * wobbleFreq + ringIdx * 1.3) * wobbleAmp;
    const r = rOuter + wobble;
    outerPts.push([cx + r * Math.cos(angle), cy + r * Math.sin(angle)]);
  }

  // Generate points along inner arc (endAngle -> startAngle, reversed)
  const innerPts = [];
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    const angle = endAngle - t * (endAngle - startAngle);
    const wobble = Math.sin(angle * wobbleFreq + ringIdx * 0.9) * wobbleAmp * 0.7;
    const r = rInner + wobble;
    innerPts.push([cx + r * Math.cos(angle), cy + r * Math.sin(angle)]);
  }

  // Build path
  let d = `M ${outerPts[0][0]} ${outerPts[0][1]}`;
  for (let i = 1; i < outerPts.length; i++) {
    d += ` L ${outerPts[i][0]} ${outerPts[i][1]}`;
  }
  d += ` L ${innerPts[0][0]} ${innerPts[0][1]}`;
  for (let i = 1; i < innerPts.length; i++) {
    d += ` L ${innerPts[i][0]} ${innerPts[i][1]}`;
  }
  d += ' Z';
  return d;
}

/**
 * Render a tree ring cross-section visualization.
 *
 * @param {string} containerId - DOM element ID to append SVG into
 * @param {Array} scoringRuns - array of scoring run objects
 * @param {Object} options - { ideal: boolean }
 */
function renderTreeRing(containerId, scoringRuns, options = {}) {
  const container = document.getElementById(containerId);
  if (!container) return;

  const runs = options.ideal ? makeIdealRuns(scoringRuns.length || 10) : scoringRuns;
  const cx = 110, cy = 110;
  const maxRadius = 90;
  const heartwoodRadius = 16;

  const svg = svgEl('svg', {
    viewBox: '0 0 220 240',
    width: '220',
    height: '240',
    style: 'display:block;margin:auto;'
  });

  // --- Defs: wood grain texture filter + bark pattern ---
  const defs = svgEl('defs', {});

  // Subtle noise filter for wood texture
  const filter = svgEl('filter', { id: 'woodGrain' });
  const turb = svgEl('feTurbulence', {
    type: 'fractalNoise', baseFrequency: '0.03 0.4', numOctaves: '4', seed: '2', result: 'grain'
  });
  const colorMatrix = svgEl('feColorMatrix', {
    in: 'grain', type: 'saturate', values: '0', result: 'bwGrain'
  });
  const blend = svgEl('feBlend', { in: 'SourceGraphic', in2: 'bwGrain', mode: 'multiply' });
  filter.append(turb, colorMatrix, blend);
  defs.append(filter);
  svg.append(defs);

  // --- Background: bark area ---
  const bark = svgEl('circle', {
    cx, cy, r: maxRadius + 6,
    fill: '#5c3d2e',
    stroke: '#3e2723',
    'stroke-width': '3'
  });
  svg.append(bark);

  // Bark texture rings (very faint)
  for (let i = 0; i < 4; i++) {
    const barkRing = svgEl('circle', {
      cx, cy, r: maxRadius + 2 + i * 1.5,
      fill: 'none',
      stroke: '#4e342e',
      'stroke-width': '0.5',
      opacity: '0.4'
    });
    svg.append(barkRing);
  }

  // --- Radial wood-grain lines (very faint, radiating from center) ---
  const grainGroup = svgEl('g', { opacity: '0.06' });
  for (let i = 0; i < 36; i++) {
    const angle = (i / 36) * Math.PI * 2;
    const line = svgEl('line', {
      x1: cx, y1: cy,
      x2: cx + (maxRadius + 4) * Math.cos(angle),
      y2: cy + (maxRadius + 4) * Math.sin(angle),
      stroke: '#1a0f00',
      'stroke-width': '0.5'
    });
    grainGroup.append(line);
  }
  svg.append(grainGroup);

  // --- Compute ring radii ---
  // Each ring gets thickness based on activity. We scale so they all fit.
  const rawThicknesses = runs.map(r => ringThickness(r.activity));
  const totalRawThickness = rawThicknesses.reduce((a, b) => a + b, 0);
  const availableRadius = maxRadius - heartwoodRadius;
  const scale = availableRadius / totalRawThickness;

  // Build cumulative radii
  const ringRadii = []; // [{inner, outer}]
  let currentR = heartwoodRadius;
  for (let i = 0; i < runs.length; i++) {
    const thickness = rawThicknesses[i] * scale;
    ringRadii.push({ inner: currentR, outer: currentR + thickness });
    currentR += thickness;
  }

  // --- Draw ring sectors ---
  const sectorAngle = (Math.PI * 2) / 6;
  // Offset so first sector is centered at 12 o'clock
  const angleOffset = -Math.PI / 2 - sectorAngle / 2;

  const ringsGroup = svgEl('g', { filter: 'url(#woodGrain)' });

  for (let ri = 0; ri < runs.length; ri++) {
    const run = runs[ri];
    const { inner, outer } = ringRadii[ri];

    for (let si = 0; si < 6; si++) {
      const dim = DIMS[si];
      const score = run[dim];
      const startA = angleOffset + si * sectorAngle;
      const endA = startA + sectorAngle;

      const path = svgEl('path', {
        d: wavySectorPath(cx, cy, inner, outer, startA, endA, ri),
        fill: woodColor(score),
        stroke: '#2c1a0e',
        'stroke-width': '0.3'
      });
      ringsGroup.append(path);
    }

    // Ring boundary (dark line at outer edge of each ring for that "growth ring" look)
    // Use a wavy circle
    if (ri < runs.length - 1) {
      const boundaryPts = [];
      const bSteps = 120;
      for (let i = 0; i <= bSteps; i++) {
        const angle = (i / bSteps) * Math.PI * 2;
        const wobble = Math.sin(angle * (3 + ri * 0.7) + ri * 1.3) * 0.8;
        const r = outer + wobble;
        boundaryPts.push(`${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`);
      }
      const boundaryPath = svgEl('polygon', {
        points: boundaryPts.join(' '),
        fill: 'none',
        stroke: '#1a0f00',
        'stroke-width': '0.4',
        opacity: '0.5'
      });
      ringsGroup.append(boundaryPath);
    }
  }

  svg.append(ringsGroup);

  // --- Heartwood center circle ---
  const latestRun = runs[runs.length - 1];
  const totalScore = latestRun ? latestRun.total : 0;
  const heartwoodFill = totalScore >= 25 ? '#65a30d' : totalScore >= 18 ? '#a3e635' : totalScore >= 12 ? '#d97706' : '#92400e';

  const heartwood = svgEl('circle', {
    cx, cy, r: heartwoodRadius,
    fill: heartwoodFill,
    stroke: '#1a0f00',
    'stroke-width': '0.6'
  });
  svg.append(heartwood);

  // Score text in center
  const scoreText = svgEl('text', {
    x: cx, y: cy + 1,
    'text-anchor': 'middle',
    'dominant-baseline': 'central',
    'font-family': 'Georgia, serif',
    'font-size': '11',
    'font-weight': 'bold',
    fill: totalScore >= 18 ? '#1a2e05' : '#fff8e1'
  });
  scoreText.textContent = totalScore;
  svg.append(scoreText);

  // --- Dimension labels (tiny, at outermost edge) ---
  for (let si = 0; si < 6; si++) {
    const angle = angleOffset + si * sectorAngle + sectorAngle / 2;
    const labelR = maxRadius + 14;
    const lx = cx + labelR * Math.cos(angle);
    const ly = cy + labelR * Math.sin(angle);
    const label = svgEl('text', {
      x: lx, y: ly,
      'text-anchor': 'middle',
      'dominant-baseline': 'central',
      'font-family': 'Helvetica, Arial, sans-serif',
      'font-size': '8',
      fill: '#d7ccc8',
      'font-weight': '600'
    });
    label.textContent = DIM_LABELS[si];
    svg.append(label);
  }

  // --- Bottom label ---
  const formLabel = svgEl('text', {
    x: 110, y: 232,
    'text-anchor': 'middle',
    'font-family': 'Georgia, serif',
    'font-size': '10',
    fill: '#5c4033'
  });
  formLabel.textContent = options.ideal ? 'Tree Ring — Ideal: Even growth, all heartwood' : 'Tree Ring';
  svg.append(formLabel);

  container.appendChild(svg);
}

/**
 * Generate ideal scoring runs — all dimensions at 5, high activity.
 */
function makeIdealRuns(count) {
  const runs = [];
  for (let i = 0; i < count; i++) {
    runs.push({
      scored_at: `2026-01-${String(15 + i * 7).padStart(2, '0')}`,
      pain: 5, power: 5, vision: 5, value: 5, change: 5, control: 5,
      total: 30, stage: 'close', activity: 6
    });
  }
  return runs;
}

// Auto-render if containers exist on page load
if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('treering')) {
      renderTreeRing('treering', SAMPLE_RUNS);
    }
    if (document.getElementById('treering-ideal')) {
      renderTreeRing('treering-ideal', SAMPLE_RUNS, { ideal: true });
    }
  });
}
