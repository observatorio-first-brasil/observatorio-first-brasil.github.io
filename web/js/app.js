import {
  IS_FTC, CONFIG_URL, loadData, SEASONS, LATEST, COMP_LABELS, COMP_KEYS, PALETTE,
  scoreColor, grade, fmt, teamSeason, trend, deltaHtml, weightedAwardCount,
  el, setMeta,
} from "./lib.js";
import { timeSeries, bandChart, rankBars, componentBars, destroyAll } from "./charts.js";

const app = document.getElementById("app");
let D;

// ------------------------------------------------------------------ router
const routes = {
  overview: viewOverview,
  team: viewTeam,
  state: viewState,
  compare: viewCompare,
  method: viewMethod,
  events: viewFTCEvents,
};

function parseHash() {
  const raw = (location.hash || "#/overview").replace(/^#\/?/, "");
  const [name, ...rest] = raw.split("/");
  return { name: routes[name] ? name : "overview", arg: decodeURIComponent(rest.join("/") || "") };
}

async function render() {
  const { name, arg } = parseHash();
  document.querySelectorAll("#nav a").forEach((a) =>
    a.classList.toggle("active", a.dataset.route === name));
  destroyAll();
  app.innerHTML = "";
  try {
    await routes[name](arg);
    const coverage = SEASONS().map((year) => {
      const seasons = D.teamList.map((t) => teamSeason(t, year)).filter(Boolean);
      return `${year}: ${IS_FTC ? "OPR" : "EPA"} ${seasons.filter((s) => IS_FTC ? s.opr_pct != null : s.epa_norm != null).length}/${seasons.length}`;
    });
    app.prepend(el("div", { class: "card", role: "status" },
      IS_FTC ? `FTC · Ano de encerramento: 2023 = 2022–23. ${coverage.join(" · ")}. Faixas: seletivas 0–39 · Nacional 40–69 · Mundial/Premier 70–100. Scores FTC e FRC não são comparáveis.` : `Cobertura · ${coverage.join(" · ")}. Sem EPA, a performance usa OPR. A mudança de fonte pode influenciar a evolução entre temporadas.`));
  } catch (e) {
    app.append(el("div", { class: "card" }, "Erro: " + e.message));
    console.error(e);
  }
}

window.addEventListener("hashchange", render);

loadData().then((d) => {
  D = d;
  const gen = new Date(d.generated_at).toLocaleString("pt-BR");
  document.getElementById("foot-generated").textContent =
    `Dados gerados em ${gen}. ${d.n_teams} equipes. `;
  render();
}).catch((e) => { app.textContent = "Não foi possível carregar os dados: " + e.message; });

// ------------------------------------------------------------------ helpers UI
function pill(score) {
  return `<span class="score-pill" style="background:${scoreColor(score)}22;color:${scoreColor(score)}">${fmt(score, 1)}</span>`;
}
function card(...kids) { return el("div", { class: "card" }, ...kids); }
function h(t, txt) { return el(t, {}, txt); }
function goTeam(n) { location.hash = `#/team/${n}`; }

function seasonSelect(value, onChange) {
  const s = el("select", { onchange: (e) => onChange(+e.target.value) });
  for (const y of SEASONS()) s.append(el("option", { value: y, selected: y === value ? "" : null }, IS_FTC ? `${y} · ${y-1}–${String(y).slice(2)}` : y));
  return el("label", { class: "fld" }, "Temporada", s);
}

// ============================================================ VISÃO GERAL
function viewOverview(arg) {
  setMeta("");
  let year = +arg || LATEST();
  let stateF = "";
  let q = "";
  let sortKey = "score", sortDir = -1;

  const wrap = el("div");
  app.append(wrap);

  function rows() {
    return D.teamList
      .map((t) => {
        const s = teamSeason(t, year);
        const tr = trend(t);
        return {
          t, s,
          num: t.team, name: t.name, state: t.state,
          score: s ? s.score : null,
          delta: tr ? tr.delta : null,
          playoff: s ? s.playoff_best : "—",
          aw: s ? weightedAwardCount(s) : 0,
          nev: s ? s.n_events : 0,
          level: s?.level_label || "—",
          rank: s ? s.rank_br : null,
        };
      })
      .filter((r) => r.s)
      .filter((r) => !stateF || r.state === stateF)
      .filter((r) => !q ||
        String(r.num).includes(q) || r.name.toLowerCase().includes(q.toLowerCase()))
      .sort((a, b) => {
        const av = a[sortKey], bv = b[sortKey];
        if (av == null) return 1;
        if (bv == null) return -1;
        return (av > bv ? 1 : av < bv ? -1 : 0) * sortDir;
      });
  }

  function draw() {
    wrap.innerHTML = "";

    // KPIs
    const rs = rows();
    const scores = rs.map((r) => r.score).sort((a, b) => a - b);
    const median = scores.length ? (scores[Math.floor((scores.length - 1) / 2)] + scores[Math.floor(scores.length / 2)]) / 2 : 0;
    const best = rs.reduce((m, r) => (!m || r.score > m.score ? r : m), null);
    const nStates = new Set(rs.map((r) => r.state)).size;
    const kpis = el("div", { class: "kpis" });
    kpis.append(
      kpi("Equipes", rs.length, `temporada ${year}`),
      kpi("Score mediano", fmt(median, 1), "Brasil"),
      kpi("Melhor score", best ? fmt(best.score, 1) : "—", best ? `#${best.num} ${best.name}` : ""),
      kpi("Estados", nStates, "com equipe ativa"),
    );
    wrap.append(kpis);

    // controls
    const ctr = el("div", { class: "controls" });
    ctr.append(
      seasonSelect(year, (y) => { year = y; location.hash = `#/overview/${y}`; }),
      (() => {
        const sel = el("select", { onchange: (e) => { stateF = e.target.value; draw(); } });
        sel.append(el("option", { value: "" }, "Todos os estados"));
        for (const st of D.stateList) sel.append(el("option", { value: st, selected: st === stateF ? "" : null }, st));
        return el("label", { class: "fld" }, "Estado", sel);
      })(),
      (() => {
        const inp = el("input", { type: "search", placeholder: "nº ou nome…", value: q,
          oninput: (e) => { q = e.target.value; draw(); } });
        return el("label", { class: "fld" }, "Buscar", inp);
      })(),
    );
    wrap.append(ctr);

    // ranking chart (top 15)
    const top = rs.slice().sort((a, b) => b.score - a.score).slice(0, 15);
    const cc = card(h("h3", `Top ${top.length} — ${year}`),
      el("div", { class: "chartbox" }, el("canvas", { id: "ov-bars" })));
    wrap.append(cc);
    rankBars("ov-bars", top.map((r) => ({
      label: `${r.num} ${r.name}`.slice(0, 26), value: r.score, color: scoreColor(r.score),
      num: r.num,
    })), { onClick: (i) => goTeam(i.num) });

    // table
    const cols = [
      ["rank", "#", "num"], ["num", "Time", ""], ["name", "Nome", ""], ["state", "UF", ""],
      ["score", "Score", "num"], ["delta", "Δ ano", "num"], ["playoff", "Melhor playoff", ""],
      ["aw", "Prêmios (pond.)", "num"], ["nev", "Eventos", "num"],
      ...(IS_FTC ? [["level", "Nível alcançado", ""]] : []),
    ];
    const thead = el("tr");
    for (const [k, label, cls] of cols) {
      const th = el("th", { class: cls === "num" ? "num" : (k ? "" : "no-sort") }, label);
      if (k) th.addEventListener("click", () => {
        if (sortKey === k) sortDir *= -1; else { sortKey = k; sortDir = k === "name" || k === "state" ? 1 : -1; }
        draw();
      });
      thead.append(th);
    }
    const tb = el("tbody");
    for (const r of rs) {
      const tr = el("tr", { onclick: () => goTeam(r.num) });
      tr.append(
        el("td", { class: "num" }, r.rank ?? "—"),
        el("td", {}, r.num),
        el("td", {}, r.name),
        el("td", {}, r.state),
        el("td", { class: "num", html: pill(r.score) }),
        el("td", { class: "num", html: deltaHtml(r.delta) }),
        el("td", {}, r.playoff),
        el("td", { class: "num" }, fmt(r.aw, 2)),
        el("td", { class: "num" }, r.nev),
        IS_FTC ? el("td", {}, r.level) : null,
      );
      tb.append(tr);
    }
    wrap.append(card(
      h("h3", `Todas as equipes (${rs.length})`),
      el("div", { class: "tablewrap" }, el("table", {}, el("thead", {}, thead), tb)),
      el("div", { class: "legend-hint" }, "Clique numa linha para abrir a equipe. Clique nos cabeçalhos para ordenar."),
    ));
  }

  draw();
}

function kpi(k, v, s) {
  return el("div", { class: "kpi" }, el("div", { class: "k" }, k),
    el("div", { class: "v" }, String(v)), el("div", { class: "s" }, s || ""));
}

// ============================================================ EQUIPE
function viewTeam(arg) {
  const first = D.teamList[0].team;
  const num = arg || first;
  const t = D.teams[String(num)];
  setMeta(t ? `#${t.team}` : "");

  const picker = el("input", {
    type: "search", placeholder: "número ou nome…", list: "team-dl",
    value: t ? `${t.team} — ${t.name}` : "",
  });
  const dl = el("datalist", { id: "team-dl" });
  for (const x of D.teamList) dl.append(el("option", { value: `${x.team} — ${x.name}` }));
  picker.addEventListener("change", () => {
    const m = picker.value.match(/\d+/);
    if (m && D.teams[m[0]]) location.hash = `#/team/${m[0]}`;
  });
  app.append(el("div", { class: "controls" },
    el("label", { class: "fld" }, "Equipe", picker), dl,
    el("button", { onclick: () => location.hash = `#/compare/${num}` }, "Comparar +")));

  if (!t) { app.append(card("Time não encontrado.")); return; }

  const ys = SEASONS().map(String).filter((y) => t.seasons[y]);
  const lastS = t.seasons[ys[ys.length - 1]];
  const tr = trend(t);

  // header
  app.append(card(
    el("div", { class: "team-title" },
      t.avatar ? el("img", { class: "team-avatar", src: t.avatar, alt: `Avatar da equipe ${t.team}` }) : null,
      el("h2", {}, `${t.team} · ${t.name}`)),
    el("p", { class: "muted" },
      `${[t.city, t.state].filter(Boolean).join(" / ")} · desde ${t.rookie_year || "—"}`),
    el("div", { class: "kpis" },
      kpi("Score atual", fmt(lastS.score, 1), `${grade(lastS.score)} · ${ys[ys.length - 1]}`),
      kpi("Variação", tr ? (tr.delta > 0 ? "+" : "") + fmt(tr.delta, 1) : "—", tr ? `${tr.from}→${tr.to}` : ""),
      kpi("Ranking BR", lastS.rank_br ? `${lastS.rank_br}º` : "—", `de ${D.teamList.filter((team) => teamSeason(team, ys[ys.length - 1])).length}`),
      kpi("Ranking " + t.state, lastS.rank_state ? `${lastS.rank_state}º` : "—", `de ${lastS.state_size || "—"}`),
      ...(IS_FTC ? [kpi("Nível alcançado", lastS.level_label, "Prioridade no ranking da temporada")] : []),
      ...(!IS_FTC && lastS.world_attended
        ? [kpi("Bônus Mundial", `+${fmt(lastS.world_bonus, 1)}`, `Score-base ${fmt(lastS.base_score, 1)}`)] : []),
      kpi("Melhor playoff", lastS.playoff_best || "—", ys[ys.length - 1]),
    ),
  ));

  // time series: per-event score + season markers
  const evPts = t.event_points.map((p) => ({
    x: p.x, y: p.score,
    meta: {
      title: `${p.year} · ${p.event_name}${p.is_champs ? " (Mundial)" : ""}`,
      lines: [
        `Playoff: ${p.playoff_label}`,
        p.qual_rank ? `Classif.: ${p.qual_rank}º/${p.qual_num_teams}` : null,
        p.epa_norm ? `EPA norm: ${fmt(p.epa_norm, 0)}` : (p.opr != null ? `OPR: ${fmt(p.opr, 1)} (p${Math.round((p.opr_pct || 0) * 100)})` : null),
        p.n_awards ? `Prêmios: ${p.n_awards}` : null,
      ].filter(Boolean),
    },
  }));
  const seasonPts = ys.map((y) => ({
    x: +y + 0.4, y: t.seasons[y].score,
    meta: { title: `Temporada ${y}`, lines: [`Score da temporada: ${fmt(t.seasons[y].score, 1)}`] },
  }));
  app.append(card(
    h("h3", "Score ao longo do tempo"),
    el("div", { class: "chartbox" }, el("canvas", { id: "team-ts" })),
    el("div", { class: "legend-hint" }, "Linha fina: score por evento. Losangos: score consolidado da temporada."),
  ));
  timeSeries("team-ts", [
    { label: "Por evento", points: evPts, color: PALETTE[0], width: 1.5, pointRadius: 4 },
    { label: "Temporada", points: seasonPts, color: PALETTE[1], width: 0, pointRadius: 7, pointStyle: "rectRot" },
  ]);

  // components over seasons (stacked-ish grouped) + per-season detail
  app.append(el("div", { class: "two-col" },
    card(h("h3", "Composição do score por temporada"),
      el("div", { class: "chartbox sm" }, el("canvas", { id: "team-comp" }))),
    card(h("h3", "Detalhe por temporada"), seasonTable(t, ys)),
  ));
  componentBars("team-comp", ys.map((y, i) => ({
    label: y, weighted: t.seasons[y].weighted, color: PALETTE[i % PALETTE.length],
  })));

  // awards list by season
  const awardSeason = el("select", { "aria-label": "Temporada dos prêmios" },
    ...ys.slice().reverse().map((y) => el("option", { value: y }, IS_FTC ? (t.seasons[y].season_label || y) : y)));
  const awardContent = el("div");
  const renderAwards = () => {
    const y = awardSeason.value;
    const aw = t.seasons[y]?.awards || [];
    awardContent.replaceChildren(aw.length
      ? el("ul", { class: "awards" }, ...aw.map((a) =>
          el("li", { html: `<span class="chip ${a.tier}">${a.tier}</span> ${a.name} <span class="muted">— ${a.event_key}${a.is_champs ? " · mundial" : ""} · peso ${a.weight}</span>` })))
      : el("p", { class: "muted" }, "Sem prêmios registrados nesta temporada."));
  };
  awardSeason.addEventListener("change", renderAwards);
  renderAwards();
  app.append(card(
    el("div", { class: "section-heading" },
      h("h3", "Prêmios"),
      el("label", { class: "fld compact" }, "Temporada", awardSeason)),
    awardContent,
  ));
  if (IS_FTC) {
    const rows = t.event_points.slice().reverse().map((p) => el("tr", {},
      el("td", {}, `${p.season}–${String(p.year).slice(2)}`),
      el("td", {}, el("a", { href:p.source_url, target:"_blank", rel:"noopener" }, p.event_name)),
      el("td", {}, p.event_type),
      el("td", {}, p.date),
      el("td", {}, p.opr == null ? "—" : fmt(p.opr,1)),
      el("td", {}, `${fmt(p.score,1)}${p.provisional ? " *" : ""}`)));
    app.append(card(h("h3", "Eventos considerados · FTC"),
      el("div", {class:"tablewrap"}, el("table", {},
        el("thead", {}, el("tr", {}, ...["Temporada","Evento","Tipo","Data","OPR","Score"].map((x)=>el("th",{},x)))),
        el("tbody", {}, ...rows))),
      el("p", {class:"muted"}, "* Dados incompletos ou evento em andamento. Scores com componentes ausentes têm os pesos redistribuídos. Prêmios do torneio principal podem entrar na temporada sem criar um ponto de evento sem partidas.")));
  }

}

function seasonTable(t, ys) {
  const tb = el("tbody");
  for (const y of ys) {
    const s = t.seasons[y];
    tb.append(el("tr", {},
      el("td", {}, IS_FTC ? `${y} · ${s.season_label}` : y),
      el("td", { class: "num", html: pill(s.score) }, s.provisional ? " *" : null),
      el("td", { class: "num" }, IS_FTC ? (s.opr_pct != null ? fmt(s.opr_pct * 100, 1) : "—") : (s.epa_norm ? fmt(s.epa_norm, 0) : "—")),
      el("td", { class: "num" }, fmt(100 * (s.components.playoff || 0), 0)),
      el("td", { class: "num" }, fmt(weightedAwardCount(s), 2)),
      el("td", { class: "num" }, s.n_events),
      !IS_FTC ? el("td", { class: "num" }, s.world_attended ? `+${fmt(s.world_bonus, 1)}` : "—") : null,
      IS_FTC ? el("td", {}, s.level_label) : null,
    ));
  }
  return el("div", { class: "tablewrap" }, el("table", {},
    el("thead", {}, el("tr", {},
      ...["Ano", "Score", IS_FTC ? "OPR perc." : "EPA n.", "Playoff", "Prêmios", "Ev.", ...(!IS_FTC ? ["Bônus Mundial"] : []), ...(IS_FTC ? ["Nível alcançado"] : [])]
        .map((x, i) => el("th", { class: i ? "num" : "" }, x)))),
    tb));
}

// ============================================================ ESTADO
function viewState(arg) {
  setMeta("");
  let st = D.states[arg] ? arg : D.stateList[0];
  let cmp = "";

  const wrap = el("div");
  app.append(wrap);

  function draw() {
    wrap.innerHTML = "";
    const ctr = el("div", { class: "controls" });
    ctr.append(
      selField("Estado", D.stateList, st, (v) => { st = v; location.hash = `#/state/${v}`; }),
      selField("Comparar com", ["", ...D.stateList.filter((x) => x !== st)], cmp, (v) => { cmp = v; draw(); }),
    );
    wrap.append(ctr);

    const rowsFor = (S) => SEASONS().map((y) => {
      const b = (D.states[S] || {})[String(y)];
      return b ? { x: y + 0.4, median: b.median, p25: b.p25, p75: b.p75, count: b.count } : null;
    }).filter(Boolean);

    // BR reference (median of all team scores per year)
    const brRows = SEASONS().map((y) => {
      const all = D.teamList.map((t) => teamSeason(t, y)).filter(Boolean).map((s) => s.score).sort((a, b) => a - b);
      return all.length ? { x: y + 0.4, median: (all[Math.floor((all.length - 1) / 2)] + all[Math.floor(all.length / 2)]) / 2 } : null;
    }).filter(Boolean);

    const selectedTeams = D.teamList.filter((t) => t.state === st);
    const series = selectedTeams.map((t, i) => ({
      label: `#${t.team} ${t.name}`,
      color: `hsl(${(i * 137.508) % 360}, 65%, 62%)`,
      width: 1.5,
      points: SEASONS().map((y) => ({
        x: y + 0.4, y: teamSeason(t, y)?.score ?? null,
        meta: { title: `${y} · #${t.team} ${t.name}` },
      })),
    }));
    const medianSeries = (label, rows, color, dash) => ({
      label, color, dash, width: 4, pointRadius: 4,
      points: rows.map((r) => ({ x: r.x, y: r.median,
        meta: { title: `${Math.floor(r.x)} · ${label}` } })),
    });
    series.push(medianSeries(`Mediana ${st}`, rowsFor(st), "#ffffff", []));
    if (cmp) series.push(medianSeries(`Mediana ${cmp}`, rowsFor(cmp), "#ffd166", [3, 3]));
    series.push(medianSeries("Mediana Brasil", brRows, "#93a4b3", [8, 5]));
    wrap.append(card(
      h("h3", `Evolução — ${st}${cmp ? " vs " + cmp : ""}`),
      el("div", { class: "chartbox", style: `height:${480 + Math.ceil(selectedTeams.length / 3) * 20}px` }, el("canvas", { id: "st-band" })),
      el("div", { class: "legend-hint" }, "Uma linha por equipe do estado. Linhas grossas = medianas estadual e brasileira. Clique na legenda para ocultar ou exibir uma série."),
    ));
    timeSeries("st-band", series);

    // KPIs latest
    const lb = (D.states[st] || {})[String(LATEST())] || {};
    wrap.append(el("div", { class: "kpis" },
      kpi("Equipes", lb.count ?? "—", `${LATEST()}`),
      kpi("Score mediano", fmt(lb.median, 1), st),
      kpi("Melhor equipe", lb.top_team ? `#${lb.top_team}` : "—", lb.top_score ? fmt(lb.top_score, 1) : ""),
      kpi("Amplitude", lb.min != null ? `${fmt(lb.min, 0)}–${fmt(lb.max, 0)}` : "—", "min–máx"),
    ));

    // teams in state (latest)
    const members = D.teamList
      .filter((t) => t.state === st && teamSeason(t, LATEST()))
      .map((t) => ({ t, s: teamSeason(t, LATEST()), tr: trend(t) }))
      .sort((a, b) => b.s.score - a.s.score);
    const tb = el("tbody");
    for (const m of members) {
      tb.append(el("tr", { onclick: () => goTeam(m.t.team) },
        el("td", { class: "num" }, m.s.rank_state ?? "—"),
        el("td", {}, m.t.team),
        el("td", {}, m.t.name),
        el("td", { class: "num", html: pill(m.s.score) }),
        el("td", { class: "num", html: deltaHtml(m.tr ? m.tr.delta : null) }),
        el("td", {}, m.s.playoff_best),
      ));
    }
    wrap.append(card(h("h3", `Equipes de ${st} — ${LATEST()}`),
      el("div", { class: "tablewrap" }, el("table", {},
        el("thead", {}, el("tr", {}, ...["#", "Time", "Nome", "Score", "Δ", "Playoff"]
          .map((x, i) => el("th", { class: i === 0 || i === 3 || i === 4 ? "num" : "" }, x)))),
        tb))));

    // state ranking bar (latest)
    const sr = D.stateList.map((S) => {
      const b = (D.states[S] || {})[String(LATEST())];
      return b ? { label: `${S} (${b.count})`, value: b.median, color: S === st ? PALETTE[1] : PALETTE[0] } : null;
    }).filter(Boolean).sort((a, b) => b.value - a.value);
    wrap.append(card(h("h3", `Ranking de estados por score mediano — ${LATEST()}`),
      el("div", { class: "chartbox" }, el("canvas", { id: "st-rank" }))));
    rankBars("st-rank", sr);
  }
  draw();
}

function selField(label, opts, value, onChange) {
  const sel = el("select", { onchange: (e) => onChange(e.target.value) });
  for (const o of opts) sel.append(el("option", { value: o, selected: o === value ? "" : null }, o || "—"));
  return el("label", { class: "fld" }, label, sel);
}

// ============================================================ COMPARAR
function viewCompare(arg) {
  setMeta("");
  let sel = new Set((arg ? arg.split(",") : []).filter((x) => D.teams[x]));
  if (sel.size === 0) sel = new Set(D.teamList.slice(0, 3).map((t) => String(t.team)));
  let year = LATEST();

  const wrap = el("div");
  app.append(wrap);

  function draw() {
    wrap.innerHTML = "";
    location.hash = `#/compare/${[...sel].join(",")}`;

    // picker
    const box = el("div", { class: "pickbox" });
    for (const t of D.teamList) {
      const id = String(t.team);
      const cb = el("input", { type: "checkbox", checked: sel.has(id) ? "" : null,
        onchange: (e) => { e.target.checked ? sel.add(id) : sel.delete(id); draw(); } });
      box.append(el("label", {}, cb, `${t.team} ${t.name}`));
    }
    wrap.append(el("div", { class: "controls" },
      el("label", { class: "fld" }, `Equipes (${sel.size})`, box),
      seasonSelect(year, (y) => { year = y; draw(); })));

    const chosen = [...sel].map((id) => D.teams[id]).filter(Boolean);
    if (!chosen.length) { wrap.append(card("Selecione ao menos uma equipe.")); return; }

    // time series (season scores)
    const series = chosen.map((t, i) => ({
      label: `${t.team} ${t.name}`.slice(0, 22),
      color: PALETTE[i % PALETTE.length],
      points: SEASONS().map(String).filter((y) => t.seasons[y]).map((y) => ({
        x: +y + 0.4, y: t.seasons[y].score,
        meta: { title: `${t.name} · ${y}`, lines: [`Score: ${fmt(t.seasons[y].score, 1)}`, `Rank BR: ${t.seasons[y].rank_br || "—"}º`] },
      })),
    }));
    wrap.append(card(h("h3", "Score por temporada"),
      el("div", { class: "chartbox" }, el("canvas", { id: "cmp-ts" }))));
    timeSeries("cmp-ts", series, { yMax: 100 });

    // component bars for selected year
    const withYear = chosen.filter((t) => t.seasons[String(year)]);
    wrap.append(card(h("h3", `Composição do score — ${year}`),
      el("div", { class: "chartbox sm" }, el("canvas", { id: "cmp-comp" })),
      withYear.length < chosen.length
        ? el("div", { class: "legend-hint" }, "Algumas equipes não têm dados nesta temporada.") : null));
    componentBars("cmp-comp", withYear.map((t, i) => ({
      label: `${t.team}`, weighted: t.seasons[String(year)].weighted,
      color: PALETTE[chosen.indexOf(t) % PALETTE.length],
    })));

    // table
    const tb = el("tbody");
    for (const t of chosen) {
      const s = t.seasons[String(year)];
      tb.append(el("tr", { onclick: () => goTeam(t.team) },
        el("td", {}, `${t.team} ${t.name}`),
        el("td", {}, t.state),
        el("td", { class: "num", html: s ? pill(s.score) : "—" }),
        el("td", { class: "num" }, s ? (s.rank_br + "º") : "—"),
        ...COMP_KEYS.map((k) => el("td", { class: "num" }, s ? fmt(s.weighted[k], 1) : "—")),
      ));
    }
    wrap.append(card(h("h3", `Números — ${year}`),
      el("div", { class: "tablewrap" }, el("table", {},
        el("thead", {}, el("tr", {}, ...["Equipe", "UF", "Score", "Rank BR", ...COMP_KEYS.map((k) => COMP_LABELS[k])]
          .map((x, i) => el("th", { class: i >= 2 ? "num" : "" }, x)))),
        tb))));
  }
  draw();
}

// ============================================================ METODOLOGIA
async function viewMethod() {
  if (IS_FTC) return viewFTCMethod();
  setMeta("");
  let cfg = {};
  try { cfg = await (await fetch(CONFIG_URL)).json(); } catch {}
  const W = cfg.weights || D.weights;

  app.append(card(
    el("h2", {}, "Como o Fator de Desenvolvimento é calculado"),
    el("p", {}, "Para cada equipe e temporada (2023–2026) calculamos primeiro um score-base com os eventos fora do Mundial. A participação e os resultados no Mundial entram depois como bônus positivo, sem possibilidade de reduzir o score-base."),
    el("div", { class: "chartbox sm" }, el("canvas", { id: "m-w" })),
  ));
  rankBars("m-w", COMP_KEYS.filter((k) => k !== "world_bonus").map((k) => ({
    label: COMP_LABELS[k], value: (W[k] || 0) * 100, color: PALETTE[COMP_KEYS.indexOf(k) % PALETTE.length],
  })));

  const dl = el("dl", { class: "method" });
  const add = (t, d) => { dl.append(el("dt", {}, t), el("dd", { html: d })); };
  add("Performance — peso " + pct(W.performance),
    `Baseado no <b>EPA normalizado</b> do Statbotics (comparável entre jogos diferentes), mapeado de <code>${cfg.epa_norm_floor ?? 1250}</code> (iniciante) a <code>${cfg.epa_norm_ceil ?? 2000}</code> (elite). Mistura <code>${Math.round((cfg.opr_blend ?? 0.15) * 100)}%</code> do percentil de OPR (TBA) do time nos seus eventos. Se o EPA não estiver disponível, cai para o OPR.`);
  add("Prêmios — peso " + pct(W.premios),
    `Cada prêmio conquistado fora do Mundial vale conforme o <b>tier</b> de importância; a soma passa por retornos decrescentes (<code>1 − e^(−k·Σ)</code>). Prêmios mundiais entram apenas no bônus mundial e recebem multiplicador reforçado.` + tierTable(cfg.tier_weight || {}));
  add("Playoff — peso " + pct(W.playoff),
    `Quão longe a equipe foi no mata-mata (melhor resultado da temporada): Campeão ${scoreOf(cfg, "winner")}, Finalista ${scoreOf(cfg, "finalist")}, Semifinal ${scoreOf(cfg, "sf")}, rodadas iniciais ${scoreOf(cfg, "playoff")}. A função na aliança acrescenta: capitão <code>+${cfg.alliance_role_bonus?.[0] ?? 0.10}</code>, pick 1 <code>+${cfg.alliance_role_bonus?.[1] ?? 0.06}</code>, pick 2 <code>+${cfg.alliance_role_bonus?.[2] ?? 0.03}</code> e pick 3/reserva <code>+${cfg.alliance_role_bonus?.[3] ?? 0.01}</code>.`);
  add("Aproveitamento — peso " + pct(W.winrate),
    "Taxa de vitórias na fase classificatória da temporada (Statbotics).");
  add("Mundial — bônus de até " + ((cfg.world_attendance_bonus ?? 2) + (cfg.world_result_bonus_max ?? 8)) + " pontos",
    `Classificar-se e disputar o Mundial acrescenta <code>+${cfg.world_attendance_bonus ?? 2}</code> pontos. Os resultados exclusivamente mundiais acrescentam até mais <code>${cfg.world_result_bonus_max ?? 8}</code> pontos. A profundidade no playoff define faixas sem sobreposição: campeão, finalista de divisão, semifinal e rodadas anteriores. A função na aliança (capitão, pick 1, pick 2 ou pick 3) ajuda a ordenar equipes dentro da mesma faixa, junto de performance, prêmios e aproveitamento. Assim, um finalista de divisão sempre supera quem foi menos longe no playoff, independentemente da classificação. O Mundial nunca reduz o score-base. Prêmios mundiais recebem multiplicador <code>${cfg.champs_award_mult ?? 2}×</code>.`);
  app.append(card(el("h3", {}, "Componentes"), dl));

  app.append(card(
    el("h3", {}, "Observações"),
    el("ul", {},
      el("li", {}, "O score mede o nível absoluto da equipe naquela temporada. A curva ao longo do tempo mostra a evolução."),
      el("li", {}, "Regionais fora do Brasil entram no score-base. Etapas e prêmios do Mundial entram somente no bônus positivo. O EPA-base é a média dos EPAs dos eventos fora do Mundial."),
      el("li", {}, "Todos os pesos e tiers ficam em data/config.py — ajuste e rode make data novamente."),
      el("li", { html: `Ranking BR e ranking estadual são calculados sobre o próprio score, entre as <b>${D.n_teams}</b> equipes brasileiras da base.` }),
    ),
  ));
}

const pct = (x) => `${Math.round((x || 0) * 100)}%`;
const scoreOf = (cfg, k) => `<code>${(cfg.playoff_score || {})[k] ?? "?"}</code>`;
function tierTable(tw) {
  const names = { S: "Impact/Chairman's, Vencedor", A: "Engineering Inspiration, Finalista, Camp. distrito",
    B: "Woodie Flowers, Autonomous, Innovation in Control, Design…", C: "Rookie, Judges, Spirit, Website…" };
  return "<table style='margin-top:8px'><thead><tr><th>Tier</th><th class='num'>Peso</th><th>Exemplos</th></tr></thead><tbody>"
    + ["S", "A", "B", "C"].map((t) => `<tr><td><span class="chip ${t}">${t}</span></td><td class="num">${tw[t] ?? "?"}</td><td>${names[t]}</td></tr>`).join("")
    + "</tbody></table>";
}

function viewFTCMethod() {
  setMeta("FTC · metodologia");
  app.append(card(h("h2", "Fator de Desenvolvimento FTC"),
    el("p", {}, "Índice de 0 a 100, separado do FRC. Ano de encerramento: 2023 corresponde a 2022–23, até 2026 = 2025–26."),
    el("p", {}, Object.keys(D.weights).map((k) => `${COMP_LABELS[k]} ${(D.weights[k] * 100).toLocaleString("pt-BR", {maximumFractionDigits:2})}%`).join(" · "))));
  const sections = [
    ["Progressão garantida", "Seletivas: 0–39 pontos. Nacional: 40–69. Mundial/Premier: 70–100. O score é o piso da faixa + desempenho ponderado × amplitude da faixa. Assim, mesmo o menor score do Nacional supera qualquer score de seletiva; o mesmo vale para Mundial/Premier sobre Nacional. É uma regra de classificação deste índice, não uma medição absoluta de força do robô. Participação ou resultado registrado confirma o nível; inscrição sem partidas nem resultados não basta. A garantia vale dentro da mesma temporada, não entre anos distintos."],
    ["Correções de classificação", "2023/BRBHS — SESI MG CENTERSTAGE: seletiva da temporada 2023–24 (ano 2024 no painel), confirmada pelo responsável; a fonte o registra como Scrimmage. Os demais amistosos validados permanecem excluídos. 2025/BRPIQ — Festival Regional Sesi de Educação: tratado como Championship de nível Nacional (2×), por correção do responsável pelo observatório. O FTCScout o registra como Qualifier; a classificação original permanece identificada na lista de eventos. 2024/BRCUS — Festival Regional SESI de Educação - Paraná: incluído como seletiva (1×), por indicação do responsável; a fonte o registra como Scrimmage."],
    ["Peso dos eventos", "Seletivas e outros oficiais: 1×. Nacional brasileiro: 2×. Mundial e Premier: 3×, no mesmo nível. Championship fora do Brasil não é classificado automaticamente como Nacional brasileiro. OPR e aproveitamento usam médias ponderadas; prêmios recebem o multiplicador; playoffs usam o melhor resultado ponderado, normalizado pelo peso do maior nível alcançado. Os quatro componentes distribuem os pontos dentro da faixa. A composição exibe separadamente o piso por nível alcançado."],
    ["Eventos considerados", "Qualifiers, super qualifiers, championships (incluindo nacional), FIRST Championship e Premier. Apenas equipes cadastradas no Brasil. Amistosos, off-seasons, ligas e eventos de demonstração são excluídos. Eventos sem partidas ou prêmios não geram score."],
    ["Performance · OPR", "Percentil do OPR sem penalidades (totalPointsNp) entre todas as equipes do mesmo evento, incluindo estrangeiras. Empates recebem o percentil médio. O valor anual é a média ponderada dos percentis dos eventos com OPR, pelos pesos 1×/2×/3×. Não é EPA; o percentil mede posição relativa no evento, não força absoluta mundial. Eventos com menos de duas equipes com OPR ficam sem performance."],
    ["Prêmios", "Inspire: peso 1,00; Think: 0,70; Connect, Control, Design, Innovate, Motivate, Reach e Sustain: 0,45; demais prêmios de equipe: 0,25. Segundo lugar recebe metade, terceiro recebe um terço. Soma convertida por 1 − exp(−0,55 × soma). Prêmios individuais são excluídos. Winner/Finalist contam apenas em playoffs, evitando duplicidade. Os pesos dos prêmios recebem também o multiplicador do nível do evento."],
    ["Playoffs", "Melhor resultado: campeão 1,00; campeão de divisão 0,90; finalista 0,80; semifinal 0,60. Double elimination: 0,25 + 0,10 por vitória, limitado a 0,60, salvo prêmio que comprove resultado superior. Usamos somente partidas efetivamente jogadas. Sem partidas eliminatórias nem prêmio de resultado: zero."],
    ["Aproveitamento", "Vitórias divididas por partidas classificatórias registradas, ponderadas pelo nível dos eventos. Empates entram no denominador. Dados faltantes não são confundidos com derrotas: o desempenho dentro da faixa redistribui os pesos entre componentes disponíveis e indica registros incompletos."],
    ["Estados e evolução", "Uma linha por equipe e medianas do estado e do Brasil. A composição de equipes e o nível dos eventos podem variar entre anos. Localização usa o cadastro atual do FTCScout. Valores não medem crescimento isoladamente e não devem ser comparados com scores FRC."],
  ];
  sections.forEach(([title, body]) => app.append(card(h("h3", title), el("p", {}, body))));
}

function viewFTCEvents() {
  if (!IS_FTC) return viewOverview();
  setMeta("FTC · eventos por temporada");
  let selected = "all";
  const wrap=el("div"); app.append(wrap);
  function draw() {
    wrap.innerHTML="";
    const selector=el("select",{onchange:(e)=>{selected=e.target.value;draw();}});
    selector.append(el("option",{value:"all",selected:selected==="all"?"":null},"Todas as temporadas"));
    SEASONS().forEach(y=>selector.append(el("option",{value:String(y),selected:selected===String(y)?"":null},`${y} · ${D.season_labels[y]}`)));
    wrap.append(h("h2","Eventos FTC considerados"),el("label",{class:"fld"},"Temporada",selector));
    for(const year of SEASONS().filter(y=>selected==="all"||String(y)===selected)) {
      const events=(D.event_catalog||[]).filter(e=>e.year===year);
      const regional=events.filter(e=>["Qualifier","SuperQualifier"].includes(e.type)&&["Brazil","Brasil","BR"].includes(e.country));
      const rows=events.map(e=>el("tr",{},
        el("td",{},e.date),el("td",{},el("a",{href:e.url,target:"_blank",rel:"noopener"},e.name)),
        el("td",{},e.type),el("td",{},e.level_label),el("td",{},e.team_count),
        el("td",{},e.played_team_count ? `${e.played_team_count} equipes com partidas` : "Sem partidas brasileiras registradas"),
        el("td",{},e.classification_note ? `Correção local; fonte: ${e.source_type}` : "FTCScout")));
      wrap.append(card(h("h3",`${year} · ${D.season_labels[year]} · ${regional.length} seletivas brasileiras`),
        el("p",{class:"muted"}, regional.length ? "Datas podem estar no ano anterior: a temporada é agrupada pelo ano de encerramento." : "Nenhuma seletiva brasileira cadastrada como Qualifier/SuperQualifier foi encontrada no catálogo desta temporada. Isso não comprova que não houve seletivas."),
        el("div",{class:"tablewrap"},el("table",{},el("thead",{},el("tr",{},...["Data","Evento","Tipo considerado","Nível","Equipes BR","Resultados","Classificação"].map(x=>el("th",{},x)))),el("tbody",{},...rows)))));
    }
    wrap.append(el("p",{class:"muted"},"Eventos sem partidas podem aparecer no catálogo; somente resultados disponíveis entram no score. Amistosos e off-seasons permanecem excluídos."));
  }
  draw();
}
