# Setting it up yourself

This fork runs speak_when_done as **one shared warm daemon** with a **per-worktree
persona system**. This guide sets that up from scratch on your own machine.

If you just want a voice to say "build's done" and nothing else, you don't need any of
this — use the upstream one-liner in the [README](../README.md) and stop there. This
guide is for the full setup: personas, the control UI, and a resident daemon.

**Platform:** macOS only right now. Playback uses `afplay` and the mic-suppression check
uses CoreAudio.

---

## 1. Prerequisites

| Thing | Why | Install |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | runs the package and pocket-tts | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| ffmpeg | persona speed-stretch | `brew install ffmpeg` |
| pocket-tts (via uvx) | the TTS model | no install; `uvx pocket-tts` fetches it |

Confirm TTS works at all before going further:

```bash
uvx pocket-tts generate --text "hello world" --quiet
```

If that doesn't make sound, nothing below will. Fix it first.

---

## 2. Install

```bash
git clone https://github.com/zionts/speak_when_done ~/.claude/speak_when_done
cd ~/.claude/speak_when_done
./scripts/install.sh
```

`install.sh` syncs deps into `.venv/`, creates `~/.claude/voices/`, validates the persona
files, and prints the MCP registration line. It does **not** register the MCP server or
load the daemon for you — those are the next two steps.

**The install path matters.** `speak_when_done/__init__.py` resolves personas from
`~/.claude/speak_when_done/personas` and voices from `~/.claude/voices`. Both are
hardcoded — they're the `_PERSONA_DIR` and `_VOICES_DIR` constants near the top of the
file, and there is no env var for either.

Cloning to the path above is the path of least resistance. If you clone somewhere else,
edit those two constants to match, or nothing will find your personas.

---

## 3. Run the daemon

The daemon holds the TTS model and every persona voice resident, so a notification doesn't
pay a cold model load. It's a LaunchAgent.

```bash
sed "s|__HOME__|$HOME|g" scripts/com.speak-when-done.plist.template \
  > ~/Library/LaunchAgents/com.speak-when-done.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.speak-when-done.plist
```

Verify it came up:

```bash
launchctl print gui/$(id -u)/com.speak-when-done | grep -E 'state|pid'
curl -s http://127.0.0.1:9877/status
tail -f ~/.claude/speak_when_done/logs/daemon.log
```

Day-to-day operation:

```bash
launchctl kickstart -k gui/$(id -u)/com.speak-when-done   # restart after code edits
```

Restart after editing `daemon.py` or `__init__.py`. Persona `.md` files are re-read on
every call — edit those freely, no restart.

---

## 4. Register the MCP server with Claude Code

The daemon speaks streamable-HTTP MCP, so every Claude session points at one URL instead
of spawning its own server process:

```bash
claude mcp add speak_when_done --scope user --transport http http://127.0.0.1:9876/mcp
```

`--scope user` registers it for all your projects. Use `--scope project` instead if you
only want it in the current one.

Then **fully quit and reopen Claude Code** — MCP config is read at session start, never
mid-session, so an open session won't see it no matter how long you wait.

Verify inside a session by asking Claude to call `list_voices` with your current directory.
You want `drift: []`; a non-empty `drift` names exactly what's out of sync.

### Optional — many Claude profiles

**Skip this unless you use tooling that creates a separate Claude profile per git
worktree.** If the command above worked, you're done; go to step 5.

Some worktree managers mint a fresh Claude profile per worktree, and those
`.claude.json` files are created with no `mcpServers` — so those sessions can't find the
daemon. `scripts/stamp_mcp_profiles.sh` additively stamps the entry into every profile it
finds (`~/.claude.json`, `~/.claude-profiles/*`, `~/tbd/profiles/*`). It's idempotent and
safe to re-run.

The script's profile globs are specific to the author's setup — read it before trusting it.

To keep newly-minted profiles stamped automatically, install the companion agent:

```bash
sed "s|__HOME__|$HOME|g" scripts/com.speak-when-done-mcp-stamper.plist.template \
  > ~/Library/LaunchAgents/com.speak-when-done-mcp-stamper.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.speak-when-done-mcp-stamper.plist
```

---

## 5. Tell Claude to actually use it

Registering the server gives Claude the tool, but it won't reach for it on its own. You
have to ask.

`~/.claude/CLAUDE.md` is Claude Code's standing-instructions file — it's loaded into every
session, in every project. Create it if it doesn't exist, and add:

```markdown
# speak_when_done

After finishing my request and presenting your final summary, call
`speak_when_done.speak`. One call, at the very end — never mid-task.

Before your first `speak` call in a session, call `list_voices` and read
`active_persona` + `active_style`. The style contains the full register. Compose in
that register. Don't pass the `voice` arg — the default is already correct.

Always pass `cwd` (your current working directory) to both `list_voices` and `speak`.
The shared daemon can't infer your worktree from the process tree; `cwd` is how it
picks the right persona.
```

