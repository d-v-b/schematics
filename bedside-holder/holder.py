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
hanger, so it rests back against the hanger.

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
    drop: float = 200.0           # where the device's foot seats (the J's centre) below the rail's top edge
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
        """Height of the J's centre, where the device's foot seats, and of
        the lip's root."""
        return -self.drop

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
        if self.lip_flare_deg <= self.lip_lean:
            raise ValueError("lip_flare_deg must exceed lip_lean, or the lip never turns back from the device")
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
                f"{self.mattress_clear:g} mattress clearance: thin t or shrink bend_ri, or flare the leaf less"
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
