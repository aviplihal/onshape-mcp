"""Axle stacks from a robot's Onshape assembly.json → kb/robots/<id>/stacks.md.

Each occurrence in assembly.json carries its world transform, so round parts
(bearings, hubs, pulleys, gears, wheels, spacers...) whose origins sit on one
line, with a local axis along that line, make up one axle. The card lists every
axle in order along its axis, with the plates (bearing groups) and how far parts
hang outboard of them, so a session can compare its own shaft against how top
teams build the same thing. No Fusion needed.

Usage: python3 -I scripts/kb/build_stacks.py [--drafts DIR] [--out DIR] [robot-id ...]
  --drafts  where the ingest drafts live (default kb/ingest/drafts)
  --out     where robot folders are (default kb/robots); only robots that already
            have a folder there are written, unless robot ids are given.
  --cards   robot cards to read titles from (default kb/robots)
"""

import argparse
import json
import math
import re
import sys
from pathlib import Path

ROUND = re.compile(
    r"bearing|bushing|hub|pulley|sprocket|gear|wheel|flywheel|weight|roller|"
    r"tubing|spacer|collar|shim|washer|shaft|axle|clamp|sleeve|mount",
    re.I,
)
SUPPORT = re.compile(r"bearing|bushing", re.I)
# Parts that make a line an axle even with no bearing on it (a flywheel on a
# bare motor shaft).
CARRIED = re.compile(r"wheel|flywheel|roller|tubing", re.I)
SKU = re.compile(r"\b(\d{4}-\d{4}-\d{4})\b")
AXIS_DOT = 0.995  # local axis counts as "along the line" (~5.7°)
RADIUS_MM = 1.5  # origin within this distance of the line
PLATE_GAP_MM = 12.0  # bearings closer than this sit in one plate
SPLIT_GAP_MM = 100.0  # a longer empty stretch means two axles on one line
MIN_PARTS = 3
MAX_AT_ONE_SPOT = 3
MIN_SPAN_MM = 15.0


def _norm(v):
    m = math.sqrt(sum(x * x for x in v))
    return tuple(x / m for x in v) if m else v


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _canon(d):
    """Direction with a fixed sign, so d and -d compare equal."""
    i = max(range(3), key=lambda k: abs(d[k]))
    return d if d[i] > 0 else tuple(-x for x in d)


def _clean(name):
    name = re.sub(r"\s*<\d+>$", "", name)
    return re.sub(r"\s+", " ", name).strip()


def occurrences(assembly):
    """(path names, world position mm, local axes) for every occurrence."""
    root = assembly["rootAssembly"]
    subs = {
        (s["documentId"], s["elementId"], s.get("fullConfiguration")): s
        for s in assembly.get("subAssemblies", [])
    }

    def children(inst):
        key = (
            inst.get("documentId"),
            inst.get("elementId"),
            inst.get("fullConfiguration"),
        )
        sub = subs.get(key)
        return {i["id"]: i for i in sub["instances"]} if sub else {}

    top = {i["id"]: i for i in root["instances"]}
    out = []
    for occ in root["occurrences"]:
        level, names, ok = top, [], True
        for pid in occ["path"]:
            inst = level.get(pid)
            if inst is None:
                ok = False
                break
            names.append(inst["name"])
            level = children(inst) if inst.get("type") == "Assembly" else {}
        if not ok or occ.get("hidden"):
            continue
        t = occ["transform"]
        pos = (t[3] * 1000, t[7] * 1000, t[11] * 1000)
        axes = ((t[0], t[4], t[8]), (t[1], t[5], t[9]), (t[2], t[6], t[10]))
        out.append((names, pos, axes))
    return out


