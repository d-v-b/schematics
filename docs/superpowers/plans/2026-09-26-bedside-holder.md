# Bedside Holder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A new `bedside-holder/` schematic: one parametric, bent-strip
profile that hooks over a 23 mm bed rail and holds a laptop or phone
upright in a pocket down the rail's outer face. It comes with coupon sweeps
to settle the spring preloads on real prints.

**Architecture:** `path.py` is a pure-Python turtle that walks a centreline
of lines and tangent arcs and samples points on it or on either face of a
strip laid along it. `holder.py` holds a frozen `HolderParams` dataclass
that solves the two spring leans, checks every constraint in `validate()`,
builds the centreline for a `full`, `clamp` or `pocket` section, thickens
it with build123d's `offset_2d`, extrudes it along print Z, and engraves a
label. A `justfile` drives the coupon sweeps and the full parts.

**Tech Stack:** Python ≥ 3.12, build123d ≥ 0.9, pytest, just, pixi
(conda-forge). This matches every other schematic in the repo.

**Spec:** `docs/superpowers/specs/2026-09-26-bedside-holder-design.md`

**Verified:** all code in this plan was prototyped outside the repo
against build123d 0.9.1. All 23 tests pass, and every justfile recipe
renders.

## Global Constraints

- Rail: 23 mm thick (`rail_t`). The mattress-side clearance is 5 mm
  (`mattress_clear`).
- Devices: `device_t` 11.5 for the MacBook Air 15", 9.3 for the iPhone 4.
  Slot gap = `device_t` + 0.5.
- Pocket floor (inside of the J): `drop` = 200 mm below the rail's top edge
  by default.
- Strip `t` = 3.0 by default. Corner bends have `bend_ri` = 3.5 inside.
- PETG: `modulus` 2000 MPa, `creep_limit` 15 MPa. Coupons override it to
  30 via the justfile.
- Coordinates: X across the rail, which is −23 ≤ x ≤ 0 with +x away from
  the bed. Y up, with y = 0 at the rail top. Z along the rail = print Z.
  The profile lies in XY.
- Everything must fit a 256 × 256 bed: `max_size` 250 on the profile.
- Every coupon carries an engraved ID (`label`, 0.4 mm deep, 5 mm text) on
  the hanger's rail-side face.
- Tests: one success test per function over reasonable parameter
  combinations, plus one test per error case.
- Commits: conventional commits, ending with the trailers
  `Assisted-by: ClaudeCode:claude-opus-5-5` and
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Run everything from `bedside-holder/`, through pixi:
  `pixi run python -m pytest -q`.

## File Structure

| file | responsibility |
|------|----------------|
| `bedside-holder/pixi.toml` | env: python, build123d, just, pytest; tasks wrap the justfile |
| `bedside-holder/path.py` | `Seg`, `Turtle`, `sample`: centreline geometry, no CAD |
| `bedside-holder/test_path.py` | the turtle's success test |
| `bedside-holder/holder.py` | `HolderParams` (solves, checks, reports), `centreline`, the solid, the label, the SVG and the CLI |
| `bedside-holder/test_holder.py` | one geometry test over combinations, plus one test per `ValueError` |
| `bedside-holder/justfile` | coupon sweeps, full parts, preview, test, clean |
| `bedside-holder/README.md` + `profile.svg` | the write-up |

`conftest.py` is not needed: pytest puts the test file's directory on the
path, and nothing here is shared between test files. This is a deliberate
change from the spec's file list.

---

### Task 1: Scaffold and centreline turtle

**Files:**
- Create: `bedside-holder/pixi.toml`
- Create: `bedside-holder/path.py`
- Test: `bedside-holder/test_path.py`

**Interfaces:**
- Produces:
  - `Pt = tuple[float, float]`
  - `Seg(start: Pt, h0: float, length=0.0, r=0.0, turn=0.0)`, frozen, with
    properties `is_arc`, `h1`, `centre`, `end`, `mid`, and methods
    `at(f, offset=0.0) -> Pt` and `sample(offset=0.0, step_deg=0.25) -> list[Pt]`
  - `Turtle(start: Pt, heading: float)` with `.pos`, `.heading`, `.segs`,
    and chainable `.line(length)`, `.arc(r, turn)` and
    `.replay_reversed(segs)`
  - `sample(segs, offset=0.0) -> list[Pt]`
  - Headings are radians, counter-clockwise from +x. A positive `turn`
    turns left, and a positive `offset` is to the left of travel.

- [ ] **Step 1: Create the pixi workspace**

`bedside-holder/pixi.toml`:

```toml
[workspace]
name = "bedside-holder"
channels = ["conda-forge"]
platforms = ["osx-arm64", "osx-64", "linux-64"]

[dependencies]
python = ">=3.12"
build123d = ">=0.9"
just = "*"
pytest = "*"

[tasks]
laptop = "just laptop"
phone = "just phone"
clamp-coupons = "just clamp-coupons"
pocket-coupons = "just pocket-coupons"
phone-coupons = "just phone-coupons"
render = "just render"
preview = "just preview"
test = "just test"
clean = "just clean"
```

Run: `cd bedside-holder && pixi install`
Expected: the environment solves and `pixi.lock` is written.

- [ ] **Step 2: Write the failing test**

`bedside-holder/test_path.py`:

```python
"""The turtle walks lines and tangent arcs; its segments know their ends,
midpoints and offset faces."""

import math

import pytest

from path import Turtle, sample


def test_turtle():
    # a stadium: up 10, a half-turn left of radius 2, down 10, a half-turn
    # left again; it closes on itself
    tw = Turtle((0.0, 0.0), math.pi / 2)
    tw.line(10).arc(2, math.pi).line(10).arc(2, math.pi)
    up, top, down, bottom = tw.segs
    assert up.end == pytest.approx((0, 10))
    assert top.centre == pytest.approx((-2, 10))
    assert top.mid == pytest.approx((-2, 12))
    assert top.end == pytest.approx((-4, 10))
    assert down.end == pytest.approx((-4, 0))
    assert bottom.end == pytest.approx((0, 0), abs=1e-12)
    assert tw.heading == pytest.approx(2 * math.pi + math.pi / 2)

    # the left face lies inside a left-turning stadium, 0.5 in from the
    # centreline everywhere; on the top arc it is at radius 1.5
    for x, y in top.sample(0.5):
        assert math.hypot(x + 2, y - 10) == pytest.approx(1.5)
    assert min(x for x, _ in sample(tw.segs, 0.5)) == pytest.approx(-3.5)
    assert max(x for x, _ in sample(tw.segs, -0.5)) == pytest.approx(0.5)

    # a right turn puts its centre on the right
    right = Turtle((0.0, 0.0), 0.0).arc(3, -math.pi / 2).segs[0]
    assert right.centre == pytest.approx((0, -3))
    assert right.end == pytest.approx((3, -3))

    # walking segments back retraces them to the start
    back = Turtle(tw.segs[2].end, tw.segs[2].h1 + math.pi).replay_reversed(tw.segs[:3])
    assert back.pos == pytest.approx((0, 0), abs=1e-12)
```

- [ ] **Step 3: Run the test and check that it fails**

Run: `pixi run python -m pytest -q test_path.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'path'`

- [ ] **Step 4: Implement `path.py`**

`bedside-holder/path.py`:

```python
"""A turtle that walks a centreline of straight lines and tangent circular
arcs in the XY plane, and the pure-Python geometry of the strip it traces:
points along the centreline, or along either face of a strip of given
thickness laid on it.

Headings are in radians, counter-clockwise from +x. An arc's ``turn`` is
positive to the left (counter-clockwise) and negative to the right.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

Pt = tuple[float, float]


@dataclass(frozen=True)
class Seg:
    """One piece of centreline: a line (``r == 0``) or an arc of radius
    ``r`` turning ``turn`` radians, from ``start`` at heading ``h0``."""

    start: Pt
    h0: float
    length: float = 0.0
    r: float = 0.0
    turn: float = 0.0

    @property
    def is_arc(self) -> bool:
        return self.r > 0

    @property
    def h1(self) -> float:
        return self.h0 + self.turn

    @property
    def centre(self) -> Pt:
        s = 1.0 if self.turn > 0 else -1.0
        return (self.start[0] - s * self.r * math.sin(self.h0), self.start[1] + s * self.r * math.cos(self.h0))

    def at(self, f: float, offset: float = 0.0) -> Pt:
        """The point a fraction f of the way along, moved ``offset`` to the
        left of the direction of travel (negative: to the right)."""
        if self.is_arc:
            h = self.h0 + f * self.turn
            s = 1.0 if self.turn > 0 else -1.0
            cx, cy = self.centre
            # the radius from the centre to the point is the left normal
            # turned by -s * 90 deg; walk out r, less the offset on the inside
            nx, ny = s * math.sin(h), -s * math.cos(h)
            rr = self.r - s * offset
            return (cx + rr * nx, cy + rr * ny)
        d = f * self.length
        x = self.start[0] + d * math.cos(self.h0) - offset * math.sin(self.h0)
        y = self.start[1] + d * math.sin(self.h0) + offset * math.cos(self.h0)
        return (x, y)

    @property
    def end(self) -> Pt:
        return self.at(1.0)

    @property
    def mid(self) -> Pt:
        return self.at(0.5)

    def sample(self, offset: float = 0.0, step_deg: float = 0.25) -> list[Pt]:
        n = max(1, math.ceil(abs(math.degrees(self.turn)) / step_deg)) if self.is_arc else 1
        return [self.at(i / n, offset) for i in range(n + 1)]


class Turtle:
    """Walks a centreline, collecting its segments."""

    def __init__(self, start: Pt, heading: float):
        self.pos, self.heading = start, heading
        self.segs: list[Seg] = []

    def _add(self, seg: Seg) -> "Turtle":
        self.segs.append(seg)
        self.pos, self.heading = seg.end, seg.h1
        return self

    def line(self, length: float) -> "Turtle":
        return self._add(Seg(self.pos, self.heading, length=length))

    def arc(self, r: float, turn: float) -> "Turtle":
        return self._add(Seg(self.pos, self.heading, r=r, turn=turn))

    def replay_reversed(self, segs: list[Seg]) -> "Turtle":
        """Walk ``segs`` backwards: each line again, each arc turning the
        other way. Start the turtle at their end, heading back."""
        for s in reversed(segs):
            if s.is_arc:
                self.arc(s.r, -s.turn)
            else:
                self.line(s.length)
        return self


def sample(segs: list[Seg], offset: float = 0.0) -> list[Pt]:
    return [p for s in segs for p in s.sample(offset)]
```

- [ ] **Step 5: Run the test and check that it passes**

Run: `pixi run python -m pytest -q test_path.py`
Expected: `1 passed`

- [ ] **Step 6: Commit**

