---
name: clone-voice
description: Clone a voice into a .safetensors tensor for speak_when_done — source audio, isolate vocals, filter to one speaker, export via pocket-tts, and audition it. Use when the user says "clone a voice", "train a voice", "make a tensor", "source audio for <character>", "why does this clone sound wrong", or is picking which voice to attempt. Covers the whole pipeline plus the lessons on which voices are hopeless.
---

# Cloning a voice

Full recipe and rationale: [docs/voice-training.md](../../../docs/voice-training.md). This
skill is the operating procedure.

## Before you touch audio

**Two questions, in this order. Both can end the task.**

1. **Do they have standing to clone this voice?** Their own, a colleague's with consent, a
   public-domain or licensed recording — fine. An identifiable person who hasn't agreed is
   their likeness, and "it's just for my terminal" stops being true the moment a file moves.
   Say this plainly once; don't moralize twice.

2. **Will it clone at all?** Apply the **recognition test**: would you know this voice in
   one sentence with your eyes closed? A character whose signature is *attitude or writing*
   rather than *sound* clones faithfully and unrecognizably. What survives cloning is
   timbre, accent, and regional flavor.

   **Known hopeless at any source quality** — say so before they spend an evening:
   - Extreme dynamic range (Jim Carrey) — ceiling ~3/5 across 20+ sources.
   - Non-standard phonation (Gollum's raspy whisper) — ceiling ~3/5 across 10+ sources.
   - Pause-cadence-as-identity (Christopher Walken) — his signature *is* the timing, and
     TTS smooths timing out. 1-2/5 across five clean sources including a full audiobook.

   Counter-intuitively, **consistency beats caricature**: Gilbert Gottfried's shrill
   register was expected to fail and came out great, because he never leaves it.

## Setup (once)

Export needs the **gated** model: accept terms at
<https://huggingface.co/kyutai/pocket-tts>, then `hf auth login`.

```bash
pip install resemblyzer scikit-learn soundfile 'setuptools<81'
```

The setuptools pin is load-bearing — webrtcvad imports `pkg_resources`, removed in 81.

## Pipeline

**1. Source.** Aim for ~60s of clean, single-speaker, single-*register* audio. 2-3 minutes
is a ceiling, not a floor. A multi-window super-concat beats one long window.

Source only from verified uploads — official broadcaster or known clip channels.
"Relaxing voice" and sleep-compilation channels **may be AI narration, not the person**: a
Morgan Freeman sleep channel cloned as weirdly *British*, almost certainly an impersonation
being cloned second-hand.

For an aging voice, pick **one era and stay in it** — a mixed-season compilation reads
"off". Pure studio voiceover beats character performance, even when the character is the
iconic one.

```bash
ffmpeg -i source.mp4 -vn -ar 16000 -ac 1 raw.wav
```

If yt-dlp refuses a kids'-channel video ("not available" + n-challenge warnings), retry
with `--extractor-args "youtube:player_client=android"`.

**2. Isolate** (only if there's music/background):

```bash
demucs --two-stems=vocals raw.wav     # -> separated/htdemucs/raw/vocals.wav
```

Works on documentary scoring and ad-bed music. **Hurts character performances** — skip if
the source is already clean speech. Reverb kills cloning outright; don't try to rescue a
reverby source.

**3. Filter to one speaker** — *only if genuinely multi-speaker*:

```bash
python tools/filter_speaker.py vocals.wav filtered.wav 180
```

**Never run this on a solo clip.** KMeans(2) forced onto one speaker splits them
arbitrarily — it twice kept 2-4s of a 24s solo source. Solo → use the raw vocals.

It clusters *speakers, not registers*: it cannot separate someone's normal voice from the
same person doing a bit. Trim wrong-register sections **by time, before** filtering.

**4. Export:**

```bash
uvx pocket-tts export-voice filtered.wav ~/.claude/voices/<name>.safetensors
```

**5. Audition — in character:**

```bash
uvx pocket-tts generate --text "<a line in this persona's register>" \
  --voice ~/.claude/voices/<name>.safetensors \
  --eos-threshold -2 --frames-after-eos 0
```

**Write the audition line in the persona's register.** A flat test sentence hides a keeper;
the same clone reads a full grade better on in-character text. This is the most common
evaluation mistake.

Use `--eos-threshold -2 --frames-after-eos 0` at audition and runtime — it prevents the
trailing-off at sentence ends. For output level use linear gain (`volume=12dB`); **loudnorm
causes audible artifacts**.

## When it sounds wrong

Check the **register before the tensor**. Delivery follows text: a calm clone reading
clipped staccato fragments sounds like a different, deadpan persona. That misdiagnosis has
already cost this project real time.

Then check `list_voices()` → `drift`. A missing tensor falls back to built-in `alba`
silently — "sounds generic" usually means the path is wrong, not the clone.

## Record it

Keep the roster note: persona, tensor, model version, speed, rating, and the **exact
source** — video ID, time window, processing chain. When a model version changes and you
re-export, that line is the difference between five minutes and an afternoon.

Never add the tensor to this repo (CLAUDE.md). It lives in `~/.claude/voices/`.

Wiring it up is the `new-persona` skill — the tensor is only one of three legs.
