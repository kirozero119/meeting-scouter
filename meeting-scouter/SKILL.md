---
name: meeting-scouter
description: Analyzes Japanese meeting minutes, transcripts, pasted notes, or meeting-note file paths and returns a playful terminal-style "air-battle index" measuring jargon, ambiguity, decision deficit, and missing accountability. Use when the user asks to diagnose a meeting, score meeting effectiveness, inspect buzzwords or vague language, roast meeting minutes, or invokes meeting-scouter with pasted text or one or more local files.
---

# Meeting Scouter

Analyze the meeting content, then use the bundled deterministic engine to score and render the result.

## Workflow

1. Resolve the input without asking the user to paste content the agent can read.
   - Treat existing file paths as sources and read them.
   - Read multiple paths in the supplied order and combine them.
   - For a directory, inspect only that directory and select likely meeting-note files.
   - Treat non-path text as the meeting content itself.
   - Use native document tools for PDF, DOCX, or other supported formats, then convert the extracted content to plain UTF-8 text for scoring.
   - Never modify the source files.
2. Read `references/analysis-contract.md` and produce the required analysis JSON.
3. Preserve exact source wording for every discovered phrase. Do not invent phrases that do not occur in the meeting.
4. Keep the roast playful and directed at the meeting, never at a named participant or protected characteristic.
5. Write the normalized meeting text and analysis JSON to temporary files.
6. Resolve this skill directory and run:

```bash
python3 <skill-dir>/scripts/meeting_scouter.py analyze \
  --text-file <temporary-meeting-text> \
  --analysis-file <temporary-analysis-json>
```

7. Return the generated TUI block verbatim. Add no long explanation unless the user asks how the score was calculated.
8. Delete temporary files when practical. The engine stores only discovered phrases, aggregate counts, and a document fingerprint under `~/.meeting-scouter/`; it does not store the transcript.

## Analysis rules

- Count only explicit decisions as decisions. A proposal, preference, or "we should consider" statement is not a decision.
- Count a concrete next step as an action even when its owner or deadline is absent.
- Use `null` for an unknown owner or deadline.
- Discover phrases by meaning, not only by dictionary match. Look for missing criteria, owners, deadlines, completion conditions, responsibility, or commitment.
- Exclude ordinary hedging that is appropriate to genuine uncertainty.
- Give discovered phrases a confidence below `0.75` when the interpretation is weak; the engine ignores those for scoring and learning.
- Do not manually calculate the score. The bundled script is the source of truth.

## Candidate dictionary

When the user asks to inspect learned phrases, run:

```bash
python3 <skill-dir>/scripts/meeting_scouter.py candidates
```

Read `references/scoring.md` only when explaining ranks, score components, or persistence behavior.
