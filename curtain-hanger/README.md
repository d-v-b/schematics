# Curtain hanger

Everything needed to hang two IKEA FRAMFUSIG curtain rails from an exposed
wooden ceiling beam (53.6 mm wide, 206.5 mm tall) without screws into the
beam: a bolted two-piece beam wrap whose lower half carries the rail clamps
fused to its base.

- **The hanger** (`beam_bolt.py` with `rails` set): two halves that meet at
  mid-height with half-length fingers, flipped end-for-end into one
  continuous band and bolted along the beam. The **lower** half has the two
  rail clamps hanging from its base by short necks and plain bolt holes; the
  **upper** half is plain and carries the slots, so the pair closes at
  whatever height the beam is. Each arm's taper into its finger is a cosine
  curve and its finger ends with the same curve into a rounded nose, so the
  two halves nest along a smooth S-shaped seam with no sharp edges. `pixi run bolt` renders both, `pixi run test-run`
  short versions for a fit check.
- **The rail clamp** (`rail_clamp.py`): a thin C per rail that grips the
  FRAMFUSIG section from above; the rail rolls in. Also available as a
  stand-alone plate-mounted part, and as fit coupons.
- **Alternatives** kept for reference: the **flex** wrap (`beam_flex.py`,
  nested half-laps with teeth, no hardware, but needs 2 mm teeth and thick
  arms), the ratchet **wrap** (`beam_wrap.py`) and the original single
  **clamp** (`beam_clamp.py`). Every beam model can still carry a dovetail
  groove in its base, but the hanger no longer uses one.
- An **assembly** (`assembly.py`) that stacks beam, both halves, bolts and
  rails and checks nothing interferes.

![hanger](assembly/hanger_assembly_front.svg)

## Files

