# Beam clip

A flexible clip that lies flush on the face of a 40 mm beam and holds on by
being stretched across it. No hardware.

It's a flat plate 3 mm thick. In the plane of the beam's face it's a
1.6 mm-wide strip following a centreline of straight runs and tangent
circular arcs, with a lip block at each end that reaches 4 mm down the
beam's side. The runs cross the beam. Between them the strip swings out
*along* the beam into three loops, each three arcs of R3.25:

- a concave foot turning 125° off the run
- a convex crown turning back through 250°
- a concave foot back

Past 90° the feet lean in, so each loop pinches to a neck under a round
crown. That packs a lot of arc length, and so a lot of compliance, into a
short span. The whole serpentine lies in one plane on the beam's face, so
the clip stands only 3 mm proud of it and covers 11.8 mm along the beam.

Relaxed, the lips are 38 mm apart. Pushed onto the 40 mm beam, the beam's
edges ride the lead-in chamfer on each lip and spread the lips 2 mm. The
loops take that stretch as bending in the plane of the face and pull the
lips in against the beam's sides.

Each lip's inside face is drafted: set back 0.5 mm at its root, where the
plate meets the beam, and leaning in about 10° to touch the beam only at
its tip, just above the lead-in chamfer. Contact is then one definite line
at the far end of the lip. A square face would touch wherever print
tolerance happened to leave it proud.

![clip](clip.svg)

As printed, the beam's face rests on top of the serpentine, between the
lips.

![plan](profile.svg)

In plan and relaxed, over the dashed beam: the lips' footprints overlap the
beam by the 1 mm per side the loops will take up.

## Why loops and not humps

2 mm of stretch across 38 mm is about 5% strain in the strip, and the clip
holds it for as long as it's on the beam. PETG creeps under sustained stress
above about 15 MPa, so the loops have to absorb the stretch without their
crowns going over that. Gentle humps can't: every one tried, from 60° to 90°
feet and 1.0 to 1.6 mm strips, came out between 15.7 and 56 MPa. Turning the
feet past square roughly halves the stress, and at the defaults the crowns
sit at 10.0 MPa, a 1.5× margin.

`validate()` refuses any geometry over the creep ceiling.

## Compliance

The model treats the strip as a thin curved beam pulled along the runs'
centreline, bending in the plane of the beam's face. The bending moment
anywhere is the pull times the distance `y` from that line, so

```
stretch      = P * ∫y² ds / (E I)        I = plate * t³ / 12
crown stress = E * stretch * h * t / (2 ∫y² ds)
```

`∫y² ds` has a closed form per loop. The runs lie on the line and add
nothing, and the tests check the closed form against a numeric integral
along the centreline the code actually builds.

**Stress doesn't depend on the plate's thickness, but grip does.** The
3 mm plate makes this a light clip:

| plate | grip on each lip | crown stress |
|---|---|---|
| 2 mm | 0.8 N | 10.0 MPa |
| **3 mm** | **1.3 N** | **10.0 MPa** |
| 4 mm | 1.7 N | 10.0 MPa |
| 6 mm | 2.5 N | 10.0 MPa |

The other lever is the strip's width, `--t`. Grip goes with its cube but
stress only linearly: `--t 2` roughly doubles the grip to 2.5 N at 12.5 MPa,
a thinner 1.2× margin, with the neck still 2.15 mm clear.

## Dimensions

| | default | flag |
|---|---|---|
| beam | 40 mm across its face | `--beam_w` |
| relaxed gap between the lips | 38 mm | `--span` |
| plate | 3 mm off the beam's face | `--plate` |
| strip | 1.6 mm wide in the face's plane | `--t` |
| loops | 3, R3.25, feet turning 125° | `--loops`, `--loop_r`, `--turn` |
| lips | 4 mm down the side, 2.4 mm thick, as wide along the beam as the loops | `--lip`, `--lip_t` |
| lip draft | inside face set back 0.5 mm at the root, about 10°, so the lips meet the beam at their tips | `--lip_relief` |
| lead-in | 1.2 mm × 45° on each lip's inside edge | `--chamfer` |
| least printable gap | 1.2 mm | `--min_gap` |
| material | PETG: E 2000 MPa, creep ceiling 15 MPa | `--modulus`, `--creep_limit` |

The narrowest gap is each loop's neck, where its feet pass closest: 2.55 mm
clear at the defaults. `validate()` refuses anything under `--min_gap`,
because a slicer can bridge or fuse a narrower gap, and a fused neck locks
the loop solid. The gap between neighbouring crowns is the neck plus a run,
so it's never the tighter of the two. The lead-in chamfer must cover at
least half the interference, so the beam's edge lands on the slope, not the
lip's flat top.

There's no engraved ID: nothing on the part is wider than the 2.4 mm lips.

## Use

```
pixi run clip                                  # stl/clip_38on40_n3_r3.25_a125_t1.6_p3.stl
pixi run render out.stl --plate 4
pixi run test
```

Print it as modelled: the serpentine flat on the bed, the lips rising from
it. Every wall is vertical except the lips' drafted inside faces, which
lean in about 10°, and the chamfers face up, so nothing overhangs
meaningfully.
The side that was on the bed faces away from the beam. Use PETG — the
numbers above assume it, and PLA creeps at a lower stress. Print the strip
solid with perimeters; at 1.6 mm wide there's no room for infill.
