# Shooter — constraint cards (rev 2026-10-22: belt-then-gear drive, motor, inertia on roller 2)

Document: "Shooter Parts" (Fusion, project Shooter). Units below: mm in text, world coordinates in cm as Fusion reports them.
Frame: shafts run along world **y**. Side Plate L y 0..0.3 (drive side is y < 0), Side Plate R y 7.55..7.85, servo side y > 7.85.
Hood ("Shooter Hood:1") pivots on the flywheel shaft (x 3.35, z 0), as-built joint "Hood angle", range −10°..0°. Build/check at 0°, sweep −10..0.
Rollers R1 (x −7.496, z +0.81) and R2 (x −7.496, z −0.81), 16.2 mm apart, on 8 mm REX axles in the hood. Ball: POLLEN Ø71 mm, 25 g.
All custom parts are 3D-printed PLA. goBILDA parts only for COTS (no REV).

Speeds: motor 6000 rpm → flywheel 4615 rpm → idler 13,615 → rollers 27,230 rpm (flywheel→roller 5.9×; both rollers turn opposite the flywheel).

## Drive train (subassembly)
```
job:          motor → flywheel shaft (belt A) → idler (belt B, 2.95×) → R1 (gear stage, 2×) ; R1 → R2 (belt C, inside the walls, 1:1)
interfaces:   belt A: 5203-2402-0001 motor 20T 3422-4008-0020 → printed 26T GT2 on flywheel shaft, belt 3423-0006-0328 (centres 141.0 mm, fits 328.05 mm, no tensioner)
              belt B: printed 59T GT2 on flywheel shaft → 20T 3422-4008-0020 on idler, belt 3423-0006-0264 (centres 91.5 mm)
              gears: 2303-4008-0040 (40T MOD0.8 steel) on idler meshing 2303-4008-0020 (20T) on R1, centre distance 24.0 mm
              belt C: 20T 3422-4008-0020 on R1 and on R2, inside the walls between the roller and the Roller Bearing Block (world y 4.70..6.15)
idler axis:   x −5.535, z +2.193 (solved: 264 mm belt from flywheel, 24 mm from R1, 35.9 mm from R2 axis)
support:      every pulley/gear between two bearings or retained by a collar; no part at a bare shaft end
envelope:     drive side may grow (user OK) — target ≤ 45 mm outboard of Side Plate L (y ≥ −4.5)
size sanity:  59T is printed (Ø37.6 pitch); 26T printed via scripts/fusion/gt2_pulley.py; 40T/20T stock steel
references:   Droid Force flywheel/roller stacks (kb_search kind=stack flywheel / roller): bearing in every plate, spacers close every gap
done when:    audit_shaft_stacks, audit_fastening, check_interference clean + cad-reviewer blockers closed
```
Belt C note: 20T/20T at 16.2 mm centres needs a 72.4 mm loop; goBILDA's shortest is 88 mm (3423-0006-0088). Use the 88 mm belt plus one 3427-0002-0001 idler pulley pressing on the outside of a span to take up 15.6 mm (place it on the Roller Bearing Block or the hood arm), or report a better option. Do not move R1/R2.

## Layer stack on the drive side (y, outward from Side Plate L)
```
Side Plate L          0 .. 0.30   (unchanged)
Hood Arm L v2        −0.05 .. −0.45 (unchanged, bearings flange to −0.55)
gear layer           ≈ −0.60 .. −1.40   40T (idler), 20T (R1)
belt B layer         ≈ −1.45 .. −2.35   59T (flywheel shaft), 20T (idler)
Hood Outer Plate     ≈ −2.45 .. −2.85   4 mm, bearings for flywheel shaft (pivot), idler, R1
belt A layer         ≈ −3.0 .. −3.9     26T (flywheel shaft), 20T (motor shaft extension)
Motor Belt Bracket   ≈ −4.0 .. −4.4     fixed to the frame, bearings for flywheel-shaft end and motor-shaft extension
```
Read real widths from `insert_part` main_axis and adjust; keep the order.

## Motor mount
```
job:          drive the flywheel shaft; 5203-2402-0001 Yellow Jacket 1:1, 6000 rpm, 24 mm 8 mm-REX shaft
interfaces:   existing spot: Side Plate L Ø14 hole at x −10.70, z −1.20 with 4× M4 on a 16 mm square (−11.50/−9.90, −2.00/−0.40); face on Side Plate L's inner face (y 0.30), body through Side Plate R's Ø38 hole. 4× M4 screws.
support:      motor shaft (24 mm) does not reach belt A: REX coupler / 8 mm REX shaft extension, its outer end in a bearing in the Motor Belt Bracket
envelope:     motor body inside the frame between the side plates; must clear the ball path and Base Plate (top z −2.50)
done when:    as above
```

