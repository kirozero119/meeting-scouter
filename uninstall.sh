#!/usr/bin/env bash
set -euo pipefail

TARGETS=()
usage() {
  cat <<'EOF'
Usage: ./uninstall.sh [--all|--claude|--codex|--codex-legacy]
EOF
}
while [[ $# -gt 0 ]]; do
  case "$1" in
    --all) TARGETS+=("$HOME/.claude/skills/meeting-scouter" "$HOME/.agents/skills/meeting-scouter") ;;
    --claude) TARGETS+=("$HOME/.claude/skills/meeting-scouter") ;;
    --codex) TARGETS+=("$HOME/.agents/skills/meeting-scouter") ;;
    --codex-legacy) TARGETS+=("$HOME/.codex/skills/meeting-scouter") ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done
if [[ ${#TARGETS[@]} -eq 0 ]]; then
  TARGETS=("$HOME/.claude/skills/meeting-scouter" "$HOME/.agents/skills/meeting-scouter")
fi
for destination in "${TARGETS[@]}"; do
  if [[ -d "$destination" ]]; then
    rm -rf "$destination"
    echo "Removed: $destination"
  else
    echo "Not installed: $destination"
  fi
done
