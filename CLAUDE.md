# CLAUDE.md

Guidance for Claude Code (and humans) working in this repo.

## What this is

A macOS text-to-speech notification tool. An AI assistant speaks to you when a long task
finishes. This fork adds two things over upstream: a **shared warm daemon** (one resident
process serving MCP over HTTP, instead of a server per session) and a **persona system**
(each project deterministically gets a cloned character voice plus a written register).

Read [docs/architecture.md](docs/architecture.md) before changing the daemon, the queue, or
persona resolution. Read [docs/setup.md](docs/setup.md) for how it's installed and configured.

## The three legs

A persona is three things that must land together:

1. `PERSONA_VOICES["<name>"]` in `speak_when_done/__init__.py` — path, speed, and
   `language` if the tensor was exported against a non-default model version.
2. `personas/<name>.md` — the register. Header `## <name> — <one-line>`, and long enough to
   be a real register (the validator enforces a floor).
3. `~/.claude/voices/<name>.safetensors` — the voice.

Adding one without the others is the mistake this repo actually makes. `list_voices()`
returns `drift`, and `--validate-personas` fails CI on legs 1 and 2. **Leg 3 is not
enforceable** — no tensor ships in this repo, and a missing one is a legal fallback
(`alba`), not an error. So a typo'd tensor path shows as "the voice sounds generic," never
as a failure. Check `drift` when a persona sounds wrong.

Retiring is the reverse: drop the file, drop the entry, archive the tensor. No back-compat
shims.

## Rules that will bite you

- **Restart the daemon after editing `daemon.py` or `__init__.py`:**
  `launchctl kickstart -k gui/$(id -u)/com.speak-when-done`. The daemon is long-lived and
  holds the old code otherwise. **Persona `.md` files are re-read on every call** — never
  restart for those.
- **`cwd` is load-bearing.** One daemon serves every session, so callers pass `cwd` and a
  hash of it picks the persona. Omit it and every project shares one persona — the feature
  silently does nothing. It fails quiet, not loud.
- **Don't test import-time constants with `importlib.reload`.** It swaps the module object
  out from under every other test file that imported a symbol by name. Those files then
  pass in isolation and fail in-suite, which is a genuinely nasty afternoon. Extract a pure
  helper taking an injected environment and test that instead — see
  `tests/test_path_resolution.py`.
- **Mic suppression must read fresh in the daemon.** A long-lived process that queries
  CoreAudio but never runs a run loop accumulates a stale HAL cache and will speak over a
  live meeting (this happened, 2026-07-05). The daemon sets `MIC_CHECK_FRESH = True` to run
  the query in a throwaway subprocess. Don't "optimize" that subprocess away.
- **The queue is not optional ceremony.** `speak` enqueues and returns immediately because
  a paged-out model once made one synthesis take 12.5 minutes, timing out every client. The
  keep-warm generation exists to stop the model paging out. Don't make `speak` synchronous.
- **`PERSONA_VOICES` values are `str | float`** (paths and speeds in one dict). Strict type
  checkers flag every read of `cfg["path"]`. That's pre-existing and not your change.

## Voices

**No voice tensors are in this repo, and none should be added.** They're clones of
identifiable real people; local use is one thing, publishing them is another. See
[docs/voice-training.md](docs/voice-training.md) — it ships the harness so people clone
voices they have the standing to clone.

If you're asked to add a tensor, a download link, or a bucket path: don't. Surface it.

## Writing a register

The registers in `personas/` are the interesting part of this repo, and they're written for
their author — `_common.md` names him and tunes the roster's temperature to his taste. That
isn't a bug; it's what a register *is*. Anyone forking should swap both.

Read `personas/dexter.md` and `personas/attenborough.md` before writing a new one — they're
the clearest worked examples of the house shape. `personas/README.md` explains the system.

Use the `new-persona` skill to add one and the `clone-voice` skill to train a voice.

## Testing

```bash
uv run pytest tests/ -q                              # all of it
uv run python -m speak_when_done.cli --validate-personas   # drift check
```

CI runs both on macOS (the only platform this supports; testing on linux would pass while
proving nothing).

Tests read live state: `state/pause.json` is real, so `test_microphone_detection` fails if
the daemon happens to be paused via the control UI when you run the suite. That's the test
environment, not your change.

## Scope

Persona work stays in this fork — it is not upstreamable to
[Marviel/speak_when_done](https://github.com/Marviel/speak_when_done). Daemon and
mic-staleness fixes are generic and do go upstream.
