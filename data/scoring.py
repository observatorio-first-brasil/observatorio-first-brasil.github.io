"""
Funções puras de scoring. Sem I/O, sem rede -> fáceis de testar (test_scoring.py).

Entradas são dicts já normalizados pelo build.py a partir das APIs.
"""

from __future__ import annotations

import math
from typing import Iterable

from . import config as C


# ---------------------------------------------------------------------------
# 1. Performance (EPA normalizado entre anos + blend opcional de OPR)
# ---------------------------------------------------------------------------
def perf_norm(epa_norm: float | None, opr_percentile: float | None = None) -> float:
    """
    epa_norm: campo epa.norm do Statbotics (média ~1500), comparável entre temporadas.
    opr_percentile: 0..1, percentil do OPR do time entre os times dos seus eventos (TBA).
    Retorna 0..1.
    """
    if epa_norm is None:
        base = 0.0 if opr_percentile is None else opr_percentile
    else:
        base = (epa_norm - C.EPA_NORM_FLOOR) / (C.EPA_NORM_CEIL - C.EPA_NORM_FLOOR)
        base = _clip01(base)
        if opr_percentile is not None and C.OPR_BLEND > 0:
            base = (1 - C.OPR_BLEND) * base + C.OPR_BLEND * _clip01(opr_percentile)
    return _clip01(base)


# ---------------------------------------------------------------------------
# 2. Prêmios ponderados por importância
# ---------------------------------------------------------------------------
def award_tier(award_type: int | None, name: str | None) -> str:
    if award_type is not None and award_type in C.AWARD_TYPE_TIER:
        return C.AWARD_TYPE_TIER[award_type]
    n = (name or "").lower()
    for needles, tier in C.AWARD_NAME_TIER:
        if any(k in n for k in needles):
            return tier
    return C.DEFAULT_AWARD_TIER


def awards_score(awards: Iterable[dict]) -> tuple[float, list[dict]]:
    """
    awards: itens {award_type, name, is_champs}. Retorna (score 0..1, detalhamento).
    detalhamento: mesma lista com tier e peso aplicado, p/ exibir na UI.
    """
    total = 0.0
    detail = []
    for a in awards:
        tier = award_tier(a.get("award_type"), a.get("name"))
        w = C.TIER_WEIGHT[tier]
        if a.get("is_champs"):
            w *= C.CHAMPS_AWARD_MULT
        total += w
        detail.append({**a, "tier": tier, "weight": round(w, 3)})
    score = 1.0 - math.exp(-C.AWARD_K * total)
    return _clip01(score), detail


# ---------------------------------------------------------------------------
# 3. Profundidade de playoff
# ---------------------------------------------------------------------------
def playoff_score_from_status(status: dict | None) -> tuple[float, str]:
    """
    status: dict normalizado do TBA team@event status:
        { "made_playoff": bool, "level": "f"|"sf"|"qf"|"ef"|None,
          "won": bool, "double_elim_round": int|None,
          "alliance_number": int|None }
    Retorna (score 0..1, rótulo legível).
    """
    if not status or not status.get("made_playoff"):
        return C.PLAYOFF_SCORE["none"], "Não classificou"

    level = (status.get("level") or "").lower()
    won = bool(status.get("won"))
    der = _parse_round(status.get("double_elim_round"))

    if won:
        key, label = "winner", "Campeão"
    elif level == "f":
        key, label = "finalist", "Finalista"
    elif level == "sf":
        key, label = "sf", "Semifinal"
    elif der is not None and der >= 4:
        key, label = "round4", f"Playoff (rodada {der})"
    elif der is not None and der == 3:
        key, label = "round3", f"Playoff (rodada {der})"
    else:
        key, label = "playoff", "Playoff (rodada inicial)"

    score = C.PLAYOFF_SCORE[key]
    role = status.get("alliance_pick")
    aln = status.get("alliance_number")
    if role in C.ALLIANCE_ROLE_BONUS:
        score = min(1.0, score + C.ALLIANCE_ROLE_BONUS[role])
        role_label = {0: "capitão", 1: "pick 1", 2: "pick 2", 3: "pick 3"}[role]
        label += f" · {role_label}" + (f" aliança {aln}" if aln is not None else "")
    return _clip01(score), label


