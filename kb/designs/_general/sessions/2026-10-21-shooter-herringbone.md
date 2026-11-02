---
title: Shooter: herringbone drive, real Axon MINI, old arms removed
robot: _general
subsystem: shooter-herringbone
date: 2026-10-21
---

Wrote scripts/fusion/herringbone_gear.py (involute herringbone, REX bore) and built the 32T/16T MOD1 pair in place of the steel 2303s; fused the 59T pulley to the 16T and pulled the belt plane and outer plate in. Imported the goBILDA Axon MINI STEP; removed the old arms. Drive side now 2.95 cm.

## Tool lessons
- Remove a body cleanly with comp.features.removeFeatures.add(body) (execute_code); undo by suppressing the RemoveBody feature.
- Herringbone: sweep half the width with twistAngle = (w/2)*tan(helix)/r_pitch, mirror about the mid-plane, join. Opposite hand on the mating gear; offset its phase half a tooth.
- On an XZ sketch, sketch y = world -Z, so arcs drawn world-ccw run the long way; swap start/end.
- goBILDA STEP zips download from gobilda.com/content/step_files/<SKU>.zip even when parts.csv has no STEP link (Axon MINI 2004-0025-0001).
- on_axis on an already-rotated occurrence stacks transforms; insert fresh with on_axis + rotate in one call.
- Deleting a cut-paste occurrence brings the original back at root every time; sweep root into Obsolete after each delete or move.
- Rebuild a rigid group via API (delete, re-add) to swap a member that blocks moves.

## Decisions and why
- Axon MINI real body reaches y 10.12 behind the plate (tabs on plate outer face, spline into the pinion).
- Drive stack: arm -0.05..-0.45, herringbones -0.6..-1.4, belt plane -1.4..-2.3, outer plate -2.4..-2.8, axles end -2.95.

## Open questions
- Pinion (Component7) needs an H25T spline bore to match the Axon.
- Herringbone 16T tip land 0.5 mm at 0.15 mm backlash — test print for strength.