## Flywheel shaft (x 3.35, z 0)
```
job:          carries Rhino wheel (existing, keep), 26T + 59T pulleys; is the hood pivot
support:      bearings: Side Plate L (:13), Side Plate R (:14), Hood Arm L (:20), Hood Arm R (:26), + new in Hood Outer Plate and Motor Belt Bracket
retained:     Hyper Hub clamps the Rhino; spacers close every gap; 2920-0001-4008 collar outboard of Hood Arm R bearing :26 (replaces "Spacer FW 6mm")
length:       from the Motor Belt Bracket bearing (≈ −4.4) to the collar (≈ 9.3); cut the shaft to that
remove:       Bike-wheel flywheel (rim + hub, occurrence "Bike-wheel flywheel:1", joint "Rigid 4"), Drive gear 94T (component "Drive gear 94T (printed PLA)")
```

## Idler shaft (new, x −5.535, z 2.193, on the hood)
```
job:          20T pulley (belt B) + 40T gear; ~13,600 rpm
support:      8 mm REX shaft, bearing 1611-0514-4008 in Hood Arm L and in Hood Outer Plate (both sides), spacers between, collar or plate retention both ends
interfaces:   Hood Arm L v2 and Hood Outer Plate need a lobe up to ≈ z 4.0 at x −5.5 to hold the bearing (Ø14 seat) and cover the 40T (tip r 16.8 mm)
```

## Roller axles R1 / R2 (existing, keep rollers, spacers, 2920 collars inside)
```
R1:     add 20T 2303 gear in the gear layer, bearing in Hood Outer Plate (axle extended to it), 20T pulley for belt C inside the walls
R2:     drive side ends at Hood Arm L bearing :18 (nothing outboard needed; add collar if the audit asks); 20T pulley for belt C inside the walls
inside: belt C pulleys between roller (ends 4.70) and Roller Bearing Block bearing (6.15): re-cut the spacers/collars there so each stack is gap-free
remove: Gear 16T R1 M0.8, Gear 16T R2 M0.8
```

## Inertia ring on R2 (servo side, existing "R2 inertia ring (steel 32-22x16)")
```
job:          all of the shot inertia now: need ≈ 215 g·cm² on R2 (×34.8 at the flywheel ≈ 7,470 g·cm² budget)
change:       lengthen 16 → 32 mm (y 8.5 .. 11.7), Ø32/Ø22 steel; check it clears the Axon (x −11.6..−7.9, y 7.1..10.1) and Base Plate (top z −2.50)
retained:     ring hub clamps R2 (set screw); axle R2 extended to the ring's outer face
```

## Hood Outer Plate (new, replaces "Drive Outer Wall (printed)")
```
job:          outboard support of flywheel shaft (pivot), idler and R1 bearings; covers belt B and the gear layer
interfaces:   ≥ 4 M4 standoffs (goBILDA, length = gap to Hood Arm L) + screws to Hood Arm L, clear of every gear/pulley OD by ≥ 2 mm; 1611 bearings in 3 seats
covers:       59T, 40T, both belt-B pulleys, R1 gear; outline follows Hood Arm L plus the idler lobe
manufacture:  4 mm PLA, print flat, Ø14 bearing seats, 0.5–1 mm rub gap to spinning parts
```

## Motor Belt Bracket (new, on the frame, not the hood)
```
job:          outboard bearings for the flywheel-shaft end and the motor-shaft extension; guards belt A
interfaces:   ≥ 3 M4 standoffs to Side Plate L placed outside the hood's −10..0° sweep and ≥ 2 mm clear of every pulley OD in every layer they pass
manufacture:  4 mm PLA, print flat
```

## Clean-up
```
remove:  idler gears 42T X/C, Pins X/C, MR63 bearings, pin spacers, Drive Outer Wall, Drive gear 94T, Gear 16T R1/R2, Bike-wheel flywheel
holes:   delete stale holes in Hood Arm L (pin X/C seats, old idler bearing hole at x 0.95) — no hole without a fastener
base:    suppress the "Base plate drive-gear notch" cut if nothing needs it any more
labels:  update the "MASTER v2 Hood drive" sketch texts to this design
```
