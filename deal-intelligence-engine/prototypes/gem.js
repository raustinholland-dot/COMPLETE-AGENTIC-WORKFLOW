/**
 * gem.js — Hexagonal Crystal Gem Visualization
 *
 * Renders a top-down brilliant-cut hexagonal gemstone where each of the 6 facets
 * represents a P2V2C2 dimension. Healthy deals look like flawless precious stones;
 * struggling deals look dull, chipped, and broken.
 *
 * Usage:
 *   renderGem('container-id', scoringRuns, { ideal: false, size: 220, label: 'Gem' })
 */

// ---------------------------------------------------------------------------
// Sample data (hardcoded for standalone testing)
// ---------------------------------------------------------------------------
const GEM_SAMPLE_RUNS = [
  { scored_at:'2026-01-15', pain:1, power:1, vision:2, value:1, change:1, control:1, total:7,  stage:'discover', activity:5 },
  { scored_at:'2026-01-22', pain:2, power:1, vision:2, value:2, change:1, control:1, total:9,  stage:'discover', activity:4 },
  { scored_at:'2026-01-29', pain:2, power:2, vision:3, value:2, change:2, control:2, total:13, stage:'qualify',  activity:6 },
  { scored_at:'2026-02-05', pain:3, power:2, vision:3, value:2, change:2, control:2, total:14, stage:'qualify',  activity:3 },
  { scored_at:'2026-02-12', pain:3, power:2, vision:3, value:3, change:2, control:2, total:15, stage:'qualify',  activity:2 },
  { scored_at:'2026-02-19', pain:2, power:1, vision:2, value:2, change:1, control:2, total:10, stage:'qualify',  activity:1 },
  { scored_at:'2026-02-26', pain:3, power:2, vision:3, value:3, change:2, control:3, total:16, stage:'prove',   activity:4 },
  { scored_at:'2026-03-05', pain:4, power:2, vision:4, value:3, change:3, control:3, total:19, stage:'prove',   activity:7 },
  { scored_at:'2026-03-12', pain:4, power:2, vision:4, value:4, change:3, control:3, total:20, stage:'prove',   activity:5 },
  { scored_at:'2026-03-19', pain:5, power:2, vision:5, value:4, change:3, control:3, total:22, stage:'prove',   activity:6 },
];

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

// The 6 P2V2C2 dimensions, clockwise from 12 o'clock (top)
const GEM_DIMENSIONS = [
  { key: 'pain',    label: 'P'  },
  { key: 'power',   label: 'Pw' },
  { key: 'vision',  label: 'V'  },
  { key: 'value',   label: 'Va' },
  { key: 'change',  label: 'Ch' },
  { key: 'control', label: 'Co' },
];

// Score-to-color mapping: gem-like palette from near-black (0) to brilliant teal (5)
const GEM_COLORS = {
  0: '#1f2937',
  1: '#4b5563',
  2: 'rgba(167, 139, 250, 0.6)', // dusty mauve at 60%
  3: '#8b5cf6',
  4: '#3b82f6',
  5: '#06b6d4',
};

// Light direction offset: upper-left light source. Each facet index gets a
// lightness multiplier (0 = top, going clockwise).
const LIGHT_OFFSETS = [0.12, 0.06, -0.04, -0.10, -0.06, 0.04];

// ---------------------------------------------------------------------------
// Helper utilities
// ---------------------------------------------------------------------------

/** Create an SVG element with attributes */
function svgEl(tag, attrs) {
  const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    el.setAttribute(k, v);
  }
  return el;
}

/** Convert a hex color to {r,g,b} */
function hexToRgb(hex) {
  hex = hex.replace('#', '');
  return {
    r: parseInt(hex.substring(0, 2), 16),
    g: parseInt(hex.substring(2, 4), 16),
    b: parseInt(hex.substring(4, 6), 16),
  };
}