The `cwd` argument is load-bearing: **without it, every project shares one persona** and
the whole per-project-character feature quietly does nothing. One daemon serves every
session, so `cwd` is the only thing telling your projects apart.

If you don't use git worktrees, none of this breaks — `cwd` is just your project
directory, and each project you work in gets its own character.

---

## 6. Voices

**This repo ships no voice files.** Fresh installs fall back to pocket-tts's built-in
`alba` for every persona — the registers still work, so personas read in character, just
not in their own timbre. (A *voice file*, or tensor, is a `.safetensors` file encoding how
one person sounds; *timbre* is that sound. The register is the writing; the tensor is the
voice.)

To get the timbre, train your own clones: **[docs/voice-training.md](voice-training.md)**.

Why no tensors ship: the author's are clones of identifiable real people. Running that on
your own machine is one thing; publishing the tensors so anyone can synthesize a real
person saying arbitrary words is another. The harness is here so you can clone voices you
have the standing to clone.

---

## 7. The control UI

The daemon serves a control page at **<http://127.0.0.1:9877/>** (separate port from the
MCP endpoint; override with `SPEAK_WHEN_DONE_CONTROL_PORT`).

One primary button mutes on demand or resumes; three chips mute for 15 / 30 / 60 minutes.
Live status shows On · Quiet (mic in use) · Muted, plus queue depth. Below that is a
**Recent** feed of the last notifications — text, relative time, outcome
(spoken · muted · mic · stale), and persona where present.

State is file-backed (`state/pause.json`), so the worker's playback-time check and the UI
always agree. Timed pauses auto-resume with no timer — expiry is evaluated on read.

Scriptable:

```bash
curl -sX POST 'http://127.0.0.1:9877/pause?minutes=30'   # quiet 30 min
curl -sX POST  http://127.0.0.1:9877/resume              # resume now
curl -s        http://127.0.0.1:9877/status              # JSON status + recent history
curl -s        http://127.0.0.1:9877/history             # just the recent-speaks feed
```

The daemon also stays silent on its own while a microphone is capturing, so it won't talk
over your meetings.

---

## 8. Configuration

Env vars, set in the LaunchAgent's `EnvironmentVariables` dict:

| Var | Default | Effect |
|---|---|---|
| `SPEAK_WHEN_DONE_HOST` | `127.0.0.1` | MCP bind host |
| `SPEAK_WHEN_DONE_PORT` | `9876` | MCP bind port |
| `SPEAK_WHEN_DONE_CONTROL_HOST` | `127.0.0.1` | control UI bind host |
| `SPEAK_WHEN_DONE_CONTROL_PORT` | `9877` | control UI bind port |
| `SPEAK_WHEN_DONE_LANGUAGE` | `english_2026-04` | pocket-tts model version. A voice tensor is tied to the model it was exported from |
| `SPEAK_WHEN_DONE_VOICE` | — | force a specific voice file or built-in name. If the path matches a persona's tensor, that persona locks in too; otherwise the register still comes from the worktree hash |
| `SPEAK_WHEN_DONE_QUEUE_MAX` | `20` | max queued messages |
| `SPEAK_WHEN_DONE_STALE_AFTER_S` | `600` | drop messages older than this at dequeue |
| `SPEAK_WHEN_DONE_KEEP_WARM_IDLE_S` | `600` | idle keep-warm interval, keeps model weights paged in |
| `SPEAK_WHEN_DONE_SYNTH_WATCHDOG_S` | `45` | WARN when one synthesis exceeds this |
| `SPEAK_WHEN_DONE_NO_CWD_DISCOVERY` | — | disable caller-cwd discovery |

Keep-warm is not a micro-optimization. A paged-out model once made a single synthesis take
12.5 minutes, timing out every queued client.

---

## Troubleshooting

**Daemon won't stay up.** `tail ~/.claude/speak_when_done/logs/daemon.log`. Usually the
`.venv` path in the plist is wrong (did `install.sh` run?) or the port is taken:
`lsof -i :9876`.

**Claude can't see the tool.** `claude mcp list`, then `claude mcp get speak_when_done`.
If it's registered and still missing, you didn't restart the session — config is read at
start.

**No audio, but the daemon logs a successful speak.** Check the control UI at
<http://127.0.0.1:9877/> — you may be muted, or a mic is live and suppression kicked in.
The Recent feed's outcome column tells you which.

**ffmpeg not found in the daemon but fine in your shell.** launchd's default PATH omits
Homebrew. The plist template sets PATH explicitly; if you hand-rolled the plist, add
`/opt/homebrew/bin`.

**Everything speaks in one persona.** Your caller isn't passing `cwd`. See step 5.

**`list_voices` reports drift.** Read the strings — they name the mismatch. Usually a
`PERSONA_VOICES` entry with no matching `personas/<name>.md`, or a tensor path that
doesn't exist on disk.
