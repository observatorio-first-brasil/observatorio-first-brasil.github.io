// Carregamento de dados + helpers compartilhados.

export const IS_FTC = location.pathname.split("/").includes("ftc");
export const DATA_URL = new URL(IS_FTC ? "../ftc/data.json" : "../data/data.json", import.meta.url);
export const CONFIG_URL = new URL(IS_FTC ? "../ftc/config.json" : "../data/config.json", import.meta.url);
let _data = null;

export async function loadData() {
  if (_data) return _data;
  const res = await fetch(DATA_URL, { cache: "no-cache" });
  if (!res.ok) throw new Error("Falha ao carregar data/data.json (rode `make data`)");
  _data = await res.json();
  _data.teamList = Object.values(_data.teams).sort((a, b) => a.team - b.team);
  _data.stateList = Object.keys(_data.states).sort();
  return _data;
}

export const SEASONS = () => _data.seasons;
export const LATEST = () => _data.seasons[_data.seasons.length - 1];

export const COMP_LABELS = {
  performance: IS_FTC ? "Performance (OPR)" : "Performance (EPA/OPR)",
  premios: "Prêmios",
  playoff: "Playoff",
  winrate: "Aproveitamento",
  progression: "Nível alcançado",
};
export const COMP_KEYS = ["performance", "premios", "playoff", "winrate", ...(IS_FTC ? ["progression"] : [])];

// paleta p/ séries
export const PALETTE = [
  "#3ea6ff", "#ffd166", "#4cc38a", "#e5677b", "#b98cff",
  "#4dd0e1", "#f28f3b", "#9ccc65", "#ff8fab", "#7986cb",
];

export function scoreColor(s) {
  if (s == null) return "#93a4b3";
  if (s >= 75) return "#4cc38a";
  if (s >= 55) return "#7bd88f";
  if (s >= 40) return "#ffd166";
  if (s >= 25) return "#e5a54b";
  return "#e5677b";
}

export function grade(s) {
  if (s == null) return "—";
  if (s >= 80) return "Elite";
  if (s >= 65) return "Muito forte";
  if (s >= 50) return "Consolidada";
  if (s >= 35) return "Em desenvolvimento";
  if (s >= 20) return "Inicial";
  return "Nascente";
}

export function fmt(n, d = 1) {
  return n == null || Number.isNaN(n) ? "—" : Number(n).toFixed(d);
}

export function teamSeason(team, year) {
  return team.seasons[String(year)] || null;
}

// variação do score entre a última temporada com dado e a anterior
export function trend(team) {
  const ys = SEASONS().map(String).filter((y) => team.seasons[y]);
  if (ys.length < 2) return null;
  const last = team.seasons[ys[ys.length - 1]].score;
  const prev = team.seasons[ys[ys.length - 2]].score;
  return { delta: last - prev, from: ys[ys.length - 2], to: ys[ys.length - 1] };
}

export function deltaHtml(delta) {
  if (delta == null) return '<span class="delta flat">—</span>';
  const cls = delta > 1.5 ? "up" : delta < -1.5 ? "down" : "flat";
  const sign = delta > 0 ? "+" : "";
  return `<span class="delta ${cls}">${sign}${delta.toFixed(1)}</span>`;
}

export function weightedAwardCount(season) {
  return (season.awards || []).reduce((a, x) => a + (x.weight || 0), 0);
}

export function el(tag, attrs = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v;
    else if (k === "html") n.innerHTML = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else if (v != null) n.setAttribute(k, v);
  }
  for (const kid of kids.flat()) {
    if (kid == null) continue;
    n.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return n;
}

export function setMeta(txt) {
  document.getElementById("meta").textContent = txt;
}
