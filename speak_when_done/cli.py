"""
CLI entry point for speak_when_done.

Usage:
    uvx speak_when_done --text "Hello world"
    uvx speak_when_done --text "Build complete" --voice alba
    uvx speak_when_done --list-voices
    uvx speak_when_done --validate-personas
"""

import argparse
import json
import sys

from . import _CALL_LOG, _DESYNC_LOG, list_voices, speak, validate_persona_sync


def _print_tail(path: str, n: int, *, label: str = "calls") -> None:
    """Print the last n JSONL records, one per line, in a compact format."""
    import os
    if not os.path.exists(path):
        print(f"(no {label} log yet at {path})")
        return
    with open(path) as f:
        lines = f.readlines()
    for line in lines[-n:]:
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            print(line.rstrip())
            continue
        ts = r.get("ts", "?")
        event = r.get("event", "?")
        persona = r.get("persona", "-")
        voice = (r.get("voice") or "-").rsplit("/", 1)[-1]
        prompt_sha = r.get("prompt_sha", "-")
        voice_sha = r.get("voice_sha") or "-"
        drift = r.get("drift")
        drift_str = f"  DRIFT={drift}" if drift else ""
        print(f"{ts}  {event:18s}  {persona:14s}  {voice:36s}  p={prompt_sha}  v={voice_sha}{drift_str}")


def main():
    parser = argparse.ArgumentParser(
        prog="speak_when_done",
        description="Speak text aloud using Pocket TTS with automatic cleanup",
    )
    parser.add_argument(
        "--text", "-t",
        help="The text to speak aloud",
    )
    parser.add_argument(
        "--voice", "-v",
        default=None,
        help="Voice to use (default: resolved from worktree persona). Can be a voice name or path to audio file for cloning.",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress pocket-tts output",
    )
    parser.add_argument(
        "--list-voices", "-l",
        action="store_true",
        help="List available voices and exit",
    )
    parser.add_argument(
        "--validate-personas",
        action="store_true",
        help="Check that PERSONA_VOICES and CLAUDE.md agree on personas; "
             "exit non-zero on drift. Use after editing either source.",
    )
    parser.add_argument(
        "--tail",
        type=int,
        nargs="?",
        const=20,
        metavar="N",
        help="Show the last N call-log entries (default 20) from "
             "~/.claude/speak_when_done/logs/calls.jsonl and exit.",
    )
    parser.add_argument(
        "--tail-desync",
        type=int,
        nargs="?",
        const=20,
        metavar="N",
        help="Show the last N desync events from desync.jsonl. Empty output "
             "is the goal — anything here is a real drift bug.",
    )

    args = parser.parse_args()

    if args.tail is not None:
        _print_tail(_CALL_LOG, args.tail)
        sys.exit(0)
    if args.tail_desync is not None:
        _print_tail(_DESYNC_LOG, args.tail_desync, label="desync")
        sys.exit(0)

    if args.validate_personas:
        result = validate_persona_sync()
        print(json.dumps(result, indent=2))
        if not result["ok"]:
            print(
                f"\nDRIFT detected. Edit {result['playbook_path']} or PERSONA_VOICES "
                f"in speak_when_done/__init__.py until both sources agree.",
                file=sys.stderr,
            )
            sys.exit(1)
        sys.exit(0)

    if args.list_voices:
        result = list_voices()
        print(f"Active worktree: {result['active_worktree']}")
        print(f"Active persona:  {result['active_persona']}")
        print(f"Default voice:   {result['default_voice']}")
        print(f"Playbook source: {result['playbook_source']}")
        print("\nBuilt-in voices:")
        for voice in result["builtin_voices"]:
            print(f"  - {voice['name']}: {voice['description']}")
        print("\nPersona voices:")
        for v in result["persona_voices"]:
            marker = " (active)" if v["name"] == result["active_persona"] else ""
            tagline = v["style"].split("\n", 1)[0]
            print(f"  - {v['name']}{marker}: {tagline[:120]}")
        sync = result["playbook_sync"]
        if not sync["ok"]:
            print(f"\n⚠ Playbook drift: {sync}", file=sys.stderr)
        sys.exit(0)

    if not args.text:
        parser.error("--text is required unless using --list-voices or --validate-personas")

    result = speak(args.text, voice=args.voice, quiet=args.quiet)

    if not result["success"]:
        if result.get("suppressed"):
            print(f"Suppressed: {result['reason']}", file=sys.stderr)
        else:
            print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
