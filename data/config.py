"""
Configuração do Fator de Desenvolvimento (FDI - Fator de Desenvolvimento Interativo).

Tudo aqui é calibrável. Depois de rodar `python3 -m data.build` os pesos usados
ficam registrados em `web/data/config.json` para referência da interface.

O score de uma temporada é:

    score = 100 * (
        W["performance"] * perf_norm      +   # EPA normalizado entre anos (base Statbotics)
        W["premios"]     * awards_score    +   # prêmios ponderados por importância (base TBA)
        W["playoff"]     * playoff_score   +   # quão longe foi no mata-mata (base TBA)
        W["winrate"]     * winrate             # aproveitamento na classificatória
    )

Os pesos somam 1.0. Ajuste `W` e rode o build de novo.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Pesos dos componentes do score (devem somar 1.0)
# ---------------------------------------------------------------------------
W = {
    "performance": 50 / 95,
    "premios": 20 / 95,
    "playoff": 18 / 95,
    "winrate": 7 / 95,
}

# ---------------------------------------------------------------------------
# Normalização de performance (EPA normalizado do Statbotics -> 0..1)
# epa.norm tem média ~1500. Abaixo mapeamos [PISO, TETO] linearmente em [0, 1].
# ---------------------------------------------------------------------------
EPA_NORM_FLOOR = 1250.0   # ~ time iniciante
EPA_NORM_CEIL = 2000.0    # ~ time de elite mundial

# Peso do OPR (do TBA) dentro do componente de performance.
# 0.0 = usa só EPA. 0.2 = 80% EPA + 20% percentil de OPR no evento.
OPR_BLEND = 0.15

# ---------------------------------------------------------------------------
# Tiers de prêmios. Cada prêmio ganho soma `tier_weight * champs_mult`.
# O total é comprimido por 1 - exp(-AWARD_K * soma) -> 0..1 (retornos decrescentes).
# ---------------------------------------------------------------------------
AWARD_K = 0.55

TIER_WEIGHT = {
    "S": 1.00,   # Impact / Chairman's, Vencedor da etapa
    "A": 0.70,   # Engineering Inspiration, Finalista, Campeão de distrito
    "B": 0.45,   # Woodie Flowers, Autonomous, Innovation in Control, Creativity,
                 # Engineering Excellence, Industrial Design, Quality, Design
    "C": 0.25,   # Rookie All-Star, Judges, Spirit, Imagery, Safety, Website, etc.
}

# Multiplicador quando o prêmio foi conquistado numa etapa mundial (Championship).
# O Mundial é tratado como bônus separado: nunca reduz o score-base da temporada.
CHAMPS_AWARD_MULT = 2.0

# Bônus mundial em pontos do score anual. Classificar-se já rende o piso; os
# resultados no Mundial acrescentam até WORLD_RESULT_BONUS_MAX pontos, usando
# os mesmos quatro componentes do índice. O score final continua limitado a 100.
WORLD_ATTENDANCE_BONUS = 2.0
WORLD_RESULT_BONUS_MAX = 8.0

# Faixas de qualidade do resultado mundial. A profundidade no playoff escolhe
# a faixa; performance, prêmios e classificatórias ordenam apenas dentro dela.
# Os intervalos não se sobrepõem, garantindo a prioridade do mata-mata.
WORLD_PLAYOFF_BANDS = {
    "none": (0.00, 0.29),
    "playoff": (0.30, 0.44),
    "round3": (0.45, 0.54),
    "round4": (0.55, 0.64),
    "sf": (0.65, 0.79),
    "finalist": (0.80, 0.94),
    "winner": (0.95, 1.00),
}

# Mapa TBA award_type (int) -> tier. O que não estiver aqui cai no fallback por nome.
# Referência: https://www.thebluealliance.com/apidocs  (Award model, award_type enum)
AWARD_TYPE_TIER = {
    0: "S",   # Chairman's / Impact
    1: "S",   # Winner
    2: "A",   # Finalist (inclui Championship Division Finalist)
    9: "A",   # Engineering Inspiration
    69: "A",  # FIRST Impact Award Finalist
    3: "B",   # Woodie Flowers Finalist
    4: "B",   # FIRST Leadership Award Finalist (sucessor do Woodie Flowers)
    16: "B",  # Industrial Design
    17: "B",  # Quality
    20: "B",  # Creativity
    21: "B",  # Engineering Excellence
    28: "B",  # Excellence in Engineering
    29: "B",  # Innovation in Control
    32: "B",  # Autonomous
    68: "B",  # Autonomous (numeração nova)
    71: "B",  # Media and Technology Innovation
    10: "C",  # Rookie All Star
    11: "C",  # Gracious Professionalism
    13: "C",  # Judges
    14: "C",  # Highest Rookie Seed
    15: "C",  # Rookie Inspiration
    18: "C",  # Safety
    22: "C",  # Entrepreneurship
    30: "C",  # Website / Digital Animation
    5: "C",   # Volunteer of the Year
    70: "C",  # Team Imagery
}

# Fallback por substring no nome do prêmio (case-insensitive), na ordem.
AWARD_NAME_TIER = [
    (("impact", "chairman"), "S"),
    (("winner", "vencedor", "campeã", "campea"), "S"),
    (("engineering inspiration",), "A"),
    (("finalist", "finalista"), "A"),
    (("district championship", "regional championship"), "A"),
    (("woodie flowers", "autonomous", "innovation in control", "creativity",
      "engineering excellence", "excellence in engineering", "industrial design",
      "quality", "controls", "excellence in design"), "B"),
    (("rookie", "judges", "judge's", "spirit", "imagery", "safety", "sportsmanship",
      "website", "animation", "visualization", "entrepreneurship", "media",
      "gracious professionalism", "coopertition", "dean's list", "volunteer"), "C"),
]
DEFAULT_AWARD_TIER = "C"

# ---------------------------------------------------------------------------
# Profundidade de playoff -> 0..1  (usa o TBA event status: playoff.level/status)
# ---------------------------------------------------------------------------
PLAYOFF_SCORE = {
    "winner": 0.90,       # ganhou a etapa; função na aliança completa até 1.0
    "finalist": 0.80,     # perdeu a final
    "sf": 0.60,           # eliminado na semi (top 3-4 no double elim moderno)
    "round4": 0.45,       # double elim rounds 3-4
    "round3": 0.35,
    "playoff": 0.25,      # entrou no mata-mata mas caiu na 1ª/2ª rodada
    "none": 0.00,         # não se classificou
}
# Bônus pela função na aliança. No TBA, alliance.pick é 0 para capitão,
# 1 para primeiro pick, 2 para segundo e 3 para terceiro.
ALLIANCE_ROLE_BONUS = {
    0: 0.10,  # capitão
    1: 0.06,  # pick 1
    2: 0.03,  # pick 2
    3: 0.01,  # pick 3 / reserva
}
ALLIANCE_ROLE_QUALITY = {
    0: 1.00,
    1: 0.60,
    2: 0.30,
    3: 0.10,
}

# ---------------------------------------------------------------------------
# Etapa mundial (Championship): tipos de evento TBA considerados "mundial"
#   3 = Championship Division, 4 = Championship Finals (Einstein), 6 = Festival of Champions
# ---------------------------------------------------------------------------
CHAMPS_EVENT_TYPES = {3, 4, 6}
DISTRICT_CHAMPS_EVENT_TYPES = {2, 5}

# champs_score: 0 se não foi ao mundial; base por participar; + fração pela colocação
CHAMPS_ATTEND_BASE = 0.55
CHAMPS_RESULT_WEIGHT = 0.45   # multiplica o playoff_score obtido no mundial

# ---------------------------------------------------------------------------
# Eventos-âncora do Brasil (usados p/ descobrir a lista de times BR mesmo se a
# consulta por país do Statbotics estiver indisponível). Etapas mundiais dos
# times são descobertas dinamicamente via TBA.
# ---------------------------------------------------------------------------
ANCHOR_EVENTS = [
    "2023brbr",
    "2024brbr",
    "2025brba",
    "2025brsp",
    "2026brba",
    "2026brsp",
]

FIRST_SEASON = 2023
LAST_SEASON = 2026

# Semana aproximada -> fração do ano, p/ posicionar eventos no eixo temporal.
def event_x(year: int, week, is_champs: bool, is_finals: bool = False) -> float:
    """Retorna um x contínuo (ex.: 2024.30) para o gráfico de score no tempo."""
    if is_champs:
        return year + (0.66 if is_finals else 0.62)
    if week is None:
        return year + 0.35
    # semanas FRC vão de 0 a ~8; mapeia para 0.05..0.55 do ano
    return year + 0.05 + (float(week) / 8.0) * 0.50
