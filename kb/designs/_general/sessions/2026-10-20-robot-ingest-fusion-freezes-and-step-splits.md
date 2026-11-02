---
title: Robot ingest: Fusion freezes and STEP splits
robot: _general
date: 2026-10-20
session_id: f1bb3466-a45e-4da9-8d8d-2671c26415dd
---

Ran the robot-ingest pilot and batches 2-3 (33 robots approved into kb/robots). Robots with loose-part mechanisms were split by importing their Onshape STEP into a throwaway Fusion document and rendering one mechanism per call; along the way Fusion kept freezing, traced to macOS sleep/App Nap.

## Tool lessons
- render_view freezes while the display sleeps, the lid is closed, or Fusion is in the background (App Nap, worse on battery) — keep the Mac plugged in, lid open, Fusion in front, caffeinate -dimsu -w <fusion pid>.
- The add-in cancels a command Fusion has not started within 30 s, and the client just times out — resend after a timeout instead of waiting for output that will never come.
- Render one mechanism per execute_code/render_view call on big imports (1,500 bodies) — several renders in one call pass the 30 s wait; work keeps running but results are lost.
- Select occurrences by exact name, not substring: find("Shooter") matched "Shooter Turret Plate" and rendered an empty mechanism — because names nest.
- A 200-330 MB STEP import takes 47-76 s and drops the MCP socket (broken pipe) — keep the document in a sys attribute and poll with ping plus a small command until the main thread answers.

## Decisions and why
- Split mechanisms by function, not by CAD tree: drivetrain = side plates + wheels, turret = bottom of the shooter assembly, front wheel bars = intake — because the user corrected every draft that followed the tree.
- Vector wheels are intake wheels, not drive wheels — user review of 18365 Chain Reaction.
