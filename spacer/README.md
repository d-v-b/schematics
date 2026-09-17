# Spacer

A star-shaped band that sits between an acrylic sheet and the rafter it is
screwed to, with the fixing screw passing through the aperture in its middle.
The screw drives home into the rafter and the band holds the sheet off the
timber, so the sheet is spaced rather than drawn down onto it.

The shape is the *perimeter* of a 5-pointed star dilated by a 6 mm disk:
every point within 3 mm of the star's outline, and nothing else. Dilating
the outline rather than the whole star is what gives the part an inside as
well as an outside — it comes out as a band of constant width with a clear
aperture down the middle. That uses about half the plastic of the solid
disk spanning the same circle, and leaves no broad flat face for water to
sit on: what lands on a 6 mm rib runs off it.

![profile](profile.svg)

## Dimensions

| | default | flag |
|---|---|---|
| tip radius | 20 mm (how far the points reach) | `--outer_r` |
| dilation radius | 3 mm, so the band is 6 mm wide and every tip is rounded to R3 | `--band_r` |
| waist | 0.382, the star's valleys as a fraction of its tips (a regular pentagram) | `--waist` |
| points | 5 | `--points` |
| thickness | 3 mm (the standoff it sets) | `--thickness` |
| least aperture | 6 mm, refused below | `--min_aperture` |

The star itself has its tips on `outer_r - band_r` = 17 mm, so growing the
outline by 3 mm lands the finished tips on 20 mm exactly. Shrinking it by
the same leaves the aperture:

```
aperture = 2 * (star_r * waist - band_r) = 2 * (17 * 0.382 - 3) = 7.0 mm
```

At 7.0 mm that is a shade over the 6 mm hole drilled for the screw, so the
spacer threads onto the screw and stays centred on it rather than sliding
about while you position the sheet. Widening `--waist` opens the aperture up
(0.5 gives 11 mm) and uses marginally less material, at the cost of that
self-centring. `validate()` refuses anything that puts the aperture under
`--min_aperture`, including a band fat enough to close the middle entirely.

## Use

```
pixi run spacer                                # stl/spacer_R20_b3_w0.382_p5_t3.stl
pixi run render out.stl --points 6 --thickness 6
pixi run test
```

Print it flat, as modelled: the aperture runs along the print's Z, so
nothing overhangs and no part of it needs support.

Printed in black PETG. PETG rather than PLA because the screw bears on the
band for the life of the fixing and PLA creeps under a steady load, and
black because carbon black absorbs UV, so it weathers better than a natural
or translucent filament.

Print it solid or near-solid for the same reason — a sparse infill will
creep and let the sheet settle. At a 6 mm band that costs almost nothing:
four perimeters at 0.45 mm fill 3.6 mm of the 6 mm on their own, so going
to 100% infill adds very little time.
