# Personas

One markdown file per persona, plus `_common.md` for shared discipline and TTS rules.

Each file is the full **register**: who they are (with verified ear-calibration quotes),
"the move" (the persona's signature two-beat structure), how each kind of turn bends them,
calibration-only vignettes, and an "avoid" list of common parody failure modes.

Files are read at runtime on every call. Edit them freely — no restart, no rebuild.

## How a persona resolves

Callers pass `cwd`. A SHA-256 hash of the worktree path deterministically maps it to a
persona, so a given project always sounds like the same character. One daemon serves every
session, so `cwd` is the only thing distinguishing them — a caller that omits it gets a
single default persona for everything.

`PERSONA_VOICES` in `speak_when_done/__init__.py` holds only audio plumbing — tensor path,
speed, language, and a one-line fallback tagline used when the persona file is missing or
unreadable. The character itself lives entirely in these `.md` files.

## The three legs

Adding a persona means three things land together:

1. **`PERSONA_VOICES["<name>"]`** in `speak_when_done/__init__.py` — path, speed,
   optionally `language` if the tensor was exported against a non-default model version.
2. **`personas/<name>.md`** — the register. Header `## <name> — <one-line>`, and long
   enough to actually be a register (the validator enforces a floor).
3. **`~/.claude/voices/<name>.safetensors`** — the voice.
   See [docs/voice-training.md](../docs/voice-training.md).

`list_voices()` returns `drift` — it catches legs 1 and 2 falling out of sync, and a
missing tensor. Aim for `drift: []`.

Retiring is the same in reverse: drop the file, drop the `PERSONA_VOICES` entry, archive
the tensor. No back-compat shims — `drift` confirms nothing's left over.

**A missing tensor is not fatal.** Personas with no voice file fall back to the built-in
pocket-tts voice `alba` (`__init__.py:692`), so a fresh clone of this repo works
immediately — right register, wrong timbre.

## Making them yours

These registers are written for their author, and it shows. `_common.md` names him
directly ("read *his* weather") and tunes the roster's temperature to his taste — warm and
wry, dark only when it's funny. That's not a bug in the file; it's what a register *is*.
Swap the name and the temperature for your own.

The same goes for the roster. These ten are one person's taste in voices. Yours will
differ, and the interesting half of this project is picking them.

## A note on cultural registers

Some personas lean on registers tied to real cultural or ethnic identities — Borscht-belt
Yiddish vocabulary, an Iranian-American actor's character, a Western-American drawl. The
"Avoid" section in each file guards against the cheapest parody traps.

The underlying question — *should you voice these registers at all* — is worth actually
asking rather than inheriting. If a register makes you uncomfortable, on your own behalf
or someone else's, change it or drop the persona. Nothing here is load-bearing.

## Overrides

Env vars, on the daemon:

| Env var | Effect |
|---|---|
| `SPEAK_WHEN_DONE_VOICE=<path-or-name>` | Use a specific voice file or built-in name. If the path matches one of the personas' tensors, that persona locks in too; otherwise the register still resolves from the worktree hash. |
| `SPEAK_WHEN_DONE_LANGUAGE=<lang>` | Override the pocket-tts model version (default `english_2026-04`). A tensor is tied to the model it was exported from. |
| `SPEAK_WHEN_DONE_NO_CWD_DISCOVERY=1` | Disable caller-cwd discovery. |

To pin one persona everywhere, point `SPEAK_WHEN_DONE_VOICE` at its tensor. To silence the
whole thing without touching config, use the control UI at <http://127.0.0.1:9877/> — one
button, or a 15/30/60-minute chip. It also self-suppresses while a mic is live.
