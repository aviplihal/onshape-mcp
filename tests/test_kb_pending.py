"""Staging subagent transcripts: condense, review, then archive."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from onshape_mcp import kb_pending as kp
from onshape_mcp import kb_sessions as ks
from onshape_mcp.kb import KnowledgeBase

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "kb" / "session_end.py"
BIG = "X" * 50000


@pytest.fixture
def kb_dir(tmp_path):
    d = tmp_path / "kb"
    (d / "rules" / "2026-27").mkdir(parents=True)
    (d / "rules" / "2026-27" / "constraints.json").write_text("{}")
    (d / "lessons.md").write_text("# Lessons\n\n## Workflow\n- Be careful.\n")
    return d


@pytest.fixture
def session(tmp_path):
    """<proj>/<sid>.jsonl (main chat) + <proj>/<sid>/subagents/agent-*.jsonl."""
    proj = tmp_path / "proj"
    sid = "abcd1234-0000-1111"
    sub = proj / sid / "subagents"
    sub.mkdir(parents=True)
    main = [
        {
            "type": "user",
            "sessionId": sid,
            "timestamp": "2026-10-22T10:00:00Z",
            "message": {"content": "Build the shooter."},
        },
        {
            "type": "assistant",
            "timestamp": "2026-10-22T10:01:00Z",
            "message": {"content": [{"type": "text", "text": "On it."}]},
        },
    ]
    (proj / f"{sid}.jsonl").write_text("\n".join(json.dumps(x) for x in main) + "\n")
    agent = [
        {
            "type": "user",
            "isSidechain": True,
            "timestamp": "2026-10-22T10:02:00Z",
            "message": {"content": "Build from card kb/designs/bb1/cards/shooter.md"},
        },
        {"type": "attachment", "attachment": {"text": BIG}},
        {"type": "api-request-blob", "blob": BIG},
        {
            "type": "assistant",
            "isSidechain": True,
            "timestamp": "2026-10-22T10:03:00Z",
            "message": {
                "content": [
                    {"type": "thinking", "thinking": "secret plan " + BIG},
                    {"type": "text", "text": "Creating the master sketch."},
                    {
                        "type": "tool_use",
                        "name": "mcp__onshape__create_sketch",
                        "input": {"name": "master", "plane": "XY"},
                    },
                    {
                        "type": "tool_use",
                        "name": "mcp__onshape__robot_design",
                        "input": {"action": "get", "robot": "bb1"},
                    },
                ]
            },
        },
        {
            "type": "user",
            "isSidechain": True,
            "message": {
                "content": [
                    {"type": "tool_result", "content": BIG},
                    {
                        "type": "tool_result",
                        "is_error": True,
                        "content": [
                            {"type": "text", "text": "NO_ACTIVE_DESIGN " + BIG}
                        ],
                    },
                    {
                        "type": "image",
                        "source": {"type": "base64", "data": BIG},
                    },
                ]
            },
        },
    ]
    path = sub / "agent-a1b2c3d4e5f6.jsonl"
    path.write_text("\n".join(json.dumps(x) for x in agent) + "\n")
    (sub / "agent-a1b2c3d4e5f6.meta.json").write_text(
        json.dumps({"agentType": "cad-builder", "description": "Build the shooter"})
    )
    return proj / f"{sid}.jsonl"


def test_stage_condenses_drops_results_and_is_idempotent(kb_dir, session):
    rows = kp.stage_subagents(kb_dir, session)
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == "2026-10-22-abcd1234-a1b2c3d4"
    assert row["agent_type"] == "cad-builder" and row["robot"] == "bb1"
    assert row["status"] == "pending"
    text = (kb_dir / row["transcript"]).read_text()
    assert "Creating the master sketch." in text
    assert "`create_sketch` name=master plane=XY" in text
    assert "Build from card" in text
    assert "ERROR: NO_ACTIVE_DESIGN" in text
    assert "secret plan" not in text and "X" * 500 not in text
    assert row["bytes"] < row["raw_bytes"] / 20
    # staging twice adds nothing
    assert kp.stage_subagents(kb_dir, session) == []
    assert len(kp.list_staged(kb_dir)) == 1


def test_staged_text_never_enters_the_index(kb_dir, session):
    kp.stage_subagents(kb_dir, session)
    kb = KnowledgeBase(kb_dir)
    assert kb.stats().get("chat", 0) == 0 and kb.stats().get("session", 0) == 0
    assert kb.search("master sketch") == []


def test_secrets_redacted_in_staged_text(kb_dir, session):
    sub = session.with_suffix("") / "subagents" / "agent-a1b2c3d4e5f6.jsonl"
    lines = sub.read_text().splitlines()
    lines.append(
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "text", "text": "key on_ziJIB5ftsw1b6XamUfWIC"}
                    ]
                },
            }
        )
    )
    sub.write_text("\n".join(lines))
    row = kp.stage_subagents(kb_dir, session)[0]
    assert "on_ziJIB" not in (kb_dir / row["transcript"]).read_text()


def test_archive_moves_card_into_robot_workspace_and_indexes_it(kb_dir, session):
    row = kp.stage_subagents(kb_dir, session)[0]
    with pytest.raises(ValueError, match="transcript-reviewer"):
        kp.archive_pending(kb_dir, row["id"])
    card = kp.card_path(kb_dir, row["id"])
    card.parent.mkdir(parents=True)
    card.write_text(
        "# Shooter review\n\n## Tool lessons\n- join_on_holes: flywheelgrounded.\n"
        ""
    )
    assert kp.list_staged(kb_dir)[0]["card_ready"] is True
    out = kp.archive_pending(kb_dir, "a1b2c3d4", with_transcript=True)
    assert "sessions/2026-10-22-cad-builder-a1b2c3d4.md" in out
    ws = kb_dir / "designs" / "bb1"
    assert (ws / "chats" / f"{row['id']}.md").is_file()
    assert "Shooter review" in next((ws / "sessions").glob("*.md")).read_text()
    assert kp.list_staged(kb_dir) == []
    assert kp.list_staged(kb_dir, "archived")[0]["card"].endswith("a1b2c3d4.md")
    assert not (kb_dir / "_pending" / "transcripts" / f"{row['id']}.md").exists()
    with pytest.raises(ValueError, match="already archived"):
        kp.archive_pending(kb_dir, row["id"])
    # staging again after archive does not resurrect it
    assert kp.stage_subagents(kb_dir, session) == []
    hits = KnowledgeBase(kb_dir).search("flywheelgrounded")
    assert hits and hits[0]["kind"] == "session"


def test_discard_and_keep(kb_dir, session):
    row = kp.stage_subagents(kb_dir, session)[0]
    assert "Discarded" in kp.discard_pending(kb_dir, row["id"], "builder was lost")
    assert not (kb_dir / row["transcript"]).exists()
    assert kp.list_staged(kb_dir) == []
    assert kp.list_staged(kb_dir, "discarded")[0]["note"] == "builder was lost"
    assert kp.stage_subagents(kb_dir, session) == []


def test_keep_leaves_files_with_note(kb_dir, session):
    row = kp.stage_subagents(kb_dir, session)[0]
    kp.discard_pending(kb_dir, row["id"], "maybe later", keep=True)
    assert (kb_dir / row["transcript"]).is_file()
    assert kp.list_staged(kb_dir, "kept")


def test_main_chat_archiving_unchanged_by_default(kb_dir, session):
    result = ks.archive_transcript(kb_dir, session)
    assert result["messages"] == 2
    assert list((kb_dir / "designs" / "_general" / "chats").glob("*.md"))
    assert not (kb_dir / "_pending").exists()


def _run(kb_dir, *args, stdin=None, env=None):
    import os

    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT), "--kb", str(kb_dir), *args],
        input=stdin,
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )


def test_hook_stages_subagents_and_archives_main_chat(kb_dir, session):
    hook = json.dumps({"transcript_path": str(session)})
    out = _run(kb_dir, stdin=hook)
    assert out.returncode == 0
    assert (kb_dir / "designs" / "_general" / "chats").is_dir()
    pend = _run(kb_dir, "--list-pending").stdout.strip().splitlines()
    assert len(pend) == 1 and json.loads(pend[0])["agent_type"] == "cad-builder"
    # hook runs again at the next session end: nothing doubles
    _run(kb_dir, stdin=hook)
    assert len(_run(kb_dir, "--list-pending").stdout.strip().splitlines()) == 1


def test_stage_main_flag_stages_instead_of_archiving(kb_dir, session):
    hook = json.dumps({"transcript_path": str(session)})
    _run(kb_dir, "--stage-main", stdin=hook)
    assert not (kb_dir / "designs").exists()
    ids = [
        json.loads(x)["id"] for x in _run(kb_dir, "--list-pending").stdout.splitlines()
    ]
    assert "2026-10-22-abcd1234-main" in ids
    # env var does the same
    other = kb_dir.parent / "kb2"
    _run(other, stdin=hook, env={"KB_STAGE_MAIN": "1"})
    assert not (other / "designs").exists() and (other / "_pending").exists()


def test_cli_archive_and_discard(kb_dir, session):
    _run(kb_dir, "--stage", str(session))
    ids = [
        json.loads(x)["id"] for x in _run(kb_dir, "--list-pending").stdout.splitlines()
    ]
    card = kb_dir.parent / "card.md"
    card.write_text("# Review\n\nBuilt the shooter.\n")
    bad = _run(kb_dir, "--archive", ids[0], "--card", str(kb_dir.parent / "nope.md"))
    assert bad.returncode == 1
    ok = _run(kb_dir, "--archive", ids[0], "--card", str(card), "--robot", "bb2")
    assert ok.returncode == 0 and (kb_dir / "designs" / "bb2" / "sessions").is_dir()
    assert _run(kb_dir, "--discard", ids[0]).returncode == 1  # already archived
