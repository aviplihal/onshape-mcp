Goal: Make a memory base + MCP server that allows Claude to completely CAD an FTC robot in Onshape with human guidance on design. (Fork of ReshefElisha/jarvis-onshape-mcp, which descends from hedless/onshape-mcp; the knowledge base and design workflow come from the sibling Fusion 360 project at ~/Projects/fusion360-mcp-server.)

Upkeep:
1. Do not change things that do not need to be changed for the task you are working on.
2. Follow the 80/20 rule. Look at what gets you 80% for 20% of the work. Ignore if asked to optimize.
3. Do not leave things half finished. Update Status.md with the part you worked on and what needs to be completed next.
4. Before a large change make a plan. If possible, run spike tests on separate parts first.
5. For a large change make a git branch so you don't break what is running.
6. When removing code, remove it fully; don't comment it out.
7. When you learn something that helps a future session, add it to Learned Lessons below.
8. Keep upstream merges easy: Onshape tool code lives in `onshape_mcp/{api,builders,analysis,server.py}` (upstream's). Our additions are the `kb*.py` files, `kb/`, `scripts/kb/`, `.claude/`, `docs/start-design-session.md`. In `server.py` only the thin glue near `list_tools` / `call_tool` is ours. `git remote add upstream https://github.com/ReshefElisha/jarvis-onshape-mcp` to pull updates.

Parts to the project:
1. MCP server: Onshape REST tools (upstream, ~70 tools: sketches, features, assemblies, mates, FeatureScript, renders, describe_part_studio) + the 8 `kb_*` / `robot_design` tools, which run inside the server and never call Onshape.
2. RAG knowledge base: `kb/` (files are the source of truth) indexed into SQLite FTS5 by `onshape_mcp/kb*.py`. Past robots, mechanism cards, axle stacks, rules, goBILDA parts (`kb/parts/parts.csv`), design rules, lessons. Keep it small and fast, spend few tokens.

Flow: Claude <-stdio MCP-> onshape_mcp/server.py <-HTTPS, HMAC keys-> cad.onshape.com. Env: `ONSHAPE_API_KEY`, `ONSHAPE_API_SECRET` (in `.env` or the environment). Lengths: bare numbers are mm; use "30 mm" style strings.

Dev commands: `uv sync --extra dev`, `uv run pytest --no-cov`, `uv run ruff check onshape_mcp/kb*.py tests/test_kb*.py`.
Design sessions: skill `.claude/skills/ftc-robot-design/`, agents `.claude/agents/` (cad-builder, cad-reviewer, transcript-reviewer), starter messages `docs/start-design-session.md`. Tool-usage protocol for Onshape: `skills/onshape/SKILL.md` (render-first, units, planes). The SessionEnd hook in `.claude/settings.json` runs `scripts/kb/session_end.py`.
The Onshape API allows 2,500 successful calls per user per year (402 after). Count them in Status.md.

Learned Lessons (carried over from the Fusion project; Fusion-only ones left out):
1. Onshape robot CAD: the BOM "Part number" field is empty. Identify COTS parts by their library names with vendor suffixes ("(GB)", "(REV)", "(SC)"). Subassemblies linked from private documents return 403 on render, so fall back to the whole-robot render. Link-shared documents (`public: false`) return 403 on the assembly even though `GET /documents` works.
2. Onshape `assembly.json` has each occurrence's world transform (`rootAssembly.occurrences[].transform`, row-major 4x4, metres); names come from `instances` and `subAssemblies`. Parts within ~2 mm of a line give a shaft's stack in order.
3. goBILDA's robots.txt asks AI agents for a 10 s crawl delay; the product data is embedded as JSON in the category pages, so scrape those (cached). `uv run --frozen` stops uv from rewriting uv.lock.
4. FTC CAD Base has no API, but its home page embeds the whole catalog as JSON in the `self.__next_f.push` strings.
5. Clean checks do not mean a good part. A fresh `cad-reviewer` subagent that never saw the chat catches unfastened frames, headless pins, unretained overhung gears. Custom subagent types only register when Claude Code starts; until then spawn `general-purpose` and tell it to read the agent file.
6. Parallel agents with `isolation: worktree` branch from `main`, not the current branch: tell them to reset to the intended commit first.
7. The `kb/` data and the three agent/skill files were adapted from the Fusion project by renaming tools; the Fusion-only audits (`audit_shaft_stacks`, `audit_fastening`, `check_robot_rules`) do not exist here, so reviewers do those checks by hand. Writing Onshape equivalents is the biggest open item (Status.md).
