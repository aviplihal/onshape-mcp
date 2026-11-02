"""Per-robot design workspace: session cards, pasted images, robot lessons, chats.

    kb/designs/<robot>/
      design.md                 robot design file (kb_design.py)
      sessions/<date>-<slug>.md session card            kind=session
      images/<name>.jpg + .md   pasted image + caption  kind=image (caption indexed)
      learned.md                lessons about this robot kind=lesson
      chats/<date>-<sid8>.md    conversation text        kind=chat, local only
    kb/designs/_general/        same layout for sessions not about one robot
    kb/lessons-pending.md       general lessons waiting for the user's OK
    kb/ingest/sessions_todo.csv sessions archived without a card, or with
                                uncaptioned images (local)
    kb/ingest/sessions_skipped.csv sessions judged not worth a card, with why
    kb/action-items.md          things sessions said need building or fixing

What matters while CADing a robot is how to use the tools, so session cards lead
with tool lessons, and anything that wouldn't change how the next part is built
is left out.
"""

from __future__ import annotations

import base64
import csv
import datetime
import json
import re
import shutil
import subprocess
from pathlib import Path

from .kb_design import slug

GENERAL = "_general"  # pseudo-robot for sessions not about one robot
ITEM_MAX_WORDS = 40
CARD_MAX_WORDS = 450
LESSONS_MAX_LINES = 150
TODO_FIELDS = ["session_id", "date", "robot", "transcript", "needs_card", "images"]
CARD_LISTS = (
    ("tool_lessons", "Tool lessons"),
    ("decisions", "Decisions and why"),
    ("rejected", "Rejected and why"),
    ("open_questions", "Open questions"),
)

# Secrets pasted into chats: API keys and long random tokens.
_SECRET_RES = [
    re.compile(r"\bon_[A-Za-z0-9]{16,}\b"),
    re.compile(
        r"(?i)\b(secret|api[_ -]?key|access[_ -]?key|token|password)"
        r"(\s*(?:key)?\s*(?:is|:|=)?\s*)([A-Za-z0-9_\-./+]{12,})"
    ),
    re.compile(
        r"\b(?=[A-Za-z0-9]*[a-z])(?=[A-Za-z0-9]*[A-Z])(?=[A-Za-z0-9]*\d)"
        r"[A-Za-z0-9]{32,}\b"
    ),
]
_NOISE_RE = re.compile(
    r"<(system-reminder|task-notification|local-command-[a-z]+|command-[a-z]+|"
    r"ide_[a-z_]+)[^>]*>.*?</\1>",
    re.S,
)


def _today() -> str:
    return datetime.date.today().isoformat()


def _words(text: str) -> int:
    return len((text or "").split())


def redact(text: str) -> str:
    text = _SECRET_RES[0].sub("[redacted]", text)
    text = _SECRET_RES[1].sub(lambda m: m.group(1) + m.group(2) + "[redacted]", text)
    return _SECRET_RES[2].sub("[redacted]", text)


def workspace(kb_dir: Path, robot: str | None) -> Path:
    return (
        kb_dir / "designs" / (GENERAL if not robot or robot == GENERAL else slug(robot))
    )


# ── session cards (written by Claude during the session) ─────────────


def _clean_items(items, field: str) -> list[str]:
    out = []
    for item in items or []:
        item = " ".join(str(item).split())
        if not item:
            continue
        if _words(item) > ITEM_MAX_WORDS:
            raise ValueError(
                f"{field}: keep each item ≤ {ITEM_MAX_WORDS} words ({item[:40]}…)"
            )
        out.append(item)
    return out