```bash
git add bedside-holder/pixi.toml bedside-holder/pixi.lock bedside-holder/path.py bedside-holder/test_path.py
git commit -m "feat(bedside-holder): centreline turtle of lines and tangent arcs

Assisted-by: ClaudeCode:claude-opus-5-5
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Parameters, spring solve and validation

**Files:**
- Create: `bedside-holder/holder.py` (parameters and centreline only; later tasks append to it)
- Test: `bedside-holder/test_holder.py` (the error tests; Task 3 replaces the file with the full version)

**Interfaces:**
- Consumes: `Pt`, `Seg`, `Turtle` and `sample` from `path.py` (Task 1).
- Produces:
  - `HolderParams`, a frozen dataclass whose fields and defaults are in the
    code below. Tasks 3 and 4 use:
    - fixed points: `rc`, `hanger_x`, `back_x`, `gap`, `j_r`, `j_y`, `top_y`
    - solved springs: `inner_lean` (radians, NaN if unsolvable),
      `lip_straight` (mm), `inner_contact`, `lip_contact` (Pt)
    - checks: `inner_stress`, `lip_stress` (MPa), `protrusion` (mm),
      `size` ((w, h) mm)
    - `validate()`, which raises `ValueError`, and `report() -> str`
  - `SECTIONS = ("full", "clamp", "pocket")`
  - `centreline(p) -> list[Seg]`: the inner-leaf tip, or the pocket stub's
    top, through to the lip tip. For `clamp` it ends `stub` below the rail
    top.

Two solves are worth understanding before you type:

- `inner_lean` bisects the leaf's lean in [0°, 45°] until the rail-side
  face (offset +t/2 walking down) reaches `x = −rail_t + inner_pre`.
- `lip_straight` has a closed form. The lip's innermost point is where its
  flare turns it back through vertical. That point is `lip_flare_r·(1−cos
  lean)` further out than the end of the straight, and the straight moves
  in by `sin(lean)` per mm.

- [ ] **Step 1: Write the failing error tests**

`bedside-holder/test_holder.py`:

```python
"""The holder's parameters refuse geometry that would not fit, would not
print, or would creep. Each test covers one validation error; the geometry
itself is tested in test_holder."""

import pytest

from holder import HolderParams


def test_non_positive():
    with pytest.raises(ValueError, match="must be positive: t, bend_ri"):
        HolderParams(t=0, bend_ri=-1).validate()


def test_section():
    with pytest.raises(ValueError, match="section must be one of"):
        HolderParams(section="middle").validate()


def test_arc_too_tight():
    with pytest.raises(ValueError, match="radius must exceed t / 2"):
        HolderParams(lip_flare_r=1.4).validate()


def test_label_too_deep():
    with pytest.raises(ValueError, match="label_depth 3 must be less than t 3"):
        HolderParams(label_depth=3.0).validate()


def test_inner_leaf_cannot_lean():
    with pytest.raises(ValueError, match="inner leaf cannot lean in"):
        HolderParams(inner_len=2.0, inner_flare_r=2.0, inner_pre=4.0).validate()


def test_lip_cannot_reach():
    with pytest.raises(ValueError, match="lip reaches the device before it stops leaning"):
        HolderParams(lip_r=200.0, lip_lean=20.0).validate()


def test_mattress_clearance():
    with pytest.raises(ValueError, match="more than the 3 mattress clearance"):
        HolderParams(mattress_clear=3.0).validate()


def test_too_big_for_the_bed():
    with pytest.raises(ValueError, match="over the 250 bed limit"):
        HolderParams(drop=250.0).validate()


def test_inner_leaf_creep():
    with pytest.raises(ValueError, match="inner leaf would sit at"):
        HolderParams(inner_pre=1.5).validate()


def test_lip_creep():
    with pytest.raises(ValueError, match="lip would sit at"):
        HolderParams(lip_base=4.0).validate()
