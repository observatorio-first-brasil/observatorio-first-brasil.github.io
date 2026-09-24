"""
Cliente The Blue Alliance API v3.

A chave é lida de:
  1. variável de ambiente TBA_AUTH_KEY
  2. arquivo .env na raiz do projeto  (linha: TBA_AUTH_KEY=...)
"""

from __future__ import annotations

import os

from .apiclient import get_json

BASE = "https://www.thebluealliance.com/api/v3"


def _load_key() -> str:
    key = os.environ.get("TBA_AUTH_KEY", "").strip()
    if key:
        return key
    env_path = os.path.join(os.path.dirname(__file__), os.pardir, ".env")
    if os.path.exists(env_path):
        for line in open(env_path, encoding="utf-8"):
            line = line.strip()
            if line.startswith("TBA_AUTH_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError(
        "Defina TBA_AUTH_KEY (env var ou arquivo .env). "
        "Pegue a chave em https://www.thebluealliance.com/account"
    )


_KEY = None


def _headers() -> dict:
    global _KEY
    if _KEY is None:
        _KEY = _load_key()
    return {"X-TBA-Auth-Key": _KEY, "User-Agent": "frc-brasil-dev/1.0"}


def _get(path: str, **kw):
    return get_json(BASE + path, headers=_headers(), **kw)


# --- endpoints usados pelo build -------------------------------------------------
def event(key: str):
    return _get(f"/event/{key}")


def event_team_keys(key: str):
    return _get(f"/event/{key}/teams/keys", allow_empty_on_fail=True) or []


def event_oprs(key: str):
    return _get(f"/event/{key}/oprs", allow_empty_on_fail=True) or {}


def event_awards(key: str):
    return _get(f"/event/{key}/awards", allow_empty_on_fail=True) or []


def team(key: str):
    return _get(f"/team/{key}")


def team_events_year(team_key: str, year: int):
    return _get(f"/team/{team_key}/events/{year}", allow_empty_on_fail=True) or []


def team_awards(team_key: str):
    return _get(f"/team/{team_key}/awards", allow_empty_on_fail=True) or []


def team_event_status(team_key: str, event_key: str):
    return _get(
        f"/team/{team_key}/event/{event_key}/status", allow_empty_on_fail=True
    )


def normalize_status(raw: dict | None) -> dict:
    """TBA status cru -> dict enxuto consumido por scoring.playoff_score_from_status."""
    if not raw:
        return {"made_playoff": False}
    playoff = raw.get("playoff") or {}
    alliance = raw.get("alliance") or {}
    qual = (raw.get("qual") or {}).get("ranking") or {}
    st = (playoff.get("status") or "").lower()
    return {
        "made_playoff": bool(playoff) and playoff.get("status") is not None,
        "level": playoff.get("level"),
        "won": st == "won",
        "double_elim_round": playoff.get("double_elim_round"),
        "alliance_number": alliance.get("number"),
        "alliance_pick": alliance.get("pick"),
        "playoff_record": playoff.get("record"),
        "qual_rank": qual.get("rank"),
        "qual_num_teams": (raw.get("qual") or {}).get("num_teams"),
        "qual_record": qual.get("record"),  # {wins, losses, ties}
        "playoff_record_wlt": playoff.get("record"),
        "status_str": raw.get("overall_status_str"),
    }