def _norm(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def _append_unique(path: Path, header: str, items: list[str]) -> list[str]:
    """Append bullets to a markdown file, skipping ones already there."""
    existing = path.read_text(encoding="utf-8") if path.is_file() else header
    seen = {_norm(line[2:]) for line in existing.splitlines() if line.startswith("- ")}
    new = [i for i in items if _norm(i) not in seen]
    if new:
        path.parent.mkdir(parents=True, exist_ok=True)
        text = existing.rstrip("\n") + "\n" + "".join(f"- {i}\n" for i in new)
        path.write_text(text, encoding="utf-8")
    return new


def save_session(
    kb_dir: Path,
    *,
    title: str,
    robot: str | None = None,
    subsystem: str | None = None,
    summary: str = "",
    tool_lessons=None,
    decisions=None,
    rejected=None,
    open_questions=None,
    entries_used=None,
    robot_lessons=None,
    general_lessons=None,
    image_captions: dict | None = None,
    action_items=None,
    session_id: str | None = None,
    date: str | None = None,
) -> str:
    if not (title or "").strip():
        raise ValueError("Give the session a short title.")
    given = {
        "tool_lessons": tool_lessons,
        "decisions": decisions,
        "rejected": rejected,
        "open_questions": open_questions,
    }
    lists = {key: _clean_items(given[key], key) for key, _ in CARD_LISTS}
    robot_lessons = _clean_items(robot_lessons, "robot_lessons")
    general_lessons = _clean_items(general_lessons, "general_lessons")
    total = _words(summary) + sum(_words(i) for v in lists.values() for i in v)
    if total > CARD_MAX_WORDS:
        raise ValueError(
            f"Card is {total} words; keep it ≤ {CARD_MAX_WORDS}. Leave out "
            "anything that wouldn't change how the next part is built."
        )
    date = date or _today()
    ws = workspace(kb_dir, robot)
    path = ws / "sessions" / f"{date}-{slug(subsystem or title)}.md"
    n = 2
    while path.exists() and session_id and session_id not in path.read_text():
        path = path.with_name(f"{date}-{slug(subsystem or title)}-{n}.md")
        n += 1
    meta = {
        "title": title.strip(),
        "robot": robot or GENERAL,
        "subsystem": subsystem,
        "date": date,
        "session_id": session_id,
        "entries": list(entries_used or []),
    }
    lines = (
        ["---"]
        + [
            f"{k}: {json.dumps(v) if isinstance(v, list) else v}"
            for k, v in meta.items()
            if v not in (None, "", [])
        ]
        + ["---", ""]
    )
    if summary.strip():
        lines += [" ".join(summary.split()), ""]
    for key, heading in CARD_LISTS:
        if lists[key]:
            lines += [f"## {heading}"] + [f"- {i}" for i in lists[key]] + [""]
    if robot_lessons:
        lines += ["## Learned about this robot"] + [f"- {i}" for i in robot_lessons]
        lines += [""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")

    out = [f"Saved {path.relative_to(kb_dir)}"]
    if robot and robot != GENERAL and robot_lessons:
        added = _append_unique(
            ws / "learned.md",
            f"# Learned: {robot}\n\nLessons about this robot, added by sessions.\n",
            robot_lessons,
        )
        out.append(f"{len(added)} new lesson(s) in {robot}'s learned.md")
    if general_lessons:
        added = add_pending(kb_dir, general_lessons, source=str(path.name))
        out.append(
            f"{len(added)} general lesson(s) waiting for the user's OK "
            "(kb_lessons action=list)"
        )
    for name, caption in (image_captions or {}).items():
        out.append(caption_image(kb_dir, robot, name, caption))
    if action_items:
        added = add_actions(kb_dir, action_items, session_id=session_id, date=date)
        out.append(f"{len(added)} new action item(s) in kb/action-items.md")
    if session_id:
        _todo_done(kb_dir, session_id, card=True, images=bool(image_captions))
    return "\n".join(out)


def caption_image(kb_dir: Path, robot: str | None, name: str, caption: str) -> str:
    img_dir = workspace(kb_dir, robot) / "images"
    stem = Path(name).stem
    if not any(img_dir.glob(f"{stem}.*")):
        raise ValueError(f"No image '{name}' in {img_dir.relative_to(kb_dir)}")
    caption = " ".join(str(caption).split())
    if not caption:
        raise ValueError(f"Empty caption for {name}")
    md = img_dir / f"{stem}.md"
    md.write_text(
        f"---\ntitle: {caption[:80]}\nimage: {stem}.jpg\n---\n\n{caption}\n",
        encoding="utf-8",
    )
    return f"Captioned {md.relative_to(kb_dir)}"


# ── general lessons: pending until the user approves ─────────────────


def _pending_path(kb_dir: Path) -> Path:
    return kb_dir / "lessons-pending.md"


def _read_pending(kb_dir: Path) -> list[dict]:
    path = _pending_path(kb_dir)
    if not path.is_file():
        return []
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^- \[(p\d+)\] (.*?)(?: \(from (.*)\))?$", line)
        if m:
            items.append({"id": m[1], "text": m[2], "source": m[3]})
    return items


def _write_pending(kb_dir: Path, items: list[dict]) -> None:
    lines = [
        "# Lessons waiting for approval",
        "",
        "General lessons proposed by sessions. Approve with kb_lessons; approved "
        "ones move into lessons.md.",
        "",
    ] + [
        f"- [{i['id']}] {i['text']}" + (f" (from {i['source']})" if i["source"] else "")
        for i in items
    ]
    _pending_path(kb_dir).write_text("\n".join(lines) + "\n", encoding="utf-8")


def add_pending(kb_dir: Path, texts: list[str], source: str | None = None) -> list[str]:
    items = _read_pending(kb_dir)
    lessons = (
        (kb_dir / "lessons.md").read_text(encoding="utf-8")
        if (kb_dir / "lessons.md").is_file()
        else ""
    )
    known = {_norm(i["text"]) for i in items} | {
        _norm(line[2:]) for line in lessons.splitlines() if line.startswith("- ")
    }
    next_n = max([int(i["id"][1:]) for i in items] or [0]) + 1
    added = []
    for text in texts:
        if _norm(text) in known:
            continue
        items.append({"id": f"p{next_n}", "text": text, "source": source})
        known.add(_norm(text))
        added.append(f"p{next_n}")
        next_n += 1
    _write_pending(kb_dir, items)
    return added


def list_pending(kb_dir: Path) -> str:
    items = _read_pending(kb_dir)
    if not items:
        return "No lessons waiting for approval."
    return "\n".join(f"{i['id']}: {i['text']}" for i in items)


def decide_pending(
    kb_dir: Path, ids: list[str], approve: bool, section: str = "Workflow"
) -> str:
    items = _read_pending(kb_dir)
    chosen = [i for i in items if i["id"] in set(ids)]
    missing = set(ids) - {i["id"] for i in chosen}
    if missing:
        raise ValueError(f"Unknown pending lessons: {', '.join(sorted(missing))}")
    if approve:
        path = kb_dir / "lessons.md"
        text = path.read_text(encoding="utf-8") if path.is_file() else "# Lessons\n"
        if len(text.splitlines()) + len(chosen) > LESSONS_MAX_LINES:
            raise ValueError(
                f"lessons.md would pass {LESSONS_MAX_LINES} lines; merge or delete "
                "old lessons first."
            )
        heading = f"## {section}"
        bullets = "".join(f"- {i['text']}\n" for i in chosen)
        if heading in text:
            start = text.index(heading) + len(heading)
            nxt = text.find("\n## ", start)
            end = len(text) if nxt == -1 else nxt + 1
            body = text[start:end].rstrip("\n") + "\n" + bullets
            text = text[:start] + body + ("\n" if nxt != -1 else "") + text[end:]
        else:
            text = text.rstrip("\n") + f"\n\n{heading}\n{bullets}"
        path.write_text(text, encoding="utf-8")
    _write_pending(kb_dir, [i for i in items if i not in chosen])
    verb = f"Added to lessons.md ({section})" if approve else "Dropped"
    return f"{verb}: {', '.join(i['id'] for i in chosen)}"


# ── archiving transcripts (session-end hook, no tokens) ──────────────

_ROBOT_TOOLS = ("robot_design", "kb_save_session", "kb_save_design")


def _entries(transcript: Path):
    with transcript.open(encoding="utf-8") as f:
        for line in f:
            try:
                yield json.loads(line)
            except ValueError:
                continue


def _robot_of(entries: list[dict]) -> str | None:
    counts: dict[str, int] = {}
    for e in entries:
        content = (e.get("message") or {}).get("content")
        if e.get("type") != "assistant" or not isinstance(content, list):
            continue
        for b in content:
            if (
                isinstance(b, dict)
                and b.get("type") == "tool_use"
                and str(b.get("name", "")).endswith(_ROBOT_TOOLS)
            ):
                robot = (b.get("input") or {}).get("robot")
                if robot and robot != GENERAL:
                    counts[slug(robot)] = counts.get(slug(robot), 0) + 1
    return max(counts, key=counts.get) if counts else None


def _save_jpeg(data: bytes, dest: Path, media_type: str) -> None:
    ext = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }.get(media_type, ".png")
    raw = dest.with_suffix(ext)
    raw.write_bytes(data)
    try:
        subprocess.run(
            [
                "sips",
                "-s",
                "format",
                "jpeg",
                "-s",
                "formatOptions",
                "80",
                "-Z",
                "1600",
                str(raw),
                "--out",
                str(dest),
            ],
            check=True,
            capture_output=True,
        )
        if raw != dest:
            raw.unlink()
    except (FileNotFoundError, subprocess.CalledProcessError):
        if raw != dest:
            shutil.move(raw, dest.with_suffix(ext))


def archive_transcript(kb_dir: Path, transcript: Path) -> dict:
    """Copy a session's conversation (redacted text) and pasted images into the
    robot's workspace; queue it for a card if it has none. Idempotent."""
    entries = [e for e in _entries(transcript) if not e.get("isSidechain")]
    if not entries:
        return {"skipped": "empty"}
    session_id = next(
        (e["sessionId"] for e in entries if e.get("sessionId")), transcript.stem
    )
    stamp = next((e["timestamp"] for e in entries if e.get("timestamp")), "")
    date = stamp[:10] or _today()
    robot = _robot_of(entries)
    ws = workspace(kb_dir, robot)
    name = f"{date}-{session_id[:8]}"

    parts, images = [], []
    for e in entries:
        content = (e.get("message") or {}).get("content")
        who = {"user": "You", "assistant": "Claude"}.get(e.get("type"))
        if not who:
            continue
        blocks = (
            [{"type": "text", "text": content}]
            if isinstance(content, str)
            else [b for b in content or [] if isinstance(b, dict)]
        )
        texts = []
        for b in blocks:
            if b.get("type") == "text":
                texts.append(b.get("text") or "")
            elif b.get("type") == "image" and who == "You":
                src = b.get("source") or {}
                if src.get("type") == "base64" and src.get("data"):
                    images.append((src["data"], src.get("media_type", "image/png")))
                    texts.append(f"[image {name}-{len(images)}.jpg]")
        text = redact(_NOISE_RE.sub("", "\n".join(texts))).strip()
        if text:
            when = (e.get("timestamp") or "")[11:16]
            parts.append(f"### {who} {when}\n\n{text}\n")

    chats = ws / "chats"
    chats.mkdir(parents=True, exist_ok=True)
    (chats / f"{name}.md").write_text(
        f"---\ntitle: Chat {date} ({session_id[:8]})\nrobot: {robot or GENERAL}\n"
        f"session_id: {session_id}\ndate: {date}\n---\n\n" + "\n".join(parts),
        encoding="utf-8",
    )
    uncaptioned = []
    if images:
        img_dir = ws / "images"
        img_dir.mkdir(parents=True, exist_ok=True)
        for n, (data, media) in enumerate(images, 1):
            dest = img_dir / f"{name}-{n}.jpg"
            if not any(img_dir.glob(f"{dest.stem}.*")):
                _save_jpeg(base64.b64decode(data), dest, media)
            if not (img_dir / f"{dest.stem}.md").exists():
                uncaptioned.append(dest.stem)

    if session_id in skipped_ids(kb_dir):
        return {
            "session_id": session_id,
            "robot": robot or GENERAL,
            "messages": len(parts),
            "images": len(images),
            "needs_card": False,
            "skipped": True,
            "chat": str((chats / f"{name}.md").relative_to(kb_dir)),
        }
    has_card = (
        any(
            session_id in p.read_text(encoding="utf-8")
            for p in (ws / "sessions").glob("*.md")
        )
        if (ws / "sessions").is_dir()
        else False
    )
    if not has_card or uncaptioned:
        _todo_add(
            kb_dir,
            {
                "session_id": session_id,
                "date": date,
                "robot": robot or GENERAL,
                "transcript": str(transcript),
                "needs_card": "no" if has_card else "yes",
                "images": ";".join(uncaptioned),
            },
        )
    return {
        "session_id": session_id,
        "robot": robot or GENERAL,
        "messages": len(parts),
        "images": len(images),
        "needs_card": not has_card,
        "chat": str((chats / f"{name}.md").relative_to(kb_dir)),
    }


def _todo_path(kb_dir: Path) -> Path:
    return kb_dir / "ingest" / "sessions_todo.csv"


def _todo_rows(kb_dir: Path) -> list[dict]:
    path = _todo_path(kb_dir)
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _todo_write(kb_dir: Path, rows: list[dict]) -> None:
    path = _todo_path(kb_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=TODO_FIELDS)
        w.writeheader()
        w.writerows(rows)


def _todo_add(kb_dir: Path, row: dict) -> None:
    rows = [r for r in _todo_rows(kb_dir) if r["session_id"] != row["session_id"]]
    _todo_write(kb_dir, rows + [row])


def _todo_done(kb_dir: Path, session_id: str, card: bool, images: bool) -> None:
    rows = []
    for r in _todo_rows(kb_dir):
        if r["session_id"] == session_id:
            if card:
                r["needs_card"] = "no"
            if images:
                r["images"] = ""
            if r["needs_card"] == "no" and not r["images"]:
                continue
        rows.append(r)
    _todo_write(kb_dir, rows)


# ── action items: things a session said need building or fixing ──────

ACTION_KINDS = ("tool", "bug", "feature", "data", "docs", "question")
_ACTION_RE = re.compile(r"^- \[( |x)\] \[(\w+)\] (.*?)(?: — from (.*))?$")


def _actions_path(kb_dir: Path) -> Path:
    return kb_dir / "action-items.md"


def add_actions(
    kb_dir: Path, items, session_id: str | None = None, date: str | None = None
) -> list[str]:
    """Append open action items ("tool: add export_dxf") to kb/action-items.md,
    skipping ones already listed (open or done). Returns the items added."""
    path = _actions_path(kb_dir)
    text = (
        path.read_text(encoding="utf-8")
        if path.is_file()
        else (
            "# Action items\n\nThings sessions said need to be built, fixed or "
            "decided. "
            "Tick `[x]` and add the commit when done. Kinds: "
            + ", ".join(ACTION_KINDS)
            + ".\n"
        )
    )
    known = {
        _norm(m.group(3)) for line in text.splitlines() if (m := _ACTION_RE.match(line))
    }
    source = (
        f"{date or _today()} {session_id[:8]}" if session_id else (date or _today())
    )
    added = []
    for raw in items or []:
        raw = " ".join(str(raw).split())
        kind, _, body = raw.partition(":")
        kind = kind.strip().lower()
        if kind not in ACTION_KINDS or not body.strip():
            raise ValueError(
                f"Action item '{raw[:40]}' must start with a kind: "
                + ", ".join(ACTION_KINDS)
                + " (e.g. 'tool: add export_dxf')"
            )
        body = body.strip()
        if _words(body) > ITEM_MAX_WORDS:
            raise ValueError(f"Keep action items ≤ {ITEM_MAX_WORDS} words")
        if _norm(body) in known:
            continue
        known.add(_norm(body))
        text = text.rstrip("\n") + f"\n- [ ] [{kind}] {body} — from {source}\n"
        added.append(body)
    if added:
        path.write_text(text, encoding="utf-8")
    return added


def open_actions(kb_dir: Path) -> list[dict]:
    path = _actions_path(kb_dir)
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _ACTION_RE.match(line)
        if m and m.group(1) == " ":
            out.append({"kind": m.group(2), "text": m.group(3), "from": m.group(4)})
    return out


def find_session(transcripts_dir: Path, marker: str) -> list[str]:
    """Session ids whose transcript contains `marker` (a unique string the
    session printed in an earlier step: how a session finds its own id)."""
    if len(marker) < 8:
        raise ValueError("Use a unique marker of 8+ characters.")
    return sorted(
        p.stem
        for p in Path(transcripts_dir).glob("*.jsonl")
        if marker in p.read_text(encoding="utf-8", errors="ignore")
    )


def _skipped_path(kb_dir: Path) -> Path:
    return kb_dir / "ingest" / "sessions_skipped.csv"


def skipped_ids(kb_dir: Path) -> set[str]:
    path = _skipped_path(kb_dir)
    if not path.is_file():
        return set()
    with path.open(newline="", encoding="utf-8") as f:
        return {r["session_id"] for r in csv.DictReader(f)}


def skip_session(kb_dir: Path, session_id: str, reason: str) -> str:
    """Mark a queued session as not worth a card (nothing that helps CAD a
    robot): logged with the reason, removed from the queue, never re-queued."""
    if not (reason or "").strip():
        raise ValueError("Say why the session is skipped.")
    rows = _todo_rows(kb_dir)
    match = [r for r in rows if r["session_id"].startswith(session_id)]
    if len(match) != 1:
        raise ValueError(f"'{session_id}' matches {len(match)} queued sessions")
    row = match[0]
    path = _skipped_path(kb_dir)
    new = not path.is_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["session_id", "date", "robot", "reason"])
        if new:
            w.writeheader()
        w.writerow(
            {
                "session_id": row["session_id"],
                "date": row["date"],
                "robot": row["robot"],
                "reason": " ".join(reason.split()),
            }
        )
    _todo_write(kb_dir, [r for r in rows if r is not row])
    return f"Skipped {row['session_id']}: {reason.strip()}"


def todo_list(kb_dir: Path) -> list[dict]:
    """Queued sessions, oldest first."""
    return sorted(_todo_rows(kb_dir), key=lambda r: r["date"])


def pending_summary(kb_dir: Path) -> str:
    """One line for session-start prompts: what's waiting from past sessions."""
    todo = _todo_rows(kb_dir)
    cards = sum(1 for r in todo if r["needs_card"] == "yes")
    imgs = sum(len([i for i in r["images"].split(";") if i]) for r in todo)
    lessons = len(_read_pending(kb_dir))
    bits = []
    if cards:
        bits.append(f"{cards} past session(s) need a card")
    if imgs:
        bits.append(f"{imgs} pasted image(s) need a caption")
    if lessons:
        bits.append(f"{lessons} general lesson(s) wait for the user's OK")
    return "; ".join(bits)
