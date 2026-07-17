"""Tests for persona-roster wiring (2026-07-02 expansion, 2026-07-10 swap).

The 2026-07-10 swap replaced the three builtin-voice originals
(flightdeck/gumshoe/expediter) with four cloned voices
(freeman/ross/cunk/dexter). Builtin voice NAMES as a persona "path" remain
supported machinery, so that path is covered via a synthetic monkeypatched
persona rather than a live roster entry. Pins in personas/assignments.json
(seeded from the frozen six-persona roster) keep pre-expansion worktrees on
their original voice. Covered here:

- builtin-name voice resolution (no coercion to the "alba" fallback, and the
  persona's own path comes back so speak()'s speed modifier still applies)
- drift checking: builtin names never flag "voice file missing on disk";
  a genuinely missing .safetensors path still does; the live cloned roster
  is drift-free against the real persona files
- assignments.json pins win over the full-roster hash (via a tmp pins file —
  never the real one)
- the swapped-in personas are reachable for unpinned (new) worktrees
- assignment is deterministic per path

All resolution tests isolate _ASSIGNMENTS_PATH to tmp_path and clear
SPEAK_WHEN_DONE_VOICE, so nothing here reads or writes the real personas dir.
"""

import json
import os

import pytest

import speak_when_done as swd
from speak_when_done import (
    _LEGACY_PERSONAS,
    PERSONA_VOICES,
    _check_drift,
    _is_builtin_voice,
    _legacy_persona_for_worktree,
    _load_persona_playbooks,
    _pick_persona_for_worktree,
    _resolve_active_persona_and_voice,
)

NEW_PERSONAS = ("freeman", "bandit", "cunk", "dexter")
BUILTIN_TEST_PERSONA = "builtin-test"


def _fake_playbook(persona: str) -> str:
    """A minimal well-formed persona section (correct header, >= 400 chars)."""
    return f"## {persona} — test register\n" + "filler register line\n" * 30


@pytest.fixture()
def pins_file(monkeypatch, tmp_path):
    """Isolate persona resolution from the real assignments.json and env.

    Points _ASSIGNMENTS_PATH at a tmp file (initially absent, i.e. no pins)
    and clears SPEAK_WHEN_DONE_VOICE so resolution takes the pin/hash path.
    """
    monkeypatch.delenv("SPEAK_WHEN_DONE_VOICE", raising=False)
    path = tmp_path / "assignments.json"
    monkeypatch.setattr(swd, "_ASSIGNMENTS_PATH", str(path))
    return path


def _pin(pins_file, worktree: str, persona: str) -> None:
    pins_file.write_text(json.dumps({"pins": {worktree: persona}}))


# ---- builtin-voice resolution ------------------------------------------------
# No live persona uses a builtin voice name since the 2026-07-10 swap, but the
# machinery must keep working (it's the documented escape hatch for auditioning
# a persona before its clone exists) — so cover it with a synthetic entry.


@pytest.fixture()
def builtin_persona(monkeypatch):
    """A synthetic persona wired to a builtin voice NAME (no file on disk)."""
    monkeypatch.setitem(
        PERSONA_VOICES,
        BUILTIN_TEST_PERSONA,
        {"path": "anna", "speed": 1.1, "tagline": "test-only builtin persona"},
    )
    return BUILTIN_TEST_PERSONA


def test_builtin_voice_persona_resolves_to_builtin_name(pins_file, builtin_persona):
    """A persona whose path is a builtin NAME resolves to that name, not 'alba'.

    Builtin names never exist on disk, so the missing-file fallback must skip
    them — otherwise every builtin-voice persona silently loses its timbre.
    """
    wt = "/Users/test/builtin-voice-worktree"
    _pin(pins_file, wt, builtin_persona)
    got_persona, got_voice = _resolve_active_persona_and_voice(wt)
    assert got_persona == builtin_persona
    expected = PERSONA_VOICES[builtin_persona]["path"]
    assert _is_builtin_voice(expected), (
        f"{builtin_persona}.path {expected!r} is expected to be a builtin voice name"
    )
    assert got_voice == expected, (
        f"builtin-name voice was coerced: got {got_voice!r}, want {expected!r}"
    )
    assert got_voice != "alba"


def test_builtin_voice_persona_speed_survives(pins_file, builtin_persona):
    """Resolution returns the persona's OWN path, which is exactly the
    condition speak() checks (is_persona_voice) before applying the persona's
    speed modifier. If resolution fell back to 'alba', speed would be lost.
    """
    wt = "/Users/test/builtin-voice-worktree"
    _pin(pins_file, wt, builtin_persona)
    _, voice = _resolve_active_persona_and_voice(wt)
    cfg = PERSONA_VOICES[builtin_persona]
    assert voice == cfg["path"], (
        "voice != persona path would disable the persona speed in speak()"
    )
    assert cfg.get("speed", 1.0) != 1.0


@pytest.mark.parametrize("persona", NEW_PERSONAS)
def test_cloned_persona_speed_is_wired(persona):
    """The swapped-in personas all carry an explicit, sane speed."""
    speed = PERSONA_VOICES[persona]["speed"]
    assert 0.8 <= speed <= 1.2


# ---- drift checking ----------------------------------------------------------


