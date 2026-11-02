"""Stage subagent transcripts, review them, then archive (no tokens in staging).

    kb/_pending/index.csv                   one row per staged transcript
    kb/_pending/transcripts/<id>.md         condensed transcript (unindexed)
    kb/_pending/cards/<id>.md               reviewed card (transcript-reviewer)
    -> on archive:
    kb/designs/<robot>/sessions/<date>-<agent>-<id8>.md   the card (indexed)
    kb/designs/<robot>/chats/<id>.md                      the transcript (optional)

Nothing in kb/_pending/ is indexed (kb._indexed_files only looks at known folders)
and it is git-ignored. A pending entry becomes searchable only after a reviewed
card is archived, which happens when the user has seen the card and said OK.
`<id>` is `<date>-<session8>-<agent8>` for a subagent; the main chat, staged
with `stage_main` (SessionEnd hook flag `--stage-main` or env KB_STAGE_MAIN=1)
instead of archived directly, is `<date>-<session8>-main`.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .kb_design import slug
from .kb_sessions import (
    _NOISE_RE,
    GENERAL,
    _entries,
    _robot_of,
    _today,
    redact,
    workspace,
)

FIELDS = [
    "id", "session_id", "agent_id", "agent_type", "description", "robot", "date",
    "status", "transcript", "card", "note",
]  # fmt: skip
PROMPT_MAX = 4000  # first prompt: it holds the cards the builder was given
TEXT_MAX = 3000
ARG_MAX = 80
ERROR_MAX = 200
LONG_ARGS = {"code"}  # execute_code bodies: show only the head


def pending_dir(kb_dir: Path) -> Path:
    return kb_dir / "_pending"


def card_path(kb_dir: Path, ident: str) -> Path:
    return pending_dir(kb_dir) / "cards" / f"{ident}.md"


def _index_path(kb_dir: Path) -> Path:
    return pending_dir(kb_dir) / "index.csv"


def _rows(kb_dir: Path) -> list[dict]:
    path = _index_path(kb_dir)
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [{k: r.get(k) or "" for k in FIELDS} for r in csv.DictReader(f)]


def _write_rows(kb_dir: Path, rows: list[dict]) -> None:
    path = _index_path(kb_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def _clip(text: str, n: int) -> str:
    text = text.strip()
    return (
        text if len(text) <= n else text[:n].rstrip() + f" [...+{len(text) - n} chars]"
    )


def _args(inp: dict) -> str:
    bits = []
    for k, v in (inp or {}).items():
        if isinstance(v, (dict, list)):
            v = json.dumps(v, separators=(",", ":"))
        v = " ".join(str(v).split())
        n = 40 if k in LONG_ARGS else ARG_MAX
        bits.append(f"{k}={v[:n]}" + ("..." if len(v) > n else ""))
    return " ".join(bits)[:300]


def condense(entries: list[dict]) -> tuple[list[str], int]:
    """Text blocks and one line per tool call; tool results, thinking, images,
    attachments and API blobs are dropped (error results keep one short line).
    Returns (markdown parts, number of tool calls)."""
    parts, calls, first_user = [], 0, True
    for e in entries:
        kind = e.get("type")
        if kind not in ("user", "assistant"):
            continue
        content = (e.get("message") or {}).get("content")
        blocks = (
            [{"type": "text", "text": content}]
            if isinstance(content, str)
            else [b for b in content or [] if isinstance(b, dict)]
        )
        lines = []
        for b in blocks:
            t = b.get("type")
            if t == "text":
                text = redact(_NOISE_RE.sub("", b.get("text") or "")).strip()
                if text:
                    cap = PROMPT_MAX if first_user and kind == "user" else TEXT_MAX
                    lines.append(_clip(text, cap))
            elif t == "tool_use":
                calls += 1
                name = str(b.get("name", "")).removeprefix("mcp__onshape__")
                lines.append(f"- `{name}` " + redact(_args(b.get("input"))))
            elif t == "tool_result" and b.get("is_error"):
                body = b.get("content")
                if isinstance(body, list):
                    body = " ".join(
                        str(x.get("text", "")) for x in body if isinstance(x, dict)
                    )
                body = redact(" ".join(str(body).split()))[:ERROR_MAX]
                lines.append(f"- ERROR: {body}")
        if lines:
            who = "Prompt" if kind == "user" else "Agent"
            when = (e.get("timestamp") or "")[11:16]
            parts.append(f"### {who} {when}\n\n" + "\n".join(lines) + "\n")
        if kind == "user":
            first_user = False
    return parts, calls


def _meta(path: Path) -> dict:
    try:
        return json.loads(path.with_suffix(".meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _stage_one(
    kb_dir: Path,
    entries: list[dict],
    *,
    session: str,
    agent_id: str,
    agent_type: str,
    desc: str,
    source: Path,
) -> dict | None:
    date = next((e["timestamp"][:10] for e in entries if e.get("timestamp")), _today())
    ident = f"{date}-{session[:8]}-{agent_id[:8]}"
    rows = _rows(kb_dir)
    if any(r["id"] == ident for r in rows):
        return None  # idempotent: already staged, archived or discarded
    parts, calls = condense(entries)
    if not parts:
        return None
    robot = _robot_of(entries)
    if not desc:
        first = parts[0].split("\n\n", 1)[-1]
        desc = " ".join(first.split())[:120]
    body = (
        f"---\ntitle: {agent_type or 'agent'} transcript {ident}\n"
        f"robot: {robot or GENERAL}\nsession_id: {session}\nagent_id: {agent_id}\n"
        f"date: {date}\n---\n\n" + "\n".join(parts)
    )
    out = pending_dir(kb_dir) / "transcripts" / f"{ident}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")
    row = {
        "id": ident, "session_id": session, "agent_id": agent_id,
        "agent_type": agent_type, "description": " ".join(desc.split()),
        "robot": robot or GENERAL, "date": date, "status": "pending",
        "transcript": str(out.relative_to(kb_dir)), "card": "", "note": "",
    }  # fmt: skip
    _write_rows(kb_dir, rows + [row])
    return {
        **row,
        "tool_calls": calls,
        "raw_bytes": source.stat().st_size,
        "bytes": len(body.encode()),
    }


def stage_subagents(kb_dir: Path, transcript: Path) -> list[dict]:
    """Condense every subagent transcript of this session into kb/_pending/.
    Skips ones already staged (any status). Returns the newly staged rows."""
    folder = transcript.with_suffix("") / "subagents"
    staged = []
    for path in sorted(folder.glob("agent-*.jsonl")) if folder.is_dir() else []:
        entries = list(_entries(path))
        if not entries:
            continue
        agent_id = path.stem.removeprefix("agent-")
        meta = _meta(path)
        row = _stage_one(
            kb_dir, entries, session=transcript.stem, agent_id=agent_id,
            agent_type=meta.get("agentType", ""), desc=meta.get("description", ""),
            source=path,
        )  # fmt: skip
        if row:
            staged.append(row)
    return staged


def stage_main(kb_dir: Path, transcript: Path) -> dict | None:
    """Same flow for the main conversation (opt-in): staged instead of archived."""
    entries = [e for e in _entries(transcript) if not e.get("isSidechain")]
    if not entries:
        return None
    return _stage_one(
        kb_dir, entries, session=transcript.stem, agent_id="main",
        agent_type="main", desc="", source=transcript,
    )  # fmt: skip


def list_staged(kb_dir: Path, status: str | None = "pending") -> list[dict]:
    rows = [r for r in _rows(kb_dir) if status in (None, r["status"])]
    for r in rows:
        r["card_ready"] = card_path(kb_dir, r["id"]).is_file()
    return rows


def _find(kb_dir: Path, ident: str) -> tuple[list[dict], dict]:
    rows = _rows(kb_dir)
    match = [r for r in rows if r["id"] == ident or r["id"].endswith("-" + ident)]
    if len(match) != 1:
        raise ValueError(f"'{ident}' matches {len(match)} staged transcripts")
    return rows, match[0]


def archive_pending(
    kb_dir: Path,
    ident: str,
    card: Path | None = None,
    *,
    robot: str | None = None,
    with_transcript: bool = False,
) -> str:
    """Move a reviewed card (and optionally the condensed transcript) into the
    robot's workspace so the indexer picks it up. Only call after the user OKs."""
    rows, row = _find(kb_dir, ident)
    if row["status"] != "pending":
        raise ValueError(f"{row['id']} is already {row['status']}")
    src = Path(card) if card else card_path(kb_dir, row["id"])
    if not src.is_file():
        raise ValueError(
            f"No reviewed card at {src}: run the transcript-reviewer first."
        )
    text = src.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError("The card is empty.")
    robot = robot or (row["robot"] if row["robot"] != GENERAL else None)
    ws = workspace(kb_dir, robot)
    if not text.startswith("---"):
        title = next(
            (ln.lstrip("# ").strip() for ln in text.splitlines() if ln.strip()),
            row["id"],
        )
        text = (
            f"---\ntitle: {title[:80]}\nrobot: {robot or GENERAL}\n"
            f"date: {row['date']}\n"
            f"source: {row['agent_type'] or 'agent'} transcript {row['id']}\n---\n\n"
            + text
        )
    name = f"{row['date']}-{slug(row['agent_type'] or 'agent')}-{row['id'][-8:]}"
    dest = ws / "sessions" / f"{name}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(redact(text), encoding="utf-8")
    out = [f"Archived card to {dest.relative_to(kb_dir)}"]
    transcript = kb_dir / row["transcript"] if row["transcript"] else None
    if with_transcript and transcript and transcript.is_file():
        chat = ws / "chats" / f"{row['id']}.md"
        chat.parent.mkdir(parents=True, exist_ok=True)
        chat.write_text(transcript.read_text(encoding="utf-8"), encoding="utf-8")
        out.append(f"Archived transcript to {chat.relative_to(kb_dir)}")
    if transcript:
        transcript.unlink(missing_ok=True)
    if pending_dir(kb_dir) in src.resolve().parents:
        src.unlink(missing_ok=True)
    row.update(status="archived", card=str(dest.relative_to(kb_dir)), transcript="")
    _write_rows(kb_dir, rows)
    return "\n".join(out)


def discard_pending(
    kb_dir: Path, ident: str, note: str = "", keep: bool = False
) -> str:
    """Reject a staged transcript: delete its files, or keep them (still not
    indexed) with a note."""
    rows, row = _find(kb_dir, ident)
    if row["status"] != "pending":
        raise ValueError(f"{row['id']} is already {row['status']}")
    if not keep:
        if row["transcript"]:
            (kb_dir / row["transcript"]).unlink(missing_ok=True)
        card_path(kb_dir, row["id"]).unlink(missing_ok=True)
        row["transcript"] = ""
    row.update(status="kept" if keep else "discarded", note=" ".join(note.split()))
    _write_rows(kb_dir, rows)
    return f"{'Kept (not indexed)' if keep else 'Discarded'} {row['id']}"
