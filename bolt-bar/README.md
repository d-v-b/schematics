# Bolt bar

A flat 40 x 4 mm bar with a row of M6 clearance holes down its middle. It
sits on top of a 40 mm aluminium extrusion rail and bolts into the rail's
T-slot with M6 bolts and T-nuts.

![profile](profile.svg)

## Dimensions

| | default | flag |
|---|---|---|
| length | 200 mm | `--length` |
| width | 40 mm | `--width` |
| thickness | 4 mm | `--thickness` |
| hole diameter | 6.6 mm (M6 clearance 6.4 + 0.2 print allowance) | `--hole_d` |
| hole pitch | 40 mm | `--pitch` |
| end margin | 20 mm (least distance from an end to a hole centre) | `--end_margin` |
| hole count | as many as fit | `--holes` |
| corner radius | 3 mm | `--corner_r` |

The row of holes is centred along the bar, so at the defaults a 200 mm bar
gets five holes at 20, 60, 100, 140 and 180 mm. `--holes N` fixes the count
instead. `--label "..."` engraves an ID into the top face.

## Use

```
pixi run bar                                   # stl/bolt_bar_L200_p40_d6.6.stl
pixi run render out.stl --length 120 --pitch 30
pixi run test
```

Print it flat, as modelled: the holes run vertically and nothing overhangs.