def test_builtin_voice_produces_no_missing_file_drift(builtin_persona):
    """Builtin voice names must not be flagged as missing files on disk."""
    voice = PERSONA_VOICES[builtin_persona]["path"]
    playbooks = {builtin_persona: _fake_playbook(builtin_persona)}
    issues = _check_drift(builtin_persona, voice, playbooks)
    assert not any("voice file missing" in i for i in issues), issues
    assert issues == []


# Voice tensors ship with nobody (docs/voice-training.md), so live-wiring checks
# that require them must skip — visibly, not silently — on fresh clones and CI.
_TENSORS_PRESENT = all(
    _is_builtin_voice(PERSONA_VOICES[p]["path"])
    or os.path.exists(PERSONA_VOICES[p]["path"])
    for p in NEW_PERSONAS
)


@pytest.mark.skipif(
    not _TENSORS_PRESENT,
    reason="live-install integrity check: requires trained voice tensors on disk; "
    "fresh clones and CI ship none (docs/voice-training.md)",
)
def test_cloned_roster_is_drift_free_against_real_playbooks():
    """The live wiring: real persona files + real safetensors → drift == []."""
    playbooks = _load_persona_playbooks()
    for persona in NEW_PERSONAS:
        issues = _check_drift(persona, PERSONA_VOICES[persona]["path"], playbooks)
        assert issues == [], f"{persona}: {issues}"


def test_missing_safetensors_still_drifts(monkeypatch, tmp_path):
    """A genuinely absent .safetensors path keeps its missing-file drift entry."""
    ghost_path = str(tmp_path / "ghost.safetensors")  # deliberately never created
    monkeypatch.setitem(
        PERSONA_VOICES,
        "ghost",
        {"path": ghost_path, "speed": 1.0, "tagline": "test-only ghost persona"},
    )
    issues = _check_drift("ghost", ghost_path, {"ghost": _fake_playbook("ghost")})
    assert any("voice file missing on disk" in i for i in issues), issues


# ---- assignment stability (pins) ----------------------------------------------


def test_pinned_worktree_overrides_full_roster_hash(pins_file):
    """A pin in assignments.json wins over whatever the nine-name hash says."""
    wt = "/Users/test/pinned-worktree"
    hashed = _pick_persona_for_worktree(wt)  # no pins file yet → pure hash
    pinned = next(n for n in sorted(PERSONA_VOICES) if n != hashed)
    _pin(pins_file, wt, pinned)
    assert _pick_persona_for_worktree(wt) == pinned
    persona, _ = _resolve_active_persona_and_voice(wt)
    assert persona == pinned


def test_seeded_pin_preserves_legacy_assignment(pins_file):
    """The roster-expansion scenario the pins exist for: a pre-expansion
    worktree whose six-roster (legacy) persona differs from the nine-roster
    hash must keep its legacy persona once pinned."""
    wt = next(
        p
        for p in (f"/Users/test/legacy-wt-{i}" for i in range(500))
        if _legacy_persona_for_worktree(p) != _pick_persona_for_worktree(p)
    )
    legacy = _legacy_persona_for_worktree(wt)
    _pin(pins_file, wt, legacy)
    persona, _ = _resolve_active_persona_and_voice(wt)
    assert persona == legacy


def test_pin_to_unknown_persona_falls_back_to_hash(pins_file):
    """A pin naming a retired/unknown persona is ignored, not a crash."""
    wt = "/Users/test/unknown-pin-worktree"
    hashed = _pick_persona_for_worktree(wt)
    _pin(pins_file, wt, "nonexistent-persona")
    assert _pick_persona_for_worktree(wt) == hashed


def test_legacy_assignment_only_uses_legacy_roster():
    """Pin seeding relies on the legacy hash never producing a new persona."""
    for i in range(64):
        persona = _legacy_persona_for_worktree(f"/Users/test/wt-{i}")
        assert persona in _LEGACY_PERSONAS


# ---- new-worktree reachability + determinism ----------------------------------


@pytest.mark.parametrize("persona", NEW_PERSONAS)
def test_new_personas_reachable_for_unpinned_worktrees(pins_file, persona):
    """Unpinned (new) worktrees hash over the FULL roster, so each new persona
    must be reachable. Deterministic: sha256 over synthetic paths, no RNG."""
    for i in range(2000):
        wt = f"/Users/test/reachability-wt-{i}"
        if _pick_persona_for_worktree(wt) == persona:
            got_persona, got_voice = _resolve_active_persona_and_voice(wt)
            assert got_persona == persona
            # The voice contract is environment-dependent by design: the tensor
            # path when the file exists, the "alba" fallback when it doesn't
            # (tensors ship with nobody). Assert whichever applies here so the
            # hashing coverage above still runs on tensor-less machines and CI.
            tensor = PERSONA_VOICES[persona]["path"]
            expected = tensor if os.path.exists(tensor) else "alba"
            assert got_voice == expected
            return
    pytest.fail(f"no synthetic path out of 2000 hashed to {persona!r}")


def test_same_path_resolves_same_persona_across_calls(pins_file):
    """Same worktree path → same (persona, voice) on every call."""
    wt = "/Users/test/determinism-worktree"
    results = {_resolve_active_persona_and_voice(wt) for _ in range(5)}
    assert len(results) == 1
