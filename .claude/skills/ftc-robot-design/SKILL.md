---
name: ftc-robot-design
description: Design and CAD an FTC robot or one of its subsystems (drivetrain, intake, transfer, shooter, turret, claw, slides...) with the user, using the knowledge base and the Onshape MCP tools. Use when the user starts or continues designing a robot ("we're designing a BIOBUZZ robot", "let's work on the shooter") or says "CAD the robot" / "CAD the <subsystem>".
---

# FTC robot design: talk first, CAD on command

The user's starter messages are in `docs/start-design-session.md`.

Two phases. Stay in **design talk** until the user says to CAD ("CAD the robot", "CAD the shooter", "build it"). Lengths in mm (explicit units). Don't use `eval_featurescript` to build parts unless the user agrees.

## Start of the chat
1. Work out the robot name (a short slug like `bb1`); ask only if it isn't clear. `robot_design action=get`. If it doesn't exist: `create`, then propose each planned subsystem's envelope (stowed + `extended` if it moves out) and its share of the 8 motors / 8 servos, and get the user's OK before anything else.
2. Read the MCP resources `kb://lessons`, `kb://design-rules`, `kb://constraints`. If the design file or `kb_lessons action=list` shows things waiting from past sessions, mention them in one line.

## Phase 1: design talk (no Onshape)
- Be a design partner: ask what the subsystem must do and what to watch out for, then go back and forth.
- When a subsystem comes up, search before proposing: `kb_search kind=mechanism type=<type>` and `kind=idea` (and `kind=rule` for legality), `kb_get` the best 2–3. Higher-rated robots and entries the user liked rank first. For how a shaft is actually built (bearings, spacers, hubs in order, plate spacing, what hangs outboard), `kb_search kind=stack <role>` (e.g. `flywheel`, `roller`, `drive wheel`).
- Propose 2–3 concepts with key numbers (size, motors/servos, ratios, wheel sizes, materials and process: laser wood, laser aluminum, FDM) and trade-offs. Say which KB entries each comes from. Check them against the envelope, the actuator budget and the design rules.
- **Record agreements as they are made**, so they survive the chat: `robot_design update_subsystem` (status=concept, envelope, motors, servos, interfaces, based_on=[entry ids]); `add_note` for anything another subsystem must know. Ask before changing an agreed envelope or budget.
- Images the user pastes are saved automatically at the end of the chat; describe what you read from them, and caption them in `kb_save_session`.
- Don't call any Onshape tool that changes a document in this phase.

## Phase 2: "CAD the …"
1. Say in one line what you're about to build, from the design file. "CAD the robot" = every subsystem with an agreed concept, drivetrain first (the others mount to it).
2. Open the robot's Onshape document (`search_documents` / `get_document_summary`) or `create_document`; ask before creating one. One Part Studio per subsystem, named after it (envelope sketched as a box).
3. **Constraint card per custom part / subassembly, before modeling it.** Fill every row from the part's function, with numbers (write "n/a because …", never leave one out). Show it to the user in one block, then append it to `kb/designs/<robot>/cards/<subsystem>.md` (Write tool; edit the card when the design changes). The reviewer checks against it.
   ```
   ### <part> (<process>)
   job:          what it does; loads, speeds (rpm, N, J) it sees
   interfaces:   each neighbour it mounts to, and HOW: fastener type, count (≥2 per joint), positions, tool access
   support:      every shaft/gear/pin it carries: supported both sides (or the overhang in mm and why); what retains it axially (head, collar, wall, screw)
   envelope:     max box in mm, derived from the neighbours, moving-part sweeps and the subsystem budget; mass budget
   covers:       what it must span/guard (every bearing, gear, pin end it supports)
   manufacture:  print orientation, min wall, inserts/nuts, clearances (kb://design-rules)
   size sanity:  what sets its size; anything bigger/heavier than the job needs, or forced by a choice to question (ratio in one stage, centre distance)
   references:   1–2 top-team entries (kb_search kind=stack / mechanism) and the numbers taken from them
   done when:    check_assembly_interference clean, mates healthy, fasteners counted + cad-reviewer blockers closed
   ```
4. **Build with the `cad-builder` subagent** (Agent tool, `subagent_type: cad-builder`, Sonnet; if the type isn't registered use `general-purpose` with `model: sonnet` and "Read and follow `.claude/agents/cad-builder.md`"). Give it only: robot name, subsystem, document id + workspace id, the card file path and the design file. It builds from the cards (it never saw the chat): master sketch first, goBILDA parts via `kb_find_part` + the Onshape FTC-library part of the same name (`add_assembly_instance`, mates), "copy a real axle" from `kb_search kind=stack`, checks, `kb_save_session`, then a report with deviations and open questions. Read that report, not its tool calls. A tiny part without a card you may build yourself. **Edit before add** (you and the builder): see `.claude/agents/cad-builder.md`.
5. Check the report yourself (renders of what the user cares about). Don't run builder and reviewer at the same time: both draw on the 2,500 API calls per year.
6. **Independent review, required before "built"/"done".** Clean checks != done. Run the `cad-reviewer` subagent (`subagent_type: cad-reviewer`, Opus; else `general-purpose` + "Read and follow `.claude/agents/cad-reviewer.md`") with only the document id, the part names and the card path, nothing about the builder's reasoning. **Spot-check each blocker against the CAD** (reviewers can be wrong, e.g. calling a part missing that lives in another component). Send confirmed blockers back to the builder by resuming it (`SendMessage` to its agent id) and re-review. Repeat until clean, or list the rest to the user and get an explicit "accept". Only then status=built; report the should-fix list with it.
7. Ask for the verdict. `kb_feedback` with only the entries that caused it. Accepted: `robot_design update_subsystem status=accepted` (actual envelope, interfaces, motors, servos), `kb_save_design`.
8. Whole robot done: `robot_design action=get` (start cube, extended box, 8/8 budget), `check_assembly_interference`, `get_assembly_features`.

## End of the chat (or after a verdict)
Builder transcripts: the SessionEnd hook condenses them into `kb/_pending/` (not indexed, not committed). Spawn `transcript-reviewer` (Opus) on each (`uv run --frozen python -I scripts/kb/session_end.py --list-pending`); it writes a card and returns its path plus 5 lines, so you never read the raw log. Show the user the card; on OK `... session_end.py --archive <id> [--with-transcript]` (moves it into `kb/designs/<robot>/`, where search finds it); if rejected `--discard <id> [--keep] why`. Nothing from a builder enters the KB before this.

`kb_save_session`: tool lessons first (what worked, what failed and the fix), then decisions and why, rejected ideas and why, open questions, the entries used, `robot_lessons`, `general_lessons` (these wait for the user's OK), and `action_items` (things that need building or fixing: "tool: …", "bug: …", "feature: …", "question: …"). Leave out anything that wouldn't change how the next part is built.

If the user asks for this session's ID: run `echo session-marker-<random 10 chars>` in one step, then in the next step `uv run --frozen python -I scripts/kb/session_end.py --find-session <that marker>`, and give them the ID it prints.