```

- [ ] **Step 2: Run the tests and check that they fail**

Run: `pixi run python -m pytest -q test_holder.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'holder'`

- [ ] **Step 3: Implement parameters and centreline**

`bedside-holder/holder.py`:

```python
"""A bedside holder: one strip of constant thickness, bent like heat-formed
plastic, that hooks over a bed's side rail and stores a device upright in a
pocket hanging down the rail's outer face.

The strip's centreline is a chain of straight lines and tangent arcs; the
strip is that centreline thickened ``t / 2`` either side. From the bed side:
a flared tip, the sprung inner leaf, a bend over the rail's inner top
corner, a straight across the top, a bend over the outer top corner, the
hanger down the outer face, a 180 degree J that is the pocket's floor, and
a spring lip that leans in and flares out again as a lead-in.

Relaxed, the inner leaf overlaps the rail by ``inner_pre`` and the lip
overlaps the device by ``lip_pre``; both are cantilevers of the strip that
those overlaps preload. The lip pushes the device's lower back onto the
hanger, so it tips back toward the bed.

Coordinates: X across the rail, which occupies -rail_t <= x <= 0 (+x away
from the bed); Y up, with y = 0 the rail's top edge; Z along the rail. The
profile lies in XY and is extruded ``length`` up Z, which is print Z: it
prints flat on the bed.

Usage:
    python holder.py -o holder.stl [--device_t 11.5] [--length 50] [--section full]
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass, fields
from functools import cached_property
from pathlib import Path

from build123d import (
    FontStyle,
    Kind,
    Line,
    Part,
    Plane,
    Side,
    Sketch,
    Text,
    ThreePointArc,
    Wire,
    export_stl,
    extrude,
    make_face,
)

from path import Pt, Seg, Turtle, sample

SECTIONS = ("full", "clamp", "pocket")
UP, DOWN = math.pi / 2, -math.pi / 2


@dataclass(frozen=True)
class HolderParams:
    rail_t: float = 23.0          # the bed rail's thickness, mm
    mattress_clear: float = 5.0   # room between the rail's inner face and the mattress
    device_t: float = 11.5        # the device's thickness: 11.5 MacBook Air 15", 9.3 iPhone 4
    slot_clearance: float = 0.5   # the pocket's gap is device_t plus this
    drop: float = 200.0           # pocket floor (inside of the J) below the rail's top edge
    t: float = 3.0                # strip thickness
    bend_ri: float = 3.5          # inside radius of the bends over the rail's top corners
    inner_len: float = 26.0       # the inner leaf's straight
    inner_pre: float = 1.0        # relaxed overlap of the inner leaf into the rail
    inner_flare_r: float = 6.0
    inner_flare_deg: float = 40.0
    lip_base: float = 10.0        # straight rising out of the J
    lip_r: float = 20.0           # radius of the lip's lean-in bend
    lip_lean: float = 6.0         # how far the lip leans in toward the device, deg
    lip_pre: float = 0.75         # relaxed overlap of the lip into the device
    lip_flare_r: float = 8.0
    lip_flare_deg: float = 40.0
    lip_tip: float = 4.0          # straight past the lip's flare
    stub: float = 40.0            # hanger kept on a clamp or pocket coupon
    section: str = "full"         # full | clamp | pocket
    length: float = 50.0          # extrusion along the rail (print Z)
    label: str = ""
    label_depth: float = 0.4
    label_size: float = 5.0
    modulus: float = 2000.0       # PETG, MPa
    creep_limit: float = 15.0     # MPa
    max_size: float = 250.0       # largest profile extent, on a 256 bed

    # --- fixed points ------------------------------------------------------

    @property
    def rc(self) -> float:
        """Centreline radius of the corner bends."""
        return self.bend_ri + self.t / 2

    @property
    def _k(self) -> float:
        # the corner bends' centres sit bend_ri / sqrt(2) in from each top
        # corner along its bisector, so their inside passes through the corner
        return self.bend_ri * math.sqrt(0.5)

    @property
    def hanger_x(self) -> float:
        """The hanger's centreline."""
        return -self._k + self.rc

    @property
    def back_x(self) -> float:
        """The hanger's outer face, where the device's back rests."""
        return self.hanger_x + self.t / 2

    @property
    def gap(self) -> float:
        return self.device_t + self.slot_clearance

    @property
    def j_r(self) -> float:
        return self.gap / 2 + self.t / 2

    @property
    def j_y(self) -> float:
        """Height of the J's centre and of the lip's root."""
        return -self.drop + self.gap / 2

    @property
    def top_y(self) -> float:
        """The strip's top face, over the rail."""
        return -self._k + self.rc + self.t / 2

    # --- the inner leaf ----------------------------------------------------

    def _leaf(self, lean: float) -> list[Seg]:
        """The inner leaf walked down from the end of the inner corner bend."""
        c1 = (-self.rail_t + self._k, -self._k)
        tw = Turtle((c1[0] - self.rc, c1[1]), DOWN)
        tw.arc(self.rc, lean).line(self.inner_len).arc(self.inner_flare_r, -math.radians(self.inner_flare_deg))
        return tw.segs

    @cached_property
    def inner_lean(self) -> float:
        """The inner leaf's lean, radians, solved so its rail-side face
        reaches inner_pre into the rail."""
        target = -self.rail_t + self.inner_pre

        def reach(lean: float) -> float:
            # walking down, the rail is on the left
            return max(x for x, _ in sample(self._leaf(lean), self.t / 2))

        lo, hi = 0.0, math.radians(45)
        if reach(lo) >= target or reach(hi) < target:
            return math.nan
        for _ in range(60):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if reach(mid) < target else (lo, mid)
        return (lo + hi) / 2

    @property
    def inner_contact(self) -> Pt:
        pts = sample(self._leaf(self.inner_lean), self.t / 2)
        return max(pts, key=lambda q: q[0])

    @property
    def inner_arm(self) -> float:
        """Lever arm of the inner leaf: its root to its contact."""
        return -self._k - self.inner_contact[1]

    @property
    def inner_stress(self) -> float:
        return 3 * self.modulus * (self.t / 2) * self.inner_pre / self.inner_arm**2

    @property
    def protrusion(self) -> float:
        """How far the fitted inner leaf stands off the rail's inner face,
        towards the mattress: the relaxed leaf swung about its root until its
        contact is back on the rail."""
        leaf = self._leaf(self.inner_lean)
        rx, ry = leaf[0].start
        cx, cy = self.inner_contact
        phi = -self.inner_pre / math.hypot(cx - rx, cy - ry)  # clockwise swings the tip out
        c, s = math.cos(phi), math.sin(phi)
        # walking down, the mattress is on the right
        xs = [rx + (x - rx) * c - (y - ry) * s for x, y in sample(leaf, -self.t / 2)]
        return -self.rail_t - min(xs)

    # --- the lip -----------------------------------------------------------

    def _lip(self, straight: float) -> list[Seg]:
        tw = Turtle((self.hanger_x + 2 * self.j_r, self.j_y), UP)
        tw.line(self.lip_base).arc(self.lip_r, math.radians(self.lip_lean)).line(straight)
        tw.arc(self.lip_flare_r, -math.radians(self.lip_flare_deg)).line(self.lip_tip)
        return tw.segs

    @cached_property
    def lip_straight(self) -> float:
        """The straight after the lip's lean, solved so the lip's inside
        reaches lip_pre into the device. Its innermost point is where the
        flare turns it back through vertical."""
        target = self.back_x + self.device_t - self.lip_pre
        a = math.radians(self.lip_lean)
        x0 = self.hanger_x + 2 * self.j_r - self.lip_r * (1 - math.cos(a))
        # walking up, the device is on the left
        innermost = x0 - self.lip_flare_r * (1 - math.cos(a)) - self.t / 2
        return (innermost - target) / math.sin(a) if a > 0 else math.nan

    @property
    def lip_contact(self) -> Pt:
        pts = sample(self._lip(self.lip_straight), self.t / 2)
        return min(pts, key=lambda q: q[0])

    @property
    def lip_arm(self) -> float:
        return self.lip_contact[1] - self.j_y

    @property
    def lip_stress(self) -> float:
        return 3 * self.modulus * (self.t / 2) * self.lip_pre / self.lip_arm**2

    # --- checks ------------------------------------------------------------

    def validate(self) -> None:
        dims = ("rail_t", "mattress_clear", "device_t", "slot_clearance", "drop", "t", "bend_ri", "inner_len",
                "inner_pre", "inner_flare_r", "inner_flare_deg", "lip_base", "lip_r", "lip_lean", "lip_pre",
                "lip_flare_r", "lip_flare_deg", "lip_tip", "stub", "length", "label_depth", "label_size",
                "modulus", "creep_limit", "max_size")
        bad = [d for d in dims if getattr(self, d) <= 0]
        if bad:
            raise ValueError(f"must be positive: {', '.join(bad)}")
        if self.section not in SECTIONS:
            raise ValueError(f"section must be one of {SECTIONS}, not {self.section!r}")
        if min(self.inner_flare_r, self.lip_r, self.lip_flare_r) <= self.t / 2:
            raise ValueError("every arc's radius must exceed t / 2, or the strip folds over itself on the inside")
        if self.label_depth >= self.t:
            raise ValueError(f"label_depth {self.label_depth:g} must be less than t {self.t:g}")
        if math.isnan(self.inner_lean):
            raise ValueError(
                f"the inner leaf cannot lean in {self.inner_pre:g} within 45 deg: lengthen inner_len or cut inner_pre"
            )
        if not self.lip_straight > 0:
            raise ValueError(
                "the lip reaches the device before it stops leaning: cut lip_r or lip_lean, or add lip_pre"
            )
        if self.protrusion > self.mattress_clear:
            raise ValueError(
                f"the fitted inner leaf stands {self.protrusion:.2f} off the rail, more than the "
                f"{self.mattress_clear:g} mattress clearance: thin t, shrink bend_ri, or flare less"
            )
        w, h = self.size
        if max(w, h) > self.max_size:
            raise ValueError(f"the profile is {w:.0f} x {h:.0f}, over the {self.max_size:g} bed limit")
        for name, sigma in (("inner leaf", self.inner_stress), ("lip", self.lip_stress)):
            if sigma > self.creep_limit:
                raise ValueError(
                    f"the {name} would sit at {sigma:.1f} MPa, over the {self.creep_limit:g} MPa creep ceiling: "
                    "cut its preload, thin t, or lengthen it"
                )

    @property
    def size(self) -> tuple[float, float]:
        pts = sample(centreline(self))
        xs, ys = [q[0] for q in pts], [q[1] for q in pts]
        return (max(xs) - min(xs) + self.t, max(ys) - min(ys) + self.t)

    def report(self) -> str:
        return (
            f"{self.section} for a {self.device_t:g} device on a {self.rail_t:g} rail, floor {self.drop:g} down, "
            f"{self.t:g} strip x {self.length:g}: inner leaf leans {math.degrees(self.inner_lean):.1f} deg, "
            f"{self.inner_stress:.1f} MPa, stands {self.protrusion:.2f} off the rail; lip {self.lip_stress:.1f} MPa; "
            f"creep ceiling {self.creep_limit:g}"
        )


