"""Archive a Claude Code session into the knowledge base (no tokens used).

Run by the SessionEnd hook (session JSON on stdin), or by hand:
    uv run --frozen python -I scripts/kb/session_end.py [--kb KB_DIR] TRANSCRIPT.jsonl
    ... session_end.py [--kb KB_DIR] --todo                 sessions waiting for a card
    ... session_end.py [--kb KB_DIR] --skip SESSION_ID "why"  no card: nothing for CAD
    ... session_end.py [--kb KB_DIR] --action SESSION_ID "tool: add export_dxf" ...
    ... session_end.py --find-session MARKER    which session printed MARKER earlier

Subagent transcripts (e.g. cad-builder) are condensed into kb/_pending/ (not
indexed, not in git) at session end. They enter the KB only after review:
    ... session_end.py [--kb KB_DIR] --list-pending
    ... session_end.py [--kb KB_DIR] --archive ID [--card FILE] [--robot R]
                                  [--with-transcript]
    ... session_end.py [--kb KB_DIR] --discard ID [--keep] [NOTE...]
    ... session_end.py [--kb KB_DIR] --stage TRANSCRIPT.jsonl   stage subagents by hand
The main chat is archived directly unless --stage-main is given or env
KB_STAGE_MAIN=1 is set: then it is staged and reviewed like a subagent's.

Copies the conversation text (redacted, local only) and any pasted images into
kb/designs/<robot>/ and queues sessions without a card in
kb/ingest/sessions_todo.csv. Never fails loudly: a hook must not block exit.
"""

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))


def main(argv: list[str]) -> int:
    try:
        from onshape_mcp.kb_sessions import (
            add_actions,
            archive_transcript,
            find_session,
            skip_session,
            todo_list,
        )
    except Exception as exc:  # package missing in this checkout: skip quietly
        print(f"session_end: skipped ({exc})", file=sys.stderr)
        return 0
    kb_dir = REPO / "kb"
    if argv[:1] == ["--kb"]:
        kb_dir, argv = Path(argv[1]), argv[2:]
    if argv[:1] == ["--find-session"] and len(argv) == 2:
        projects = Path.home() / ".claude" / "projects"
        project = projects / ("-" + str(REPO).strip("/").replace("/", "-"))
        print("\n".join(find_session(project, argv[1])) or "no session found yet")
        return 0
    if argv[:1] == ["--action"] and len(argv) >= 3:
        try:
            added = add_actions(kb_dir, argv[2:], session_id=argv[1])
            print(f"{len(added)} new action item(s) in kb/action-items.md")
            return 0
        except ValueError as exc:
            print(f"session_end: {exc}", file=sys.stderr)
            return 1
    if argv[:1] == ["--todo"]:
        for row in todo_list(kb_dir):
            print(json.dumps(row))
        return 0
    if argv[:1] == ["--skip"] and len(argv) >= 3:
        try:
            print(skip_session(kb_dir, argv[1], " ".join(argv[2:])))
            return 0
        except ValueError as exc:
            print(f"session_end: {exc}", file=sys.stderr)
            return 1
    if argv[:1] == ["--list-pending"]:
        from onshape_mcp.kb_pending import list_staged

        for row in list_staged(kb_dir):
            print(json.dumps(row))
        return 0
    if argv[:1] == ["--archive"] and len(argv) >= 2:
        from onshape_mcp.kb_pending import archive_pending

        rest = argv[2:]
        opt = {"--card": None, "--robot": None}
        for k in opt:
            if k in rest and rest.index(k) + 1 < len(rest):
                opt[k] = rest[rest.index(k) + 1]
        try:
            print(
                archive_pending(
                    kb_dir,
                    argv[1],
                    Path(opt["--card"]) if opt["--card"] else None,
                    robot=opt["--robot"],
                    with_transcript="--with-transcript" in rest,
                )
            )
            return 0
        except ValueError as exc:
            print(f"session_end: {exc}", file=sys.stderr)
            return 1
    if argv[:1] == ["--discard"] and len(argv) >= 2:
        from onshape_mcp.kb_pending import discard_pending

        note = " ".join(a for a in argv[2:] if a != "--keep")
        try:
            print(discard_pending(kb_dir, argv[1], note, keep="--keep" in argv))
            return 0
        except ValueError as exc:
            print(f"session_end: {exc}", file=sys.stderr)
            return 1
    from onshape_mcp.kb_pending import stage_main as stage_main_chat
    from onshape_mcp.kb_pending import stage_subagents

    only_stage = argv[:1] == ["--stage"]
    stage_main = "--stage-main" in argv or os.environ.get("KB_STAGE_MAIN") == "1"
    argv = [a for a in argv if a not in ("--stage", "--stage-main")]
    paths = [Path(p) for p in argv]
    if not paths and not sys.stdin.isatty():
        try:
            hook = json.load(sys.stdin)
            paths = [Path(hook["transcript_path"])]
        except (ValueError, KeyError) as exc:
            print(f"session_end: no transcript ({exc})", file=sys.stderr)
            return 0
    for path in paths:
        try:
            if only_stage:
                pass
            elif stage_main:
                print(json.dumps(stage_main_chat(kb_dir, path)))
            else:
                print(json.dumps(archive_transcript(kb_dir, path)))
            for row in stage_subagents(kb_dir, path):
                print(json.dumps(row))
        except Exception as exc:
            print(f"session_end: {path}: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
