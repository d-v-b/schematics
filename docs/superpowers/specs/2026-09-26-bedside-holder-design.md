# Bedside holder: design

A clip that hooks over the bed's side rail and stores a device upright in a
pocket that hangs down the rail's outer face. It's for storage, not
viewing: the device sits low, out of the way when getting in and out of
bed, and leans with its top toward the bed so it can't flop outward. One
parametric profile makes both
the laptop and the phone versions. Printed in PETG.

## Requirements

- Clamps over the bed rail: a board on edge, 23 mm thick and 160 mm tall,
  with its top edge exposed. The mattress sits inside the rail, with 5 mm
  of clearance between the rail's inner face and the mattress. Its top is
  40–80 mm above the rail's top edge.
- Holds a 15" M4 MacBook Air (340 × 238 × 11.5 mm, 1.51 kg), standing on
  its long edge, and, as a separate part, an iPhone 4 with no case
  (115 × 59 × 9.3 mm).
- The device's seat is 160–200 mm below the rail top (default 200), so the
  phone sits wholly below the rail top and the laptop pokes out about
  35 mm, at or below the mattress top.
- The device leans `lean` (default 7°) with its top toward the bed, lying
  on the hanger, and doesn't rattle. (Added after the first build: an
  upright laptop could flop away from the bed.)
- Looks like one strip of heat-bent plastic: constant thickness, smooth
  bends, no sharp corners. Its compliance comes from those bends.
- Prints flat on a 256 × 256 mm bed, with the extrusion (along the rail)
  as print Z (see the repo's print-orientation rule).

## Coordinates

X runs across the rail: the rail occupies −23 ≤ x ≤ 0, so +x points away
from the bed. Y points up, with y = 0 at the rail's top edge. Z runs along
the rail. The part is drawn in its XY profile and extruded along Z by
`length`; that profile lies flat on the bed when printed, so Z is print Z.

## Geometry

The whole part is one **strip** of thickness `t` (default 3.0 mm). Its
centreline is a chain of straight lines and tangent arcs, and the strip is
that centreline offset by ±t/2 (as in `beam-clip`). In order, from the bed
side:

1. **Inner-leaf flare:** an arc of R 6, turning 40°, that curls the tip
   away from the rail so the clip pushes on easily.
2. **Inner leaf:** a straight of `inner_len` (default 26) that leans in so
   that, relaxed, its inner surface overlaps the rail face by `inner_pre`
   (default 1.0) at the knee above the flare. The lean angle is solved from
   `inner_pre`.
3. **Inner corner bend:** an arc of inside radius `bend_ri` (default 3.5).
   It's placed so that its inner surface passes through the rail's top
   corner. The strip therefore touches the corner rather than the faces
   next to it, and it stands about 0.29·`bend_ri` (1 mm) off the top edge
   and off the faces near the corner.
4. **Top:** a straight across the rail.
5. **Outer corner bend:** the same as 3, mirrored, but it stops `lean`
   short of vertical.
6. **Hanger:** a straight leaning `lean` down and away from the outer
   face, to the J. Everything from here on (J, lip, flare) is built in the
   hanger's frame, so the pocket leans with it.
7. **J-bend:** a 180° arc whose centreline radius is gap/2 + t/2, where
   gap = `device_t` + `slot_clearance` (default 0.5). Its centre sits at
   y = −`drop` (default 200), which is where the device's foot seats; its
   inside bottom is gap/2 lower.
8. **Lip:** a straight of 10, then an arc of R 20 leaning `lip_lean`
   (default 6°) in toward the device, then a straight whose length is
   solved so that, relaxed, the lip's inner surface reaches the device by
   `lip_pre` (default 0.75) where its flare turns it back parallel to the
   hanger.
9. **Lip flare:** an arc of R 8 turning 40° outward, then a 4 mm straight,
   as a lead-in.

**Pad.** A solid buttress on the hanger's rail side holds it off the rail
face at y = −`pad_y` (default 140, which leaves 14 mm to the bottom of the
160 mm rail). Its outline is a nose of radius `pad_r` (default 6) that
touches the rail face along one line, joined to the hanger's rail-side face
above and below by concave fillets of radius `pad_fillet` (default 15),
tangent at every joint. Nothing crosses the hanger's device-side face,
which stays flat for the device to lie on. At 7° the pad spans about
18 mm. It isn't part of the strip: it is solid so the lean doesn't sag
under the laptop. (The first version was a stadium centred on the hanger's
centreline; it poked 4.5 mm through the device-side face.)

The device's back lies on the hanger's outer surface, and its foot sits in
the J. The lip's preload pushes the device's lower back onto the hanger,
and the lean lays the rest of it there. The device's weight presses the
hanger onto the pad and the clamp, so the lean is set by solid material.
The laptop's top ends about 35 mm above the rail top, right over the
rail's outer face.

Parts, all from this one profile:

| part   | `device_t` | `length` | count | spacing on rail |
|--------|-----------:|---------:|------:|-----------------|
| laptop |       11.5 |       50 |     2 | ~200 mm apart   |
| phone  |        9.3 |       40 |     1 | —               |

## Parameters

A frozen `HolderParams` dataclass with the defaults above, plus `rail_t`
23.0, `mattress_clear` 5.0, `label` "", `label_depth` 0.4, `label_size`
5.0, `modulus` 2000 MPa and `creep_limit` 15 MPa (PETG, the same values as
the other schematics). It also has `max_size` 250,
`lean` 7°, `rail_h` 160, `pad_y` 140, `pad_r` 6 and `pad_fillet` 15.

## Validation

`validate()` raises `ValueError` for:

- any non-positive dimension
- `bend_ri` ≤ 0, or any arc whose centreline radius is ≤ t/2, since the
  offset would self-intersect
- a lean that can't be solved: the inner leaf or the lip can't reach its
  preload with the given lengths
- the inner leaf, with its flare, protruding more than `mattress_clear`
  from the rail's inner face
- a profile bounding box larger than 250 mm on either side, which leaves
  margin on the 256 bed
- inner-leaf or lip bending stress above `creep_limit`
- `label_depth` ≥ `t`
- a pad that hangs off the bottom of the rail (`pad_y` + `pad_r` >
  `rail_h`)
- a pad that misses the hanger (its blends above its start, or below the J)
- a lean too small to hold the hanger off the rail at the pad
- a `pad_fillet` too small to reach from the nose to the hanger

**Stress model.** Each spring is treated as a cantilever of the strip,
deflected at its knee by its preload δ:

    σ = 3·E·(t/2)·δ / L²

L is the vertical lever arm from the leaf's root (the end of the corner
bend, or the top of the J) to its contact point. At the defaults that gives
12.5 MPa for the inner leaf and 12.4 MPa for the lip (from the prototype).
The bends add compliance on top of this, so the cantilever is conservative.
A rail 0.5 mm over its nominal thickness raises the inner leaf's δ by half,
which takes it over the limit at both t = 3 (about 19 MPa) and t = 2.5
(about 16 MPa). That's the reason to sweep `inner_pre` and `t` on coupons
against the real rail. The lip's stress is partly self-limiting: a larger
`lip_pre` also lengthens its solved straight, and so its arm.