def centreline(p: HolderParams) -> list[Seg]:
    """The strip's centreline for p.section, from the inner leaf's tip (or,
    for a pocket coupon, the hanger stub's top) to the lip's tip."""
    leaf = p._leaf(p.inner_lean) if p.section != "pocket" else []
    if leaf:
        tw = Turtle(leaf[-1].end, leaf[-1].h1 + math.pi).replay_reversed(leaf)
        tw.arc(p.rc, -math.pi / 2)  # the rest of the inner corner bend, to heading +x
        tw.line(p.rail_t - 2 * p._k)
        tw.arc(p.rc, -math.pi / 2)
    else:
        tw = Turtle((p.hanger_x, p.j_y + p.stub), DOWN)
    if p.section == "clamp":
        tw.line(tw.pos[1] + p.stub)
        return tw.segs
    tw.line(tw.pos[1] - p.j_y)
    tw.arc(p.j_r, math.pi)
    return tw.segs + p._lip(p.lip_straight)
```

- [ ] **Step 4: Run the tests and check that they pass**

Run: `pixi run python -m pytest -q test_holder.py`
Expected: `10 passed`

Then check the defaults. They must validate and report the numbers the
spec relies on:

Run: `pixi run python -c "from holder import HolderParams as H; p=H(); p.validate(); print(p.report())"`
Expected output includes: `inner leaf leans 4.4 deg, 12.5 MPa, stands 4.03 off the rail; lip 12.4 MPa`

- [ ] **Step 5: Commit**

```bash
git add bedside-holder/holder.py bedside-holder/test_holder.py
git commit -m "feat(bedside-holder): parameters, spring solves and validation

Assisted-by: ClaudeCode:claude-opus-5-5
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The solid and its label

**Files:**
- Modify: `bedside-holder/holder.py` (append after `centreline`)
- Test: `bedside-holder/test_holder.py` (replace with the full version below)

