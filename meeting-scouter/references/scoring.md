# Scoring and persistence

The engine reports four score components totaling 0–100:

1. **Jargon (0–25)**: fixed and AI-discovered buzzword density.
2. **Ambiguity (0–30)**: vague, responsibility-blurring, decision-avoidance, and meeting-meta phrase density.
3. **Decision deficit (0–20)**: highest when no explicit decision exists; time-aware when the meeting length is known.
4. **Accountability gap (0–25)**: missing action owners and deadlines. A meeting with no actions receives a smaller fixed penalty. Ratio-based, so it is independent of meeting length.

## Time-aware scoring

When `meeting_minutes` is provided, density and decision efficiency are normalized by meeting time instead of text length:

- **Density**: jargon and ambiguity counts are divided by 30-minute units (minimum 15 minutes to avoid explosive rates for micro-meetings). The calibration assumption is that 30 minutes of meeting ≈ 1,000 characters of condensed minutes, keeping coefficients compatible with the character-based path. The same 10 buzzwords are dense in a 30-minute meeting and diluted in a 3-hour one.
- **Decision deficit**: judged on decisions per hour — ≥3/h scores 0, ≥2/h scores 6, ≥1/h scores 12, below 1/h scores 16. Zero decisions always score 20.

When `meeting_minutes` is `null`, the engine falls back to character-count normalization (per 1,000 characters, minimum 500) and absolute decision counts (0→20, 1→12, 2→6, 3+→0). Transcripts shorter than 200 characters receive a low-confidence note.

## Person-hours damage

`attendee_count` never changes the 0–100 score; the index measures the meeting's content quality. When both `meeting_minutes` and `attendee_count` are known, the TUI reports:

- **Person-hours**: `minutes / 60 × attendees`.
- **Wasted person-hours (推定被害)**: `person-hours × index / 100` — the estimated human time lost to the air battle. A 2-person rambling meeting and an 8-person one can share the same index while causing very different damage.

## Ranks

| Index | Rank | Label |
|---:|:---:|---|
| 0–19 | 健全 | 仕事が進んでいます |
| 20–39 | C | 少し足元が浮いています |
| 40–59 | B | 会議らしくフワついています |
| 60–79 | A | かなり空中です |
| 80–94 | S | 地上との通信が途絶えています |
| 95–100 | SSS | 会議そのものが目的です |

Battle power is theatrical: `1,000 + index × 100`. The comparison baseline is a fictional in-tool baseline of 4,000 and must always be labeled `当スカウター基準`; it is not real-world benchmark data.

## Candidate learning

The engine stores state in `~/.meeting-scouter/` or `MEETING_SCOUTER_HOME`:

- `candidates.json`: aggregate phrase counts, confidence, and promotion eligibility.
- `history.jsonl`: timestamps, source labels, fingerprints, and discovered phrases.
- `dictionary.json`: optional user-maintained promoted terms.

The transcript itself is never persisted. A candidate becomes `eligible_for_promotion` after at least three occurrences across at least two distinct document fingerprints with average confidence of at least 0.85. Promotion is deliberately manual in the MVP.
