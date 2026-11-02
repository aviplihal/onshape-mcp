# Lessons

Loaded every session. Short, one lesson per bullet. Cap ~150 lines: merge or delete old lessons before adding. Infrastructure notes go in Claude.md, not here.

## Onshape modeling and assembly
- Lengths: bare numbers are mm; pass explicit suffixes ("30 mm") when unsure. The API itself works in meters. Robot frame: origin at the footprint centre on the tiles, +x right, +y front, +z up (see the robot's design file).
- Each subsystem lives in its own Part Studio (or clearly prefixed features); assemble them in one Assembly. Work only in your subsystem's studio.
- The API allows 2,500 successful calls per user per year (402 after that, no dashboard). Prefer `describe_part_studio` (text + images in one call) over many small reads.
- Check every mutating result's status; a silent regen failure shows as a feature with a non-OK status in `get_features`.
- Public FTC robot docs: BOM "Part number" is empty; COTS parts are named with vendor suffixes "(GB)", "(REV)", "(SC)". Link-shared (non-public) documents return 403.

## Design
- Check the actuator budget (8 motors, 8 servos for the whole robot) before choosing a concept, not after building it.
- Give the stowed envelope and the extended envelope separately; R102 applies stowed, R105 extended.
- Size every part from its function: state what it must do, the requirement that sizes it and the calculation, and mark assumptions — never place a placeholder size without saying so.
- On a pivoting hood, drive from a pulley or gear on the pivot axle and put any direction reversal on the hood, so belt length and gear mesh stay constant.
- Check COTS hardware outer diameters (bearing flanges, pulley hubs) against shaft spacing in the master sketch before building.

## Workflow
- Don't use `eval_featurescript` to build parts in a design session unless the user agrees; if a tool is missing, note it for the tool lane instead.