**Interfaces:**
- Consumes: `HolderParams` and `centreline` (Task 2); `Seg.start`, `.mid`,
  `.end` and `.is_arc` (Task 1).
- Produces:
  - `profile(p) -> Sketch`: validates, then thickens the centreline t/2
    either side with round end caps
  - `label_y(p) -> float`
  - `holder(p) -> Part`: extruded `length` up Z; if `p.label` is set, the
    ID is engraved `label_depth` into the hanger's face toward the rail
    (x = `hanger_x` − t/2), reading down the hanger

- [ ] **Step 1: Write the failing success test**

Replace `bedside-holder/test_holder.py` with:

```python
"""The holder is one bent strip, extruded along the rail. Across devices,
sections, strip thicknesses and drops it builds one valid solid of the
expected extents; its pocket floor, inner-leaf contact and lip contact sit
where the parameters put them; it clears the mattress and stays under the
creep ceiling; and a label engraves it.

One test covers the combinations; the rest each cover one validation error.
"""

import pytest
from build123d import Vector

from holder import HolderParams, holder

TOL = 1e-3


@pytest.mark.parametrize("section", ["full", "clamp", "pocket"])
@pytest.mark.parametrize("device_t,t,drop", [
    (11.5, 3.0, 200.0),   # the laptop, as specified
    (9.3, 3.0, 200.0),    # the phone
    (11.5, 2.5, 160.0),   # thinner strip, shallowest pocket
    (9.3, 2.5, 180.0),
])
def test_holder(section, device_t, t, drop):
    p = HolderParams(device_t=device_t, t=t, drop=drop, section=section, length=10)
    p.validate()
    body = holder(p)
    assert body.is_valid() and len(body.solids()) == 1

    bb = body.bounding_box()
    assert (bb.min.Z, bb.max.Z) == pytest.approx((0, p.length), abs=TOL)
    top = p.top_y if section != "pocket" else p.j_y + p.stub + t / 2
    bottom = -drop - t if section != "clamp" else -p.stub - t / 2
    assert (bb.min.Y, bb.max.Y) == pytest.approx((bottom, top), abs=TOL)

    z = p.length / 2
    if section != "pocket":
        # relaxed, the inner leaf reaches inner_pre into the rail at one point
        x, y = p.inner_contact
        assert x == pytest.approx(-p.rail_t + p.inner_pre, abs=1e-6)
        assert body.is_inside(Vector(x - 0.05, y, z)) and not body.is_inside(Vector(x + 0.05, y, z))
        assert p.protrusion <= p.mattress_clear
        assert p.inner_stress <= p.creep_limit
    if section != "clamp":
        # the pocket's floor, the inside of the J, is drop below the rail top
        mid = p.back_x + device_t / 2
        assert body.is_inside(Vector(mid, -drop - 0.05, z)) and not body.is_inside(Vector(mid, -drop + 0.05, z))
        # relaxed, the lip reaches lip_pre into the device at one point
        x, y = p.lip_contact
        assert x == pytest.approx(p.back_x + device_t - p.lip_pre, abs=1e-6)
        assert body.is_inside(Vector(x + 0.05, y, z)) and not body.is_inside(Vector(x - 0.05, y, z))
        assert p.lip_stress <= p.creep_limit

    labelled = holder(HolderParams(device_t=device_t, t=t, drop=drop, section=section, length=10, label="ip1.0 t3"))
    assert labelled.is_valid() and labelled.volume < body.volume


def test_non_positive():
    with pytest.raises(ValueError, match="must be positive: t, bend_ri"):
        HolderParams(t=0, bend_ri=-1).validate()


def test_section():
    with pytest.raises(ValueError, match="section must be one of"):
        HolderParams(section="middle").validate()


def test_arc_too_tight():
    with pytest.raises(ValueError, match="radius must exceed t / 2"):
        HolderParams(lip_flare_r=1.4).validate()


def test_label_too_deep():
    with pytest.raises(ValueError, match="label_depth 3 must be less than t 3"):
        HolderParams(label_depth=3.0).validate()


def test_inner_leaf_cannot_lean():
    with pytest.raises(ValueError, match="inner leaf cannot lean in"):
        HolderParams(inner_len=2.0, inner_flare_r=2.0, inner_pre=4.0).validate()


def test_lip_cannot_reach():
    with pytest.raises(ValueError, match="lip reaches the device before it stops leaning"):
        HolderParams(lip_r=200.0, lip_lean=20.0).validate()


def test_mattress_clearance():
    with pytest.raises(ValueError, match="more than the 3 mattress clearance"):
        HolderParams(mattress_clear=3.0).validate()


def test_too_big_for_the_bed():
    with pytest.raises(ValueError, match="over the 250 bed limit"):
        HolderParams(drop=250.0).validate()


def test_inner_leaf_creep():
    with pytest.raises(ValueError, match="inner leaf would sit at"):
        HolderParams(inner_pre=1.5).validate()


def test_lip_creep():
    with pytest.raises(ValueError, match="lip would sit at"):
        HolderParams(lip_base=4.0).validate()
```

- [ ] **Step 2: Run the tests and check that they fail**

Run: `pixi run python -m pytest -q test_holder.py`
Expected: FAIL with `ImportError: cannot import name 'holder' from 'holder'`

- [ ] **Step 3: Append the solid to `holder.py`**

Append to `bedside-holder/holder.py`, after `centreline`, with two blank
lines before it:

