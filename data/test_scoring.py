"""
Testes das funções de scoring.  Rode:  python3 -m unittest data.test_scoring -v
"""

import unittest

from . import config as C
from . import scoring as S


class PerfNorm(unittest.TestCase):
    def test_floor_and_ceil(self):
        self.assertEqual(S.perf_norm(C.EPA_NORM_FLOOR), 0.0)
        self.assertEqual(S.perf_norm(C.EPA_NORM_CEIL), 1.0)
        self.assertEqual(S.perf_norm(C.EPA_NORM_FLOOR - 500), 0.0)  # clip
        self.assertEqual(S.perf_norm(C.EPA_NORM_CEIL + 500), 1.0)

    def test_midpoint(self):
        mid = (C.EPA_NORM_FLOOR + C.EPA_NORM_CEIL) / 2
        self.assertAlmostEqual(S.perf_norm(mid), 0.5, places=6)

    def test_none_epa_uses_opr(self):
        self.assertEqual(S.perf_norm(None), 0.0)
        self.assertAlmostEqual(S.perf_norm(None, 0.7), 0.7)

    def test_opr_blend(self):
        base = S.perf_norm(1625)  # sem opr
        blended = S.perf_norm(1625, 0.0)  # opr percentil 0 puxa p/ baixo
        self.assertLess(blended, base)


class AwardTier(unittest.TestCase):
    def test_by_type(self):
        self.assertEqual(S.award_tier(0, None), "S")   # Impact
        self.assertEqual(S.award_tier(1, None), "S")   # Winner
        self.assertEqual(S.award_tier(9, None), "A")   # EI
        self.assertEqual(S.award_tier(2, None), "A")   # Finalist

    def test_by_name_fallback(self):
        self.assertEqual(S.award_tier(None, "Regional Winners"), "S")
        self.assertEqual(S.award_tier(None, "FIRST Impact Award"), "S")
        self.assertEqual(S.award_tier(None, "Innovation in Control Award"), "B")
        self.assertEqual(S.award_tier(999, "Algum Prêmio Desconhecido"), "C")

    def test_world_award_has_extra_weight(self):
        plain, _ = S.awards_score([{"award_type": 1, "name": "Winner", "is_champs": False}])
        champ, _ = S.awards_score([{"award_type": 1, "name": "Winner", "is_champs": True}])
        self.assertGreater(champ, plain)

    def test_diminishing_returns(self):
        one, _ = S.awards_score([{"award_type": 1, "name": "W"}])
        five, _ = S.awards_score([{"award_type": 1, "name": "W"}] * 5)
        self.assertLess(five - one, 4 * one)   # não é linear
        self.assertLessEqual(five, 1.0)


class Playoff(unittest.TestCase):
    def test_none(self):
        s, label = S.playoff_score_from_status({"made_playoff": False})
        self.assertEqual(s, 0.0)

    def test_winner_with_captain_bonus(self):
        s, label = S.playoff_score_from_status(
            {"made_playoff": True, "level": "f", "won": True,
             "double_elim_round": "Finals", "alliance_number": 1,
             "alliance_pick": 0})
        self.assertEqual(s, 1.0)          # já estava no teto
        self.assertIn("Campeão", label)
        self.assertIn("capitão", label)

    def test_finalist(self):
        s, _ = S.playoff_score_from_status(
            {"made_playoff": True, "level": "f", "won": False,
             "alliance_number": 3, "alliance_pick": 0})
        self.assertAlmostEqual(s, C.PLAYOFF_SCORE["finalist"] + C.ALLIANCE_ROLE_BONUS[0])

    def test_alliance_role_hierarchy(self):
        scores = [S.playoff_score_from_status(
            {"made_playoff": True, "level": "sf", "won": False,
             "alliance_number": 4, "alliance_pick": pick})[0]
            for pick in range(4)]
        self.assertGreater(scores[0], scores[1])
        self.assertGreater(scores[1], scores[2])
        self.assertGreater(scores[2], scores[3])

    def test_round_string_parse(self):
        s, label = S.playoff_score_from_status(
            {"made_playoff": True, "level": "", "won": False,
             "double_elim_round": "Round 4", "alliance_number": 12})
        self.assertEqual(s, C.PLAYOFF_SCORE["round4"])

    def test_best_of_many(self):
        s, label = S.best_playoff([
            {"made_playoff": True, "level": "sf", "won": False},
            {"made_playoff": True, "level": "f", "won": True,
             "double_elim_round": "Finals", "alliance_pick": 0},
            {"made_playoff": False},
        ])
        self.assertEqual(s, 1.0)


class Champs(unittest.TestCase):
    def test_absent(self):
        self.assertEqual(S.champs_score(False, 0.9), 0.0)

    def test_attend_only(self):
        self.assertAlmostEqual(S.champs_score(True, None), C.CHAMPS_ATTEND_BASE)

    def test_attend_plus_result(self):
        self.assertAlmostEqual(
            S.champs_score(True, 1.0),
            C.CHAMPS_ATTEND_BASE + C.CHAMPS_RESULT_WEIGHT)

    def test_world_bonus_is_never_negative(self):
        self.assertEqual(S.world_bonus(False, {k: 1 for k in C.W}), 0.0)
        self.assertEqual(S.world_bonus(True, {}), C.WORLD_ATTENDANCE_BONUS)

    def test_world_results_only_raise_bonus(self):
        low = S.world_bonus(True, {k: 0 for k in C.W})
        high = S.world_bonus(
            True, {k: 1 for k in C.W},
            [{"made_playoff": True, "level": "f", "won": True, "alliance_pick": 0}])
        self.assertGreater(high, low)
        self.assertEqual(high, C.WORLD_ATTENDANCE_BONUS + C.WORLD_RESULT_BONUS_MAX)

    def test_division_finalist_always_beats_shallower_playoff(self):
        finalist = S.world_result_quality(
            {"performance": 0, "premios": 0, "winrate": 0},
            [{"made_playoff": True, "level": "f", "won": False}])
        semifinal = S.world_result_quality(
            {"performance": 1, "premios": 1, "winrate": 1},
            [{"made_playoff": True, "level": "sf", "won": False}])
        no_playoff = S.world_result_quality(
            {"performance": 1, "premios": 1, "winrate": 1},
            [{"made_playoff": False}])
        self.assertGreater(finalist, semifinal)
        self.assertGreater(finalist, no_playoff)


class Composite(unittest.TestCase):
    def test_world_component_has_no_effect(self):
        self.assertEqual(S.season_score({"mundial": 1}), 0)

    def test_zero(self):
        self.assertEqual(S.season_score({}), 0.0)

    def test_max(self):
        self.assertEqual(
            S.season_score({k: 1.0 for k in C.W}), 100.0)

    def test_weights_sum(self):
        self.assertTrue(S.weights_sum_ok())

    def test_monotonic_in_performance(self):
        lo = S.season_score({"performance": 0.2, "premios": 0.5, "playoff": 0.5,
                             "winrate": 0.5, "mundial": 0.0})
        hi = S.season_score({"performance": 0.9, "premios": 0.5, "playoff": 0.5,
                             "winrate": 0.5, "mundial": 0.0})
        self.assertGreater(hi, lo)


if __name__ == "__main__":
    unittest.main()
