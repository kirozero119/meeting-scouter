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
        text = (ROOT / "tests" / "fixtures" / f"{name}-meeting.md").read_text(
            encoding="utf-8"
        )
        analysis = json.loads(
            (ROOT / "tests" / "fixtures" / f"{name}-analysis.json").read_text(
                encoding="utf-8"
            )
        )
        return text, analysis

    def test_fixed_dictionary_counts_known_terms(self) -> None:
        terms = engine._load_terms(ROOT / "meeting-scouter" / "data" / "buzzwords.json")
        summary = engine._count_terms(
            "アジェンダを確認してKPIをアラインします。", terms
        )
        self.assertGreaterEqual(summary.total, 3)
        self.assertIn("アジェンダ", summary.counts)
        self.assertIn("KPI", summary.counts)
        self.assertIn("アライン", summary.counts)

    def test_airy_meeting_scores_higher_than_healthy_meeting(self) -> None:
        healthy_text, healthy_analysis = self.load_fixture("healthy")
        airy_text, airy_analysis = self.load_fixture("airy")
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)
            healthy = engine.analyze(
                healthy_text, healthy_analysis, state_dir, learn=False
            )
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

    def test_longer_meeting_dilutes_jargon_density(self) -> None:
        text, analysis = self.load_fixture("airy")
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)
            short = engine.analyze(
                text, {**analysis, "meeting_minutes": 30}, state_dir, learn=False
            )
            long = engine.analyze(
                text, {**analysis, "meeting_minutes": 180}, state_dir, learn=False
            )
        self.assertGreater(short.score.jargon, long.score.jargon)
        self.assertGreater(short.score.ambiguity, long.score.ambiguity)
        self.assertGreater(short.index, long.index)

    def test_decision_deficit_scales_with_meeting_length(self) -> None:
        text, analysis = self.load_fixture("healthy")
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)
            # 2 decisions in 20 minutes = 6/h → no deficit.
            quick = engine.analyze(
                text, {**analysis, "meeting_minutes": 20}, state_dir, learn=False
            )
            # 2 decisions in 180 minutes = 0.67/h → heavy deficit.
            slow = engine.analyze(
                text, {**analysis, "meeting_minutes": 180}, state_dir, learn=False
            )
        self.assertEqual(quick.score.decision_deficit, 0)
        self.assertEqual(slow.score.decision_deficit, 16)

    def test_zero_decisions_always_max_deficit(self) -> None:
        text, analysis = self.load_fixture("airy")
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)
            timed = engine.analyze(
                text, {**analysis, "meeting_minutes": 15}, state_dir, learn=False
            )
            untimed = engine.analyze(
                text, {**analysis, "meeting_minutes": None}, state_dir, learn=False
            )
        self.assertEqual(timed.score.decision_deficit, 20)
        self.assertEqual(untimed.score.decision_deficit, 20)

    def test_null_minutes_falls_back_to_character_density(self) -> None:
        text, analysis = self.load_fixture("airy")
        with tempfile.TemporaryDirectory() as temp_dir:
            result = engine.analyze(
                text, {**analysis, "meeting_minutes": None}, Path(temp_dir), learn=False
            )
        self.assertIsNone(result.meeting_minutes)
        self.assertGreater(result.index, 0)

    def test_person_hours_damage_reported(self) -> None:
        text, analysis = self.load_fixture("airy")
        with tempfile.TemporaryDirectory() as temp_dir:
            result = engine.analyze(
                text,
                {**analysis, "meeting_minutes": 120, "attendee_count": 8},
                Path(temp_dir),
                learn=False,
            )
        self.assertEqual(result.person_hours, 16.0)
        self.assertAlmostEqual(
            result.wasted_person_hours, round(16.0 * result.index / 100, 1)
        )
        output = engine.render_tui(result)
        self.assertIn("16.0人時", output)
        self.assertIn("推定被害", output)
        self.assertIn("決定効率", output)

    def test_attendees_without_minutes_reports_no_damage(self) -> None:
        text, analysis = self.load_fixture("airy")
        analysis = {**analysis, "attendee_count": 8}
        analysis.pop("meeting_minutes")
        with tempfile.TemporaryDirectory() as temp_dir:
            result = engine.analyze(text, analysis, Path(temp_dir), learn=False)
        self.assertIsNone(result.person_hours)
        self.assertIsNone(result.wasted_person_hours)
        self.assertNotIn("推定被害", engine.render_tui(result))

    def test_attendees_do_not_change_score(self) -> None:
        text, analysis = self.load_fixture("airy")
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)
            small = engine.analyze(
                text, {**analysis, "attendee_count": 2}, state_dir, learn=False
            )
            big = engine.analyze(
                text, {**analysis, "attendee_count": 12}, state_dir, learn=False
            )
        self.assertEqual(small.index, big.index)
        self.assertLess(small.wasted_person_hours, big.wasted_person_hours)

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
