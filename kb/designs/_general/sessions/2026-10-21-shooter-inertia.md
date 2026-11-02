---
title: Shooter: split inertia, bike-wheel flywheel, servo-side ring
robot: _general
subsystem: shooter-inertia
date: 2026-10-21
---

Moved inertia off the belt path: bike-wheel steel rim on the flywheel shaft plus a small steel ring on roller 2, both on the servo side, clear of the Axon MINI. Rebuilt Hood Arm R (mirror of L). Drive side 4.9 -> 3.6 cm; herringbone restack pending user's gears.

## Tool lessons
- Mirror only uses base planes; mirror across XZ then move_body to place a symmetric part (arm L -> arm R about the ball mid-plane).
- Sketches in a component are in its local coordinates; a shaft component with origin on its axis needs centers at (0,0).
- Fusion won't cut a body to empty; suppress the creating feature by timeline index ('#229') instead.
- Undo may not remove a feature after a failed combine; check get_timeline and suppress by index.
- Sweep scope root drags in hidden Obsolete parts; set_joint_value + check_interference with component_names is cleaner.

## Decisions and why
- Split inertia ~50/50 so the ball's two sides each draw from their own store and the belt/gears carry little — permits PLA herringbones.
- Flywheel side: steel rim 100/86 x 9 mm (144 g, ~3140 g*cm^2) on a 5-spoke PLA hub, servo side, y 9.0-9.9 — bigger diameter = half the mass of 2x goBILDA 82 mm.
- Roller side: steel ring 32/22 x 16 mm (39 g, 102 g*cm^2) on roller 2, servo side — max dia 32: 19.2 mm min gap to the Axon at hood -10 deg.
- Gears: printed PLA herringbone MOD1 32T/16T (same 24 mm center as 40T/20T MOD0.8); idler fused with 59T pulley.
- Axon MINI: standard 20x40 footprint, ~19 mm behind the plate (estimate; no CAD published).

## Rejected and why
- Ring on roller 1 servo side — only 16 mm from the Axon at -10 deg.
- Steel 2303 gears with pulley on the hub — 40T hub caps the idler pulley at 48T, needs a 250 mm non-goBILDA belt and a slower roller.

## Open questions
- Rim hangs 2.2 cm below the base plate and 1.4 cm ahead of the Rhino — check against the turret/robot.
- Roller-2 ring reaches y 10.15, ~4 mm past the estimated Axon depth.
- Measure Axon MINI depth; split assumes rollers do ~half the ball's work — test for belt skip.