/** Lighten or darken an rgb by a factor (-1..1). Positive = lighten. */
function adjustBrightness(hex, factor) {
  // Handle rgba strings
  if (hex.startsWith('rgba')) {
    const match = hex.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
    if (match) {
      let r = parseInt(match[1]), g = parseInt(match[2]), b = parseInt(match[3]);
      if (factor > 0) {
        r = Math.min(255, Math.round(r + (255 - r) * factor));
        g = Math.min(255, Math.round(g + (255 - g) * factor));
        b = Math.min(255, Math.round(b + (255 - b) * factor));
      } else {
        r = Math.max(0, Math.round(r * (1 + factor)));
        g = Math.max(0, Math.round(g * (1 + factor)));
        b = Math.max(0, Math.round(b * (1 + factor)));
      }
      return `rgb(${r},${g},${b})`;
    }
  }
  const { r, g, b } = hexToRgb(hex);
  let nr, ng, nb;
  if (factor > 0) {
    nr = Math.min(255, Math.round(r + (255 - r) * factor));
    ng = Math.min(255, Math.round(g + (255 - g) * factor));
    nb = Math.min(255, Math.round(b + (255 - b) * factor));
  } else {
    nr = Math.max(0, Math.round(r * (1 + factor)));
    ng = Math.max(0, Math.round(g * (1 + factor)));
    nb = Math.max(0, Math.round(b * (1 + factor)));
  }
  return `rgb(${nr},${ng},${nb})`;
}

/** Get (x, y) for a point on a circle at a given angle (in radians) and radius. */
function polarToCart(cx, cy, radius, angleRad) {
  return {
    x: cx + radius * Math.cos(angleRad),
    y: cy + radius * Math.sin(angleRad),
  };
}

// ---------------------------------------------------------------------------
// Main render function
// ---------------------------------------------------------------------------

/**
 * Render the hexagonal gem visualization.
 *
 * @param {string} containerId  - DOM id of the container element
 * @param {Array}  scoringRuns  - Array of scoring run objects
 * @param {Object} options      - { ideal: bool, size: number, label: string }
 */
