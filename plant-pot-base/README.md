# Plant pot base

Round bases for plant pots: a floor and a 2.4 mm wall, whose top edge
rises and falls in gentle waves round the rim. There are two:

- a 7 cm base with a flat 2 mm floor and six waves (`pixi run base`), and
- a 15 cm base whose floor is rippled, so the pot rests on rounded peaks
  and water stands in the dimples between them, where air reaches it and
  it dries (`pixi run base-15`). See [The 15 cm base](#the-15-cm-base).

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
| floor ripple amplitude | 0, a flat floor | `--ripple_a` |
| floor ripple wavelength | 40 mm | `--ripple_l` |

`validate()` refuses a trough too low for the crest rounding to fit above
the floor (the ripples' peaks, if any), rounding wider than half the wall,
and anything over the 256 mm bed.

## The 15 cm base

![preview](preview-15.svg)

150 mm across and 25 mm tall: the same base with a 145.2 mm pocket
(`--pot_d 140.2 --slack 5`), a wall waving between 21 and 25 mm over 11
lobes about 43 mm long, and a rippled floor:

```
z(x, y) = floor + ripple_a * (1 + cos(k x) * cos(k y)),   k = 2 pi / ripple_l
```

With `ripple_a` 5 mm and `ripple_l` 40 mm, the floor is 2 mm thick at the
bottom of the dimples and 12 mm at the peaks, which sit 28 mm apart on a
diagonal grid, one of them on the axis. The pot rests on the peaks and
stands 13 mm into the wall at the wall's highest points, 9 mm at its
lowest. Between neighboring peaks the surface dips 5 mm through a saddle,
so air moves under the pot in both directions, and each dimple holds
water on its own. The steepest slope is about 38 degrees, and it faces
up, so it prints without support.

The base is about 142 cm³ if printed solid; most of that is the floor
under the peaks, so the slicer's infill sets how much plastic it takes.
In the drawing the ripples show only as their silhouettes, with a few
stray arcs at the sides where the hidden-line pass trips over the curved
floor.

## Use

```
pixi run base                       # stl/base_d70_s5_h6-10_l6.stl
pixi run base-15                    # stl/base_d150_h21-25_l11_ripple5x40.stl
pixi run render out.stl --lobes 8 --trough_h 4
pixi run test
```

Print it as modeled, floor on the bed. The wall is vertical and the crest
only ever faces up, so nothing overhangs and nothing needs support. It is
about 13.4 cm³ of plastic.

The floor is solid, so the base also works as a drip tray.

## How it is built

The wall's foot is a plain ring, turned about the axis, from the bed to
midway between the floor's top and the crest's rounding. Above it the wall
is lofted through its cross-section stood up in radial planes, one
half-lobe (peak to trough) at a time; that piece is mirrored and turned
round the rim, and the floor is fused in. A single loft round the whole rim
gave OCCT booleans that returned wrong volumes once the wave had more than
six lobes, so the tests check the base's volume against the analytic value
as well as its heights.

The rippled floor is a B-spline fitted through the cosine on a grid about 2.5 mm apart,
within about 5 µm of it, and a disc is cut off under it. OCCT could not
intersect that B-spline with the lofted wall, so the ring is there to give
the floor a true cylinder to meet. The tests compare the volume against the
analytic integral, which needs a Bessel function for the part of the
ripple left over at the pocket's edge, and integrate the volume more
finely than build123d's default, which is off by about 0.5 % on the
B-spline.
