# Bolt bar

A flat 40 x 4 mm bar with a row of slots for M6 bolts down its middle. It
sits on top of a 40 mm aluminium extrusion rail and bolts into the rail's
T-slot with M6 bolts and T-nuts; the slots let each bolt sit anywhere
along its 30 mm. Each end is a 20 mm radius semicircle centred on the
first slot, so a bar pivoting on a bolt there turns on the rail without
its end swinging out past the bar's own width.

![profile](profile.svg)

## Dimensions

| | default | flag |
|---|---|---|
| length | 200 mm | `--length` |
| width | 40 mm | `--width` |
| thickness | 4 mm | `--thickness` |
| slot width | 6.6 mm (M6 clearance 6.4 + 0.2 print allowance) | `--slot_w` |
| slot length | 30 mm overall, round ends | `--slot_l` |
| slot pitch | 40 mm (so 10 mm of material between slots) | `--pitch` |
| end margin | 20 mm (square ends only: least distance from an end to a slot centre) | `--end_margin` |
| slot count | as many as fit | `--slots` |
| end cap radius | 20 mm (arc centred that far in from the tip; 20 = semicircle, 0 = square) | `--end_r` |
| corner radius | 3 mm, where a larger end arc meets the sides | `--corner_r` |

The end slots are always centred on the end arcs' centres, since that is
the pivot the bar can turn on without its end reaching past the arc. The
length must therefore be two radii plus a whole number of pitches: at the
defaults 200 mm gives five slots centred at 20, 60, 100, 140 and 180 mm,
each reaching 5 mm short of the next, and 210 mm is refused with the
nearest valid lengths named. `--slots N` fixes the count instead. With
square ends (`--end_r 0`) the row is simply centred along the bar with at
least `--end_margin` at each end. `--slot_l 6.6` (equal to the width)
gives plain round holes. `--label "..."` engraves an ID into the top face
beside the slots.

## Use

```
pixi run bar                                   # stl/bolt_bar_L200_p40_s30x6.6_r20.stl
pixi run render out.stl --length 120 --pitch 30 --slot_l 20 --end_r 0
pixi run test
```

Print it flat, as modelled: the slots run vertically and nothing overhangs.
