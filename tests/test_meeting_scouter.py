from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "meeting-scouter" / "scripts" / "meeting_scouter.py"
SPEC = importlib.util.spec_from_file_location("meeting_scouter_engine", SCRIPT)
assert SPEC and SPEC.loader
engine = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = engine
SPEC.loader.exec_module(engine)


class MeetingScouterTests(unittest.TestCase):
    def load_fixture(self, name: str) -> tuple[str, dict]:
        text = (ROOT / "tests" / "fixtures" / f"{name}-meeting.md").read_text(encoding="utf-8")
        analysis = json.loads(
            (ROOT / "tests" / "fixtures" / f"{name}-analysis.json").read_text(encoding="utf-8")
        )
        return text, analysis

    def test_fixed_dictionary_counts_known_terms(self) -> None:
        terms = engine._load_terms(ROOT / "meeting-scouter" / "data" / "buzzwords.json")
        summary = engine._count_terms("アジェンダを確認してKPIをアラインします。", terms)
        self.assertGreaterEqual(summary.total, 3)
        self.assertIn("アジェンダ", summary.counts)
        self.assertIn("KPI", summary.counts)
        self.assertIn("アライン", summary.counts)

    def test_airy_meeting_scores_higher_than_healthy_meeting(self) -> None:
        healthy_text, healthy_analysis = self.load_fixture("healthy")
        airy_text, airy_analysis = self.load_fixture("airy")
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)
            healthy = engine.analyze(healthy_text, healthy_analysis, state_dir, learn=False)
            airy = engine.analyze(airy_text, airy_analysis, state_dir, learn=False)
        self.assertLess(healthy.index, airy.index)
        self.assertLess(healthy.battle_power, airy.battle_power)
        self.assertGreaterEqual(airy.index, 60)

    def test_candidate_learning_does_not_store_transcript(self) -> None:
        text, analysis = self.load_fixture("airy")
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)
            result = engine.analyze(text, analysis, state_dir, learn=True)
            candidates = (state_dir / "candidates.json").read_text(encoding="utf-8")
            history = (state_dir / "history.jsonl").read_text(encoding="utf-8")
        self.assertTrue(result.new_candidates)
        self.assertNotIn(text, candidates)
        self.assertNotIn(text, history)
        self.assertIn("詳細は次回改めて議論します", candidates)

    def test_low_confidence_discovery_is_ignored(self) -> None:
        text, analysis = self.load_fixture("healthy")
        analysis["discovered_phrases"] = [
            {
                "phrase": "少し確認します",
                "category": "vague",
                "reason": "弱い推測",
                "confidence": 0.4,
                "occurrences": 10,
            }
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            result = engine.analyze(text, analysis, Path(temp_dir), learn=False)
        self.assertEqual(result.discovered_counts["vague"], 0)

    def test_render_contains_primary_metrics(self) -> None:
        text, analysis = self.load_fixture("airy")
        with tempfile.TemporaryDirectory() as temp_dir:
            result = engine.analyze(text, analysis, Path(temp_dir), learn=False)
        output = engine.render_tui(result)
        self.assertIn("空中戦指数", output)
        self.assertIn("会議戦闘力", output)
        self.assertIn("当スカウター基準", output)
        self.assertIn("診断", output)


if __name__ == "__main__":
    unittest.main()
