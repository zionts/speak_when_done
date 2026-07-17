---
name: new-persona
description: Add a new persona (character voice + written register) to speak_when_done, or retire an existing one. Use when the user says "add a persona", "new persona", "make a <character> voice", "retire <persona>", "write a register", or names a character they want their notifications to sound like. Handles the three-legs contract (PERSONA_VOICES entry + personas/<name>.md + tensor) so none is forgotten.
---

# Adding a persona

A persona is **three legs**, and the mistake this repo actually makes is landing one
without the others. Do all three, then verify `drift: []`.

Before anything: **has this voice got a chance of cloning?** Read
[docs/voice-training.md § Picking a voice that will actually work](../../../docs/voice-training.md).
A character whose signature is attitude rather than *sound* clones accurately and
unrecognizably — that's a wasted evening. If the user names a voice on the known-hopeless
list (extreme dynamic range, non-standard phonation, pause-cadence-as-identity), say so
before they source audio, not after.

## Leg 1 — the register (`personas/<name>.md`)

This is the actual work. The tensor is the easy half.

**Read `personas/dexter.md` and `personas/attenborough.md` first.** They're the clearest
worked examples of the house shape. Match it:

- `## <name> — <one-line>` header.
- **Who they are** — a paragraph placing them somewhere physical, plus *ear-calibration
  quotes* (real, verifiable lines from the source, marked as cadence-only).
- **The move** — the signature two-beat structure. This is what makes the persona
  reproducible rather than vibes.
- **How the work bends them** — triumph, disaster, tedium, absurdity, rescue. The persona
  must have a *different* line for a merge than for a four-day grind.
- **Calibration vignettes** — marked "calibration only; never quote verbatim".
- **Avoid** — the parody traps. Usually "not <the adjacent persona>", because the failure
  mode is drifting into a neighbour.

Register quality beats tensor quality. A calm clone reading clipped fragments sounds like a
*different persona* — if a persona sounds wrong in the wild, suspect the register before
the voice.

The file must clear the validator's length floor (400 chars). Read `_common.md` — it holds
the shared discipline and TTS-writing rules and applies to every persona.

## Leg 2 — the plumbing (`PERSONA_VOICES` in `speak_when_done/__init__.py`)

```python
"<name>": {
    "path": os.path.join(_VOICES_DIR, "<name>.safetensors"),
    "speed": 0.95,          # 0.92-1.0; slower reads weightier. Tune by ear.
    "tagline": "<who they are, one line>",   # fallback if the .md is unreadable
},
```

Add `"language": "english_2026-01"` **only** if the tensor was exported against a
non-default model version. A tensor is tied to the model that produced it.

## Leg 3 — the voice (`~/.claude/voices/<name>.safetensors`)

Use the `clone-voice` skill. **No tensors live in this repo and none may be added** — see
CLAUDE.md.

This leg is not enforceable: a missing tensor silently falls back to the built-in `alba`
voice. So a typo'd path shows up as "sounds generic," never as an error. Check it by ear.

## Verify

```bash
uv run python -m speak_when_done.cli --validate-personas   # want ok:true, empty lists
uv run pytest tests/test_persona_sync.py -q
```

Then hear it. Compose the audition line **in the persona's register** — a flat test
sentence hides a keeper, and the same clone reads a full grade better on in-character text.

Persona `.md` files are re-read on every call, so no restart. If you touched
`__init__.py`, restart: `launchctl kickstart -k gui/$(id -u)/com.speak-when-done`.

## Retiring

Reverse all three: delete `personas/<name>.md`, drop the `PERSONA_VOICES` entry, archive
the tensor out of `~/.claude/voices/`. No back-compat shims. `--validate-personas` confirms
nothing's left over.

Consider benching the register (keep the `.md` somewhere) rather than deleting — a clone
can be fine while the *persona* just never lands, and that register may be worth reviving
against a different voice.
