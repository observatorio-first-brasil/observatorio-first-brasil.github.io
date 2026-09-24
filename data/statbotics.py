"""
Cliente Statbotics REST API v3.  Sem chave. Seja gentil com os servidores deles.
Docs: https://www.statbotics.io/docs/rest
"""

from __future__ import annotations

import urllib.parse
import json
from pathlib import Path
from functools import lru_cache

from . import apiclient
from .apiclient import get_json

BASE = "https://api.statbotics.io/v3"

# Disjuntor: se a API do Statbotics estiver fora, para de tentar depois de
# muitas falhas seguidas (evita esperar ret/backoff em centenas de chamadas).
_fail_streak = 0
_TRIPPED = False
_TRIP_AFTER = 8


def _get(path: str, params: dict | None = None, **kw):
    global _fail_streak, _TRIPPED
    if _TRIPPED:
        return None
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    kw.setdefault("retries", 2)
    kw.setdefault("backoff", 1.0)
    kw.setdefault("allow_empty_on_fail", True)
    res = get_json(url, **kw)
    if res is None or res == {} or res == []:
        _fail_streak += 1
        if _fail_streak >= _TRIP_AFTER:
            _TRIPPED = True
            print("[statbotics] API sem resposta útil; desativando chamadas neste run "
                  "(rode de novo com --no-cache quando voltar).", flush=True)
    else:
        _fail_streak = 0
    return res


@lru_cache(maxsize=None)
def _site_snapshot(name):
    path = Path(__file__).parent / "raw" / "statbotics_site" / (name + ".json")
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _site_record(name, collection, team):
    snapshot = _site_snapshot(name)
    for row in snapshot.get("data", {}).get(collection, []):
        if row.get("team") == team:
            return {**row, "_source": "statbotics_site", "_source_url": snapshot["source_url"],
                    "_retrieved_at": snapshot["retrieved_at"]}
    return {}


def api_ok() -> bool:
    return not _TRIPPED


def team_year(team: int, year: int):
    """EPA da temporada. Retorna {} se o time não competiu / API fora."""
    return _site_record(f"team_years_{year}", "team_years", team) or _get(f"/team_year/{team}/{year}", allow_empty_on_fail=True) or {}


def team_event(team: int, event: str):
    return _site_record(f"event_{event}", "team_events", team) or _get(f"/team_event/{team}/{event}", allow_empty_on_fail=True) or {}


def team_years(country: str = "Brazil", year: int | None = None, limit: int = 1000):
    return _get("/team_years", {"country": country, "year": year, "limit": limit},
               allow_empty_on_fail=True) or []


def teams(country: str = "Brazil", limit: int = 1000):
    return _get("/teams", {"country": country, "limit": limit},
               allow_empty_on_fail=True) or []


# --- extração tolerante a chaves faltando --------------------------------------
def epa_norm(obj: dict):
    """epa.norm (comparável entre anos). Cai p/ epa.unitless, depois None."""
    epa = obj.get("epa") or {}
    for k in ("norm", "unitless"):
        v = epa.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    return None


def epa_points(obj: dict):
    epa = obj.get("epa") or {}
    tp = epa.get("total_points")
    if isinstance(tp, dict):
        return tp.get("mean")
    if isinstance(tp, (int, float)):
        return float(tp)
    return epa.get("mean")


def epa_breakdown(obj: dict) -> dict:
    epa = obj.get("epa") or {}
    bd = epa.get("breakdown")
    return bd if isinstance(bd, dict) else {}


def winrate(obj: dict):
    rec = obj.get("record") or {}
    qual = rec.get("qual") or rec.get("total") or {}
    wr = qual.get("winrate")
    if isinstance(wr, (int, float)):
        return float(wr)
    w, l, t = qual.get("wins"), qual.get("losses"), qual.get("ties")
    if None not in (w, l):
        n = (w or 0) + (l or 0) + (t or 0)
        return (w / n) if n else None
    return None


def rank_block(obj: dict, scope: str) -> dict:
    """scope: 'total' | 'country' | 'state' | 'district'."""
    ranks = (obj.get("epa") or {}).get("ranks") or {}
    b = ranks.get(scope)
    return b if isinstance(b, dict) else {}
