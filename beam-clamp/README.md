# Beam clamp

Two models for a rectangular wooden beam (53.6 mm wide, 206.5 mm tall):

- **Clamp** (`beam_clamp.py`): a C-shaped spring clip that cups the underside
  of the beam and grips its two sides.
- **Wrap** (`beam_wrap.py`): two identical halves that ratchet together
  around the whole beam. See [Beam wrap](#beam-wrap) below.
- **Bolt** (`beam_bolt.py`): the same two-half idea with a bolted finger
  joint instead of the ratchet. See [Beam bolt](#beam-bolt) below.
- **Flex** (`beam_flex.py`): two halves that snap together using the arms'
  own compliance, no jog and no hardware. See [Beam flex](#beam-flex) below.

![profile](profile.svg)

## Files

- `beam_clamp.py` — the clamp model, written with
  [build123d](https://build123d.readthedocs.io/). Every dimension is a field of
  `ClampParams` and a `--flag` on the command line (`python beam_clamp.py --help`).
- `beam_wrap.py` — the wrap model, sharing the clamp's corner and helper code.
  Parameters are `WrapParams` (`python beam_wrap.py --help`).
- `beam_bolt.py` — the bolted variant. Parameters are `BoltParams`.
- `beam_flex.py` — the compliant snap variant. Parameters are `FlexParams`.
- `compliance.py` — cantilever model of an arm: force and stress for a
  deflection, per material.
- `justfile` — dev actions (`just --list`): render either phase, refresh the
  profile drawing, run tests, clean.
- `pixi.toml` — the schematic's environment. `pixi run <recipe>` runs any just
  recipe inside it.
- `test_beam_clamp.py`, `test_beam_wrap.py`, `test_beam_bolt.py`,
  `test_beam_flex.py` — geometry
  checks across a grid of parameters (for the two-half models: mate a rotated
  copy and prove it neither interferes nor pulls apart, and for the bolt that
  the bolts pass at every slot position), plus one test per validation error.
- `stl/` — rendered output, ready to slice.

## Setup

```bash
pixi install
```

That is the whole setup; build123d and its OpenCASCADE kernel come from
conda-forge. Then either `pixi shell` and use `just` directly, or prefix
commands with `pixi run`.

## Geometry

- Inner span = `beam_w + clearance` (default 53.6 + 0.3 mm).
- Arms reach `arm_len` (53.6 mm) along the beam sides, so the profile is square.
- Wall thickness `wall` is uniform everywhere, including around the corners:
  each corner is a bent-sheet elbow with inner radius `fillet_r` and outer
  radius `fillet_r + wall`. The rounded inner corner is the strain relief.
  Because the beam's corner is square, it rests on the two fillets and holds
  the base about `0.41 * fillet_r` (≈0.8 mm) off the beam. Grip comes from the
  arms, so this does not matter.
- Each arm has a shallow rounded ridge (`bump_h` tall, formed from a circle of
  radius `bump_r`) on its inner face, `bump_from_tip` below the tip. The bumps
  set the interference and therefore the clamping force, independent of how
  closely the walls fit. Arm tips are fully rounded for lead-in.
- `length` is the dimension along the beam: 40 mm for the real part.
- `label` engraves text on the outer face of the base.

The model exports `.stl` by default; give the output a `.step` suffix for a
STEP file or `.svg` for a drawing of the 2D profile.

## Printing

Print with the C profile flat on the bed (the model's native orientation).
Bending stress in the arms then lies within layers instead of across them.
No supports are needed. For a springy part, use PETG or similar; PLA works
but creeps under sustained load.

## Phase 1: fit prototypes

```bash
pixi run proto
```

Renders a sweep of wall thickness × clearance, each only 10 mm long so they
print quickly, with the values engraved on the base (`w3 c0.3` = 3 mm wall,
0.3 mm clearance). Edit `proto_walls` and `proto_clearances` at the top of the
`justfile` to change the sweep. Push each one onto the beam and pick the
combination that seats fully and holds.

Note that a 10 mm prototype has a quarter of the spring force of the 40 mm
part, since stiffness scales with `length`. The fit is what the sweep tests;
if you want to feel the real force, set `proto_length := "40"`.

Tuning notes:

- If a part won't seat, increase `clearance` or reduce `bump_h`.
- If it seats but is loose, reduce `clearance` or increase `bump_h`.
- If the arms crack at the corner, increase `fillet_r` or `wall`.

## Phase 2: full-scale part

Set `full_wall` and `full_clearance` in the `justfile` to the winning values and:

```bash
pixi run full
```

## Beam flex

![assembly](flex_assembly.svg)

The third option: the ratchet's teeth without its jog, held by the arms'
own compliance.

- Both arms are straight and flush against the beam. The mating half is
  rotated 180° about the beam axis, so at each joint one part's arm is
  inside and the other's outside.
- Over the lap each arm is halved across the wall: the **left** arm keeps
  its outer half and carries teeth on the resulting inner face; the
  **right** arm keeps its inner half and carries a matching row recessed
  into its outer face. The halves nest flush, so the outside of the
  assembly is one unbroken surface and the inside stays against the beam.
- The re-entrant corner where each arm steps down to its lap is filleted
  (`shoulder_r`), since that is where the arm bends. The lap tips are rounded
  at a larger radius, so they nest past the fillets at every ratchet
  position. The tooth flats stay square: they are the retention faces.
- To assemble, push the halves together: the outside arm flexes outward by
  the tooth height to click over the teeth, then springs back. A negative
  `joint_clearance` (default −0.3 mm) leaves the outside arm held slightly
  flexed so the teeth stay pressed together. The joint closes at whichever
  tooth the halves reach (`cinch_teeth` past nominal, `slack_teeth` short).
- Rendering a part prints its compliance report: the force and root stress
  to click over the teeth and, for the interference, the stress the arm
  holds permanently, against the material's creep ceiling (`material`:
  `pla`, `petg` or `abs`). With 5 mm PLA walls the click takes about 8 N
  on the 50 mm part and the held stress is under 1.5 MPa.

### Phase 1: joint coupons

```bash
pixi run flex-coupon
```

Two loose joint pieces per STL over `joint_clearance` × `tooth_h`. Print
each twice and check the laps nest flush and the click is positive.

### Phase 2: full halves

Set the `flex_*` values at the top of the `justfile` and:

```bash
pixi run flex
```

Print twice.

## Arm compliance

`compliance.py` treats an arm as a cantilever and reports the force and
root stress for a given tip deflection, for PLA, PETG or ABS, with a creep
ceiling for permanently deflected parts:

```bash
pixi run python compliance.py --wall 5 --length 50 --arm_len 87 --deflection 5.3
```

## Assembled around the beam

```bash
pixi run assembly
```

Writes, for each model, `assembly/<model>_assembly.step` (beam and parts as
separate coloured solids), an STL of the same, and front and isometric SVG
line drawings, and prints the overlap volume between the beam and each part.
The beam is seated where its square corners rest on the inner fillets; that
seat gap (`seat`, about 1.2 mm with the defaults) is built into the wrap
models' base-to-base span (`span_h`), so the halves close at nominal with the
beam between them.

## Tests

```bash
pixi run test
```

## Beam wrap

![assembly](wrap_assembly.svg)

Two copies of one part enclose the beam. One half cups the beam from below;
the other is the same part rotated 180° about the beam axis and cups it from
above. The halves meet at mid-height on both sides in a snap lap joint:

- The **left arm** jogs outward by `wall + joint_clearance` just below
  mid-height and continues as an outer tab, `lap_len` tall, with a row of
  `n_teeth` sawteeth on its inner face. Each tooth stands `tooth_h` proud of
  the tab with a flat face on the base side and a ramp on the tip side.
- The **right arm** stays flush against the beam. A matching row is cut into
  its outer face: the crests sit flush with the face and the roots `tooth_h`
  in, with the same orientation. The recess runs `1 + cinch_teeth` pitches
  below the row and `slack_teeth` pitches above it so the mating tab's teeth
  have room at every allowed position.
- After rotation every left tab lands outside a right arm and the two rows
  face each other with opposite orientation. Pushing the halves together
  ratchets the ramps past one another one tooth at a time. Pulling apart
  loads the flat faces of every engaged tooth across the full `length`.
- The joint closes at whichever tooth the halves reach: up to `slack_teeth`
  pitches short of nominal for a taller beam (with `n_teeth - slack_teeth`
  still engaged) and `cinch_teeth` pitches past it for a shorter one. With
  the defaults that is a 6 mm window around `beam_h`. To take it apart, pry
  the outer tabs.

Why not identical arms with teeth on both? The mating move is a 180° turn
about the beam axis, which keeps the outer side of an arm on the outside, so
identical arm tips could only meet end to end. One arm has to step outside
the other; the jog is that step.

Both arms of one part are different (`outer_arm_len` and `inner_arm_len`), but
the part itself is what you print twice. The bumps sit at `bump_y` above the
inner base face on both arms to preload the fit.

### Phase 1: joint coupons

```bash
pixi run wrap-coupon
```

Renders the joint region only (a short outer tab and a short inner-arm tip,
as two loose pieces in one STL) over a sweep of `joint_clearance` × `tooth_h`.
Print each coupon **twice**: one print's tab mates with the other print's arm
tip. Pick the combination that ratchets with a clear click and does not slip
when pulled. `tooth_pitch` and `n_teeth` are also parameters if the row needs
to be finer or longer.

### Phase 2: full halves

Set `wrap_wall`, `wrap_clearance` and `wrap_joint_clearance` in the `justfile`
and:

```bash
pixi run wrap
```

Print the resulting STL twice. Each half is about 146 mm long in its print
orientation (profile flat on the bed), so check it fits your bed diagonally
if needed.

## Beam bolt

![assembly](bolt_assembly.svg)

The competitor to the ratchet. Same two identical halves meeting at
mid-height, but bolted, with the bolts running **along the beam**, which is
also the print direction, so every hole is a clean vertical slot in the
profile. Assembled, the pair is one continuous band of the same `length`
everywhere.

- The part is **mirror-symmetric**. Over the lap each arm tapers (over
  `taper_len`) from the full `length` down to a finger of half that,
  `finger_len`, and both fingers sit on the **same** end of the length, the
  bed side when printed, so nothing floats and the taper is an upward-facing
  face.
- The mating half is the same part **flipped end-for-end**: rotated 180°
  about the beam's width axis through the centre of the span. That maps each
  arm onto the same-side arm of the other half and sends its fingers to the
  other end of the length, so the two parts' fingers interlock flat face to
  flat face, with no offset along the beam. (Rotating about the beam axis
  instead would keep the fingers at the same end, which is what forced the
  earlier stagger and scarf designs.)
- The wall is 5 mm and carries the slot on its own, so the arms keep one
  thickness from elbow to tip. No boss and no tension bumps: the bolt holds
  the wrap.
- Each finger carries a slot `slot_len` long on the wall's centreline,
  running along the beam and elongated along the arm. A bolt through the two
  aligned slots clamps the fingers; the faces are perpendicular to the bolt,
  so tension just clamps, and the slot gives `slot_travel = slot_len - hole_d`
  of height tolerance each way (5.7 mm with the defaults) for beams that are
  not exactly `beam_h`. Head and nut sit on the parts' end faces, clear of
  the wood.

Hardware per assembly: `2 * n_bolts` bolts long enough for `length` plus
head and nut (M2×20 for the 10 mm test part, M2×60 for 50 mm), and nuts. For
M3, set `wall` to 6.

### Phase 1: joint coupons

```bash
pixi run bolt-coupon
```

Two loose joint pieces per STL over a sweep of `joint_clearance` (the gap
between the finger faces). Print each twice, bolt one print's finger to the
other's, and check the faces sit flat and the bolt slides along the slots.

### Phase 2: full halves

Set the `bolt_*` values at the top of the `justfile` and:

```bash
pixi run bolt
```

Print twice.

## Beam flex

![assembly](flex_assembly.svg)

The third option: the ratchet's teeth without its jog, held by the arms'
own compliance.

- Both arms are straight and flush against the beam. The mating half is
  rotated 180° about the beam axis, so at each joint one part's arm is
  inside and the other's outside.
- Over the lap each arm is halved across the wall: the **left** arm keeps
  its outer half and carries teeth on the resulting inner face; the
  **right** arm keeps its inner half and carries a matching row recessed
  into its outer face. The halves nest flush, so the outside of the
  assembly is one unbroken surface and the inside stays against the beam.
- The re-entrant corner where each arm steps down to its lap is filleted
  (`shoulder_r`), since that is where the arm bends. The lap tips are rounded
  at a larger radius, so they nest past the fillets at every ratchet
  position. The tooth flats stay square: they are the retention faces.
- To assemble, push the halves together: the outside arm flexes outward by
  the tooth height to click over the teeth, then springs back. A negative
  `joint_clearance` (default −0.3 mm) leaves the outside arm held slightly
  flexed so the teeth stay pressed together. The joint closes at whichever
  tooth the halves reach (`cinch_teeth` past nominal, `slack_teeth` short).
- Rendering a part prints its compliance report: the force and root stress
  to click over the teeth and, for the interference, the stress the arm
  holds permanently, against the material's creep ceiling (`material`:
  `pla`, `petg` or `abs`). With 5 mm PLA walls the click takes about 8 N
  on the 50 mm part and the held stress is under 1.5 MPa.

### Phase 1: joint coupons

```bash
pixi run flex-coupon
```

Two loose joint pieces per STL over `joint_clearance` × `tooth_h`. Print
each twice and check the laps nest flush and the click is positive.

### Phase 2: full halves

Set the `flex_*` values at the top of the `justfile` and:

```bash
pixi run flex
```

Print twice.

## Arm compliance

`compliance.py` treats an arm as a cantilever and reports the force and
root stress for a given tip deflection, for PLA, PETG or ABS, with a creep
ceiling for permanently deflected parts:

```bash
pixi run python compliance.py --wall 5 --length 50 --arm_len 87 --deflection 5.3
```

## Assembled around the beam

```bash
pixi run assembly
```

Writes, for each model, `assembly/<model>_assembly.step` (beam and parts as
separate coloured solids), an STL of the same, and front and isometric SVG
line drawings, and prints the overlap volume between the beam and each part.
The beam is seated where its square corners rest on the inner fillets; that
seat gap (`seat`, about 1.2 mm with the defaults) is built into the wrap
models' base-to-base span (`span_h`), so the halves close at nominal with the
beam between them.

## Tests

```bash
pixi run test
```

## Beam wrap

![assembly](wrap_assembly.svg)

Two copies of one part enclose the beam. One half cups the beam from below;
the other is the same part rotated 180° about the beam axis and cups it from
above. The halves meet at mid-height on both sides in a snap lap joint:

- The **left arm** jogs outward by `wall + joint_clearance` just below
  mid-height and continues as an outer tab, `lap_len` tall, with a row of
  `n_teeth` sawteeth on its inner face. Each tooth stands `tooth_h` proud of
  the tab with a flat face on the base side and a ramp on the tip side.
- The **right arm** stays flush against the beam. A matching row is cut into
  its outer face: the crests sit flush with the face and the roots `tooth_h`
  in, with the same orientation. The recess runs `1 + cinch_teeth` pitches
  below the row and `slack_teeth` pitches above it so the mating tab's teeth
  have room at every allowed position.
- After rotation every left tab lands outside a right arm and the two rows
  face each other with opposite orientation. Pushing the halves together
  ratchets the ramps past one another one tooth at a time. Pulling apart
  loads the flat faces of every engaged tooth across the full `length`.
- The joint closes at whichever tooth the halves reach: up to `slack_teeth`
  pitches short of nominal for a taller beam (with `n_teeth - slack_teeth`
  still engaged) and `cinch_teeth` pitches past it for a shorter one. With
  the defaults that is a 6 mm window around `beam_h`. To take it apart, pry
  the outer tabs.

Why not identical arms with teeth on both? The mating move is a 180° turn
about the beam axis, which keeps the outer side of an arm on the outside, so
identical arm tips could only meet end to end. One arm has to step outside
the other; the jog is that step.

Both arms of one part are different (`outer_arm_len` and `inner_arm_len`), but
the part itself is what you print twice. The bumps sit at `bump_y` above the
inner base face on both arms to preload the fit.

### Phase 1: joint coupons

```bash
pixi run wrap-coupon
```

Renders the joint region only (a short outer tab and a short inner-arm tip,
as two loose pieces in one STL) over a sweep of `joint_clearance` × `tooth_h`.
Print each coupon **twice**: one print's tab mates with the other print's arm
tip. Pick the combination that ratchets with a clear click and does not slip
when pulled. `tooth_pitch` and `n_teeth` are also parameters if the row needs
to be finer or longer.

### Phase 2: full halves

Set `wrap_wall`, `wrap_clearance` and `wrap_joint_clearance` in the `justfile`
and:

```bash
pixi run wrap
```

Print the resulting STL twice. Each half is about 146 mm long in its print
orientation (profile flat on the bed), so check it fits your bed diagonally
if needed.

## Beam bolt

![assembly](bolt_assembly.svg)

The competitor to the ratchet. Same two identical halves meeting at
mid-height, but bolted, with the bolts running **along the beam**, which is
also the print direction. Assembled, the pair is one continuous band of the
same `length` everywhere; the halves meet along a diagonal seam on each
side.

- Over the lap each arm becomes a finger spanning part of the `length`. The
  two fingers of the mated halves interlock along the beam and share a bolt.
  Head and nut sit on the parts' end faces, clear of the wood.
- The seam is a **scarf** at `scarf_angle` from horizontal. Each finger is
  thick where it leaves its arm and thin at its tip (at least `min_finger`).
  In print orientation every underside is then an overhang no steeper than
  the seam, so nothing floats; a flat step at half length would leave one
  finger of every part unsupported. The tests check this. `lap_len = 0`
  picks the longest lap the seam allows for the part's `length`.
- The wall is 5 mm and carries the hole on its own, so the arms keep one
  thickness from elbow to tip. No boss and no tension bumps: the bolt holds
  the wrap.
- Because the seam is inclined, bolt tension has a component along the arm
  that would slide the halves apart if the holes were slots. They are
  therefore plain round holes: the bolt shaft fixes the height, the joint
  closes at nominal (the seat gap is built into the span), and the bolt
  carries that sliding component in shear. Steeper seams reduce it.
- Short parts need a flatter seam and thinner tips, since the seam has to
  cross the whole length within the lap: the 10 mm test print uses 45° and
  1 mm tips; the 50 mm part can use 60° and 3 mm.

Hardware per assembly: `2 * n_bolts` bolts long enough for `length` plus
head and nut, and nuts. For M3, set `wall` to 6.

### Phase 1: joint coupons

```bash
pixi run bolt-coupon
```

Two loose joint pieces per STL over a sweep of `joint_clearance` (the gap
between the seam faces). Coupons keep the part's full `length`, since the
seam spans it. Print each twice, bolt one print's finger to the other's, and
check the seam faces meet without a gap and the bolt passes through both.

### Phase 2: full halves

Set the `bolt_*` values at the top of the `justfile` and:

```bash
pixi run bolt
```

Print twice.

## Beam flex

![assembly](flex_assembly.svg)

The third option: the ratchet's teeth without its jog, held by the arms'
own compliance.

- Both arms are straight and flush against the beam. The mating half is
  rotated 180° about the beam axis, so at each joint one part's arm is
  inside and the other's outside.
- Over the lap each arm is halved across the wall: the **left** arm keeps
  its outer half and carries teeth on the resulting inner face; the
  **right** arm keeps its inner half and carries a matching row recessed
  into its outer face. The halves nest flush, so the outside of the
  assembly is one unbroken surface and the inside stays against the beam.
- The re-entrant corner where each arm steps down to its lap is filleted
  (`shoulder_r`), since that is where the arm bends. The lap tips are rounded
  at a larger radius, so they nest past the fillets at every ratchet
  position. The tooth flats stay square: they are the retention faces.
- To assemble, push the halves together: the outside arm flexes outward by
  the tooth height to click over the teeth, then springs back. A negative
  `joint_clearance` (default −0.3 mm) leaves the outside arm held slightly
  flexed so the teeth stay pressed together. The joint closes at whichever
  tooth the halves reach (`cinch_teeth` past nominal, `slack_teeth` short).
- Rendering a part prints its compliance report: the force and root stress
  to click over the teeth and, for the interference, the stress the arm
  holds permanently, against the material's creep ceiling (`material`:
  `pla`, `petg` or `abs`). With 5 mm PLA walls the click takes about 8 N
  on the 50 mm part and the held stress is under 1.5 MPa.

### Phase 1: joint coupons

```bash
pixi run flex-coupon
```

Two loose joint pieces per STL over `joint_clearance` × `tooth_h`. Print
each twice and check the laps nest flush and the click is positive.

### Phase 2: full halves

Set the `flex_*` values at the top of the `justfile` and:

```bash
pixi run flex
```

Print twice.

## Arm compliance

`compliance.py` treats an arm as a cantilever and reports the force and
root stress for a given tip deflection, for PLA, PETG or ABS, with a creep
ceiling for permanently deflected parts:

```bash
pixi run python compliance.py --wall 5 --length 50 --arm_len 87 --deflection 5.3
```

## Assembled around the beam

```bash
pixi run assembly
```

Writes, for each model, `assembly/<model>_assembly.step` (beam and parts as
separate coloured solids), an STL of the same, and front and isometric SVG
line drawings, and prints the overlap volume between the beam and each part.
The beam is seated where its square corners rest on the inner fillets; that
seat gap (`seat`, about 1.2 mm with the defaults) is built into the wrap
models' base-to-base span (`span_h`), so the halves close at nominal with the
beam between them.

## Tests

```bash
pixi run test
```

## Beam wrap

![assembly](wrap_assembly.svg)

Two copies of one part enclose the beam. One half cups the beam from below;
the other is the same part rotated 180° about the beam axis and cups it from
above. The halves meet at mid-height on both sides in a snap lap joint:

- The **left arm** jogs outward by `wall + joint_clearance` just below
  mid-height and continues as an outer tab, `lap_len` tall, with a row of
  `n_teeth` sawteeth on its inner face. Each tooth stands `tooth_h` proud of
  the tab with a flat face on the base side and a ramp on the tip side.
- The **right arm** stays flush against the beam. A matching row is cut into
  its outer face: the crests sit flush with the face and the roots `tooth_h`
  in, with the same orientation. The recess runs `1 + cinch_teeth` pitches
  below the row and `slack_teeth` pitches above it so the mating tab's teeth
  have room at every allowed position.
- After rotation every left tab lands outside a right arm and the two rows
  face each other with opposite orientation. Pushing the halves together
  ratchets the ramps past one another one tooth at a time. Pulling apart
  loads the flat faces of every engaged tooth across the full `length`.
- The joint closes at whichever tooth the halves reach: up to `slack_teeth`
  pitches short of nominal for a taller beam (with `n_teeth - slack_teeth`
  still engaged) and `cinch_teeth` pitches past it for a shorter one. With
  the defaults that is a 6 mm window around `beam_h`. To take it apart, pry
  the outer tabs.

Why not identical arms with teeth on both? The mating move is a 180° turn
about the beam axis, which keeps the outer side of an arm on the outside, so
identical arm tips could only meet end to end. One arm has to step outside
the other; the jog is that step.

Both arms of one part are different (`outer_arm_len` and `inner_arm_len`), but
the part itself is what you print twice. The bumps sit at `bump_y` above the
inner base face on both arms to preload the fit.

### Phase 1: joint coupons

```bash
pixi run wrap-coupon
```

Renders the joint region only (a short outer tab and a short inner-arm tip,
as two loose pieces in one STL) over a sweep of `joint_clearance` × `tooth_h`.
Print each coupon **twice**: one print's tab mates with the other print's arm
tip. Pick the combination that ratchets with a clear click and does not slip
when pulled. `tooth_pitch` and `n_teeth` are also parameters if the row needs
to be finer or longer.

### Phase 2: full halves

Set `wrap_wall`, `wrap_clearance` and `wrap_joint_clearance` in the `justfile`
and:

```bash
pixi run wrap
```

Print the resulting STL twice. Each half is about 146 mm long in its print
orientation (profile flat on the bed), so check it fits your bed diagonally
if needed.

## Beam bolt

![assembly](bolt_assembly.svg)

The competitor to the ratchet. Same two identical halves meeting at
mid-height, but bolted, with the bolts running **along the beam**, which is
also the print direction, so every hole is a clean vertical slot in the
profile:

- The wall is 5 mm, thick enough to carry a slot for a 2 mm bolt with
  `min_slot_wall` of material either side, so the arms keep one thickness
  from elbow to tip. No boss, and no tension bumps: the bolt holds the wrap,
  not friction.
- Over the `lap_len` overlap each arm tapers (over `taper_len`) from the full
  `length` down to a finger of half that, `finger_len`. Both fingers of a
  part are on the **same** end of the length, the bed side when printed, so
  nothing floats and the taper is an upward-facing face.
- The mating half is rotated 180° about the beam axis **and shifted half a
  length along the beam**. Its fingers then sit beside this half's fingers,
  flat face to flat face, and the assembly spans 1.5 × `length` along the
  beam. Without the stagger, identical parts would need one finger at the
  far end of the length, which cannot be printed without support.
- Each finger carries a slot `slot_len` long on the wall's centreline,
  running along the beam and elongated along the arm. A bolt through the two
  aligned slots clamps the fingers; the mating faces are perpendicular to
  the bolt, so tension just clamps, and the slot gives
  `slot_travel = slot_len - hole_d` of height adjustment each way (5.7 mm
  with the defaults). Head and nut sit on the parts' end faces, clear of
  the wood.

Hardware per assembly: `2 * n_bolts` bolts long enough for `length` plus
head and nut (M2×60 for a 50 mm part), and nuts. For M3, set `wall` to 6.

### Phase 1: joint coupons

```bash
pixi run bolt-coupon
```

Two loose joint pieces per STL over a sweep of `joint_clearance`, at a short
`length` to print fast. Print each twice, bolt one print's finger to the
other's, and check the faces sit flat and the bolt slides along the slots.

### Phase 2: full halves

Set `bolt_wall`, `bolt_clearance` and `bolt_joint_clearance` in the
`justfile` and:

```bash
pixi run bolt
```

Print twice.