```python
def _wire(segs: list[Seg]) -> Wire:
    edges = [ThreePointArc(s.start, s.mid, s.end) if s.is_arc else Line(s.start, s.end) for s in segs]
    return Wire(edges)


def profile(p: HolderParams) -> Sketch:
    p.validate()
    wire = _wire(centreline(p))
    return Sketch([make_face(wire.offset_2d(p.t / 2, kind=Kind.ARC, side=Side.BOTH, closed=True))])


def label_y(p: HolderParams) -> float:
    """Where along the hanger's rail-side face the ID is centred."""
    if p.section == "clamp":
        return -p._k - p.stub / 2
    if p.section == "pocket":
        return p.j_y + p.stub / 2
    return -p.drop / 2


def holder(p: HolderParams) -> Part:
    body = extrude(profile(p), amount=p.length)
    if p.label:
        # on the hanger's face toward the rail, reading down the hanger
        face = Plane(origin=(p.hanger_x - p.t / 2, label_y(p), p.length / 2), x_dir=(0, -1, 0), z_dir=(-1, 0, 0))
        text = face * Text(p.label, font_size=p.label_size, font_style=FontStyle.BOLD)
        body -= extrude(text, amount=-p.label_depth)
    return body
```

- [ ] **Step 4: Run the tests and check that they pass**

Run: `pixi run python -m pytest -q`
Expected: `23 passed`: 12 combinations, 10 error tests and `test_turtle`.

- [ ] **Step 5: Commit**

```bash
git add bedside-holder/holder.py bedside-holder/test_holder.py
git commit -m "feat(bedside-holder): bent-strip solid with an engraved ID

Assisted-by: ClaudeCode:claude-opus-5-5
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: CLI, justfile, README and drawing

**Files:**
- Modify: `bedside-holder/holder.py` (append after `holder`)
- Create: `bedside-holder/justfile`
- Create: `bedside-holder/README.md`
- Create: `bedside-holder/profile.svg` (generated)

**Interfaces:**
- Consumes: `HolderParams`, `profile` and `holder` (Tasks 2 and 3).
- Produces: `python holder.py -o <file.stl|.step|.svg> [--<field> value ...]`,
  with one flag per `HolderParams` field. It prints `-> <path>` and then
  `report()`.

- [ ] **Step 1: Append the CLI to `holder.py`**

Append to `bedside-holder/holder.py`, after `holder`, with two blank lines
before it:

```python
def _svg(p: HolderParams, out: Path) -> None:
    """The profile, relaxed, over the rail (dashed) with the device ghosted."""
    from build123d import ExportSVG, LineType, Location, Rectangle

    rail = Rectangle(p.rail_t, 160).moved(Location((-p.rail_t / 2, -80)))
    dev = Rectangle(p.device_t, 60).moved(Location((p.back_x + p.device_t / 2, -p.drop + 30)))
    svg = ExportSVG(scale=2, margin=6, line_weight=0.35)
    svg.add_layer("rail", line_color=(150, 150, 150), line_type=LineType.ISO_DASH, line_weight=0.2)
    svg.add_layer("device", line_color=(190, 190, 190), line_type=LineType.ISO_DOT, line_weight=0.2)
    svg.add_shape(rail, layer="rail")
    if p.section != "clamp":
        svg.add_shape(dev, layer="device")
    svg.add_shape(profile(p))
    svg.write(str(out))


def _cli() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("-o", "--output", type=Path, required=True, help=".stl, .step or .svg path")
    for f in fields(HolderParams):
        ap.add_argument(f"--{f.name}", type=type(f.default), default=f.default)
    return ap


def main(argv: list[str] | None = None) -> None:
    args = _cli().parse_args(argv)
    p = HolderParams(**{f.name: getattr(args, f.name) for f in fields(HolderParams)})
    out: Path = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix == ".svg":
        _svg(p, out)
    elif out.suffix == ".step":
        from build123d import export_step

        export_step(holder(p), str(out))
    else:
        export_stl(holder(p), str(out), tolerance=0.01, angular_tolerance=0.1)
    print(f"-> {out}")
    print(p.report())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create the justfile**

`bedside-holder/justfile`:

```just
# Dev actions for the bedside holder: one bent strip that hooks over the bed
# rail and stores a device upright in a pocket down the rail's outer face.
# Run `just` to list them.
#
# Run inside the pixi env (`pixi shell`) or via `pixi run <recipe>`.

python := env("PYTHON", "python")
out := "stl"

t := "3"              # strip thickness, mm
inner_pre := "1.0"    # relaxed overlap of the inner leaf into the rail, mm
lip_pre := "0.75"     # relaxed overlap of the lip into the device, mm
drop := "200"         # pocket floor below the rail's top edge, mm
laptop_t := "11.5"    # MacBook Air 15"
phone_t := "9.3"      # iPhone 4, no case
args := "--t " + t + " --inner_pre " + inner_pre + " --lip_pre " + lip_pre + " --drop " + drop

# --- Coupons: the profile extruded 10 mm, cropped to the clamp or the pocket.
# Short fit tests, so the creep ceiling is relaxed: the sweep deliberately
# brackets it.
coupon_length := "10"
coupon_ts := "2.5 3"
coupon_inner_pres := "0.5 1.0 1.5"
coupon_lip_pres := "0.5 0.75 1.0"
coupon_args := "--length " + coupon_length + " --creep_limit 30"

default:
    @just --list

# Render the holder (.stl, .step or .svg) with any --param overrides, e.g. `just render out.stl --t 2.5`
[positional-arguments]
render outfile *args:
    {{python}} holder.py -o "$@"

# Clamp coupons over inner_pre x t: push each onto the rail
clamp-coupons:
    #!/usr/bin/env bash
    set -euo pipefail
    for t in {{coupon_ts}}; do
        for ip in {{coupon_inner_pres}}; do
            just render "{{out}}/clamp_coupon_t${t}_ip${ip}.stl" {{coupon_args}} --section clamp \
                --t "$t" --inner_pre "$ip" --label "ip$ip t$t"
        done
    done

# Pocket coupons for one device thickness over lip_pre x t: slide the device in and out
[positional-arguments]
pocket-coupons device_t=laptop_t:
    #!/usr/bin/env bash
    set -euo pipefail
    for t in {{coupon_ts}}; do
        for lp in {{coupon_lip_pres}}; do
            just render "{{out}}/pocket_coupon_d{{device_t}}_t${t}_lp${lp}.stl" {{coupon_args}} --section pocket \
                --device_t {{device_t}} --t "$t" --lip_pre "$lp" --label "lp$lp t$t"
        done
    done

# Pocket coupons for the phone
phone-coupons:
    just pocket-coupons {{phone_t}}

# One laptop clip (print two, ~200 mm apart under the laptop)
laptop:
    just render "{{out}}/holder_laptop_t{{t}}_ip{{inner_pre}}_lp{{lip_pre}}.stl" {{args}} \
        --device_t {{laptop_t}} --length 50 --label "laptop t{{t}}"

# The phone clip
phone:
    just render "{{out}}/holder_phone_t{{t}}_ip{{inner_pre}}_lp{{lip_pre}}.stl" {{args}} \
        --device_t {{phone_t}} --length 40 --label "phone t{{t}}"

# Regenerate the drawing used by the README
preview:
    just render profile.svg {{args}}

# Run the geometry tests
test:
    {{python}} -m pytest -q

# Delete rendered output
clean:
    rm -rf {{out}}
```

