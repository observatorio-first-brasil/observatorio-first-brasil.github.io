"""
Pipeline: descobre times FRC do Brasil, busca dados (Statbotics + TBA),
calcula o Fator de Desenvolvimento por temporada e escreve web/data/data.json.

Uso:
    python3 -m data.build                # roda tudo (usa cache em data/raw)
    python3 -m data.build --limit 15     # só os 15 primeiros times (teste rápido)
    python3 -m data.build --no-cache     # ignora cache e rebusca tudo
    python3 -m data.build --fixtures     # não usa rede; copia data/fixtures/sample_data.json

Requer TBA_AUTH_KEY (env var ou .env). Statbotics não precisa de chave.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import shutil
import statistics
import sys
import threading
import time
import traceback

from . import config as C
from . import scoring as S
from . import statbotics as SB
from . import tba
from . import first_api

WEB_DATA = os.path.join(os.path.dirname(__file__), os.pardir, "web", "data")
OUT_PATH = os.path.join(WEB_DATA, "data.json")
CONFIG_OUT = os.path.join(WEB_DATA, "config.json")
FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_data.json")

OFFICIAL_EVENT_TYPES = {0, 1, 2, 3, 4, 5, 6}
_print_lock = threading.Lock()

STATE_FIX = {
    "sao paulo": "SP", "são paulo": "SP", "rio de janeiro": "RJ",
    "minas gerais": "MG", "distrito federal": "DF", "parana": "PR", "paraná": "PR",
    "rio grande do sul": "RS", "santa catarina": "SC", "bahia": "BA",
    "pernambuco": "PE", "ceara": "CE", "ceará": "CE", "goias": "GO", "goiás": "GO",
    "espirito santo": "ES", "espírito santo": "ES", "amazonas": "AM", "para": "PA",
    "pará": "PA", "mato grosso": "MT", "mato grosso do sul": "MS",
    "rio grande do norte": "RN", "paraiba": "PB", "paraíba": "PB",
    "maranhao": "MA", "maranhão": "MA", "piaui": "PI", "piauí": "PI",
    "alagoas": "AL", "sergipe": "SE", "tocantins": "TO", "acre": "AC",
    "rondonia": "RO", "rondônia": "RO", "roraima": "RR", "amapa": "AP", "amapá": "AP",
}


def norm_state(s):
    if not s:
        return "??"
    s = s.strip()
    return STATE_FIX.get(s.lower(), s.upper() if len(s) <= 3 else s)


def log(*a):
    with _print_lock:
        print(*a, file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Descoberta de times
# ---------------------------------------------------------------------------
def discover_team_keys() -> list[str]:
    keys: set[str] = set()
    for ev in C.ANCHOR_EVENTS:
        try:
            got = tba.event_team_keys(ev)
            log(f"  {ev}: {len(got)} times")
            keys.update(got)
        except Exception as e:
            log(f"  {ev}: FALHOU ({e})")
    # complemento opcional via Statbotics (se estiver no ar)
    try:
        for t in SB.teams(country="Brazil"):
            num = t.get("team") or t.get("team_number")
            if num:
                keys.add(f"frc{num}")
    except Exception:
        pass
    return sorted(keys, key=lambda k: int(k[3:]))


# ---------------------------------------------------------------------------
# Processamento de um time
# ---------------------------------------------------------------------------
def opr_percentile(event_key: str, team_key: str):
    data = tba.event_oprs(event_key)
    oprs = (data or {}).get("oprs") or {}
    mine = oprs.get(team_key)
    if mine is None or len(oprs) < 3:
        return None, mine
    vals = sorted(oprs.values())
    below = sum(1 for v in vals if v <= mine)
    return below / len(vals), mine


def process_team(team_key: str) -> dict | None:
    num = int(team_key[3:])
    try:
        info = tba.team(team_key)
    except Exception as e:
        log(f"[{team_key}] sem info TBA: {e}")
        info = {}

    country = (info.get("country") or "").strip()
    if country and country.lower() not in ("brazil", "brasil"):
        log(f"  {team_key} ignorado (país = {country})")
        return None

    state = norm_state(info.get("state_prov"))
    rec = {
        "team": num,
        "name": info.get("nickname") or info.get("name") or f"Team {num}",
        "state": state,
        "city": info.get("city"),
        "rookie_year": info.get("rookie_year"),
        "country": info.get("country"),
        "avatar": first_api.avatar_for_team(num, info.get("rookie_year")),
        "seasons": {},
        "event_points": [],
    }

    all_awards = tba.team_awards(team_key)
    awards_by_year: dict[int, list] = {}
    for a in all_awards:
        awards_by_year.setdefault(a.get("year"), []).append(a)

    for year in range(C.FIRST_SEASON, C.LAST_SEASON + 1):
        events = [e for e in tba.team_events_year(team_key, year)
                  if e.get("event_type") in OFFICIAL_EVENT_TYPES]
        if not events:
            continue
        events.sort(key=lambda e: (e.get("start_date") or f"{year}-99"))
        awards_at_event: dict[str, list] = {}
        for a in awards_by_year.get(year, []):
            awards_at_event.setdefault(a.get("event_key"), []).append(a)

        # --- Statbotics: EPA da temporada
        # O score-base usa só eventos fora do Mundial. O Mundial é calculado
        # separadamente como bônus positivo, portanto nunca derruba a temporada.
        sy = {}
        e_norm = None
        wr = None
        event_epas = []
        world_event_epas = []

        # --- por evento
        ev_statuses = []
        world_statuses = []
        champs_playoff = 0.0
        attended_champs = False
        competed_world_events = []
        opr_pcts = []
        world_opr_pcts = []
        qual_w = qual_l = qual_t = 0
        world_qual_w = world_qual_l = world_qual_t = 0
        for e in events:
            ekey = e["key"]
            etype = e.get("event_type")
            is_champs = etype in C.CHAMPS_EVENT_TYPES

            raw_status = tba.team_event_status(team_key, ekey)
            st = tba.normalize_status(raw_status)
            pct, my_opr = opr_percentile(ekey, team_key)

            # Evento "guarda-chuva" do Championship (ex.: 2025cmptx quando o time
            # jogou numa divisão): sem participação real em partidas -> não pontua,
            # mas os prêmios dele continuam contando na temporada.
            competed = bool(st.get("qual_num_teams") or st.get("made_playoff")
                            or pct is not None)
            if not competed:
                continue

            if is_champs:
                attended_champs = True
                competed_world_events.append(ekey)

            p_score, p_label = S.playoff_score_from_status(st)
            if is_champs:
                champs_playoff = max(champs_playoff, p_score)
                world_statuses.append(st)
                if pct is not None:
                    world_opr_pcts.append(pct)
            else:
                ev_statuses.append(st)
                if pct is not None:
                    opr_pcts.append(pct)
            qrec = st.get("qual_record") or {}
            if is_champs:
                world_qual_w += qrec.get("wins") or 0
                world_qual_l += qrec.get("losses") or 0
                world_qual_t += qrec.get("ties") or 0
            else:
                qual_w += qrec.get("wins") or 0
                qual_l += qrec.get("losses") or 0
                qual_t += qrec.get("ties") or 0

            se = SB.team_event(num, ekey)
            ep_norm = SB.epa_norm(se)
            if ep_norm is not None:
                (world_event_epas if is_champs else event_epas).append(se)

            # score do evento (mesmos pesos, entradas em nível de evento)
            perf_e = S.perf_norm(ep_norm, pct)
            qr, qn = st.get("qual_rank"), st.get("qual_num_teams")
            wr_e = (1.0 - (qr - 1) / (qn - 1)) if (qr and qn and qn > 1) else 0.0
            ev_awards = [{
                "award_type": a.get("award_type"), "name": a.get("name"),
                "is_champs": is_champs,
            } for a in awards_at_event.get(ekey, [])]
            aw_e, _ = S.awards_score(ev_awards)
            event_components = {
                "performance": perf_e, "premios": aw_e, "playoff": p_score,
                "winrate": wr_e,
            }
            ev_score = (round(100 * S.world_result_quality(event_components, [st]), 2)
                        if is_champs else S.season_score(event_components))

            rec["event_points"].append({
                "event": ekey,
                "event_name": e.get("short_name") or e.get("name"),
                "year": year,
                "week": e.get("week"),
                "is_champs": is_champs,
                "date": e.get("end_date") or e.get("start_date"),
                "x": round(C.event_x(year, e.get("week"), is_champs, etype == 4), 3),
                "score": ev_score,
                "epa_norm": ep_norm,
                "epa_source": se.get("_source", "statbotics_api") if ep_norm is not None else None,
                "epa_source_url": se.get("_source_url"),
                "playoff_score": round(p_score, 3),
                "playoff_label": p_label,
                "alliance_number": st.get("alliance_number"),
                "alliance_pick": st.get("alliance_pick"),
                "opr": round(my_opr, 2) if isinstance(my_opr, (int, float)) else None,
                "opr_pct": round(pct, 3) if pct is not None else None,
                "qual_rank": qr,
                "qual_num_teams": qn,
                "n_awards": len(ev_awards),
            })

        # --- prêmios da temporada
        ev_type_by_key = {e["key"]: e.get("event_type") for e in events}
        season_awards = []
        world_awards = []
        for a in awards_by_year.get(year, []):
            if a.get("event_key") not in ev_type_by_key:
                continue
            etype = ev_type_by_key.get(a.get("event_key"))
            is_champs_award = etype in C.CHAMPS_EVENT_TYPES if etype is not None \
                else str(a.get("event_key", "")).endswith(("cmptx", "cmpmi", "cmp"))
            normalized_award = {
                "award_type": a.get("award_type"),
                "name": a.get("name"),
                "event_key": a.get("event_key"),
                "is_champs": is_champs_award,
            }
            (world_awards if is_champs_award else season_awards).append(normalized_award)

        # Média dos EPAs dos eventos permitidos, sem usar o consolidado mundial.
        if event_epas:
            e_norm = statistics.mean(SB.epa_norm(e) for e in event_epas)
            pts = [SB.epa_points(e) for e in event_epas if SB.epa_points(e) is not None]
            sy = {"epa": {"total_points": {"mean": statistics.mean(pts) if pts else None}}}

        # --- componentes
        opr_pct_season = statistics.mean(opr_pcts) if opr_pcts else None
        perf = S.perf_norm(e_norm, opr_pct_season)
        aw_score, aw_detail = S.awards_score(season_awards)
        pf_score, pf_label = S.best_playoff(ev_statuses)
        # winrate: Statbotics (preferido) -> agregado das classificatórias no TBA
        wr_val = wr
        if wr_val is None and (qual_w + qual_l + qual_t) > 0:
            wr_val = qual_w / (qual_w + qual_l + qual_t)
        comps = {
            "performance": perf,
            "premios": aw_score,
            "playoff": pf_score,
            "winrate": wr_val or 0.0,
        }
        base_score = S.season_score(comps)

        # Mundial: calcula os quatro componentes somente com eventos mundiais e
        # soma um bônus. Resultados ruins não entram nas médias nacionais e nunca
        # podem reduzir base_score.
        world_epa_norm = (statistics.mean(SB.epa_norm(e) for e in world_event_epas)
                          if world_event_epas else None)
        world_opr_pct = statistics.mean(world_opr_pcts) if world_opr_pcts else None
        world_perf = S.perf_norm(world_epa_norm, world_opr_pct)
        world_aw_score, world_aw_detail = S.awards_score(world_awards)
        world_pf_score, world_pf_label = S.best_playoff(world_statuses)
        world_total_quals = world_qual_w + world_qual_l + world_qual_t
        world_wr = world_qual_w / world_total_quals if world_total_quals else 0.0
        world_comps = {
            "performance": world_perf,
            "premios": world_aw_score,
            "playoff": world_pf_score,
            "winrate": world_wr,
        }
        world_quality = S.world_result_quality(world_comps, world_statuses)
        world_bonus = S.world_bonus(attended_champs, world_comps, world_statuses)
        score = round(min(100.0, base_score + world_bonus), 2)

        rec["seasons"][str(year)] = {
            "score": score,
            "base_score": base_score,
            "world_bonus": world_bonus,
            "components": {k: round(v, 4) for k, v in comps.items()},
            "weighted": {
                **{k: round(100 * C.W[k] * S._clip01(comps[k]), 2) for k in C.W},
                "world_bonus": world_bonus,
            },
            "epa_norm": e_norm,
            "epa_source": "mean_non_championship_events" if e_norm is not None else None,
            "epa_event_sources": [e.get("_source_url") for e in event_epas],
            "epa_source_url": sy.get("_source_url"),
            "epa_points": SB.epa_points(sy),
            "epa_breakdown": SB.epa_breakdown(sy),
            "winrate": wr_val,
            "winrate_source": "statbotics" if wr is not None else ("tba" if wr_val is not None else None),
            "qual_record": {"w": qual_w, "l": qual_l, "t": qual_t},
            "events": [e["key"] for e in events],
            "n_events": len(ev_statuses) + len(world_statuses),
            "awards": aw_detail + world_aw_detail,
            "playoff_best": pf_label,
            "world_attended": attended_champs,
            "world_events": competed_world_events,
            "world_components": {k: round(v, 4) for k, v in world_comps.items()},
            "world_result_quality": round(world_quality, 4),
            "world_epa_norm": world_epa_norm,
            "world_opr_pct": world_opr_pct,
            "world_playoff_best": world_pf_label if attended_champs else None,
            "sb_rank_country": (SB.rank_block(sy, "country") or {}).get("rank"),
            "sb_rank_total": (SB.rank_block(sy, "total") or {}).get("rank"),
        }

    rec["event_points"].sort(key=lambda p: p["x"])
    if not rec["seasons"]:
        return None
    return rec


# ---------------------------------------------------------------------------
# Agregação
# ---------------------------------------------------------------------------
def build_states(teams: dict) -> dict:
    out: dict = {}
    for year in range(C.FIRST_SEASON, C.LAST_SEASON + 1):
        ys = str(year)
        by_state: dict[str, list] = {}
        for t in teams.values():
            s = t["seasons"].get(ys)
            if not s:
                continue
            by_state.setdefault(t["state"], []).append((t["team"], s["score"]))
        for state, rows in by_state.items():
            scores = sorted(r[1] for r in rows)
            top = max(rows, key=lambda r: r[1])
            out.setdefault(state, {})[ys] = {
                "count": len(rows),
                "mean": round(statistics.mean(scores), 2),
                "median": round(statistics.median(scores), 2),
                "p25": round(_quantile(scores, 0.25), 2),
                "p75": round(_quantile(scores, 0.75), 2),
                "max": scores[-1],
                "min": scores[0],
                "top_team": top[0],
                "top_score": top[1],
            }
    return out


def assign_ranks(teams: dict):
    for year in range(C.FIRST_SEASON, C.LAST_SEASON + 1):
        ys = str(year)
        rows = [(t["team"], t["state"], t["seasons"][ys]["score"])
                for t in teams.values() if ys in t["seasons"]]
        for rank, (num, _st, _sc) in enumerate(sorted(rows, key=lambda r: -r[2]), 1):
            teams[str(num)]["seasons"][ys]["rank_br"] = rank
        by_state: dict[str, list] = {}
        for num, st, sc in rows:
            by_state.setdefault(st, []).append((num, sc))
        for st, lst in by_state.items():
            for rank, (num, _sc) in enumerate(sorted(lst, key=lambda r: -r[1]), 1):
                teams[str(num)]["seasons"][ys]["rank_state"] = rank
                teams[str(num)]["seasons"][ys]["state_size"] = len(lst)


def _quantile(sorted_vals, q):
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = q * (len(sorted_vals) - 1)
    lo = int(pos)
    frac = pos - lo
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--cached-only", action="store_true", help="Recalcula com snapshots do site e cache TBA, sem rede")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--fixtures", action="store_true")
    args = ap.parse_args()

    if args.cached_only:
        from . import apiclient
        apiclient.CACHE_ONLY = True

    os.makedirs(WEB_DATA, exist_ok=True)

    if args.fixtures:
        shutil.copyfile(FIXTURE, OUT_PATH)
        _dump_config()
        log(f"OK (fixtures) -> {OUT_PATH}")
        return

    if args.no_cache:
        from . import apiclient
        apiclient.FORCE_REFRESH = True

    t0 = time.time()
    log("Descobrindo times do Brasil...")
    keys = discover_team_keys()
    if args.limit:
        keys = keys[:args.limit]
    log(f"{len(keys)} times para processar.\n")

    teams: dict = {}
    done = 0
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(process_team, k): k for k in keys}
        for fut in cf.as_completed(futs):
            k = futs[fut]
            done += 1
            try:
                rec = fut.result()
            except Exception:
                log(f"[{k}] ERRO:\n{traceback.format_exc()}")
                continue
            if rec:
                teams[str(rec["team"])] = rec
                log(f"  ({done}/{len(keys)}) {k} {rec['name']} "
                    f"[{rec['state']}] temporadas={list(rec['seasons'])}")
            else:
                log(f"  ({done}/{len(keys)}) {k} sem dados relevantes")

    assign_ranks(teams)
    states = build_states(teams)

    # cobertura
    n_perf = sum(1 for t in teams.values() for s in t["seasons"].values()
                 if s["epa_norm"] is not None)
    n_seasons = sum(len(t["seasons"]) for t in teams.values())
    log(f"\nCobertura EPA: {n_perf}/{n_seasons} temporadas-time com EPA do Statbotics")
    if n_perf == 0:
        log("!! Statbotics não retornou EPA (API fora do ar?). "
            "O componente 'performance' ficou baseado só em OPR/zero. "
            "Rode de novo quando a API voltar: python3 -m data.build --no-cache")

    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "seasons": list(range(C.FIRST_SEASON, C.LAST_SEASON + 1)),
        "weights": C.W,
        "n_teams": len(teams),
        "teams": teams,
        "states": states,
        "anchor_events": C.ANCHOR_EVENTS,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    _dump_config()
    log(f"\nOK -> {OUT_PATH}  ({len(teams)} times, {time.time()-t0:.0f}s)")


def _dump_config():
    cfg = {
        "weights": C.W,
        "epa_norm_floor": C.EPA_NORM_FLOOR,
        "epa_norm_ceil": C.EPA_NORM_CEIL,
        "opr_blend": C.OPR_BLEND,
        "award_k": C.AWARD_K,
        "tier_weight": C.TIER_WEIGHT,
        "champs_award_mult": C.CHAMPS_AWARD_MULT,
        "world_attendance_bonus": C.WORLD_ATTENDANCE_BONUS,
        "world_result_bonus_max": C.WORLD_RESULT_BONUS_MAX,
        "world_playoff_bands": C.WORLD_PLAYOFF_BANDS,
        "playoff_score": C.PLAYOFF_SCORE,
        "alliance_role_bonus": C.ALLIANCE_ROLE_BONUS,
        "alliance_role_quality": C.ALLIANCE_ROLE_QUALITY,
    }
    with open(CONFIG_OUT, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
