# Analysis contract

Create one UTF-8 JSON object with this shape:

```json
{
  "source_label": "docs/weekly-meeting.md",
  "meeting_minutes": 60,
  "decisions": [
    {"text": "料金プランを月額980円にする"}
  ],
  "actions": [
    {
      "task": "新料金案のLPを修正する",
      "owner": null,
      "deadline": "次回会議まで"
    }
  ],
  "discovered_phrases": [
    {
      "phrase": "温度感を見ながら",
      "category": "vague",
      "reason": "判断条件が示されていない",
      "confidence": 0.92,
      "occurrences": 1
    }
  ],
  "roast": "価格は決まりましたが、誰が作るかはまだ採用選考中です。"
}
```

## Field rules

- `source_label`: Short label shown in the TUI. Prefer a relative path or `貼り付けられた議事録`.
- `meeting_minutes`: Integer when explicitly known; otherwise `null`.
- `decisions`: Explicitly settled outcomes only. Each item must contain `text`.
- `actions`: Concrete next steps. `owner` and `deadline` are strings or `null`.
- `discovered_phrases`: Exact quotes that are not merely obvious fixed-dictionary matches.
- `roast`: One concise Japanese sentence. Keep it funny, non-abusive, and about the meeting structure.

## Discovery categories

Use exactly one of these categories:

- `buzzword`: Corporate jargon or imported terminology used without adding precision.
- `vague`: Missing criteria, scope, timing, or completion conditions.
- `responsibility_blur`: Responsibility is diffused, passive, collective, or deliberately unclear.
- `decision_avoidance`: A phrase postpones or avoids a decision while sounding productive.
- `meeting_meta`: Language about aligning, discussing, organizing, or meeting again instead of advancing the work.

## Confidence guidance

- `0.90–1.00`: Clearly vague or responsibility-blurring in context.
- `0.75–0.89`: Reasonably clear but context-dependent.
- Below `0.75`: Weak or debatable; retained in JSON for transparency but ignored by the engine.

## Good discoveries

- `温度感を見ながら` — no decision criterion.
- `各所と連携して進める` — ownership is unclear.
- `次回改めて議論する` — decision is deferred.
- `一度整理した上で認識を合わせる` — activity is described without a concrete outcome.

## Do not discover

- Exact fixed terms such as `アジェンダ`, `アライン`, or `一旦持ち帰ります`; the engine already counts them.
- Names, teams, products, or ordinary domain terminology.
- Polite language that does not reduce clarity.
- A phrase not quoted verbatim from the source.
