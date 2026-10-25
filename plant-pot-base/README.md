# Plant pot base

A round base for a 7 cm plant pot: a 2 mm floor and a 2.4 mm wall, whose
top edge rises and falls in six gentle waves round the rim.

![preview](preview.svg)

The pot's sides slope outward, which is not modeled. Instead the pocket is
5 mm wider than the pot's foot, so the pot drops in without catching on the
wall.

The crest follows a raised cosine round the rim:

```
z(theta) = trough_h + (peak_h - trough_h) * (1 + cos(lobes * theta)) / 2
```

At the defaults it peaks at 10 mm and dips to 6 mm, both measured from the
bed, over six lobes about 42 mm long. In every radial section the crest is
level across the wall, with both corners rounded to R1, so the rounding
looks the same on the steep parts of the wave as on the peaks.

## Dimensions

| | default | flag |
|---|---|---|
| pot diameter at the foot | 70 mm | `--pot_d` |
| slack | 5 mm, so the pocket is 75 mm across | `--slack` |
| wall | 2.4 mm, so the base is 79.8 mm across | `--wall` |
| floor | 2 mm | `--floor` |
| wave peaks | 10 mm from the bed | `--peak_h` |
| wave troughs | 6 mm from the bed | `--trough_h` |
| lobes | 6 | `--lobes` |
| crest rounding | R1 on both corners | `--crest_r` |
| foot chamfer | 0.5 mm on the outer edge, against elephant's foot | `--foot_chamfer` |

`validate()` refuses a trough too low for the crest rounding to fit above
the floor, rounding wider than half the wall, and anything over the 256 mm
bed.

## Use

```
pixi run base                       # stl/base_d70_s5_h6-10_l6.stl
pixi run render out.stl --lobes 8 --trough_h 4
pixi run test
```

Print it as modeled, floor on the bed. The wall is vertical and the crest
only ever faces up, so nothing overhangs and nothing needs support. It is
about 13.4 cm³ of plastic.

The floor is solid, so the base also works as a drip tray.

## How it is built

The wall is lofted through its cross-section stood up in radial planes, one
half-lobe (peak to trough) at a time; that piece is mirrored and turned
round the rim, and the floor is fused in. A single loft round the whole rim
gave OCCT booleans that returned wrong volumes once the wave had more than
six lobes, so the tests check the base's volume against the analytic value
as well as its heights.
