#!/usr/bin/env bash
# install.sh — set up the speak_when_done warm daemon + persona system.
#
# What this does:
#   1. Preflight (uv, ffmpeg, install path)
#   2. Sync Python deps into .venv/ via uv
#   3. Create ~/.claude/voices/ and report which persona voices you have
#   4. Validate the persona files (drift check)
#   5. Print the next two steps you must run yourself
#
# What this does NOT do:
#   - Install the LaunchAgent (step 3 of docs/setup.md)
#   - Register the MCP server with Claude Code (step 4 of docs/setup.md)
#   - Ship or download voice tensors — this repo has none. Personas fall back to the
#     built-in pocket-tts voice "alba" until you train your own.
#     See docs/voice-training.md.

set -euo pipefail

PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PERSONA_DIR="${PACKAGE_DIR}/personas"
VOICES_DIR="${HOME}/.claude/voices"
EXPECTED_DIR="${HOME}/.claude/speak_when_done"

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
ok() { printf '\033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '\033[33m⚠\033[0m %s\n' "$*" >&2; }
die() {
    printf '\033[31m✗\033[0m %s\n' "$*" >&2
    exit 1
}

# --- 1. preflight ---------------------------------------------------------
bold "1/4  Preflight"
[ "$(uname)" = "Darwin" ] || die "macOS only — playback uses afplay, mic suppression uses CoreAudio."
command -v uv > /dev/null || die "uv not on PATH. See https://docs.astral.sh/uv/"
command -v ffmpeg > /dev/null || warn "ffmpeg not on PATH — persona speed-stretch will not work. brew install ffmpeg"
[ -d "$PERSONA_DIR" ] || die "persona dir missing at $PERSONA_DIR"

# __init__.py hardcodes ~/.claude/speak_when_done/personas and ~/.claude/voices.
# A clone elsewhere works only if you edit those constants, so say so loudly.
if [ "$PACKAGE_DIR" != "$EXPECTED_DIR" ]; then
    warn "Installed at $PACKAGE_DIR, but __init__.py resolves personas from $EXPECTED_DIR/personas."
    warn "Either clone to $EXPECTED_DIR, or edit _PERSONA_DIR in speak_when_done/__init__.py."
fi
ok "macOS, uv, and personas/ present"

# --- 2. python deps -------------------------------------------------------
bold "2/4  Sync Python deps"
cd "$PACKAGE_DIR"
uv sync --quiet
ok "speak_when_done installed into $PACKAGE_DIR/.venv"

# --- 3. voices ------------------------------------------------------------
bold "3/4  Voices"
mkdir -p "$VOICES_DIR"
found=$(find "$VOICES_DIR" -maxdepth 1 -name '*.safetensors' 2> /dev/null | wc -l | tr -d ' ')
if [ "$found" -eq 0 ]; then
    warn "No voice tensors in $VOICES_DIR — every persona falls back to built-in 'alba'."
    warn "Registers still work; the timbre won't. To clone your own: docs/voice-training.md"
else
    ok "$found voice tensor(s) in $VOICES_DIR"
fi

# --- 4. validate ----------------------------------------------------------
bold "4/4  Validate personas"
uv run --quiet python -m speak_when_done.cli --validate-personas

cat << EOF

$(bold "Two steps left — run these yourself (docs/setup.md):")

  $(bold "1. Start the daemon")

    sed "s|__HOME__|\$HOME|g" scripts/com.speak-when-done.plist.template \\
      > ~/Library/LaunchAgents/com.speak-when-done.plist
    launchctl bootstrap gui/\$(id -u) ~/Library/LaunchAgents/com.speak-when-done.plist

  $(bold "2. Register the MCP server")

    claude mcp add speak_when_done --scope user --transport http http://127.0.0.1:9876/mcp

  Then restart any open Claude Code session — MCP config is read at session start.

$(bold "Verify:") curl -s http://127.0.0.1:9877/status
$(bold "Verify in a session:") call \`list_voices(cwd="...")\` — \`drift\` should be \`[]\`.
$(bold "Control UI:") http://127.0.0.1:9877/
EOF