def candidates(occs):
    """Round parts, skipping the insides of one already counted (bearing races)."""
    out, seen = [], set()
    for names, pos, axes in occs:
        if not ROUND.search(_clean(names[-1])):
            continue
        # A matching ancestor below the top level that isn't a team's own
        # "... Assembly" is a COTS part (a bearing): count it, not its races.
        if any(
            ROUND.search(_clean(n)) and "assembl" not in n.lower() for n in names[1:-1]
        ):
            continue
        key = (tuple(names), tuple(round(p, 2) for p in pos))
        if key not in seen:
            seen.add(key)
            out.append((names, pos, axes))
    # Part-studio parts placed at their studio's origin all share one spot;
    # a real axle has at most a mirrored pair (hub + mount) at one position.
    spots = {}
    for _, pos, _ in out:
        spot = tuple(round(p, 1) for p in pos)
        spots[spot] = spots.get(spot, 0) + 1
    return [
        o for o in out if spots[tuple(round(p, 1) for p in o[1])] <= MAX_AT_ONE_SPOT
    ]


def _is_axle_part(name):
    return bool(SUPPORT.search(name) or CARRIED.search(name))


def find_axles(parts):
    """Greedy line clustering: biggest stacks first, each part used once."""
    lines = {}
    for i, (_, p, axes) in enumerate(parts):
        for a in axes:
            d = _canon(_norm(a))
            for j, (_, q, axes_j) in enumerate(parts):
                if j <= i:
                    continue
                if not any(abs(_dot(d, b)) > AXIS_DOT for b in axes_j):
                    continue
                v = tuple(q[k] - p[k] for k in range(3))
                s = _dot(v, d)
                if math.sqrt(max(0.0, _dot(v, v) - s * s)) < RADIUS_MM:
                    key = (i, tuple(round(x, 2) for x in d))
                    lines.setdefault(key, (p, d))
    used, axles = set(), []
    while True:
        best = None
        for p, d in lines.values():
            members = []
            for k, (_, q, axes) in enumerate(parts):
                if k in used:
                    continue
                match = [b for b in axes if abs(_dot(d, b)) > AXIS_DOT]
                if not match:
                    continue
                v = tuple(q[i] - p[i] for i in range(3))
                s = _dot(v, d)
                if math.sqrt(max(0.0, _dot(v, v) - s * s)) < RADIUS_MM:
                    members.append((s, k, 1 if _dot(match[0], d) > 0 else -1))
            if len(members) >= MIN_PARTS and (
                best is None or len(members) > len(best[2])
            ):
                best = (p, d, members)
        if best is None:
            break
        p, d, members = best
        if not any(_is_axle_part(parts[k][0][-1]) for _, k, _ in members):
            # Only spacers and hubs: a row of standoffs on a plate, not an axle.
            # Drop the line but keep its parts free for other axles.
            lines = {key: v for key, v in lines.items() if v != (p, d)}
            continue
        used.update(k for _, k, _ in members)
        run = []
        for m in sorted(members):
            if run and m[0] - run[-1][0] > SPLIT_GAP_MM:
                axles.append((p, d, run))
                run = []
            run.append(m)
        axles.append((p, d, run))
    # A split can leave a stub with no bearing or too few parts.
    return [
        a
        for a in axles
        if len(a[2]) >= MIN_PARTS
        and any(_is_axle_part(parts[k][0][-1]) for _, k, _ in a[2])
    ]


def role(names, sub):
    text = " ".join(names).lower()
    if re.search(r"mecanum|omni|traction|drive ?wheel", text):
        return "drive wheel"
    if re.search(r"flywheel|weight", text):
        return "flywheel"
    if re.search(r"wheel", text) and re.search(
        r"shoot|launch|flywheel|outt?ake", sub.lower()
    ):
        return "flywheel"
    for pattern, label in (
        (r"tubing|roller", "roller"),
        (r"wheel", "wheel"),
        (r"spool", "spool"),
        (r"gear", "gear shaft"),
        (r"pulley", "pulley shaft"),
    ):
        if re.search(pattern, text):
            return label
    return "axle"


def plates(rows):
    """Group bearing positions into plates: list of (start, end) mm."""
    out = []
    for s, name, _ in rows:
        if not SUPPORT.search(name):
            continue
        if out and s - out[-1][1] < PLATE_GAP_MM:
            out[-1][1] = s
        else:
            out.append([s, s])
    return out