## Coupons

Because the part is 2.5-D, a coupon is a 1 mm slice of the full profile
(`--length 1`). Each one tests the clamp on the rail and the pocket with
the device at once, at their real positions, with the lean and the pad.
(The first version cropped 10 mm coupons to the clamp or the pocket by a
`section` parameter; slices of the whole part replaced them.)

A slice is too thin for text on a side face, so it carries its ID
engraved 0.4 mm into its top face (z = `length`), centred on the hanger
between the rail top and the pad, reading up the hanger, in text `t` − 1
tall so it fits the strip's width (as `curtain-hanger/` does for short
coupons). A full part, long enough for `label_size` text, carries its ID in
the hanger's rail-side face instead, hidden in use.

The sweeps deliberately bracket the creep ceiling, so the coupon recipes
pass `--creep_limit 30`, in the same way `curtain-hanger/` passes
`--min_safety 0` to its coupons. Justfile sweeps (the values are editable
at the top of the justfile, as in `curtain-hanger/`):

- `coupons`: (`inner_pre`, `lip_pre`) ∈ {(0.5, 0.5), (1.0, 0.75),
  (1.5, 1.0)} × `t` ∈ {2.5, 3.0} for the laptop's `device_t`, labelled e.g.
  `ip1.0 lp0.75 t3`; `phone-coupons` does the same at 9.3. Twelve slices in
  all.

Once the coupons settle the values, `laptop` and `phone` render the full
parts.

## Layout in the repo

A new `bedside-holder/` directory, following `beam-clip/`:

- `path.py`: a pure-Python turtle of lines and tangent arcs, which samples
  the centreline or either face of the strip
- `test_path.py`
- `holder.py`: params, spring solves, validation, centreline, profile,
  part, and a CLI that writes STL, STEP or SVG
- `test_holder.py`
- `justfile`: `laptop`, `phone`, the coupon sweeps, `render` (any output),
  `preview` (the README's SVG profile), `test`, `clean`
- `pixi.toml`
- `README.md`: a short write-up with the rendered `profile.svg`

No `conftest.py` is needed, since nothing is shared between the test files.

## Testing

Following the repo's rule, there is one test that builds the part across a
grid of reasonable parameters: both devices, a 1 mm slice and a 10 mm part, `t` 2.5 and
3.0, a few `drop` values, and leans of 5°, 7° and 9°. The pocket is
checked in its own frame, from the J's centre with u across the slot and v
up the hanger. For each, it checks that:

- the solid is valid
- its bounding box matches the expected extents
- the device's seat, the J's centre, is at y = −`drop`
- the hanger's device-side face lies along the lean
- on the full part, the pad touches the rail face at y = −`pad_y`, and only
  there; the hanger's device-side face is clear across the pad's blend; and
  the pad's outline is tangent at all four joints
- the relaxed slot gap at the lip knee equals `device_t` − `lip_pre`
- the inner leaf's knee overlaps the rail by `inner_pre`
- the mattress-side protrusion is ≤ `mattress_clear`
- the modelled stresses are below `creep_limit`
- a label removes material, from the top face within the strip's width on
  a slice, and from the hanger's rail-side face on a longer part

Then there is one test per `ValueError` case listed under Validation.
