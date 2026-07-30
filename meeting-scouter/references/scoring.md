# Scoring and persistence

The engine reports four score components totaling 0–100:

1. **Jargon (0–25)**: fixed and AI-discovered buzzword density per 1,000 characters.
2. **Ambiguity (0–30)**: vague, responsibility-blurring, decision-avoidance, and meeting-meta phrase density.
3. **Decision deficit (0–20)**: highest when no explicit decision exists.
4. **Accountability gap (0–25)**: missing action owners and deadlines. A meeting with no actions receives a smaller fixed penalty.

Long transcripts are normalized by character count. Transcripts shorter than 200 characters receive a low-confidence note.

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