def describe(robot_id, occs):
    parts = candidates(occs)
    axles = find_axles(parts)
    sections = []
    for p, d, members in axles:
        rows = [(s, _clean(parts[k][0][-1]), f) for s, k, f in members]
        s0 = rows[0][0]
        rows = [(s - s0, n, f) for s, n, f in rows]
        sub = _clean(parts[members[0][1]][0][0])
        names = [n for _, n, _ in rows]
        pl = plates(rows)
        span = rows[-1][0]
        # Bearings inside a COTS part (a gearbox, a V-groove wheel) aren't an axle.
        if span < MIN_SPAN_MM or SKU.search(sub):
            continue
        lines = [
            f"axis ({d[0]:.2f}, {d[1]:.2f}, {d[2]:.2f})"
            f" · origin parts span {span:.0f} mm"
        ]
        if pl:
            centres = [(a + b) / 2 for a, b in pl]
            gaps = [f"{b - a:.0f}" for a, b in zip(centres, centres[1:])]
            lines.append(
                f"supports: {len(pl)} plate(s), "
                f"{sum(1 for n in names if SUPPORT.search(n))} bearings"
                + (f"; plate spacing {', '.join(gaps)} mm" if gaps else "")
                + f"; outboard {pl[0][0]:.0f} mm / {span - pl[-1][1]:.0f} mm"
            )
        else:
            lines.append("supports: none (no bearing on this line)")
        lines.append("")
        for s, n, f in rows:
            sku = SKU.search(n)
            short = SKU.sub("", n).strip(" ,")[:70]
            lines.append(
                f"- {s:6.1f}  {'+' if f > 0 else '-'}  {short}"
                + (f" ({sku.group(1)})" if sku else "")
            )
        sections.append((role(names, sub), sub, lines))
    order = {"flywheel": 0, "roller": 1}
    sections.sort(key=lambda x: (order.get(x[0], 2), x[1]))
    return sections


LEGEND = (
    "Positions: part origins in mm along the axle. +/−: the part's own axis; "
    "compare only between copies of one part (mirrored hubs differ). "
    "Shaft often missing."
)
# Copied from robot.md so search ranks a team's axles like its robot.
INHERITED = ("season", "team", "rating")


def render(robot_id, title, sections, card_meta=()):
    out = [
        "---",
        f"robot: {robot_id}",
        f"title: Axle stacks · {title}",
        *card_meta,
        "source: scripts/kb/build_stacks.py (Onshape assembly.json)",
        "---",
        "",
        LEGEND,
    ]
    for n, (r, sub, lines) in enumerate(sections, 1):
        out += ["", f"## {n}. {r} · {sub}", *lines]
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--drafts", default="kb/ingest/drafts")
    ap.add_argument("--out", default="kb/robots")
    ap.add_argument("--cards", default="kb/robots", help="robot cards, for titles")
    ap.add_argument("robots", nargs="*")
    args = ap.parse_args(argv)
    drafts, out = Path(args.drafts), Path(args.out)
    ids = args.robots or sorted(p.name for p in out.iterdir() if p.is_dir())
    for rid in ids:
        src = drafts / rid / "assembly.json"
        if not src.is_file():
            print(f"{rid}: no assembly.json, skipped")
            continue
        occs = occurrences(json.loads(src.read_text()))
        sections = describe(rid, occs)
        if not sections:
            # Mostly part-studio or STEP-imported CAD: nothing to say.
            (out / rid / "stacks.md").unlink(missing_ok=True)
            print(f"{rid}: 0 axles")
            continue
        title, meta = rid, []
        card = Path(args.cards) / rid / "robot.md"
        if card.is_file():
            text = card.read_text()
            m = re.search(r"^title: (.+)$", text, re.M)
            title = m.group(1) if m else rid
            meta = [
                line for line in text.splitlines() if line.split(":")[0] in INHERITED
            ]
        (out / rid).mkdir(parents=True, exist_ok=True)
        (out / rid / "stacks.md").write_text(render(rid, title, sections, meta))
        print(f"{rid}: {len(sections)} axles")


if __name__ == "__main__":
    sys.exit(main())
