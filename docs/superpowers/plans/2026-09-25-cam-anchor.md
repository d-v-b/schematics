# Cam anchor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A printable four-cam anchor (`cam-anchor/`) that spring-sets into an
80 mm gap between ceiling beams and self-tightens under a hanging load.

**Architecture:** One module, `anchor.py`. It holds a frozen `AnchorParams`
with `validate()`, pure-math helpers for the cam (spiral, reach, torques) and
one build123d builder per part. A CLI renders any part to .stl/.step/.svg.
The tests check the maths and the solids.

**Tech Stack:** Python ≥ 3.12, build123d ≥ 0.9, pytest, just, pixi
(conda-forge).

**Spec:** `docs/superpowers/specs/2026-09-25-cam-anchor-design.md`

## Global Constraints

- α = 14°, μ = 0.4 for rough-sawn wood; the cam holds only if tan α < μ.
- Reach per side is 34 mm retracted and 45 mm expanded; the gap is 80 mm.
- Axle and eye: M6 bolts. Every hole runs along print Z (the Y axis in model
  coordinates).
- Drawn in the XZ profile and extruded along Y. X runs across the gap, Z is
  up, and the axle is on the Y axis.
- Commits: conventional commits, with the `Assisted-by: ClaudeCode:claude-opus-5-5` trailer.
- Tests: one sweep test, plus one test per `validate()` error.

## Two refinements to the spec, settled while planning

- The **rubber band hooks over the eye sleeve**, at (0, −drop). The sleeve
  is the only part on the centreline that spans the whole cam stack, so no
  separate hook is needed.
- The **trigger hole sits near the tip of the cam's lobe**, the end of the
  spiral with the largest radius. From there the cord runs down to the
  finger-pull without crossing the cam. The spec's "20° from straight
  below" rule becomes a direct check: pulling the cord toward its
  finger-pull hole turns the cam clockwise (retracting it) over the whole
  range, from retracted to the spring's rest position.

## Cam maths (+x cam, drawn at ρ = 0 = fully retracted)

- k = tan α. Spiral: r(ψ) = r0·e^(kψ). The point at spiral parameter ψ sits
  at world angle ρ − ψ.
- Contact is at ψ = ρ + α, with reach(ρ) = r0·e^(k(ρ+α))·cos α.
  r0 = reach_min / (cos α · e^(kα)), so reach(0) = reach_min.
- ρ_max = ln(reach_max / reach_min) / k ≈ 64.4°. The spring rests at
  ρ_rest = ρ_max + 10°.
- The spiral spans ψ from α − 10° to ρ_rest + α + 4°. The cam is:
  - the spiral sector, closed by straight lines back to the hub,
  - the hub disc,
  - an inboard spring arm.
- The spring hole sits at world angle −90° − ρ_rest when ρ = 0, so it comes
  directly below the axle, where the band has no leverage, exactly at
  ρ_rest.
- Torque of a pull from point p toward point h, taking counter-clockwise
  as positive: τ = p_x·(h_z − p_z) − p_z·(h_x − p_x).

## Tasks

### Task 1: Scaffold, parameters, maths

- Create `cam-anchor/` with the following files:
  - `pixi.toml` and `justfile`, copied from `beam-clip` and adapted
  - `conftest.py` with `assert_printable`
  - `anchor.py`, containing:
    - `AnchorParams` and `validate()`
    - `r0`, `rho_max`, `rho_rest`, `reach(rho)`
    - `spring_hole(rho)`, `trigger_hole(rho)`, `torque(p, h)`
- In `test_anchor.py`, add the sweep test's maths assertions and one test
  per error:
  - reach range excludes the gap
  - tan α ≥ μ
  - plate not narrower than the retracted span
  - cam lobe hits the sleeve
- Run `pixi run test` and commit.

### Task 2: Part solids

- Builders:
  - `cam(p, mirror=False)`: serrated spiral with its tooth tips on the
    spiral, a Ø `hole` axle bore, and the trigger and spring holes
  - `plate(p)`
  - `sleeve(p)`
  - `finger_pull(p)`
  - `coupon(p)`: Ø 6.2 / 6.4 / 6.6 holes with each size engraved
  - `assembly(p, rho)`, for drawings only
- Extend the sweep test so each part is:
  - valid
  - a single solid
  - printable, with holes along Z
- Also check that:
  - the contact point is the cam's maximum x at ρ = 0, ρ_max and ρ_rest
  - the tooth tips lie on the spiral
- Run the tests and commit.

### Task 3: CLI, drawings, README

- `main()` with `--part {cam,plate,sleeve,pull,coupon,assembly}` and an
  `--rho` option for the assembly view.
- `just parts` writes every STL. `just preview` writes the README's SVGs.
- Write `README.md` (mechanism, bill of materials, assembly steps) and add
  a line to the top-level README.
- Render everything, look at the SVGs and commit.
