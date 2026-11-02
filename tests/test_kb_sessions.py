"""Design workspaces: session cards, pasted images, lessons, archived chats."""

import base64
import json
import subprocess
import sys
from pathlib import Path

import pytest

from onshape_mcp import kb_sessions as ks
from onshape_mcp.kb import KnowledgeBase
from onshape_mcp.kb_design import subsystem_prompt
from onshape_mcp.kb_tools import call_kb_tool

# 1×1 PNG
PNG = base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
        "1f15c4890000000d49444154789c63f8cfc0f01f0005000201a5f6a0d500"
        "00000049454e44ae426082"
    )
).decode()


@pytest.fixture
def kb_dir(tmp_path):
    d = tmp_path / "kb"
    (d / "rules" / "2026-27").mkdir(parents=True)
    (d / "rules" / "2026-27" / "constraints.json").write_text("{}")
    (d / "lessons.md").write_text(
        "# Lessons\n\n## Design\n- Check the budget first.\n\n## Workflow\n"
        "- Never use execute_code.\n"
    )
    return d


def _transcript(tmp_path, robot="bb1", image=False, secret=False):
    def user(text, extra=None):
        content = [{"type": "text", "text": text}] + (extra or [])
        return {
            "type": "user",
            "sessionId": "abcd1234-0000",
            "timestamp": "2026-10-21T15:04:00Z",
            "message": {"role": "user", "content": content},
        }

    lines = [
        user(
            "<system-reminder>ignore me</system-reminder>Let's work on the shooter."
            + (
                " key on_ziJIB5ftsw1b6XamUfWIC secret is lSxIZAZo19JN044UyEQx8Ioz"
                "cXfQNpE7qwOy6Kqc4zEL50k1"
                if secret
                else ""
            ),
            [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": PNG,
                    },
                }
            ]
            if image
            else None,
        ),
        {
            "type": "assistant",
            "timestamp": "2026-10-21T15:05:00Z",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Opening the design file."},
                    {
                        "type": "tool_use",
                        "name": "mcp__onshape__robot_design",
                        "input": {"action": "get", "robot": robot},
                    },
                ],
            },
        },
        {"type": "user", "isSidechain": True, "message": {"content": "subagent noise"}},
        {
            "type": "user",
            "message": {
                "content": [{"type": "tool_result", "content": "huge tool output"}]
            },
        },
    ]
    path = tmp_path / "t.jsonl"
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\nnot json\n")
    return path


# ── redaction ────────────────────────────────────────────────────────


def test_redact_hides_keys_but_keeps_ordinary_text():
    text = (
        "access on_ziJIB5ftsw1b6XamUfWIC and secret key is "
        "lSxIZAZo19JN044UyEQx8IozcXfQNpE7qwOy6Kqc4zEL50k1; commit 26adb4f ok"
    )
    out = ks.redact(text)
    assert "on_ziJIB" not in out and "lSxIZ" not in out
    assert out.count("[redacted]") == 2
    assert "commit 26adb4f ok" in out


# ── session cards ────────────────────────────────────────────────────


def test_save_session_writes_card_lessons_and_pending(kb_dir):
    out = ks.save_session(
        kb_dir,
        title="Shooter v1",
        robot="BB1",
        subsystem="shooter",
        summary="Picked a counter roller.",
        tool_lessons=["join_on_holes needs the fixed part grounded first."],
        decisions=["Counter roller — fits the 2-motor budget."],
        entries_used=["cb-x/shooter"],
        robot_lessons=["Hood needs 2 mm clearance on our printer."],
        general_lessons=["Check the budget first.", "Render after every joint."],
    )
    card = next((kb_dir / "designs" / "bb1" / "sessions").glob("*-shooter.md"))
    text = card.read_text()
    assert text.index("## Tool lessons") < text.index("## Decisions and why")
    assert 'entries: ["cb-x/shooter"]' in text
    learned = (kb_dir / "designs" / "bb1" / "learned.md").read_text()
    assert "2 mm clearance" in learned
    # the lesson already in lessons.md is not proposed again
    assert ks.list_pending(kb_dir) == "p1: Render after every joint."
    assert "1 general lesson(s) waiting" in out
    # same robot lesson again is not duplicated
    ks.save_session(
        kb_dir,
        title="Again",
        robot="bb1",
        robot_lessons=["Hood needs 2 mm clearance on our printer."],
    )
    assert learned == (kb_dir / "designs" / "bb1" / "learned.md").read_text()


