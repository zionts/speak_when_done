# speak_when_done

Your AI assistant speaks to you when a long task finishes.

You kick off a build, a test suite, a deployment, and go do something else. When it's done,
you hear about it:

> "Your build completed successfully with no errors."

> "The test suite finished. 47 passed, 2 failed."

Works as a CLI tool, a Python library, or an MCP server for AI assistants.

---

## This fork

Upstream is [Marviel/speak_when_done](https://github.com/Marviel/speak_when_done). This
fork adds two things.

**A shared warm daemon.** One resident process instead of a server per session. With dozens
of concurrent Claude Code sessions, the per-session stdio design piled up ~2 GB of idle
interpreters and reloaded the TTS model cold on every notification. The daemon collapses
that into a single process with the model and every voice resident, serving MCP over HTTP.
It also gets a pause/mute control UI, a mic check so it won't talk over your meetings, and
an async queue so audio never overlaps.

**Personas.** Instead of one flat TTS voice, each worktree deterministically gets its own
character — a cloned voice plus a written *register* telling the model how that character
talks. Your infra repo sounds like a nature documentary; your side project sounds like a
noir detective. It makes a notification something you look forward to instead of a beep.

**Platform:** macOS only (`afplay` playback, CoreAudio mic detection).

### Set it up

**[docs/setup.md](docs/setup.md)** — the full walkthrough: install, daemon, MCP
registration, control UI, config, troubleshooting.

The short version:

```bash
git clone https://github.com/zionts/speak_when_done ~/.claude/speak_when_done
cd ~/.claude/speak_when_done && ./scripts/install.sh
```

…then follow the two steps it prints (load the LaunchAgent, register the MCP server).

### Voices

**No voice files ship with this repo**, and there's no download link. The author's are
clones of identifiable real people — running that locally is one thing, publishing tensors
that let anyone synthesize a real person saying arbitrary words is another.

So the repo ships the **harness** instead. A fresh install works immediately: every persona
falls back to pocket-tts's built-in `alba` voice — right register, wrong timbre. To get the
timbre, clone your own:

**[docs/voice-training.md](docs/voice-training.md)** — the full recipe (source → isolate →
filter → export → audition), `tools/filter_speaker.py`, and the accumulated lessons on
which voices clone well and which are hopeless no matter how good your source is.

### Personas

**[personas/README.md](personas/README.md)** — how the register system works, the
three-legs contract for adding one, and how to make the roster yours. The ten shipped
registers are one person's taste in voices; picking your own is the interesting half.

---

## Documentation

| Doc | What's in it |
|---|---|
| [docs/setup.md](docs/setup.md) | Full setup, daemon operation, config, troubleshooting |
| [docs/voice-training.md](docs/voice-training.md) | Cloning your own voices — the harness and the lessons |
| [personas/README.md](personas/README.md) | The persona / register system |
| [docs/architecture.md](docs/architecture.md) | How the daemon, queue, and persona resolution fit together |

---

## Prerequisites

- macOS
- [uv](https://docs.astral.sh/uv/)
- ffmpeg (`brew install ffmpeg`) — persona speed-stretch

Confirm TTS works before anything else:

```bash
uvx pocket-tts generate --text "hello world" --quiet
```

---

## Without the daemon

The upstream paths still work if you want the simple thing.

### CLI

```bash
uvx --from git+https://github.com/Marviel/speak_when_done speak_when_done --text "Hello world"
```

| Flag | Long | Description |
|------|------|-------------|
| `-t` | `--text` | Text to speak (required) |
| `-v` | `--voice` | Voice to use (default: alba) |
| `-q` | `--quiet` | Suppress TTS output |

### Python library

```bash
uv add git+https://github.com/Marviel/speak_when_done
```

```python
from speak_when_done import speak

result = speak("Hello world")
result = speak("Hello", voice="alba", quiet=True)
```

### MCP server (stdio, no daemon)

Claude Code:

```bash
claude mcp add speak_when_done -s user -- uvx --from git+https://github.com/Marviel/speak_when_done python -m speak_when_done.server
```

Cursor — add to `~/.cursor/mcp.json` (global) or `.cursor/mcp.json` (project), then reload
the window:

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

---

## Telling your assistant to use it

Once the MCP server is registered, your assistant has a `speak` tool:

> "Run the full test suite and tell me out loud when it's done"

> "Deploy to staging and speak to me when it completes"

Add to your `CLAUDE.md` or custom instructions:

```
When using the speak_when_done MCP:
- Only use the speak tool after completing long-running tasks (builds, tests,
  deployments, extensive searches)
- Keep spoken messages brief and informative
- Do not use speak for routine responses or simple questions
```

Using the persona system? See [docs/setup.md § 5](docs/setup.md) — the instructions differ,
and passing `cwd` is required.

---

## Troubleshooting

**"Command not found":** make sure `uvx` and `pocket-tts` are on your PATH.

**No audio:** check macOS isn't muted and `afplay` works —
`afplay /System/Library/Sounds/Glass.aiff`.

**MCP not connecting in Claude Code:** `claude mcp list`, then
`claude mcp get speak_when_done`. If it's registered and still missing, restart the
session — MCP config is read at session start.

**MCP not connecting in Cursor:** Settings → Features → MCP to confirm MCP is enabled,
then verify your JSON is valid.

Daemon-specific problems: [docs/setup.md § Troubleshooting](docs/setup.md).