- [ ] **Step 3: Run every recipe and check the output**

Run: `pixi run just clamp-coupons && pixi run just pocket-coupons && pixi run just phone-coupons && pixi run just laptop && pixi run just phone && pixi run just preview && ls stl | wc -l`
Expected:
- 20 files in `stl/`: 6 clamp, 6 laptop-pocket and 6 phone-pocket
  coupons, plus 2 full parts
- `profile.svg` written
- the clamp coupon labelled `ip1.5 t3` reports `18.6 MPa` against
  `creep ceiling 30`, which proves the coupon override works
- `laptop` reports `creep ceiling 15`

`stl/` is already ignored by the repo's `.gitignore`.

- [ ] **Step 4: Write the README**

`bedside-holder/README.md`:

````markdown
# Bedside holder

A clip that hooks over the bed's side rail and stores a device upright in a
pocket that hangs down the rail's outer face. The device sits low, so it's
out of the way when you get in and out of bed, and it leans back against
the rail. The same design makes a laptop clip (a 15" MacBook Air; print
two, about 200 mm apart) and a phone clip (an iPhone 4).

It's one 3 mm strip, bent like heat-formed plastic: straight runs joined by
tangent arcs, thickened evenly either side. From the bed side:

- a flared tip and the **inner leaf**, which leans in so that, relaxed, it
  overlaps the 23 mm rail by 1 mm and springs against it when pushed on
- two soft bends over the rail's top corners, with an inside radius of 3.5.
  They're placed to touch the corners, so the strip stands about 1 mm clear
  of the top edge and doesn't care how square it is
- the **hanger** down the outer face; the device's back rests on it
- a 180° **J**, whose inside is the pocket floor, 200 mm below the rail top
- the **spring lip**, which leans in 6° to overlap the device by 0.75 mm,
  pressing its lower back onto the hanger so it tips toward the bed, then
  flares out as a lead-in

![profile](profile.svg)

The profile relaxed, over the rail (dashed), with the laptop's foot dotted.

It prints flat: the profile lies on the bed and the clip's width along the
rail is print Z.

## Springs and creep

The inner leaf and the lip are cantilevers of the strip, held deflected for
as long as the clip is on. At a deflection δ, a cantilever of arm L has a
root stress of `σ = 3·E·(t/2)·δ / L²`. That gives 12.5 MPa in the inner
leaf and 12.4 MPa in the lip at the defaults, against PETG's creep ceiling
of about 15 MPa. The bends add compliance on top of this, so the estimate
is conservative. `validate()` refuses any geometry over the ceiling, and
any inner leaf that would stand more than 5 mm off the rail, since that's
all the room there is before the mattress.

A rail 0.5 mm thicker than nominal takes the inner leaf over the ceiling.
That's what the coupons are for.

## Coupons

The part is one profile, so a coupon is that profile extruded 10 mm,
cropped to the part you're testing, with its parameters engraved on the
hanger's rail side:

```bash
pixi run just clamp-coupons    # inner_pre 0.5/1.0/1.5 x t 2.5/3: push onto the rail
pixi run just pocket-coupons   # lip_pre 0.5/0.75/1.0 x t 2.5/3 for the laptop
pixi run just phone-coupons    # the same for the phone
```

Coupons relax the creep ceiling to 30 MPa, because the sweep deliberately
brackets it. Pick the loosest clamp coupon that doesn't slide on the rail,
and the loosest pocket coupon that holds the device without rattling. Set
those values at the top of the `justfile`, then:

```bash
pixi run just laptop   # print two
pixi run just phone
```
````

- [ ] **Step 5: Run the full test suite**

Run: `pixi run just test`
Expected: `23 passed`

- [ ] **Step 6: Commit**

```bash
git add bedside-holder/holder.py bedside-holder/justfile bedside-holder/README.md bedside-holder/profile.svg
git commit -m "feat(bedside-holder): CLI, coupon sweeps and write-up

Assisted-by: ClaudeCode:claude-opus-5-5
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