- `beam_clamp.py` — the clamp model, written with
  [build123d](https://build123d.readthedocs.io/). Every dimension is a field of
  `ClampParams` and a `--flag` on the command line (`python beam_clamp.py --help`).
- `beam_wrap.py` — the wrap model, sharing the clamp's corner and helper code.
  Parameters are `WrapParams` (`python beam_wrap.py --help`).
- `beam_bolt.py` — the bolted variant. Parameters are `BoltParams`.
- `beam_flex.py` — the compliant snap variant. Parameters are `FlexParams`.
- `framfusig.py` — the measured FRAMFUSIG rail sections (`INNER`, `OUTER`).
- `rail_clamp.py` — the rail clamp. Parameters are `ClipParams`.
- `compliance.py` — cantilever model of an arm: force and stress for a
  deflection, per material. Used by the flex wrap and the rail clamp.
- `assembly.py` — places each design around a solid beam, and the whole
  hanger, reporting overlap volumes; writes STEP, STL and SVG views.
- `justfile` — dev actions (`just --list`): render either phase, refresh the
  profile drawing, run tests, clean.
- `pixi.toml` — the schematic's environment. `pixi run <recipe>` runs any just
  recipe inside it.
- `test_beam_clamp.py`, `test_beam_wrap.py`, `test_beam_bolt.py`,
  `test_beam_flex.py`, `test_framfusig.py`, `test_rail_clamp.py`,
  `test_assembly.py` — geometry
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

## Beam wrap

![assembly](wrap_assembly.svg)

Two copies of one part enclose the beam. One half cups the beam from below;
the other is the same part rotated 180° about the beam axis and cups it from
above. The halves meet at mid-height on both sides in a snap lap joint:

- The **left arm** jogs outward by `wall + joint_clearance` just below
  mid-height and continues as an outer tab, `lap_len` tall, with a row of
  sawteeth on its inner face running the full length the mating arm can
  cover. Each tooth stands `tooth_h` proud of the tab with a flat face on
  the base side and a ramp on the tip side.
- The **right arm** stays flush against the beam. A matching row is cut into
  its outer face along the whole lap: the crests sit flush with the face and
  the roots `tooth_h` in, with the same orientation. Teeth are 2 mm on a
  4 mm pitch: 0.8 mm teeth did not print on the user's printer. Both rows run all the
  way, so there are no empty runs: at any position the teeth beyond the
  other part's row simply sit unengaged against its plain face.
- After rotation every left tab lands outside a right arm and the two rows
  face each other with opposite orientation. Pushing the halves together
  ratchets the ramps past one another one tooth at a time. Pulling apart
  loads the flat faces of every engaged tooth across the full `length`.
- The joint closes at whichever tooth the halves reach: `cinch_teeth`
  pitches past nominal for a shorter beam and `slack_teeth` short of it for
  a taller one are the travel the tips are cleared for (a 6 mm window with
  the defaults); the tab's row is sized so the arm's row still covers it
  at the slackest position. To take it apart, pry the outer tabs.

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
when pulled. `tooth_pitch` is a parameter if the row needs to be finer.

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
  its outer half, the **right** arm its inner half, and they nest flush, so
  the outside of the assembly is one unbroken surface and the inside stays
  against the beam. The parting plane runs through the middle of the tooth
  height: each lap is the same solid slab (half the wall less half a tooth)
  with identical sawteeth reaching half a tooth past the plane, the left
  arm's inward and the right arm's outward. Both rows run the full length
  the other can cover, so nothing is cut into either part and the two laps
  are the same thickness everywhere.
- Each arm tapers smoothly from the full wall down to its lap slab over
  `taper_len` just below the lap, instead of stepping down at a corner:
  that is where the arm bends when the joint is loaded, and a gradual
  change of section spreads the stress rather than concentrating it. The
  tooth flats stay square: they are the retention faces.
- To assemble, push the halves together: the outside arm flexes outward by
  the tooth height to click over the teeth, then springs back. A negative
  `joint_clearance` (default −0.3 mm) thickens both slabs by half of it, so
  the outside arm is held slightly flexed and the two sawtooth surfaces
  press together over their whole length. The joint closes at whichever
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

## Dovetail (no longer used)

Every beam model can cut a female dovetail groove in the underside of its
base (`dovetail_w`, `dovetail_h`, `dovetail_angle`, `dovetail_clearance`),
and the stand-alone rail clamp can carry the matching ridge. The hanger was
built that way first; after prototyping, the sliding joint was judged more
trouble than it was worth and the rail clamps were fused to the lower half
instead. The parameters remain, default off. What was learned: the printer
cuts grooves about 0.125 mm oversize per side, so a snug fit needed a
modelled clearance of −0.025 mm.

## Rail clamp

![rail profiles](rail_profiles.svg)

The FRAMFUSIG rail is a telescopic single-track ceiling rail of two nested
steel tubes with a glider slot on the underside. IKEA publishes no profile
dimensions; these were measured with calipers. The outer tube is modelled as
a full stadium, the narrowest it can be at the lips.

| Tube  | Width | Height | Corner radius | Slot |
|-------|-------|--------|---------------|------|
| Inner | 17.4  | 10.0   | 5.0 (full stadium) | 6.75 |
| Outer | 19.5  | 12.2   | 6.1 (full stadium) | 6.75 |

![rail clamp profile](rail_clamp_profile.svg)

The clamp grips the rails from above, leaving the underside clear for the
gliders and the curtain, and holds two rails side by side (`tubes` is a
list, one entry per rail, each `inner` or `outer` since the rail is
telescopic).

The rail is telescopic, so along its length a hanger meets either the outer
tube or the inner one, and each C must be cut for the section it will sit on:
`rails` lists the section per C, e.g. `outer,outer`, `inner,inner` or
`outer,inner`. The 10 mm opening serves both (contact 77° on the outer tube,
75° on the inner). Coupons and test runs cover both sections.

In the hanger the Cs hang straight from the lower beam-clamp half's base
(`rails`, `rail_spacing`, `rail_wall`, `rail_opening`, `rail_clearance` on
`BoltParams`). The stand-alone version below puts them under their own plate.

- Each rail sits in a C of uniform `wall` following the rail's section at
  `clearance` (zero or negative to squeeze the rail), open at the bottom.
  Grip scales with the cube of the wall: 1.2 mm held curtains too weakly, so
  the default is 2.0 mm, about 4.6 times stiffer.
  The lips follow the rail's lower rounds down until the gap between them
  is `opening`, narrower than the rail. The rail is rolled in one lip at a
  time. Openings of 16 mm and above slipped in prints; 15 mm gripped and
  10 mm gripped best, so 10 is the default. The lips cannot wrap under the
  rail: its flat underside is 7.3 mm and the slot takes 6.75 mm of it, so
  9.15 mm is the narrowest opening at a 1.2 mm wall.
- The Cs hang from a flat top plate, `plate_t` thick, spanning them at
  `spacing` centre to centre, by short necks (`stem_w` x `stem_h`) with
  `fillet_r` fillets. The neck and fillets must stay on each C's flat top:
  the rounds are where the flex lives, and material on them stiffens the
  clip drastically. The plate is a square-cornered bar exactly as wide as
  the flat underside of the beam clamp it hangs under (`mate_w` less twice
  `mate_r`), butting squarely against it and ending where the clamp's
  arcs begin, with its four corners rounded slightly (`corner_r`). `mate_w = 0` gives a plate just wide enough for the Cs, with
  rounded corners (used for coupons).
- Rendering prints a compliance report: the force and stress to snap a rail
  in (irrelevant when rolling it in; `min_safety` gates it) and a rough
  estimate of the downward force before the rail pushes the lips apart.
  Each lip's spring force acts on the rail's lower round; its vertical share
  is that force times the tangent of the contact angle, so shallow lips
  barely hold and deep ones hold hard.

```bash
pixi run rail-coupons   # 3 mm fit coupons over wall x opening
pixi run rail-clamp     # the two-rail clamp with the values in the justfile
```

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

Writes, for each model and for the whole hanger, `assembly/<name>_assembly.step`
(beam and parts as separate coloured solids), an STL of the same, and front and
isometric SVG line drawings, and prints the overlap volume between the beam and
each part (and, for the hanger, between the rail clamp, the beam clamp and the
rails).
The beam is seated where its square corners rest on the inner fillets; that
seat gap (`seat`, about 1.2 mm with the defaults) is built into the wrap
models' base-to-base span (`span_h`), so the halves close at nominal with the
beam between them.

## Tests

```bash
pixi run test
```

