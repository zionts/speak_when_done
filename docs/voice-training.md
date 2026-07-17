# Cloning a voice

No voice files ship with this repo. This is the harness to make your own.

The whole pipeline is **source audio → isolate → filter → export → audition**, and the
export step is a single command. The hard part isn't the tooling, it's picking a voice
that clones well and finding clean audio of it. Most of this doc is about that.

> **Budget a few hours per voice, not a few minutes.** Setup is half an hour, once. After
> that, a voice that works can take one clip and twenty minutes — or a dozen sources
> across an evening. **Plenty of voices never work at any source quality**, and no amount
> of effort rescues them. Read [Picking a voice that will actually work](#picking-a-voice-that-will-actually-work)
> *before* you go hunting for audio; it's the section that saves you the most time.

## Before you start: whose voice?

Clone voices you have the standing to clone — your own, a colleague's with their consent,
a public-domain recording, a licensed one. A voice clone of an identifiable person is
their likeness, and "it's just for my terminal" stops being true the moment a file gets
shared.

That's why this repo ships the recipe and not the tensors.

---

## Setup

Export needs the **gated** pocket-tts model:

1. Accept the terms at <https://huggingface.co/kyutai/pocket-tts>
2. `hf auth login`

The speaker filter (`tools/filter_speaker.py`) needs:

```bash
pip install resemblyzer scikit-learn soundfile 'setuptools<81'
```

`setuptools<81` is not optional — webrtcvad reaches for `pkg_resources`, which newer
setuptools removed.

For source prep you'll also want `ffmpeg` and, for music/background removal,
[demucs](https://github.com/adefossez/demucs).

---

## The pipeline

### 1. Get clean source audio

Aim for **~60 seconds of clean, single-speaker, single-register audio**. Two to three
minutes is a ceiling, not a floor — 60s of well-filtered audio beats 4 minutes of mixed.
A multi-window "super-concat" (several separate clean windows stitched together) beats one
long window.

```bash
ffmpeg -i source.mp4 -vn -ar 16000 -ac 1 raw.wav
```

### 2. Strip music and background (if any)

```bash
demucs --two-stems=vocals raw.wav
# → separated/htdemucs/raw/vocals.wav
```

Demucs works well on documentary scoring and ad-bed music. It **hurts** character
performances — if the source is already clean speech, skip it.

### 3. Filter to one speaker (only if genuinely multi-speaker)

Interviews and best-of compilations have a host and a guest. This keeps the dominant one:

```bash
python tools/filter_speaker.py vocals.wav filtered.wav 180
```

Sliding-window d-vector embeddings → KMeans(k=2) → keep the dominant cluster, drop windows
near the decision boundary, stitch with short crossfades. The third arg caps output
seconds.

**Do not run this on solo clips.** KMeans(2) forced onto a single speaker splits them
arbitrarily — it twice kept 2-4s of a 24s solo clip. Solo source → use the raw demucs
vocals.

It also clusters **speakers, not registers**. It cannot separate someone's normal voice
from the same person doing a bit. Trim wrong-register sections by time *before* filtering.

### 4. Export the tensor

```bash
uvx pocket-tts export-voice filtered.wav ~/.claude/voices/<name>.safetensors
```

The tensor is tied to the model version it was exported from. If you export against a
different pocket-tts language than the runtime default (`english_2026-04`), record it in
that persona's `PERSONA_VOICES["language"]` entry.

### 5. Audition — in character

```bash
uvx pocket-tts generate \
  --text "<a line written in this persona's register>" \
  --voice ~/.claude/voices/<name>.safetensors \
  --eos-threshold -2 --frames-after-eos 0
```

**Write the audition line in the persona's voice, not a flat test sentence.** The same
clone reads a full grade better on in-register text — flat lines hide keepers. This is the
single biggest evaluation mistake.

Use `--eos-threshold -2 --frames-after-eos 0` everywhere; it prevents the trailing-off at
sentence ends.

### 6. Wire it up

See [personas/README.md](../personas/README.md) — a persona is a tensor **plus** a
register file **plus** a `PERSONA_VOICES` entry, and all three have to land together.

---

## Picking a voice that will actually work

This is the part that costs days if you get it wrong. Hard-won:

### Clones well

- **Consistent register.** One emotional gear, sustained.
- **Clear articulation.**
- **Distinctive timbre** — see the recognition test below.
- Distinctive ≠ safe, but consistency beats caricature. Gilbert Gottfried's shrill
  kvetch was expected to fail and came out great, purely because he never leaves the
  register.

### Clones badly, at any source quality

- **Extreme dynamic range** — Jim Carrey. Ceiling of 3/5 across 20+ sources attempted.
- **Non-standard phonation** — Gollum's raspy whisper. Ceiling of 3/5 across 10+ sources.
- **Pause-cadence-as-identity** — Christopher Walken. His signature *is* the timing, and
  TTS smooths timing out. 1-2/5 across five clean sources including a full audiobook.

When a voice is on this list, more source audio does not help. Stop.

### The recognition test

Before sourcing anything, ask: **would you know this voice in one sentence with your eyes
closed?**

A character whose signature is *attitude or writing* rather than *sound* clones
accurately but unrecognizably — the listener has no timbre fingerprint to match against.
Ferris Bueller failed twice this way: the clone was faithful, and nobody could tell who it
was. The traits that survive cloning are timbre, accent, and regional flavor.

---

## Sourcing lessons

- **Pure voiceover beats character performance.** Sam Elliott's "Beef. It's What's For
  Dinner" ads (demucs'd off the hoe-down music) cloned dramatically better than his Big
  Lebowski narration. Studio VO is consistent by design.
- **Reverb kills cloning.** Baked-in studio reverb on an audiobook produced a 1/5. Clean
  broadcast audio wins.
- **Compilation and "relaxing voice" channels may be AI narration, not the person.** A
  "Go To Bed With Morgan Freeman" sleep channel cloned as weirdly *British* — almost
  certainly an AI impersonation being cloned second-hand. Source only from verified
  uploads: official broadcaster channels, known clip channels.
- **Single-era sources for aging voices.** A mixed-season Dexter compilation read as
  "off"; season-1-only monologues fixed it. Pick one era and stay in it.
- **yt-dlp on kids'-channel videos** may refuse the default client ("This video is not
  available" plus n-challenge warnings). Retry with
  `--extractor-args "youtube:player_client=android"`.

## Audio-processing lessons

- **Loudnorm causes audible artifacts** in TTS output. Use simple linear gain
  (`volume=12dB`), never `loudnorm=...`.
- **`--eos-threshold -2 --frames-after-eos 0`** globally, at both audition and runtime.

## Runtime lessons

- **Delivery follows text, not just the tensor.** A calm clone reading clipped staccato
  fragments sounds like a different, deadpan character entirely — this happened, and the
  tensor got blamed for a month before the register file turned out to be the cause. If a
  persona sounds wrong in the wild, check whether the *message* was composed in-register
  before you touch the tensor.
- **A good clone can still be a bad persona.** One voice cloned at 4/5 and got retired
  anyway: the register never landed, and the author didn't know the character well enough
  to write for him. Cloning is the easy half.

---

## Keeping a workshop

Cloning is iterative and most attempts fail, so keep notes or you'll re-source the same
dead end twice. A useful layout, with the big binaries gitignored:

```
PREFERENCES.md        # the roster table: persona | tensor | model | speed | rating | exact source
sources/              # per-attempt logs — what was tried, what it scored
candidates/           # experiments not yet promoted
retired/              # archived tensors, with a note on why
bench-registers/      # register drafts for personas that never shipped
```

The roster table is the important one. Record the **exact source** — video ID, time
window, and processing chain — for every keeper. When a model version changes and you need
to re-export, that line is the difference between five minutes and an afternoon.