def test_save_session_caps(kb_dir):
    with pytest.raises(ValueError, match="≤ 40 words"):
        ks.save_session(kb_dir, title="t", tool_lessons=["word " * 41])
    with pytest.raises(ValueError, match="wouldn't change"):
        ks.save_session(kb_dir, title="t", summary="w " * 451)
    with pytest.raises(ValueError, match="title"):
        ks.save_session(kb_dir, title=" ")


def test_sessions_without_robot_go_to_general(kb_dir):
    ks.save_session(kb_dir, title="Planning the KB")
    assert list((kb_dir / "designs" / "_general" / "sessions").glob("*.md"))


def test_approve_and_reject_pending_lessons(kb_dir):
    ks.add_pending(kb_dir, ["Render after every joint.", "Name parts right away."])
    out = ks.decide_pending(kb_dir, ["p1"], approve=True, section="Workflow")
    assert "Added to lessons.md (Workflow): p1" == out
    lessons = (kb_dir / "lessons.md").read_text()
    workflow = lessons[lessons.index("## Workflow") :]
    assert "- Render after every joint." in workflow
    assert lessons.index("## Design") < lessons.index("## Workflow")
    ks.decide_pending(kb_dir, ["p2"], approve=False)
    assert ks.list_pending(kb_dir) == "No lessons waiting for approval."
    with pytest.raises(ValueError, match="Unknown"):
        ks.decide_pending(kb_dir, ["p9"], approve=True)


def test_approve_into_new_section(kb_dir):
    ks.add_pending(kb_dir, ["Use kb_find_part before modeling COTS."])
    ks.decide_pending(kb_dir, ["p1"], approve=True, section="Tools")
    assert "## Tools\n- Use kb_find_part" in (kb_dir / "lessons.md").read_text()


# ── archiving transcripts ────────────────────────────────────────────


def test_archive_transcript_copies_chat_images_and_queues(kb_dir, tmp_path):
    result = ks.archive_transcript(
        kb_dir, _transcript(tmp_path, image=True, secret=True)
    )
    assert result["robot"] == "bb1" and result["images"] == 1
    assert result["needs_card"] is True
    chat = (kb_dir / result["chat"]).read_text()
    assert "Let's work on the shooter." in chat
    assert "ignore me" not in chat and "subagent noise" not in chat
    assert "huge tool output" not in chat and "on_ziJIB" not in chat
    assert "[image 2026-10-21-abcd1234-1.jpg]" in chat
    imgs = list((kb_dir / "designs" / "bb1" / "images").iterdir())
    assert imgs and imgs[0].stem == "2026-10-21-abcd1234-1"
    assert "past session(s) need a card" in ks.pending_summary(kb_dir)
    assert "image(s) need a caption" in ks.pending_summary(kb_dir)
    # a card with captions clears the to-do entry
    ks.save_session(
        kb_dir,
        title="Shooter",
        robot="bb1",
        session_id="abcd1234-0000",
        image_captions={"2026-10-21-abcd1234-1.jpg": "Hood sketch"},
    )
    assert ks.pending_summary(kb_dir) == ""
    assert (kb_dir / "designs" / "bb1" / "images" / "2026-10-21-abcd1234-1.md").exists()


def test_archive_is_idempotent_and_skips_queue_when_card_exists(kb_dir, tmp_path):
    t = _transcript(tmp_path)
    ks.save_session(kb_dir, title="Shooter", robot="bb1", session_id="abcd1234-0000")
    first = ks.archive_transcript(kb_dir, t)
    second = ks.archive_transcript(kb_dir, t)
    assert first == second and first["needs_card"] is False
    assert ks.pending_summary(kb_dir) == ""


