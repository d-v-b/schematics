# Bolt bar

A flat 40 x 4 mm bar with a row of slots for M6 bolts down its middle. It
sits on top of a 40 mm aluminium extrusion rail and bolts into the rail's
T-slot with M6 bolts and T-nuts; the slots let each bolt sit anywhere
along its 30 mm.

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
| end margin | 20 mm (least distance from an end to a slot centre) | `--end_margin` |
| slot count | as many as fit | `--slots` |
| corner radius | 3 mm | `--corner_r` |

The row of slots is centred along the bar, so at the defaults a 200 mm bar
gets five slots centred at 20, 60, 100, 140 and 180 mm, each reaching 5 mm
short of the next. `--slots N` fixes the count instead. `--slot_l 6.6`
(equal to the width) gives plain round holes. `--label "..."` engraves an
ID into the top face beside the slots.

## Use

```
pixi run bar                                   # stl/bolt_bar_L200_p40_s30x6.6.stl
pixi run render out.stl --length 120 --pitch 30 --slot_l 20
pixi run test
```

Print it flat, as modelled: the slots run vertically and nothing overhangs.
