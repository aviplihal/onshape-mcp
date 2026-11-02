# Status

**Onshape API calls used this year: ~2 of 2,500 (this fork; the Fusion project's ingest counts separately in kb/ingest/api_calls.csv)** (update when you ingest or run long sessions).

## Fork + knowledge-base port (2026-11-01, branch `ftc-kb`, not merged)
- Forked ReshefElisha/jarvis-onshape-mcp (MIT, Python, 70+ Onshape tools, truth-telling envelopes, renders) to aviplihal/onshape-mcp, chosen over hedless/onshape-mcp (no license, fewer features) and gpambrozio/onshape-mcp (TypeScript).
- Ported from the Fusion project: `kb*.py` (SQLite FTS5 index, 8 kb tools, design files, parts, session cards, pending-transcript staging), their 5 test files, `kb/` data (22 MB: robots, rules, books, parts, designs, lessons; ingest scratch data left behind), `scripts/kb/` (session_end, scrape_gobilda, build_stacks, build_part_classes), the `ftc-robot-design` skill, `cad-builder` / `cad-reviewer` / `transcript-reviewer` agents (tool lists and steps rewritten for Onshape tools), `docs/start-design-session.md`, CLAUDE.md rules and portable lessons.
- Wired into `server.py`: `list_tools` / `call_tool` wrappers, KB resources (`kb://lessons`, `kb://design-rules`, `kb://constraints`) and prompts. 77 tools total.
- Verified: 824 tests pass (upstream + KB), ruff clean on our files, `kb_search` answers through the server.

## Next
1. DONE 2026-11-02: registered user-scope as `onshape` (restart Claude Code to load it; tools appear as `mcp__onshape__*`); `.env` (git-ignored) holds the keys; `list_documents` returned real documents, so auth works.
2. Live test on the user's existing robot document (first task): read-only first (`get_document_summary`, `get_assembly`, `describe_part_studio`), and ask before any edit; make edits in a copy/branch workspace if possible.
3. Missing vs Fusion: STEP import of goBILDA parts (`kb_find_part` downloads the STEP; no import tool, so use the Onshape FTC library parts by name), `audit_shaft_stacks` / `audit_fastening` / `check_robot_rules` equivalents, `set_joint_value`-style mate sweeps.
4. Prompt text in `kb_design.py` and the KB cards still mention some Fusion-specific details in older design notes (`kb/designs`, `kb/robots`); fix as they are met.
5. Pyproject metadata (name/author/description) still says Jarvis.
