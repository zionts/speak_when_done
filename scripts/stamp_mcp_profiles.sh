#!/bin/bash
# Stamp the speak_when_done HTTP-MCP registration into every Claude profile's
# .claude.json so all sessions (zadam, home, and each TBD per-worktree profile)
# can reach the shared daemon at 127.0.0.1:9876.
#
# Why this exists: TBD mints a fresh profile dir per worktree, and Claude Code
# creates each profile's .claude.json from scratch — nothing seeds mcpServers.
# The daemon was only ever registered in ~/.claude-profiles/zadam/.claude.json,
# so every TBD session failed to find the server (2026-07-10 diagnosis).
# Runs periodically via LaunchAgent com.speak-when-done-mcp-stamper to catch
# newly-minted profiles; safe to run any time (idempotent, additive-only).
#
# A live session may overwrite a freshly-stamped file with its in-memory copy;
# the next periodic run re-heals it, and the session after that picks it up.

set -u

MCP_JSON='{"type":"http","url":"http://127.0.0.1:9876/mcp"}'
LOG="$HOME/.claude/speak_when_done/logs/stamper.log"
mkdir -p "$(dirname "$LOG")"

stamped=0
created=0
skipped=0
failed=0

stamp_file() {
  local f="$1"
  if [ ! -f "$f" ]; then
    # Profile dir exists but Claude Code hasn't minted .claude.json yet —
    # pre-seed it; Claude Code merges rather than replaces on first run.
    if printf '{"mcpServers":{"speak_when_done":%s}}\n' "$MCP_JSON" > "$f" 2>/dev/null; then
      created=$((created+1))
    else
      failed=$((failed+1))
    fi
    return
  fi
  if jq -e '.mcpServers.speak_when_done.url == "http://127.0.0.1:9876/mcp"' "$f" >/dev/null 2>&1; then
    skipped=$((skipped+1))
    return
  fi
  local tmp="${f}.mcp-stamp.$$"
  if jq --argjson mcp "$MCP_JSON" '.mcpServers = ((.mcpServers // {}) + {speak_when_done: $mcp})' "$f" > "$tmp" 2>/dev/null \
     && jq -e . "$tmp" >/dev/null 2>&1; then
    mv "$tmp" "$f"
    stamped=$((stamped+1))
  else
    rm -f "$tmp"
    failed=$((failed+1))
  fi
}

# Home config (plain `claude` runs) + legacy named profiles
stamp_file "$HOME/.claude.json"
for f in "$HOME"/.claude-profiles/*/.claude.json; do
  [ -e "$(dirname "$f")" ] && stamp_file "$f"
done

# TBD per-worktree profiles
for d in "$HOME"/tbd/profiles/*/claude; do
  [ -d "$d" ] && stamp_file "$d/.claude.json"
done

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) stamped=$stamped created=$created ok=$skipped failed=$failed" >> "$LOG"
[ "$failed" -eq 0 ]
