#!/usr/bin/env python3
"""Deterministic scoring, candidate learning, and TUI rendering for meeting-scouter."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import textwrap
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SKILL_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = SKILL_DIR / "data"
DEFAULT_STATE_DIR = Path(os.environ.get("MEETING_SCOUTER_HOME", "~/.meeting-scouter")).expanduser()
CANDIDATE_CONFIDENCE_THRESHOLD = 0.75
BASELINE_POWER = 4_000

CATEGORY_LABELS = {
    "buzzword": "横文字",
    "vague": "曖昧表現",
    "responsibility_blur": "責任ぼかし",
    "decision_avoidance": "決定回避",
    "meeting_meta": "会議メタ表現",
}


class ScouterError(RuntimeError):
    """User-actionable error from meeting-scouter."""


@dataclass(frozen=True)
class MatchSummary:
    total: int
    unique: int
    counts: dict[str, int]


@dataclass(frozen=True)
class ScoreBreakdown:
    jargon: int
    ambiguity: int
    decision_deficit: int
    accountability_gap: int

    @property
    def total(self) -> int:
        return min(100, max(0, self.jargon + self.ambiguity + self.decision_deficit + self.accountability_gap))


@dataclass(frozen=True)
class ScouterResult:
    source_label: str
    character_count: int
    meeting_minutes: int | None
    fixed_buzzwords: MatchSummary
    fixed_vague_phrases: MatchSummary
    discovered_counts: dict[str, int]
    decisions: int
    actions: int
    missing_owner: int
    missing_deadline: int
    score: ScoreBreakdown
    index: int
    rank: str
    rank_label: str
    battle_power: int
    baseline_multiple: float
    roast: str
    new_candidates: list[dict[str, Any]]
    persistence_warning: str | None


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ScouterError(f"必要なファイルが見つかりません: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ScouterError(f"JSONを読み込めません: {path}: {exc}") from exc


def _load_terms(path: Path) -> list[dict[str, Any]]:
    raw = _load_json(path)
    if not isinstance(raw, list):
        raise ScouterError(f"辞書は配列である必要があります: {path}")
    terms: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("term"), str):
            raise ScouterError(f"辞書エントリが不正です: {path}")
        variants = item.get("variants", [item["term"]])
        if not isinstance(variants, list) or not all(isinstance(v, str) and v for v in variants):
            raise ScouterError(f"variants が不正です: {path}: {item.get('term')}")
        terms.append({"term": item["term"], "variants": variants})
    return terms


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _count_terms(text: str, terms: list[dict[str, Any]]) -> MatchSummary:
    normalized = _normalize_text(text)
    counts: dict[str, int] = {}
    for entry in terms:
        variants = sorted(set(entry["variants"]), key=len, reverse=True)
        pattern = "|".join(re.escape(variant) for variant in variants)
        count = len(re.findall(pattern, normalized, flags=re.IGNORECASE))
        if count:
            counts[entry["term"]] = count
    return MatchSummary(total=sum(counts.values()), unique=len(counts), counts=counts)


def _load_user_terms(state_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    path = state_dir / "dictionary.json"
    if not path.exists():
        return [], []
    raw = _load_json(path)
    if not isinstance(raw, dict):
        raise ScouterError(f"ユーザー辞書が不正です: {path}")
    return _coerce_user_terms(raw.get("buzzwords", [])), _coerce_user_terms(raw.get("vague_phrases", []))


def _coerce_user_terms(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    result: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, str) and item.strip():
            value = item.strip()
            result.append({"term": value, "variants": [value]})
        elif isinstance(item, dict) and isinstance(item.get("term"), str):
            variants = item.get("variants", [item["term"]])
            if isinstance(variants, list) and all(isinstance(v, str) and v for v in variants):
                result.append({"term": item["term"], "variants": variants})
    return result


def _validate_analysis(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ScouterError("analysis JSON のルートはオブジェクトである必要があります")

    decisions = raw.get("decisions", [])
    actions = raw.get("actions", [])
    discovered = raw.get("discovered_phrases", [])
    if not isinstance(decisions, list) or not isinstance(actions, list) or not isinstance(discovered, list):
        raise ScouterError("decisions, actions, discovered_phrases は配列である必要があります")

    cleaned_discovered: list[dict[str, Any]] = []
    for item in discovered:
        if not isinstance(item, dict):
            continue
        phrase = str(item.get("phrase", "")).strip()
        category = str(item.get("category", "vague")).strip()
        if not phrase or category not in CATEGORY_LABELS:
            continue
        try:
            confidence = float(item.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        try:
            occurrences = max(1, int(item.get("occurrences", 1)))
        except (TypeError, ValueError):
            occurrences = 1
        cleaned_discovered.append(
            {
                "phrase": phrase,
                "category": category,
                "reason": str(item.get("reason", "")).strip(),
                "confidence": min(1.0, max(0.0, confidence)),
                "occurrences": occurrences,
            }
        )

    minutes = raw.get("meeting_minutes")
    if minutes is not None:
        try:
            minutes = max(1, int(minutes))
        except (TypeError, ValueError):
            minutes = None

    return {
        "source_label": str(raw.get("source_label", "貼り付けられた議事録")).strip() or "貼り付けられた議事録",
        "meeting_minutes": minutes,
        "decisions": decisions,
        "actions": actions,
        "discovered_phrases": cleaned_discovered,
        "roast": str(raw.get("roast", "")).strip(),
    }


def _action_missing(action: Any, field: str) -> bool:
    if not isinstance(action, dict):
        return True
    value = action.get(field)
    return value is None or (isinstance(value, str) and not value.strip())


def _discovered_counts(discovered: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts = {key: 0 for key in CATEGORY_LABELS}
    for item in discovered:
        if item["confidence"] >= CANDIDATE_CONFIDENCE_THRESHOLD:
            counts[item["category"]] += item["occurrences"]
    return counts


def _score(
    character_count: int,
    buzzword_count: int,
    vague_count: int,
    responsibility_blur_count: int,
    decision_avoidance_count: int,
    decisions: int,
    actions: int,
    missing_owner: int,
    missing_deadline: int,
) -> ScoreBreakdown:
    # Density prevents long transcripts from being punished simply for being long.
    effective_chars = max(character_count, 500)
    buzz_density = buzzword_count * 1000 / effective_chars
    vague_density = (vague_count + responsibility_blur_count + decision_avoidance_count) * 1000 / effective_chars

    jargon = round(min(25, buzz_density * 4.2))
    ambiguity = round(min(30, vague_density * 5.0))

    if decisions == 0:
        decision_deficit = 20
    elif decisions == 1:
        decision_deficit = 12
    elif decisions == 2:
        decision_deficit = 6
    else:
        decision_deficit = 0

    if actions == 0:
        accountability_gap = 18 if decisions == 0 else 10
    else:
        owner_ratio = missing_owner / actions
        deadline_ratio = missing_deadline / actions
        accountability_gap = round(min(25, owner_ratio * 14 + deadline_ratio * 11))

    return ScoreBreakdown(
        jargon=jargon,
        ambiguity=ambiguity,
        decision_deficit=decision_deficit,
        accountability_gap=accountability_gap,
    )


def _rank(index: int) -> tuple[str, str]:
    if index >= 95:
        return "SSS", "会議そのものが目的です"
    if index >= 80:
        return "S", "地上との通信が途絶えています"
    if index >= 60:
        return "A", "かなり空中です"
    if index >= 40:
        return "B", "会議らしくフワついています"
    if index >= 20:
        return "C", "少し足元が浮いています"
    return "健全", "仕事が進んでいます"


def _default_roast(result_data: dict[str, int]) -> str:
    if result_data["decisions"] == 0 and result_data["actions"] == 0:
        return "全員で認識を合わせましたが、何を決めたのかは誰も覚えていません。"
    if result_data["actions"] > 0 and result_data["missing_owner"] == result_data["actions"]:
        return "やることは決まりました。やる人だけが、まだこの世界に存在していません。"
    if result_data["missing_deadline"] > 0:
        return "前には進みましたが、いつ着くかは未定です。"
    if result_data["decisions"] >= 3 and result_data["missing_owner"] == 0 and result_data["missing_deadline"] == 0:
        return "異常に有意義な会議です。くだらなさが不足しています。"
    return "会議は終わりました。議題が終わったかどうかは別問題です。"


def _fingerprint(text: str) -> str:
    return hashlib.sha256(_normalize_text(text).encode("utf-8")).hexdigest()[:16]


def _phrase_token(phrase: str) -> str:
    return re.sub(r"\s+", "", phrase).casefold()


def _candidate_key(phrase: str, category: str) -> str:
    return f"{category}:{_phrase_token(phrase)}"


def _learn_candidates(
    state_dir: Path,
    discovered: list[dict[str, Any]],
    text: str,
    source_label: str,
    enabled: bool,
) -> tuple[list[dict[str, Any]], str | None]:
    eligible = [item for item in discovered if item["confidence"] >= CANDIDATE_CONFIDENCE_THRESHOLD]
    if not enabled or not eligible:
        return [], None

    now = datetime.now(timezone.utc).isoformat()
    doc_id = _fingerprint(text)
    path = state_dir / "candidates.json"
    history_path = state_dir / "history.jsonl"
    warning: str | None = None

    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        current = _load_json(path) if path.exists() else {"version": 1, "candidates": {}}
        if not isinstance(current, dict) or not isinstance(current.get("candidates"), dict):
            current = {"version": 1, "candidates": {}}
        candidates: dict[str, Any] = current["candidates"]
        new_items: list[dict[str, Any]] = []

        for item in eligible:
            key = _candidate_key(item["phrase"], item["category"])
            entry = candidates.get(key)
            if not isinstance(entry, dict):
                entry = {
                    "phrase": item["phrase"],
                    "category": item["category"],
                    "count": 0,
                    "document_count": 0,
                    "documents": [],
                    "confidence_sum": 0.0,
                    "examples": [],
                    "first_seen": now,
                    "last_seen": now,
                }
                candidates[key] = entry
                new_items.append(item)

            occurrences = item["occurrences"]
            entry["count"] = int(entry.get("count", 0)) + occurrences
            documents = list(entry.get("documents", []))
            if doc_id not in documents:
                documents.append(doc_id)
                entry["document_count"] = int(entry.get("document_count", 0)) + 1
            entry["documents"] = documents[-20:]
            entry["confidence_sum"] = float(entry.get("confidence_sum", 0.0)) + item["confidence"] * occurrences
            entry["last_seen"] = now
            examples = list(entry.get("examples", []))
            example = item.get("reason") or source_label
            if example and example not in examples:
                examples.append(example)
            entry["examples"] = examples[-3:]
            entry["average_confidence"] = round(entry["confidence_sum"] / max(1, entry["count"]), 3)
            entry["eligible_for_promotion"] = (
                entry["count"] >= 3
                and entry["document_count"] >= 2
                and entry["average_confidence"] >= 0.85
            )

        path.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        history_record = {
            "timestamp": now,
            "source_label": source_label,
            "document_fingerprint": doc_id,
            "discovered_phrases": eligible,
        }
        with history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(history_record, ensure_ascii=False) + "\n")
        return new_items, None
    except (OSError, ScouterError, json.JSONDecodeError) as exc:
        warning = f"候補辞書を保存できませんでした: {exc}"
        return [], warning


def analyze(text: str, analysis_raw: Any, state_dir: Path, learn: bool) -> ScouterResult:
    if not _normalize_text(text):
        raise ScouterError("議事録の本文が空です")

    analysis = _validate_analysis(analysis_raw)
    base_buzzwords = _load_terms(DATA_DIR / "buzzwords.json")
    base_vague = _load_terms(DATA_DIR / "vague-phrases.json")
    user_buzzwords, user_vague = _load_user_terms(state_dir)
    fixed_buzzwords = _count_terms(text, base_buzzwords + user_buzzwords)
    fixed_vague = _count_terms(text, base_vague + user_vague)
    known_tokens = {
        _phrase_token(variant)
        for entry in (base_buzzwords + base_vague + user_buzzwords + user_vague)
        for variant in entry["variants"]
    }
    discovered = [
        item for item in analysis["discovered_phrases"]
        if _phrase_token(item["phrase"]) not in known_tokens
    ]
    discovered_counts = _discovered_counts(discovered)

    decisions = len(analysis["decisions"])
    actions = len(analysis["actions"])
    missing_owner = sum(_action_missing(action, "owner") for action in analysis["actions"])
    missing_deadline = sum(_action_missing(action, "deadline") for action in analysis["actions"])
    char_count = len(_normalize_text(text))

    score = _score(
        character_count=char_count,
        buzzword_count=fixed_buzzwords.total + discovered_counts["buzzword"],
        vague_count=fixed_vague.total + discovered_counts["vague"] + discovered_counts["meeting_meta"],
        responsibility_blur_count=discovered_counts["responsibility_blur"],
        decision_avoidance_count=discovered_counts["decision_avoidance"],
        decisions=decisions,
        actions=actions,
        missing_owner=missing_owner,
        missing_deadline=missing_deadline,
    )
    index = score.total
    rank, rank_label = _rank(index)
    battle_power = 1_000 + index * 100
    new_candidates, warning = _learn_candidates(
        state_dir=state_dir,
        discovered=discovered,
        text=text,
        source_label=analysis["source_label"],
        enabled=learn,
    )
    roast = analysis["roast"] or _default_roast(
        {
            "decisions": decisions,
            "actions": actions,
            "missing_owner": missing_owner,
            "missing_deadline": missing_deadline,
        }
    )

    return ScouterResult(
        source_label=analysis["source_label"],
        character_count=char_count,
        meeting_minutes=analysis["meeting_minutes"],
        fixed_buzzwords=fixed_buzzwords,
        fixed_vague_phrases=fixed_vague,
        discovered_counts=discovered_counts,
        decisions=decisions,
        actions=actions,
        missing_owner=missing_owner,
        missing_deadline=missing_deadline,
        score=score,
        index=index,
        rank=rank,
        rank_label=rank_label,
        battle_power=battle_power,
        baseline_multiple=round(battle_power / BASELINE_POWER, 1),
        roast=roast,
        new_candidates=new_candidates,
        persistence_warning=warning,
    )


def _bar(value: int, width: int = 24) -> str:
    filled = round(width * value / 100)
    return "█" * filled + "░" * (width - filled)


def _display_width(text: str) -> int:
    # Treat only East Asian wide/full-width characters as two columns.
    return sum(2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1 for char in text)


def _pad(text: str, width: int) -> str:
    return text + " " * max(0, width - _display_width(text))


def _box(lines: list[str], width: int = 62) -> str:
    inner = width - 2
    output = ["╭" + "─" * inner + "╮"]
    for line in lines:
        output.append("│" + _pad(line, inner) + "│")
    output.append("╰" + "─" * inner + "╯")
    return "\n".join(output)


def render_tui(result: ScouterResult) -> str:
    lines: list[str] = []
    lines.append("                  会議スカウター")
    lines.append("          この会議、本当に必要でしたか？")
    lines.append("")
    lines.append(f"  解析対象    {result.source_label}")
    lines.append(f"  文字数      {result.character_count:,}文字")
    if result.meeting_minutes is not None:
        lines.append(f"  会議時間    {result.meeting_minutes}分")
    lines.append("")
    lines.append(f"  空中戦指数  {result.index:>3}/100  {_bar(result.index)}")
    lines.append(f"  ランク      {result.rank}  — {result.rank_label}")
    lines.append(f"  会議戦闘力  {result.battle_power:,}")
    lines.append(f"  当スカウター基準: 一般的な定例会議の約{result.baseline_multiple:.1f}倍")
    lines.append("")
    lines.append("  ── 内訳 ─────────────────────────────────────")
    lines.append(f"  横文字              {result.fixed_buzzwords.total + result.discovered_counts['buzzword']:>3}回")
    vague_total = (
        result.fixed_vague_phrases.total
        + result.discovered_counts["vague"]
        + result.discovered_counts["responsibility_blur"]
        + result.discovered_counts["decision_avoidance"]
        + result.discovered_counts["meeting_meta"]
    )
    lines.append(f"  曖昧・責任ぼかし    {vague_total:>3}回")
    lines.append(f"  決定事項            {result.decisions:>3}件")
    lines.append(f"  アクション          {result.actions:>3}件")
    lines.append(f"  担当者不明          {result.missing_owner:>3}件")
    lines.append(f"  期限不明            {result.missing_deadline:>3}件")
    lines.append("")
    lines.append(
        f"  得点内訳  横文字 {result.score.jargon:>2} / 曖昧 {result.score.ambiguity:>2} / "
        f"未決定 {result.score.decision_deficit:>2} / 責任 {result.score.accountability_gap:>2}"
    )

    if result.fixed_buzzwords.counts:
        top = sorted(result.fixed_buzzwords.counts.items(), key=lambda item: (-item[1], item[0]))[:3]
        lines.append("  頻出語      " + "、".join(f"{term}×{count}" for term, count in top))

    if result.new_candidates:
        lines.append("")
        lines.append("  ── 新種会議語 ───────────────────────────────")
        for item in result.new_candidates[:3]:
            label = CATEGORY_LABELS.get(item["category"], item["category"])
            phrase = textwrap.shorten(item["phrase"], width=24, placeholder="…")
            lines.append(f"  「{phrase}」  {label} / 信頼度 {item['confidence']:.0%}")
        if len(result.new_candidates) > 3:
            lines.append(f"  ほか {len(result.new_candidates) - 3}件")

    lines.append("")
    lines.append("  ── 診断 ─────────────────────────────────────")
    for wrapped in textwrap.wrap(result.roast, width=27) or [result.roast]:
        lines.append(f"  {wrapped}")

    if result.character_count < 200:
        lines.append("")
        lines.append("  ※ 本文が短いため、指数の信頼度は低めです。")
    if result.persistence_warning:
        lines.append("")
        for wrapped in textwrap.wrap(result.persistence_warning, width=27):
            lines.append(f"  ⚠ {wrapped}")

    return _box(lines)


def result_to_json(result: ScouterResult) -> dict[str, Any]:
    raw = asdict(result)
    raw["score"]["total"] = result.score.total
    return raw


def _read_text(args: argparse.Namespace) -> str:
    if args.text_file:
        path = Path(args.text_file).expanduser()
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise ScouterError(f"本文ファイルが見つかりません: {path}") from exc
        except UnicodeDecodeError as exc:
            raise ScouterError(f"本文ファイルはUTF-8テキストに変換してください: {path}") from exc
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise ScouterError("--text-file を指定するか、標準入力から本文を渡してください")


def _read_analysis(path_value: str) -> Any:
    path = Path(path_value).expanduser()
    return _load_json(path)


def _list_candidates(state_dir: Path, as_json: bool) -> str:
    path = state_dir / "candidates.json"
    if not path.exists():
        return "[]" if as_json else "候補辞書はまだ空です。"
    raw = _load_json(path)
    candidates = list(raw.get("candidates", {}).values()) if isinstance(raw, dict) else []
    candidates.sort(key=lambda item: (-int(item.get("count", 0)), str(item.get("phrase", ""))))
    if as_json:
        return json.dumps(candidates, ensure_ascii=False, indent=2)
    if not candidates:
        return "候補辞書はまだ空です。"
    lines = ["会議語候補:"]
    for item in candidates:
        marker = "昇格候補" if item.get("eligible_for_promotion") else "観測中"
        lines.append(
            f"- {item.get('phrase')} [{CATEGORY_LABELS.get(item.get('category'), item.get('category'))}] "
            f"{item.get('count', 0)}回 / {item.get('document_count', 0)}議事録 / {marker}"
        )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="会議スカウターの決定論的スコアリングエンジン")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_parser = subparsers.add_parser("analyze", help="議事録とAI分析JSONから結果を生成")
    analyze_parser.add_argument("--text-file", help="UTF-8の議事録本文ファイル。省略時は標準入力")
    analyze_parser.add_argument("--analysis-file", required=True, help="analysis contract準拠のJSON")
    analyze_parser.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR), help="候補辞書の保存先")
    analyze_parser.add_argument("--format", choices=("tui", "json"), default="tui")
    analyze_parser.add_argument("--no-learn", action="store_true", help="候補辞書を更新しない")

    candidates_parser = subparsers.add_parser("candidates", help="蓄積された新語候補を表示")
    candidates_parser.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR))
    candidates_parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "analyze":
            text = _read_text(args)
            analysis_raw = _read_analysis(args.analysis_file)
            result = analyze(text, analysis_raw, Path(args.state_dir).expanduser(), learn=not args.no_learn)
            if args.format == "json":
                print(json.dumps(result_to_json(result), ensure_ascii=False, indent=2))
            else:
                print(render_tui(result))
            return 0
        if args.command == "candidates":
            print(_list_candidates(Path(args.state_dir).expanduser(), args.json))
            return 0
        parser.error("unknown command")
        return 2
    except ScouterError as exc:
        print(f"meeting-scouter: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
