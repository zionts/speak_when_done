# Architecture

How the fork's daemon, queue, and persona resolution fit together. Read
[setup.md](setup.md) first if you just want it running.

## Why a daemon

Upstream spawns a `uv run` wrapper plus a python stdio server **per session**, and reloads
the TTS model cold on every notification. With dozens of concurrent Claude Code sessions
that piled up ~2 GB of idle interpreters and made every notification pay a model load.

`speak_when_done/daemon.py` is one long-running process (LaunchAgent `com.speak-when-done`,
bound to `127.0.0.1:9876`). It loads the model once, preloads every persona's voice state
at boot, and serves the `speak` / `list_voices` tools over **streamable-HTTP MCP** at
`http://127.0.0.1:9876/mcp`. Every session registers `{"type":"http","url":".../mcp"}` —
zero per-session processes.

The default language (`english_2026-04`) loads eagerly; others (e.g. attenborough's
`english_2026-01`) load lazily on first use.

## The async queue

`speak` validates, enqueues, and returns immediately (`queued: true`, `position: N`). One
background worker synthesizes and plays strictly in arrival order, so audio never overlaps
and MCP requests never block on the model.

That last part is not theoretical: a paged-out model once made a single synthesis take
12.5 minutes, timing out every queued client. Hence:

- Messages older than 10 min are dropped at dequeue.
- An idle keep-warm generation (every 10 min, discarded, never played) keeps the model
  weights paged in.
- A watchdog WARNs when one synthesis exceeds 45 s.

Tunables (env, or constants in `daemon.py`): `SPEAK_WHEN_DONE_QUEUE_MAX` (20),
`_STALE_AFTER_S` (600), `_KEEP_WARM_IDLE_S` (600), `_SYNTH_WATCHDOG_S` (45).

## Persona resolution

Persona is **per-worktree**: callers pass `cwd`, and the deterministic worktree-hash in
`__init__.py` maps it to a persona + voice. The daemon swaps only the synthesis backend via
the `_GENERATOR` hook in `__init__.py` — speed-stretch, the cross-session playback lock,
mic-suppression, and drift logging are reused unchanged.

When `_GENERATOR` is unset (e.g. the legacy `server.py` stdio entrypoint), `speak()` falls
back to spawning `uvx pocket-tts`.

See [personas/README.md](../personas/README.md) for the register system.

## Microphone suppression reads *fresh*

`speak()` stays silent while a mic is capturing (`is_microphone_active()`, CoreAudio).

In a long-lived daemon the in-process CoreAudio read goes **stale** — a process that
queries device properties but never runs a CoreAudio run loop misses some mic on/off
transitions, so it drifts and can speak over a live meeting (observed 2026-07-05). The
daemon therefore sets `swd.MIC_CHECK_FRESH = True`, which runs the query in a throwaway
subprocess; a fresh HAL client always reads current state (~0.1 s per playback).

Short-lived CLI and library callers leave the flag `False` — they're already fresh.

## Control server

A second HTTP server on `127.0.0.1:9877` (`SPEAK_WHEN_DONE_CONTROL_PORT`) serves the pause
UI and a JSON API. State is file-backed (`state/pause.json`) so the worker's playback-time
check and the UI always agree on one source of truth. Timed pauses need no timer — expiry
is evaluated on read.

## MCP registration for per-worktree profiles

Tooling that mints a fresh Claude profile per worktree creates each `.claude.json` with
**no** `mcpServers`, so those sessions can't find the daemon (diagnosed 2026-07-10).
`scripts/stamp_mcp_profiles.sh` additively stamps the HTTP entry into every profile it
finds, idempotently; the optional `com.speak-when-done-mcp-stamper` LaunchAgent re-runs it
every 10 min to catch new profiles. A session picks the entry up on its next start, never
mid-session.

## Operating

```bash
launchctl print gui/$(id -u)/com.speak-when-done | grep -E 'state|pid'   # status
launchctl kickstart -k gui/$(id -u)/com.speak-when-done                  # restart
tail -f ~/.claude/speak_when_done/logs/daemon.log                        # logs
```

Restart after editing `daemon.py` or `__init__.py`. Persona `.md` files are re-read on
every call. The LaunchAgent is `KeepAlive`, so it auto-restarts on crash.
