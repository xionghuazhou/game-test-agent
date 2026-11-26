"""Deterministic analyzer fallbacks must not miss obvious game bugs."""
import unittest

from app.agents.analyzer_agent import AnalyzerAgent


class AnalyzerFallbackTest(unittest.TestCase):
    def analyze(self, state):
        return AnalyzerAgent._rule_based_fallback(state, "provider unavailable", [], False)

    def test_negative_hp_is_a_high_severity_logic_bug(self):
        result = self.analyze({
            "last_action_result": "success",
            "indicators": {"hp": -3, "score": 134, "fps": 58},
        })
        self.assertTrue(result["is_bug"])
        self.assertEqual(result["severity"], "high")
        self.assertEqual(result["category"], "logic")
        self.assertIn("hp=-3", result["actual"])

    def test_nan_is_a_bug(self):
        result = self.analyze({
            "last_action_result": "success",
            "indicators": {"progress": float("nan")},
        })
        self.assertTrue(result["is_bug"])

    def test_no_response_is_a_bug(self):
        result = self.analyze({
            "last_action_result": "no_response",
            "indicators": {"hp": 100},
        })
        self.assertTrue(result["is_bug"])
        self.assertEqual(result["category"], "ui")

    def test_normal_battle_damage_is_not_a_bug(self):
        result = self.analyze({
            "last_action_result": "success",
            "indicators": {"hp": 81, "score": 61, "fps": 60},
        })
        self.assertFalse(result["is_bug"])


if __name__ == "__main__":
    unittest.main()
