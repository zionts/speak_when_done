"""Tests for persona/voice directory resolution.

These directories used to be hardcoded to ~/.claude/..., so a clone anywhere else
silently found no personas. personas/ now resolves relative to the package (it ships
in the repo), and both dirs take an env override.

The resolution logic is exercised through the pure `_resolve_*` helpers with a fake
environment. Do NOT reload the module to test this: the constants are bound at import
time, and reloading swaps the module object out from under every other test file that
imported a symbol by name (it silently breaks test_persona_wiring.py).
"""

import os

from speak_when_done import (
    _PACKAGE_ROOT,
    _PERSONA_DIR,
    _VOICES_DIR,
    _resolve_persona_dir,
    _resolve_voices_dir,
)


def test_persona_dir_resolves_next_to_the_package_by_default():
    """No env var: personas/ is found beside the code, not under a fixed home."""
    assert _resolve_persona_dir(environ={}, package_root="/opt/swd") == (
        "/opt/swd/personas"
    )


def test_persona_dir_env_override_wins(tmp_path):
    assert _resolve_persona_dir(
        environ={"SPEAK_WHEN_DONE_PERSONA_DIR": str(tmp_path)},
        package_root="/opt/swd",
    ) == str(tmp_path)


def test_empty_env_value_falls_back_rather_than_resolving_to_nothing():
    """An exported-but-empty var is a misconfiguration, not a request for "" ."""
    assert _resolve_persona_dir(
        environ={"SPEAK_WHEN_DONE_PERSONA_DIR": ""}, package_root="/opt/swd"
    ) == "/opt/swd/personas"
    assert _resolve_voices_dir(environ={"SPEAK_WHEN_DONE_VOICES_DIR": ""}) == (
        os.path.expanduser("~/.claude/voices")
    )


def test_voices_dir_defaults_to_home():
    """Voice tensors are user data, so they stay under the home dir by default."""
    assert _resolve_voices_dir(environ={}) == os.path.expanduser("~/.claude/voices")


def test_voices_dir_env_override(tmp_path):
    assert _resolve_voices_dir(
        environ={"SPEAK_WHEN_DONE_VOICES_DIR": str(tmp_path)}
    ) == str(tmp_path)


def test_overrides_expand_user():
    assert _resolve_persona_dir(
        environ={"SPEAK_WHEN_DONE_PERSONA_DIR": "~/p"}, package_root="/opt/swd"
    ) == os.path.expanduser("~/p")
    assert _resolve_voices_dir(environ={"SPEAK_WHEN_DONE_VOICES_DIR": "~/v"}) == (
        os.path.expanduser("~/v")
    )


def test_module_constants_point_at_the_real_shipped_personas():
    """The live constants must find the personas/ that ships in this repo."""
    assert _PERSONA_DIR == os.path.join(_PACKAGE_ROOT, "personas")
    assert os.path.isdir(_PERSONA_DIR)
    assert os.path.isfile(os.path.join(_PERSONA_DIR, "_common.md"))


def test_canonical_install_keeps_its_historical_paths():
    """No behavior change for the ~/.claude/speak_when_done install.

    This is the regression guard: the default resolution must land on exactly the
    paths that were hardcoded before.
    """
    canonical = os.path.expanduser("~/.claude/speak_when_done")
    assert _resolve_persona_dir(environ={}, package_root=canonical) == (
        os.path.expanduser("~/.claude/speak_when_done/personas")
    )
    assert _resolve_voices_dir(environ={}) == os.path.expanduser("~/.claude/voices")
    assert _VOICES_DIR == os.path.expanduser("~/.claude/voices")
