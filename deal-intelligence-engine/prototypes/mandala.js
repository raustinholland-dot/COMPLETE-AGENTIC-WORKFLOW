/**
 * Mandala Visualization — Deal Health as 6-Fold Radial Symmetry
 *
 * 6 radial arms (one per P2V2C2 dimension), 60 degrees apart.
 * Each arm is built from layered segments (one per scoring run).
 * Segment width = dimension score. Segment color = health gradient.
 * Perfect symmetry = balanced deal. Asymmetry = obvious weakness.
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

const DIMS = ['pain', 'power', 'vision', 'value', 'change', 'control'];
const DIM_LABELS = ['P', 'Pw', 'V', 'Va', 'Ch', 'Co'];

// Score-to-mandala-color mapping
function mandalaColor(score) {
  if (score <= 1) return '#b91c1c'; // red
  if (score === 2) return '#f59e0b'; // amber
  if (score === 3) return '#eab308'; // yellow
  if (score === 4) return '#22c55e'; // green
  return '#15803d';                  // deep green
}

// Slightly darker version for decorative inner lines
function mandalaColorDark(score) {
  if (score <= 1) return '#7f1d1d';
  if (score === 2) return '#b45309';
  if (score === 3) return '#a16207';
  if (score === 4) return '#15803d';
  return '#0f5132';
}

const SVG_NS = 'http://www.w3.org/2000/svg';

function svgEl(tag, attrs) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) el.setAttribute(k, v);
  return el;
}

/**
 * Build a petal/segment shape for one arm at one layer.
 *
 * The segment is a trapezoid along the radial arm direction.
 * Width (angular spread) is proportional to the dimension score.
 * It sits between rInner and rOuter along the arm's angle.
 *
 * @param {number} cx - center x
 * @param {number} cy - center y
 * @param {number} armAngle - angle of the arm axis in radians
 * @param {number} rInner - inner radius of this segment
 * @param {number} rOuter - outer radius of this segment
 * @param {number} score - 0-5, controls angular width
 * @returns {string} SVG path d
 */
function petalPath(cx, cy, armAngle, rInner, rOuter, score) {
  // Max half-angle for a segment: 28 degrees (just under 30 to leave gaps)
  const maxHalfAngle = (28 * Math.PI) / 180;
  // Score 0 still gets a thin sliver (2 degrees), score 5 gets full width
  const halfAngle = ((Math.max(score, 0.4) / 5) * maxHalfAngle);

  // Slight taper: outer edge is slightly wider than inner for organic petal feel
  const innerHalf = halfAngle * 0.85;
  const outerHalf = halfAngle;

  // Four corners of the petal
  const p1 = polarToCart(cx, cy, rInner, armAngle - innerHalf);
  const p2 = polarToCart(cx, cy, rInner, armAngle + innerHalf);
  const p3 = polarToCart(cx, cy, rOuter, armAngle + outerHalf);
  const p4 = polarToCart(cx, cy, rOuter, armAngle - outerHalf);

  // Use arcs for the inner and outer edges for roundedness
  const innerArc = `A ${rInner} ${rInner} 0 0 1 ${p2[0]} ${p2[1]}`;
  const outerArc = `A ${rOuter} ${rOuter} 0 0 0 ${p4[0]} ${p4[1]}`;

  return `M ${p1[0]} ${p1[1]} ${innerArc} L ${p3[0]} ${p3[1]} ${outerArc} Z`;
}

/**
 * Build a decorative inner line within a petal (thin arc at midpoint).
 */
function decorativeLine(cx, cy, armAngle, rInner, rOuter, score) {
  const maxHalfAngle = (28 * Math.PI) / 180;
  const halfAngle = ((Math.max(score, 0.4) / 5) * maxHalfAngle) * 0.5; // narrower than petal
  const rMid = (rInner + rOuter) / 2;

  const p1 = polarToCart(cx, cy, rMid, armAngle - halfAngle);
  const p2 = polarToCart(cx, cy, rMid, armAngle + halfAngle);

  return `M ${p1[0]} ${p1[1]} A ${rMid} ${rMid} 0 0 1 ${p2[0]} ${p2[1]}`;
}

