# Spacer

A flat disk that sits between an acrylic sheet and the rafter it is screwed
to, with the fixing screw passing through its bore. The screw drives home
into the rafter and the disk holds the sheet off the timber, so the sheet is
spaced rather than drawn down onto it.

![profile](profile.svg)

## Dimensions

| | default | flag |
|---|---|---|
| outer radius | 20 mm | `--outer_r` |
| bore | 6 mm, the hole drilled for the screw | `--hole_d` |
| thickness | 3 mm (the standoff it sets) | `--thickness` |

That leaves 17 mm of wall between the bore and the rim, and a 40 mm face to
bear on the acrylic — wide enough that tightening the screw presses on the
sheet over an area rather than at a point.

`--thickness` is the dimension worth varying: it is the gap the spacer
exists to set. `--label "..."` engraves an ID into the top face, in the ring
of material beside the bore.

## Use

```
pixi run spacer                                # stl/spacer_R20_d6_t3.stl
pixi run render out.stl --thickness 6
pixi run test
```

Print it flat, as modelled: the bore runs along the print's Z, so nothing
overhangs and the bore needs no support. Print it solid or near-solid — the
screw bears on the disk through its whole life, and a sparse infill will
creep and let the sheet settle.
