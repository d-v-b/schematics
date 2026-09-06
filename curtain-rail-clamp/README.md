# Curtain rail clamp

A clamp for the IKEA FRAMFUSIG curtain rail: a telescopic single-track
ceiling rail of two nested steel tubes with a glider slot on the underside.

![rail profiles](rail_profiles.svg)

IKEA publishes no profile dimensions; these were measured with calipers.

| Tube  | Width | Height | Corner radius | Slot |
|-------|-------|--------|---------------|------|
| Inner | 17.4  | 10.0   | 5.0 (full stadium) | 6.75 |
| Outer | 19.5  | 12.2   | 5.5           | 6.75 |

All in millimetres. Wall thickness is assumed 0.8 mm.

## The clamp

![clamp profile](clamp_profile.svg)

A snap-on clamp that grips the rails from above, leaving the underside clear
for the gliders and the curtain. It holds two rails side by side (or one, or
more: `tubes` is a list).

- Each rail sits in a thin C of uniform `wall` following the rail's section
  at `clearance` (zero or negative to squeeze the rail), open at the bottom.
  The lips follow the rail's lower rounds down until the gap between them is
  `opening`, which is narrower than the rail: the rail is pushed up into the
  C, each half flexes outward as a curved cantilever, and it springs back to
  trap the rail. The lips cannot wrap under the rail: its flat underside
  is only 7.3 mm wide and the glider slot takes 6.75 mm of it. The deepest
  practical lips (about a 9.5 mm opening) contact the rail at nearly 80
  degrees from vertical; a clamp that tight cannot snap on and must slide
  on from the rail's end (set `min_safety` to 0 to render it).
- The Cs hang from a flat top plate, `plate_t` thick, spanning them at
  `spacing` centre to centre. The plate is the mounting face. Every C's top
  is at the same height, so a smaller (inner) tube hangs a little lower.
- Each C hangs by a short neck (`stem_w` × `stem_h`) on its flat top, with
  `fillet_r` fillets at the neck's four corners, so both junctions are
  smooth. The neck and fillets must stay on the flat top: the C's rounds are
  where the flex lives, and blending material onto them stiffens the snap
  so much that insertion would exceed PLA's strength (the validation
  refuses it). The compliance figures treat the C as clamped at the edge
  of the fillet.
- Rendering prints a compliance report: the force and stress to snap a rail
  in, and a rough estimate of the downward force before the rail pushes the
  lips apart and escapes. Each lip's spring force acts on the rail's lower
  round, whose surface at the lip is some angle from vertical; the vertical
  share is that force times the tangent of the angle. Shallow lips barely
  hold, which is what the first prints showed; lips near the underside hold
  until they break. Thicker walls also hold more but stress more on
  insertion, and the model has proved conservative for printed walls:
  `min_safety` sets where it refuses.

Print with the profile flat on the bed, rails' axis vertical.

Sizing the grip: the interference is the rail's own width minus the
opening. Prints with 0.76 to 1.3 mm of interference and lips 2.5 to 3.5 mm
past the rounds all slipped; the defaults are now a 16 mm opening (3.5 mm
of interference, lips 4.3 mm past the rounds, 45 deg contact) at zero
clearance. The outer tube is modelled as a full stadium, the narrowest it
can be at the lips.

## Files

- `framfusig.py` — the two rail sections (`INNER`, `OUTER`) as build123d
  sketches, plus the drawing above.
- `rail_clip.py` — the clamp. Parameters are `ClipParams`
  (`python rail_clip.py --help`).
- `compliance.py` — cantilever model used for the snap figures.
- `test_framfusig.py`, `test_rail_clip.py` — the sections match the
  measurements; the clamp seats every rail without touching it, traps it,
  keeps clear of the underside, and stays within the material's strength.

## Setup

```bash
pixi install
pixi run sweep     # single-C test prints over wall x lip_depth
pixi run clamp     # the two-rail clamp with the values in the justfile
pixi run preview   # redraw the drawings
pixi run test
```