/**
 * Small decorative dot at the tip of a petal segment.
 */
function decorativeDot(cx, cy, armAngle, rOuter) {
  const pos = polarToCart(cx, cy, rOuter - 2, armAngle);
  return { x: pos[0], y: pos[1] };
}

function polarToCart(cx, cy, r, angle) {
  return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)];
}

/**
 * Render a 6-fold radial mandala visualization.
 *
 * @param {string} containerId - DOM element ID
 * @param {Array} scoringRuns - array of scoring run objects
 * @param {Object} options - { ideal: boolean }
 */
function renderMandala(containerId, scoringRuns, options = {}) {
  const container = document.getElementById(containerId);
  if (!container) return;

  const runs = options.ideal ? makeIdealRuns(scoringRuns.length || 10) : scoringRuns;
  const cx = 110, cy = 110;
  const maxRadius = 88;
  const centerRadius = 14;

  const svg = svgEl('svg', {
    viewBox: '0 0 220 240',
    width: '220',
    height: '240',
    style: 'display:block;margin:auto;'
  });

  // --- Background ---
  const bg = svgEl('rect', {
    x: 0, y: 0, width: 220, height: 240,
    fill: '#0f172a', rx: '4'
  });
  svg.append(bg);

  // --- Outer border circle (subtle) ---
  const outerBorder = svgEl('circle', {
    cx, cy, r: maxRadius + 4,
    fill: 'none',
    stroke: '#334155',
    'stroke-width': '0.5',
    opacity: '0.5'
  });
  svg.append(outerBorder);

  // --- 60-degree guide lines (the skeleton) ---
  const guideGroup = svgEl('g', { opacity: '0.15' });
  for (let i = 0; i < 6; i++) {
    const angle = -Math.PI / 2 + i * (Math.PI / 3);
    const x2 = cx + (maxRadius + 2) * Math.cos(angle);
    const y2 = cy + (maxRadius + 2) * Math.sin(angle);
    const line = svgEl('line', {
      x1: cx, y1: cy, x2, y2,
      stroke: '#94a3b8',
      'stroke-width': '0.5'
    });
    guideGroup.append(line);
  }
  svg.append(guideGroup);

  // --- Concentric guide rings (very faint) ---
  const ringGuideGroup = svgEl('g', { opacity: '0.08' });
  for (let i = 1; i <= runs.length; i++) {
    const r = centerRadius + (i / runs.length) * (maxRadius - centerRadius);
    const ring = svgEl('circle', {
      cx, cy, r,
      fill: 'none',
      stroke: '#94a3b8',
      'stroke-width': '0.3'
    });
    ringGuideGroup.append(ring);
  }
  svg.append(ringGuideGroup);

  // --- Compute segment radii ---
  // Each scoring run gets an equal radial band
  const bandHeight = (maxRadius - centerRadius) / runs.length;

  // --- Draw petal segments for each arm and each run ---
  const petalsGroup = svgEl('g', {});

  for (let si = 0; si < 6; si++) {
    const armAngle = -Math.PI / 2 + si * (Math.PI / 3);
    const dim = DIMS[si];

    for (let ri = 0; ri < runs.length; ri++) {
      const run = runs[ri];
      const score = run[dim];
      const rInner = centerRadius + ri * bandHeight;
      const rOuter = centerRadius + (ri + 1) * bandHeight;

      // Main petal shape
      const petal = svgEl('path', {
        d: petalPath(cx, cy, armAngle, rInner + 0.5, rOuter - 0.5, score),
        fill: mandalaColor(score),
        stroke: '#0f172a',
        'stroke-width': '0.4',
        opacity: '0.9'
      });
      petalsGroup.append(petal);

      // Decorative inner arc line
      if (score >= 1) {
        const deco = svgEl('path', {
          d: decorativeLine(cx, cy, armAngle, rInner + 0.5, rOuter - 0.5, score),
          fill: 'none',
          stroke: mandalaColorDark(score),
          'stroke-width': '0.6',
          opacity: '0.5'
        });
        petalsGroup.append(deco);
      }

      // Decorative dot at outer edge of outermost segments
      if (ri === runs.length - 1 && score >= 3) {
        const dot = decorativeDot(cx, cy, armAngle, rOuter - 0.5);
        const dotEl = svgEl('circle', {
          cx: dot.x, cy: dot.y, r: 1.2,
          fill: mandalaColorDark(score),
          opacity: '0.6'
        });
        petalsGroup.append(dotEl);
      }
    }
  }

  svg.append(petalsGroup);

  // --- Outermost segment border ring ---
  const outerSegBorder = svgEl('circle', {
    cx, cy, r: maxRadius - 0.5,
    fill: 'none',
    stroke: '#475569',
    'stroke-width': '0.5',
    opacity: '0.4'
  });
  svg.append(outerSegBorder);

  // --- Central circle with total score ---
  const latestRun = runs[runs.length - 1];
  const totalScore = latestRun ? latestRun.total : 0;
  const centerFill = totalScore >= 25 ? '#15803d' : totalScore >= 18 ? '#22c55e' : totalScore >= 12 ? '#eab308' : '#b91c1c';

  // Outer glow ring
  const glow = svgEl('circle', {
    cx, cy, r: centerRadius + 2,
    fill: 'none',
    stroke: centerFill,
    'stroke-width': '1',
    opacity: '0.3'
  });
  svg.append(glow);

  // Center disc
  const center = svgEl('circle', {
    cx, cy, r: centerRadius,
    fill: '#0f172a',
    stroke: centerFill,
    'stroke-width': '1.5'
  });
  svg.append(center);

  // Score text
  const scoreText = svgEl('text', {
    x: cx, y: cy + 1,
    'text-anchor': 'middle',
    'dominant-baseline': 'central',
    'font-family': 'Helvetica, Arial, sans-serif',
    'font-size': '11',
    'font-weight': 'bold',
    fill: centerFill
  });
  scoreText.textContent = totalScore;
  svg.append(scoreText);

  // --- Dimension labels ---
  for (let si = 0; si < 6; si++) {
    const angle = -Math.PI / 2 + si * (Math.PI / 3);
    const labelR = maxRadius + 12;
    const lx = cx + labelR * Math.cos(angle);
    const ly = cy + labelR * Math.sin(angle);
    const label = svgEl('text', {
      x: lx, y: ly,
      'text-anchor': 'middle',
      'dominant-baseline': 'central',
      'font-family': 'Helvetica, Arial, sans-serif',
      'font-size': '8',
      fill: '#94a3b8',
      'font-weight': '600'
    });
    label.textContent = DIM_LABELS[si];
    svg.append(label);
  }

  // --- Bottom label ---
  const formLabel = svgEl('text', {
    x: 110, y: 232,
    'text-anchor': 'middle',
    'font-family': 'Helvetica, Arial, sans-serif',
    'font-size': '10',
    fill: '#64748b'
  });
  formLabel.textContent = options.ideal ? 'Mandala — Ideal: Perfect 6-fold symmetry' : 'Mandala';
  svg.append(formLabel);

  container.appendChild(svg);
}

/**
 * Generate ideal scoring runs — all dimensions at 5.
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
    if (document.getElementById('mandala')) {
      renderMandala('mandala', SAMPLE_RUNS);
    }
    if (document.getElementById('mandala-ideal')) {
      renderMandala('mandala-ideal', SAMPLE_RUNS, { ideal: true });
    }
  });
}