def test_session_end_script_reads_hook_json(kb_dir, tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts" / "kb" / "session_end.py"
    hook = json.dumps(
        {"session_id": "x", "transcript_path": str(_transcript(tmp_path))}
    )
    out = subprocess.run(
        [sys.executable, "-I", str(script), "--kb", str(kb_dir)],
        input=hook,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(out.stdout)["robot"] == "bb1"


# ── search and prompts ───────────────────────────────────────────────


def test_index_covers_sessions_images_lessons_and_chunked_chats(kb_dir, tmp_path):
    ks.archive_transcript(kb_dir, _transcript(tmp_path, image=True))
    ks.save_session(
        kb_dir,
        title="Shooter hood",
        robot="bb1",
        tool_lessons=["insert_part reuses a component on reinsert."],
        robot_lessons=["Hood pivot sits 30 cm up."],
        image_captions={"2026-10-21-abcd1234-1.jpg": "Whiteboard hood"},
    )
    long_chat = "\n".join(f"### You 10:{n:02d}\n\n" + "hood " * 300 for n in range(6))
    chats = kb_dir / "designs" / "bb1" / "chats"
    (chats / "2026-10-22-long.md").write_text(f"---\ntitle: Long\n---\n\n{long_chat}")
    kb = KnowledgeBase(kb_dir)
    stats = kb.stats()
    assert stats["session"] == 1 and stats["image"] == 1 and stats["lesson"] == 1
    assert stats["chat"] >= 3  # the long chat is split into chunks
    hits = kb.search("hood", limit=20)
    kinds = [h["kind"] for h in hits]
    assert kinds.index("session") < kinds.index("chat")
    assert kb.get("bb1/learned")["kind"] == "lesson"


def test_prompt_mentions_waiting_items_and_session_card(kb_dir, tmp_path):
    ks.archive_transcript(kb_dir, _transcript(tmp_path))
    text = subsystem_prompt(kb_dir, "bb1", "shooter")
    assert "Waiting from past sessions" in text
    assert "kb_save_session" in text


def test_tools_save_session_and_lessons(kb_dir):
    kb = KnowledgeBase(kb_dir)
    out = call_kb_tool(
        "kb_save_session",
        {"title": "Drive v1", "robot": "bb1", "general_lessons": ["Ground first."]},
        kb,
    )
    assert not out.isError and "Saved designs/bb1/sessions/" in out.content[0].text
    assert (
        "p1: Ground first."
        in call_kb_tool("kb_lessons", {"action": "list"}, kb).content[0].text
    )
    ok = call_kb_tool(
        "kb_lessons", {"action": "approve", "ids": ["p1"], "section": "Workflow"}, kb
    )
    assert "Added to lessons.md" in ok.content[0].text
    bad = call_kb_tool("kb_lessons", {"action": "nope"}, kb)
    assert bad.isError


def test_skip_session_clears_queue_and_is_not_requeued(kb_dir, tmp_path):
    t = _transcript(tmp_path)
    ks.archive_transcript(kb_dir, t)
    assert [r["session_id"] for r in ks.todo_list(kb_dir)] == ["abcd1234-0000"]
    with pytest.raises(ValueError, match="why"):
        ks.skip_session(kb_dir, "abcd1234", " ")
    assert "Skipped abcd1234-0000" in ks.skip_session(
        kb_dir, "abcd1234", "Install help only; nothing for CAD."
    )
    assert ks.todo_list(kb_dir) == []
    assert ks.archive_transcript(kb_dir, t)["skipped"] is True
    assert ks.todo_list(kb_dir) == []
    assert (
        "Install help only" in (kb_dir / "ingest" / "sessions_skipped.csv").read_text()
    )


def test_action_items_from_cards_and_cli(kb_dir):
    out = ks.save_session(
        kb_dir,
        title="Planning",
        session_id="cf04c090-xxxx",
        date="2026-10-20",
        action_items=[
            "tool: Add export_dxf (sketch.saveAsDXF) for laser plates.",
            "bug: close_document with no name closed the active document.",
        ],
    )
    assert "2 new action item(s)" in out
    text = (kb_dir / "action-items.md").read_text()
    assert (
        "- [ ] [tool] Add export_dxf (sketch.saveAsDXF) for laser plates. — "
        "from 2026-10-20 cf04c090" in text
    )
    # duplicates (even reworded case/punctuation) are skipped; kinds are checked
    assert (
        ks.add_actions(
            kb_dir, ["tool: add export_dxf (sketch.saveAsDXF) for laser plates"]
        )
        == []
    )
    with pytest.raises(ValueError, match="kind"):
        ks.add_actions(kb_dir, ["make it better"])
    assert [a["kind"] for a in ks.open_actions(kb_dir)] == ["tool", "bug"]


def test_find_session_by_marker(tmp_path):
    (tmp_path / "aaa.jsonl").write_text('{"text": "echo marker-1234abcd"}\n')
    (tmp_path / "bbb.jsonl").write_text('{"text": "something else"}\n')
    assert ks.find_session(tmp_path, "marker-1234abcd") == ["aaa"]
    with pytest.raises(ValueError):
        ks.find_session(tmp_path, "short")
