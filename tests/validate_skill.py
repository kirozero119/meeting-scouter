from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "meeting-scouter"
SKILL_MD = SKILL / "SKILL.md"


def fail(message: str) -> None:
    raise SystemExit(f"validation failed: {message}")


text = SKILL_MD.read_text(encoding="utf-8")
match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
if not match:
    fail("SKILL.md must begin with YAML frontmatter")
frontmatter = match.group(1)
name_match = re.search(r"^name:\s*(.+)$", frontmatter, re.MULTILINE)
description_match = re.search(r"^description:\s*(.+)$", frontmatter, re.MULTILINE)
if not name_match or not description_match:
    fail("frontmatter requires name and description")
name = name_match.group(1).strip()
description = description_match.group(1).strip()
if name != SKILL.name:
    fail("skill directory and name must match")
if not re.fullmatch(r"[a-z0-9-]{1,64}", name):
    fail("name must contain only lowercase letters, digits, and hyphens")
if not description or len(description) > 1024:
    fail("description must contain 1-1024 characters")
if len(text.splitlines()) > 500:
    fail("SKILL.md must stay under 500 lines")

required = [
    SKILL / "agents" / "openai.yaml",
    SKILL / "scripts" / "meeting_scouter.py",
    SKILL / "references" / "analysis-contract.md",
    SKILL / "references" / "scoring.md",
    SKILL / "data" / "buzzwords.json",
    SKILL / "data" / "vague-phrases.json",
    SKILL / "LICENSE.txt",
]
for path in required:
    if not path.exists():
        fail(f"missing required file: {path.relative_to(ROOT)}")

for dictionary in (SKILL / "data" / "buzzwords.json", SKILL / "data" / "vague-phrases.json"):
    items = json.loads(dictionary.read_text(encoding="utf-8"))
    if not isinstance(items, list) or not items:
        fail(f"dictionary must be a non-empty list: {dictionary}")
    for item in items:
        if not isinstance(item, dict) or not item.get("term") or not item.get("variants"):
            fail(f"invalid dictionary entry in {dictionary}")

openai_yaml = (SKILL / "agents" / "openai.yaml").read_text(encoding="utf-8")
for key in ("display_name:", "short_description:", "default_prompt:"):
    if key not in openai_yaml:
        fail(f"agents/openai.yaml missing {key}")
if "$meeting-scouter" not in openai_yaml:
    fail("default_prompt must mention $meeting-scouter")

print("skill validation passed")