function renderGem(containerId, scoringRuns, options) {
  const opts = Object.assign({ ideal: false, size: 220, label: 'Gem' }, options || {});
  const runs = scoringRuns && scoringRuns.length ? scoringRuns : GEM_SAMPLE_RUNS;
  const latest = runs[runs.length - 1];

  // Resolve scores — if ideal mode, all 5s
  const scores = GEM_DIMENSIONS.map(d => opts.ideal ? 5 : (latest[d.key] || 0));
  const total = opts.ideal ? 30 : (latest.total || scores.reduce((a, b) => a + b, 0));

  // Geometry
  const W = opts.size;
  const H = opts.size + 20; // extra for label
  const cx = W / 2;
  const cy = W / 2;         // gem center (label goes below)
  const maxR = W * 0.41;    // full radius for score 5
  const minR = W * 0.07;    // minimum radius for score 0

  // Create SVG
  const svg = svgEl('svg', {
    viewBox: `0 0 ${W} ${H}`,
    width: W,
    height: H,
    style: 'display:block;',
  });

  // ------- Defs: gradients, filters -------
  const defs = svgEl('defs');

  // Drop shadow / glow filter for the gem
  const glowFilter = svgEl('filter', { id: 'gem-glow', x: '-50%', y: '-50%', width: '200%', height: '200%' });
  const feGauss = svgEl('feGaussianBlur', { in: 'SourceGraphic', stdDeviation: '6', result: 'blur' });
  const feMerge = svgEl('feMerge');
  const fmNode1 = svgEl('feMergeNode', { in: 'blur' });
  const fmNode2 = svgEl('feMergeNode', { in: 'SourceGraphic' });
  feMerge.appendChild(fmNode1);
  feMerge.appendChild(fmNode2);
  glowFilter.appendChild(feGauss);
  glowFilter.appendChild(feMerge);
  defs.appendChild(glowFilter);

  // Background radial gradient (jeweler's display)
  const bgGrad = svgEl('radialGradient', { id: 'gem-bg-grad', cx: '50%', cy: '45%', r: '55%' });
  bgGrad.appendChild(svgEl('stop', { offset: '0%', 'stop-color': '#1e293b' }));
  bgGrad.appendChild(svgEl('stop', { offset: '100%', 'stop-color': '#0f172a' }));
  defs.appendChild(bgGrad);

  // Per-facet gradients (center-bright to edge-dark)
  scores.forEach((score, i) => {
    const baseColor = GEM_COLORS[score] || GEM_COLORS[0];
    const lightAdj = LIGHT_OFFSETS[i];
    const brightCenter = adjustBrightness(baseColor, 0.35 + lightAdj);
    const darkEdge = adjustBrightness(baseColor, -0.15 + lightAdj);

    const grad = svgEl('radialGradient', {
      id: `facet-grad-${i}`,
      cx: '30%',
      cy: '30%',
      r: '80%',
    });
    grad.appendChild(svgEl('stop', { offset: '0%', 'stop-color': brightCenter }));
    grad.appendChild(svgEl('stop', { offset: '100%', 'stop-color': darkEdge }));
    defs.appendChild(grad);
  });

  // Center highlight gradient (table facet)
  const tableGrad = svgEl('radialGradient', { id: 'gem-table-grad', cx: '40%', cy: '35%', r: '60%' });
  tableGrad.appendChild(svgEl('stop', { offset: '0%', 'stop-color': 'rgba(255,255,255,0.35)' }));
  tableGrad.appendChild(svgEl('stop', { offset: '100%', 'stop-color': 'rgba(255,255,255,0)' }));
  defs.appendChild(tableGrad);

  svg.appendChild(defs);

  // ------- Background -------
  const bgRect = svgEl('rect', {
    x: 0, y: 0, width: W, height: W,
    rx: 12,
    fill: 'url(#gem-bg-grad)',
  });
  svg.appendChild(bgRect);

  // Subtle setting ring behind the gem
  svg.appendChild(svgEl('circle', {
    cx, cy, r: maxR + 8,
    fill: 'none',
    stroke: '#334155',
    'stroke-width': 1.5,
    opacity: 0.5,
  }));

  // ------- Compute facet vertices -------
  // Hexagon vertices: 6 points evenly spaced, starting at -90 deg (12 o'clock)
  const startAngle = -Math.PI / 2;
  const angleStep = (2 * Math.PI) / 6;

  // For each facet i, the triangle is: center -> vertex[i] -> vertex[i+1]
  // vertex distance from center = lerp(minR, maxR, score/5)
  const vertexRadii = scores.map(s => minR + (maxR - minR) * (s / 5));

  // Pre-compute vertex positions
  const vertices = vertexRadii.map((r, i) => {
    const angle = startAngle + i * angleStep;
    return polarToCart(cx, cy, r, angle);
  });

  // ------- Draw facets -------
  const facetGroup = svgEl('g', { filter: 'url(#gem-glow)' });

  scores.forEach((score, i) => {
    const next = (i + 1) % 6;
    const v1 = vertices[i];
    const v2 = vertices[next];

    // Facet triangle path: center -> v1 -> v2
    const d = `M ${cx} ${cy} L ${v1.x} ${v1.y} L ${v2.x} ${v2.y} Z`;

    // Main facet fill
    const facet = svgEl('path', {
      d,
      fill: `url(#facet-grad-${i})`,
      stroke: 'rgba(255,255,255,0.25)',
      'stroke-width': 1,
      'stroke-linejoin': 'round',
    });
    facetGroup.appendChild(facet);

    // Inner highlight line from center partway toward midpoint of outer edge
    // simulates the "star facet" reflection seen in brilliant-cut gems
    const midX = (v1.x + v2.x) / 2;
    const midY = (v1.y + v2.y) / 2;
    const hlLen = 0.55; // how far the highlight line extends
    const hlLine = svgEl('line', {
      x1: cx,
      y1: cy,
      x2: cx + (midX - cx) * hlLen,
      y2: cy + (midY - cy) * hlLen,
      stroke: 'rgba(255,255,255,0.12)',
      'stroke-width': 0.7,
    });
    facetGroup.appendChild(hlLine);
  });

  svg.appendChild(facetGroup);

  // ------- Center "table" facet -------
  // A small hexagonal highlight in the center to simulate the table
  const tableR = minR * 1.1;
  let tablePath = '';
  for (let i = 0; i < 6; i++) {
    const angle = startAngle + i * angleStep;
    const p = polarToCart(cx, cy, tableR, angle);
    tablePath += (i === 0 ? 'M' : 'L') + ` ${p.x} ${p.y} `;
  }
  tablePath += 'Z';

  svg.appendChild(svgEl('path', {
    d: tablePath,
    fill: 'url(#gem-table-grad)',
    stroke: 'rgba(255,255,255,0.15)',
    'stroke-width': 0.5,
  }));

  // ------- Center score text -------
  const scoreText = svgEl('text', {
    x: cx,
    y: cy + 1,
    'text-anchor': 'middle',
    'dominant-baseline': 'central',
    'font-family': "'SF Pro Display', 'Inter', system-ui, sans-serif",
    'font-size': total >= 10 ? '13' : '14',
    'font-weight': '700',
    fill: total >= 20 ? '#e0f2fe' : total >= 15 ? '#c7d2fe' : '#94a3b8',
    'letter-spacing': '0.5',
  });
  scoreText.textContent = total;
  svg.appendChild(scoreText);

  // ------- Sparkle dots on high-score facet tips -------
  scores.forEach((score, i) => {
    if (score >= 4) {
      const v = vertices[i];
      // Place sparkle near the vertex tip
      const sparkle = svgEl('circle', {
        cx: v.x,
        cy: v.y,
        r: score === 5 ? 2.2 : 1.5,
        fill: 'white',
        opacity: score === 5 ? 0.85 : 0.55,
      });
      svg.appendChild(sparkle);

      // A second tiny sparkle offset slightly for brilliance
      if (score === 5) {
        const offset = polarToCart(v.x, v.y, 5, startAngle + i * angleStep - 0.4);
        svg.appendChild(svgEl('circle', {
          cx: offset.x,
          cy: offset.y,
          r: 1,
          fill: 'white',
          opacity: 0.6,
        }));
      }
    }
  });

  // ------- Dimension labels (outside the gem) -------
  const labelR = maxR + 16;
  GEM_DIMENSIONS.forEach((dim, i) => {
    const angle = startAngle + i * angleStep;
    const p = polarToCart(cx, cy, labelR, angle);
    const lbl = svgEl('text', {
      x: p.x,
      y: p.y,
      'text-anchor': 'middle',
      'dominant-baseline': 'central',
      'font-family': "'SF Pro Text', 'Inter', system-ui, sans-serif",
      'font-size': '8',
      'font-weight': '500',
      fill: '#94a3b8',
      'letter-spacing': '0.3',
    });
    lbl.textContent = dim.label;
    svg.appendChild(lbl);
  });

  // ------- Bottom label -------
  const labelText = opts.ideal
    ? `${opts.label}  |  Ideal: flawless, brilliant, symmetric`
    : `${opts.label}  |  ${latest.scored_at || ''}  ${latest.stage || ''}`;

  const bottomLabel = svgEl('text', {
    x: W / 2,
    y: W + 14,
    'text-anchor': 'middle',
    'dominant-baseline': 'central',
    'font-family': "'SF Pro Text', 'Inter', system-ui, sans-serif",
    'font-size': '9',
    fill: '#64748b',
    'letter-spacing': '0.3',
  });
  bottomLabel.textContent = labelText;
  svg.appendChild(bottomLabel);

  // ------- Mount into container -------
  const container = document.getElementById(containerId);
  if (container) {
    container.appendChild(svg);
  }

  return svg;
}
