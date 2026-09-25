# Cam anchor: design

An anchor that goes up into the 80 mm gap between two ceiling beams and holds
a hanging load (a clothes-drying rod on cord or hooks) by pressing spring-set
cams against the beams' vertical, rough-sawn sides. The load itself drives
the cams harder into the walls, as in a climbing cam. Printed in PETG.

## Requirements

- Fits a gap with vertical, parallel walls, nominally 80 mm apart. The walls
  are rough-sawn wood (PETG on it: μ ≈ 0.4–0.5).
- Holds at least 10 kg hung from an eye below it.
- Installed and removed by hand from below with a pull trigger. A rubber
  band sets the cams.
- Every part prints flat on a 256 × 256 mm bed, with every hole along print Z
  (see the repo's print-orientation rule).

## Coordinates

X runs across the gap, with the walls at x = ±gap/2. Y runs along the beams.
Z points up. The axle is on the Y axis, through the origin. Every part is
drawn in its XZ profile and extruded along Y; that profile lies flat on the
bed when printed, so Y is print Z.

## Mechanism

Four cams turn on one M6 bolt (the axle). Two cams press on each wall.
Along Y they are stacked L R R L, each pair mirrored, so the grip is
symmetric about the unit's centre and it cannot twist. The stack from end to
end is: plate | washer | L | washer | R | washer | R | washer | L | washer |
plate.

### Cam profile

The working edge of each cam is a logarithmic spiral, r(ψ) = r0·e^(kψ) with
k = tan α and α = 14°. A spiral keeps the same angle between its radius and
its normal all the way round, so the cam's contact angle is the same at any
reach.

- For the cam on the +x wall, the spiral grows clockwise. Seen in the world
  frame, turning the cam counter-clockwise (ρ > 0) increases its reach.
- The cam touches the wall where its normal is horizontal. That point lies α
  below the horizontal through the axle, and the reach there is
  r·cos α.
- **Self-locking:** the wall's reaction (N inward, F upward) must pass
  through the axle, so F / N = tan α. The cam holds whenever μ > tan 14° ≈
  0.25, which gives about 2× margin on rough-sawn wood. A downward load on
  the axle turns the +x cam counter-clockwise, which expands it: the anchor
  tightens itself.
- **Reach per side:** 34 mm retracted, 45 mm fully expanded, so the unit
  spans 68–90 mm and covers the 80 mm gap with ±10 mm to spare. That needs
  r from 35.0 to 46.4 mm, which is 64° of cam rotation.
- **Teeth:** the edge carries small serrations, about 0.8 mm deep, cut
  *into* the spiral, so the tooth tips lie on it and the reach model still
  holds. They are in the profile, so they print cleanly.
- The rest of the cam closes back to a hub round the axle hole (Ø 6.4). The
  contact point must stay the cam's outermost point in x over the whole
  working range, so nothing else on the cam rubs the wall.
- Default thickness 10 mm.

### Spring and trigger

Each cam is a lever on the axle with two holes:

- **Trigger hole** (outboard side, x > 0 for the +x cam). A cord pulled down
  here turns the cam clockwise, which retracts it. At every point of the
  working range the hole stays at least 20° from straight below the axle,
  so the pull always has leverage.
- **Spring hole** (inboard side, x < 0). A rubber band from here down to a
  hook on the stem's centreline turns the cam counter-clockwise, which
  expands it. The band has no leverage once the spring hole comes directly
  below the axle, so the cam comes to rest there. That rest position is
  placed about 10° past full reach (45 mm), so the cam needs no hard stop.

The four trigger cords run down between the plates to a printed finger-pull.

### Frame and eye

- **Side plates:** two identical stadium-ended plates, 24 mm wide in x
  (well inside the 68 mm retracted span) and 6 mm thick. Each has the axle
  hole at the top and an eye hole `drop` (80 mm by default) below it, plus a
  notch or hook on the centreline that anchors the rubber band.
- **Eye:** a second M6 bolt through the plates' lower holes, carrying a
  printed sleeve (Ø 12 tube, printed upright). Cords and S-hooks hang on the
  sleeve.
- **Clearance:** the cams' lobes must clear the eye sleeve over the whole
  rotation, from the retracted position to the spring's rest position.

### Loads

At W = 100 N (10 kg), each wall sees about W / (2 tan α) ≈ 200 N, shared by
two cams. The bearing stress on a 10 mm cam at the Ø 6 axle stays under 2
MPa. Every load stays in the printed plane, so none pulls across layer
lines.

## Parts and hardware

| Part | Qty | Notes |
|---|---|---|
| Cam | 4 | one STL; turn two over to make the mirrored pair |
| Side plate | 2 | one STL |
| Eye sleeve | 1 | tube, printed upright |
| Finger-pull | 1 | ring or toggle with 4 cord holes |
| Axle-hole coupon | 1 | holes Ø 6.2 / 6.4 / 6.6, each labelled with its size |
| M6 × 70 bolt + nut, M6 × 30 bolt + nut, 5 M6 washers, cord, rubber band | | |

## Code layout

Everything goes in a new `cam-anchor/` directory, laid out like
`beam-clip/`:

- `anchor.py` (build123d)
  - An `AnchorParams` frozen dataclass: gap range, α, r0, cam thickness,
    tooth depth and pitch, plate size, `drop`, hole Ø.
  - `validate()` rejects inconsistent parameters, for example:
    - a reach range that doesn't include the gap
    - tan α ≥ μ
    - a plate wider than the retracted span
    - cams that would hit the sleeve
  - One builder per part.
  - A CLI like `clip.py`'s, rendering `.stl`, `.step` or `.svg`, with an
    `--part` choice and an assembly view.
- `justfile` recipes: `parts`, `coupon`, `preview`, `test`, `clean`.
- `pixi.toml`, `conftest.py` (with `assert_printable`) and `README.md`
  with drawings.
- A line for the new directory in the top-level README.

## Tests

Following the repo convention, one test sweeps parameter combinations and
checks the geometry:

- The tooth tips lie on the spiral.
- The contact reach is r·cos α and covers 68–90 mm.
- Over the working range, the contact point is the cam's outermost point
  in x.
- The trigger hole's and spring hole's leverage have the right sign, and
  the spring's rest position is past full reach.
- The cams clear the sleeve.
- Every part is a single valid solid, printable flat, with its holes
  along Z.

Then one test for each error that `validate()` raises.

## Out of scope

- A torsion spring (the rubber band does its job).
- Walls that are painted or not parallel.
- Loads that pull sideways on the anchor.