def alliance_role_quality(statuses: Iterable[dict]) -> float:
    return max((C.ALLIANCE_ROLE_QUALITY.get(st.get("alliance_pick"), 0.0)
                for st in statuses if st), default=0.0)


def best_playoff(statuses: Iterable[dict]) -> tuple[float, str]:
    best_s, best_l = 0.0, "Não classificou"
    for st in statuses:
        s, l = playoff_score_from_status(st)
        if s > best_s:
            best_s, best_l = s, l
    return best_s, best_l


# ---------------------------------------------------------------------------
# 4. Mundial (Championship)
# ---------------------------------------------------------------------------
def champs_score(attended: bool, champs_playoff_score: float | None) -> float:
    if not attended:
        return 0.0
    s = C.CHAMPS_ATTEND_BASE
    if champs_playoff_score:
        s += C.CHAMPS_RESULT_WEIGHT * _clip01(champs_playoff_score)
    return _clip01(s)


def _world_playoff_key(statuses: Iterable[dict]) -> str:
    best_key, best_floor = "none", -1.0
    for status in statuses:
        if not status or not status.get("made_playoff"):
            key = "none"
        else:
            level = (status.get("level") or "").lower()
            der = _parse_round(status.get("double_elim_round"))
            if status.get("won"):
                key = "winner"
            elif level == "f":
                key = "finalist"
            elif level == "sf":
                key = "sf"
            elif der is not None and der >= 4:
                key = "round4"
            elif der == 3:
                key = "round3"
            else:
                key = "playoff"
        floor = C.WORLD_PLAYOFF_BANDS[key][0]
        if floor > best_floor:
            best_key, best_floor = key, floor
    return best_key


def world_result_quality(components: dict, statuses: Iterable[dict]) -> float:
    """Qualidade 0..1 com faixa determinada pela profundidade no playoff."""
    key = _world_playoff_key(statuses)
    floor, ceil = C.WORLD_PLAYOFF_BANDS[key]
    secondary_keys = ("performance", "premios", "winrate")
    weight_total = sum(C.W[k] for k in secondary_keys)
    metrics = sum(C.W[k] * _clip01(components.get(k, 0.0))
                  for k in secondary_keys) / weight_total
    # Dentro da mesma faixa de avanço mundial, a função na aliança representa
    # 25% da ordenação: capitão > pick 1 > pick 2 > pick 3.
    secondary = 0.75 * metrics + 0.25 * alliance_role_quality(statuses)
    return _clip01(floor + (ceil - floor) * secondary)


def world_bonus(attended: bool, components: dict, statuses: Iterable[dict] = ()) -> float:
    """Bônus 0..10 do Mundial, somado ao score-base sem possibilidade de perda."""
    if not attended:
        return 0.0
    quality = world_result_quality(components, statuses)
    return round(C.WORLD_ATTENDANCE_BONUS + C.WORLD_RESULT_BONUS_MAX * quality, 2)


# ---------------------------------------------------------------------------
# 5. Composição final
# ---------------------------------------------------------------------------
def season_score(components: dict) -> float:
    """
    components: {performance, premios, playoff, winrate} todos 0..1.
    Retorna 0..100.
    """
    s = sum(C.W[k] * _clip01(components.get(k, 0.0)) for k in C.W)
    return round(100.0 * s, 2)


def weights_sum_ok() -> bool:
    return abs(sum(C.W.values()) - 1.0) < 1e-9


def _parse_round(der) -> int | None:
    """double_elim_round do TBA vem como 'Round 4', 'Finals', ou às vezes int."""
    if der is None:
        return None
    if isinstance(der, (int, float)):
        return int(der)
    s = str(der).strip().lower()
    if "final" in s:
        return 5
    digits = "".join(ch for ch in s if ch.isdigit())
    return int(digits) if digits else None


def _clip01(x: float) -> float:
    if x != x:  # NaN
        return 0.0
    return 0.0 if x < 0 else 1.0 if x > 1 else x
