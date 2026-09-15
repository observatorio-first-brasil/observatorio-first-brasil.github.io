// Wrappers finos sobre o Chart.js (carregado via CDN como `window.Chart`).
import { PALETTE, COMP_LABELS, COMP_KEYS } from "./lib.js";

const GRID = "#2b3742";
const TICK = "#93a4b3";

Chart.defaults.color = TICK;
Chart.defaults.font.family =
  "-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif";

const _live = new Map();
function mount(canvasId, cfg) {
  if (_live.has(canvasId)) _live.get(canvasId).destroy();
  const ctx = document.getElementById(canvasId);
  const c = new Chart(ctx, cfg);
  _live.set(canvasId, c);
  return c;
}
export function destroyAll() {
  for (const c of _live.values()) c.destroy();
  _live.clear();
}

const yearAxis = (min, max) => ({
  type: "linear",
  min: min - 0.15,
  max: max + 0.75,
  grid: { color: GRID },
  ticks: {
    stepSize: 1,
    callback: (v) => (Number.isInteger(v) ? v : ""),
  },
  title: { display: true, text: "Temporada" },
});

// Score no tempo — 1+ times. series: [{label, points:[{x,y,meta}], color}]
export function timeSeries(canvasId, series, { yLabel = "Score (0–100)", yMax = 100 } = {}) {
  const xs = series.flatMap((s) => s.points.map((p) => p.x));
  const min = Math.floor(Math.min(...xs, 2023));
  const max = Math.floor(Math.max(...xs, 2026));
  return mount(canvasId, {
    type: "line",
    data: {
      datasets: series.map((s, i) => ({
        label: s.label,
        data: s.points.map((p) => ({ x: p.x, y: p.y, meta: p.meta })),
        borderColor: s.color || PALETTE[i % PALETTE.length],
        backgroundColor: s.color || PALETTE[i % PALETTE.length],
        borderWidth: s.width || 2,
        borderDash: s.dash || [],
        pointRadius: s.pointRadius ?? 3,
        pointStyle: s.pointStyle || "circle",
        tension: 0.25,
        spanGaps: false,
      })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "nearest", intersect: false },
      scales: {
        x: yearAxis(min, max),
        y: { min: 0, max: yMax, grid: { color: GRID }, title: { display: true, text: yLabel } },
      },
      plugins: {
        legend: { display: series.length > 1, position: "bottom" },
        tooltip: {
          callbacks: {
            title: (items) => items[0].raw.meta?.title || "",
            label: (it) => {
              const m = it.raw.meta || {};
              const base = `${it.dataset.label}: ${it.parsed.y.toFixed(1)}`;
              return m.lines ? [base, ...m.lines] : base;
            },
          },
        },
      },
    },
  });
}

// Faixa p25–p75 + mediana de um estado (e opcionalmente outro + ref BR)
export function bandChart(canvasId, bands) {
  // bands: [{label,color, rows:[{x, median, p25, p75}]}], primeiro tem faixa
  const ds = [];
  bands.forEach((b, i) => {
    const col = b.color || PALETTE[i % PALETTE.length];
    if (b.rows[0] && b.rows[0].p25 != null && i === 0) {
      ds.push({
        label: "p25–p75",
        data: b.rows.map((r) => ({ x: r.x, y: r.p75 })),
        borderColor: "transparent",
        backgroundColor: hexA(col, 0.13),
        pointRadius: 0,
        fill: "+1",
      });
      ds.push({
        label: "_p25",
        data: b.rows.map((r) => ({ x: r.x, y: r.p25 })),
        borderColor: "transparent",
        pointRadius: 0,
        fill: false,
      });
    }
    ds.push({
      label: b.label,
      data: b.rows.map((r) => ({ x: r.x, y: r.median })),
      borderColor: col,
      backgroundColor: col,
      borderWidth: b.width || 2.5,
      borderDash: b.dash || [],
      pointRadius: 3,
      tension: 0.25,
    });
  });
  const xs = bands.flatMap((b) => b.rows.map((r) => r.x));
  const min = Math.min(...xs), max = Math.max(...xs);
  return mount(canvasId, {
    type: "line",
    data: { datasets: ds },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: "nearest", intersect: false },
      scales: {
        x: yearAxis(min, max),
        y: { min: 0, max: 100, grid: { color: GRID }, title: { display: true, text: "Score (0–100)" } },
      },
      plugins: {
        legend: {
          position: "bottom",
          labels: { filter: (i) => !i.text.startsWith("_") },
        },
      },
    },
  });
}

// Barras horizontais — ranking
export function rankBars(canvasId, items, { onClick } = {}) {
  return mount(canvasId, {
    type: "bar",
    data: {
      labels: items.map((i) => i.label),
      datasets: [{
        data: items.map((i) => i.value),
        backgroundColor: items.map((i) => i.color || PALETTE[0]),
        borderRadius: 4,
      }],
    },
    options: {
      indexAxis: "y",
      responsive: true, maintainAspectRatio: false,
      onClick: (_e, els) => { if (els.length && onClick) onClick(items[els[0].index]); },
      scales: {
        x: { min: 0, max: 100, grid: { color: GRID } },
        y: { grid: { display: false } },
      },
      plugins: { legend: { display: false } },
    },
  });
}

// Barras agrupadas — componentes do score p/ N times numa temporada
export function componentBars(canvasId, teams) {
  // teams: [{label, weighted:{...}, color}]
  return mount(canvasId, {
    type: "bar",
    data: {
      labels: COMP_KEYS.map((k) => COMP_LABELS[k]),
      datasets: teams.map((t, i) => ({
        label: t.label,
        data: COMP_KEYS.map((k) => t.weighted[k] ?? 0),
        backgroundColor: t.color || PALETTE[i % PALETTE.length],
        borderRadius: 4,
      })),
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: {
        x: { grid: { display: false } },
        y: { grid: { color: GRID }, title: { display: true, text: "Pontos no score (ponderado)" } },
      },
      plugins: { legend: { position: "bottom" } },
    },
  });
}

function hexA(hex, a) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}
