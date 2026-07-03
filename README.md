# speak_when_done

Text-to-speech with automatic temp file handling. Speaks text aloud and cleans up after itself.

Works as a CLI tool, Python library, or MCP server for AI assistants.

## Local deployment: shared warm daemon (this machine)

> This fork runs as **one shared HTTP-MCP daemon**, not a per-session stdio server.
> Background: with dozens of concurrent Claude Code sessions, the old design spawned
> a `uv run` wrapper + a python stdio server *per session* (and reloaded the TTS model
> cold on every notification), piling up ~2 GB of idle interpreters. The daemon collapses
> all of that into a single process with the model + all persona voices resident.

**Architecture**
- `speak_when_done/daemon.py` — long-running process (LaunchAgent `com.speak-when-done`,
  bound to `127.0.0.1:9876`). Loads the Pocket TTS model once, preloads every persona's
  voice state at boot, and serves the `speak` / `list_voices` tools over **streamable-HTTP MCP**
  at `http://127.0.0.1:9876/mcp`. The default language (`english_2026-04`) is loaded eagerly;
  other languages (e.g. attenborough's `english_2026-01`) load lazily on first use.
- **Async FIFO queue**: `speak` validates, enqueues, and returns immediately
  (`queued: true`, `position: N`). One background worker synthesizes and plays
  strictly in arrival order, so audio never overlaps and MCP requests never block
  on the TTS model (a paged-out model once made a single synthesis take 12.5 min,
  timing out every queued client). Messages older than 10 min are dropped at
  dequeue; an idle keep-warm generation (every 10 min, discarded, never played)
  keeps the model weights paged in; a watchdog WARNs when one synthesis exceeds
  45 s. Tunables (env or constants in `daemon.py`): `SPEAK_WHEN_DONE_QUEUE_MAX`
  (20), `_STALE_AFTER_S` (600), `_KEEP_WARM_IDLE_S` (600), `_SYNTH_WATCHDOG_S` (45).
- Every Claude session registers `speak_when_done` as `{"type":"http","url":".../mcp"}`
  (in `~/.claude-profiles/zadam/.claude.json`) — **zero per-session processes**.
- Persona is per-worktree: callers pass `cwd`, and the deterministic worktree-hash in
  `__init__.py` maps it to a persona + voice. The daemon swaps only the synthesis backend
  via the `_GENERATOR` hook in `__init__.py`; speed-stretch, the cross-session playback lock,
  mic-suppression and drift logging are reused unchanged. When `_GENERATOR` is unset (e.g.
  the legacy `server.py` stdio entrypoint), `speak()` falls back to spawning `uvx pocket-tts`.

**Operate**
```bash
launchctl print gui/$(id -u)/com.speak-when-done | grep -E 'state|pid'   # status
launchctl kickstart -k gui/$(id -u)/com.speak-when-done                  # restart (e.g. after code edits)
tail -f ~/.claude/speak_when_done/logs/daemon.log                        # logs
```
After editing `daemon.py` or `__init__.py`, `kickstart -k` to reload. Persona `.md` files are
re-read on every call and need no restart. The LaunchAgent is `KeepAlive` (auto-restarts on crash).

## What it does

```bash
uvx --from git+https://github.com/Marviel/speak_when_done speak_when_done --text "Your build is complete"
```

That's it. It generates speech, plays it, and cleans up the temp file automatically.

### As an MCP server

You kick off a long task (build, test suite, deployment) and go do something else. When it's done, your AI speaks to you:

> "Your build completed successfully with no errors."

> "The test suite finished. 47 passed, 2 failed."

> "I found the bug you were looking for in the auth module."

## Prerequisites

- macOS (uses `afplay` for audio playback)
- [uv](https://docs.astral.sh/uv/) package manager

Test that pocket-tts works:
```bash
uvx pocket-tts generate --text "hello world" --quiet
```

## Installation

### CLI (via uvx)

No installation needed! Just run:
```bash
uvx --from git+https://github.com/Marviel/speak_when_done speak_when_done --text "Hello world"
```

Options:
```bash
uvx --from git+https://github.com/Marviel/speak_when_done speak_when_done -t "Hello" -v alba -q
```

| Flag | Long | Description |
|------|------|-------------|
| `-t` | `--text` | Text to speak (required) |
| `-v` | `--voice` | Voice to use (default: alba) |
| `-q` | `--quiet` | Suppress TTS output |

### Python library

```bash
pip install git+https://github.com/Marviel/speak_when_done
# or
uv add git+https://github.com/Marviel/speak_when_done
```

```python
from speak_when_done import speak

result = speak("Hello world")
result = speak("Hello", voice="alba", quiet=True)
```

### MCP Server for Claude Code

Add globally (available in all projects):
```bash
claude mcp add speak_when_done -s user -- uvx --from git+https://github.com/Marviel/speak_when_done python -m speak_when_done.server
```

Or project-specific:
```bash
claude mcp add speak_when_done -- uvx --from git+https://github.com/Marviel/speak_when_done python -m speak_when_done.server
```

### MCP Server for Cursor

Add to `~/.cursor/mcp.json` (global) or `.cursor/mcp.json` (project):

```json
{
  "mcpServers": {
    "speak_when_done": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/Marviel/speak_when_done",
        "python",
        "-m",
        "speak_when_done.server"
      ]
    }
  }
}
```

Then restart Cursor or reload the window.

## Usage with AI assistants

Once installed as an MCP server, your AI has access to a `speak` tool. Ask it to notify you when something finishes:

> "Run the full test suite and tell me out loud when it's done"

> "Deploy to staging and speak to me when it completes"

> "Search for all usages of the deprecated API and let me know what you find"

## Recommended Instructions

Add to your custom instructions or CLAUDE.md:

```
When using the speak_when_done MCP:
- Only use the speak tool after completing long-running tasks (builds, tests, deployments, extensive searches)
- Keep spoken messages brief and informative
- Do not use speak for routine responses or simple questions
```

## Voices

Pocket TTS supports multiple voices. The default "alba" is a natural-sounding voice. You can also provide a path to an audio file for voice cloning.

## Troubleshooting

**"Command not found" error:**
Make sure `uvx` and `pocket-tts` are available in your PATH.

**No audio playback:**
Ensure your macOS audio is not muted and `afplay` is working:
```bash
afplay /System/Library/Sounds/Glass.aiff
```

**MCP not connecting in Claude Code:**
```bash
claude mcp list
claude mcp get speak_when_done
```

**MCP not connecting in Cursor:**
Check Settings → Features → MCP to ensure MCP is enabled, then verify your JSON config is valid.
