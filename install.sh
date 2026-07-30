#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$ROOT_DIR/meeting-scouter"
FORCE=0
TARGETS=()

usage() {
  cat <<'EOF'
Usage: ./install.sh [--all|--claude|--codex|--codex-legacy] [--force]

  --all           Install for Claude Code and Codex (recommended paths)
  --claude        Install to ~/.claude/skills/meeting-scouter
  --codex         Install to ~/.agents/skills/meeting-scouter
  --codex-legacy  Install to ~/.codex/skills/meeting-scouter
  --force         Replace an existing installation
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --all) TARGETS+=("$HOME/.claude/skills" "$HOME/.agents/skills") ;;
    --claude) TARGETS+=("$HOME/.claude/skills") ;;
    --codex) TARGETS+=("$HOME/.agents/skills") ;;
    --codex-legacy) TARGETS+=("$HOME/.codex/skills") ;;
    --force) FORCE=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

if [[ ${#TARGETS[@]} -eq 0 ]]; then
  TARGETS=("$HOME/.claude/skills" "$HOME/.agents/skills")
fi

for base in "${TARGETS[@]}"; do
  destination="$base/meeting-scouter"
  mkdir -p "$base"
  if [[ -e "$destination" ]]; then
    if [[ "$FORCE" -ne 1 ]]; then
      echo "Already exists: $destination (use --force to replace)" >&2
      exit 1
    fi
    rm -rf "$destination"
  fi
  cp -R "$SOURCE_DIR" "$destination"
  echo "Installed: $destination"
done

echo "Restart Codex if the skill picker does not refresh. Claude Code normally hot-reloads skills."
