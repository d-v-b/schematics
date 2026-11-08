"""A bedside holder: one strip of constant thickness, bent like heat-formed
plastic, that hooks over a bed's side rail and stores a device upright in a
pocket hanging down the rail's outer face.

The strip's centreline is a chain of straight lines and tangent arcs; the
strip is that centreline thickened ``t / 2`` either side. From the bed side:
a flared tip, the sprung inner leaf, a bend over the rail's inner top
corner, a straight across the top, a bend over the outer top corner that
stops ``lean`` short of vertical, the hanger leaning down and away from the
rail's outer face, a 180 degree J in which the device's foot seats, and a
spring lip that leans in and flares out again as a lead-in. A solid pad
holds the hanger off the rail face ``pad_y`` below its top, so the device
lying on the hanger tips its top toward the bed. The pad is a buttress on
the hanger's rail side only: a round nose on the rail face, swept into the
hanger's rail-side face by a concave fillet above and below, tangent all
the way, so the hanger's device-side face stays flat.

Relaxed, the inner leaf overlaps the rail by ``inner_pre`` and the lip
overlaps the device by ``lip_pre``; both are cantilevers of the strip that
those overlaps preload. The lip pushes the device's lower back onto the
hanger, and the lean lays the rest of it there.

Coordinates: X across the rail, which occupies -rail_t <= x <= 0 (+x away
from the bed); Y up, with y = 0 the rail's top edge; Z along the rail. The
profile lies in XY and is extruded ``length`` up Z, which is print Z: it
prints flat on the bed.

Usage:
    python holder.py -o holder.stl [--device_t 11.5] [--length 50]
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass, fields
from functools import cached_property
from pathlib import Path

from build123d import (
    Edge,
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

UP, DOWN = math.pi / 2, -math.pi / 2


@dataclass(frozen=True)
class HolderParams:
    rail_t: float = 23.0          # the bed rail's thickness, mm
    mattress_clear: float = 5.0   # room between the rail's inner face and the mattress
    device_t: float = 11.5        # the device's thickness: 11.5 MacBook Air 15", 9.3 iPhone 4
    slot_clearance: float = 0.5   # the pocket's gap is device_t plus this
    drop: float = 200.0           # where the device's foot seats (the J's centre) below the rail's top edge
    lean: float = 7.0             # the hanger's lean off the rail face, deg: the device's top tips toward the bed
    rail_h: float = 160.0         # the bed rail's height
    pad_y: float = 140.0          # the pad's centre, below the rail's top edge
    pad_r: float = 6.0            # radius of the pad's nose on the rail face
    pad_fillet: float = 15.0      # radius of the concave sweeps from the nose into the hanger
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
    length: float = 50.0          # extrusion along the rail (print Z); 1 for a coupon slice
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
    def _a(self) -> float:
        return math.radians(self.lean)

    @property
    def hanger_dir(self) -> Pt:
        """Unit vector down the hanger."""
        return (math.sin(self._a), -math.cos(self._a))

    @property
    def hanger_n(self) -> Pt:
        """Unit normal off the hanger, away from the rail, toward the device."""
        return (math.cos(self._a), math.sin(self._a))

    @property
    def hanger_start(self) -> Pt:
        """The hanger's centreline where the outer corner bend ends."""
        return (-self._k + self.rc * math.cos(self._a), -self._k + self.rc * math.sin(self._a))

    @property
    def gap(self) -> float:
        return self.device_t + self.slot_clearance

    @property
    def j_r(self) -> float:
        return self.gap / 2 + self.t / 2

    @property
    def hanger_end(self) -> Pt:
        """The hanger's centreline where the J begins: its centre, j_r off
        the hanger, is drop below the rail top."""
        (x, y), (dx, dy) = self.hanger_start, self.hanger_dir
        n = (y - (-self.drop - self.j_r * self.hanger_n[1])) / -dy
        return (x + n * dx, y + n * dy)

    @property
    def hanger_len(self) -> float:
        (x0, y0), (x1, y1) = self.hanger_start, self.hanger_end
        return math.hypot(x1 - x0, y1 - y0)

    def hanger_at(self, y: float) -> Pt:
        """The hanger's centreline at height y."""
        (x0, y0), (dx, dy) = self.hanger_start, self.hanger_dir
        return (x0 + (y - y0) / dy * dx, y)

    def world(self, u: float, v: float) -> Pt:
        """The pocket's frame: u across the slot away from the hanger, v up
        the hanger, from the J's centre, where the device seats."""
        (x, y), (nx, ny), (dx, dy) = self.hanger_end, self.hanger_n, self.hanger_dir
        return (x + (self.j_r + u) * nx - v * dx, y + (self.j_r + u) * ny - v * dy)

    def local(self, q: Pt) -> Pt:
        """The inverse of world."""
        cx, cy = self.world(0, 0)
        (nx, ny), (dx, dy) = self.hanger_n, self.hanger_dir
        return ((q[0] - cx) * nx + (q[1] - cy) * ny, -((q[0] - cx) * dx + (q[1] - cy) * dy))

    @property
    def pad_nose(self) -> Pt:
        """Centre of the pad's nose, which touches the rail face at pad_y."""
        return (self.pad_r, -self.pad_y)

    @property
    def pad_gap(self) -> float:
        """From the nose's centre to the hanger's rail-side face."""
        (cx, cy), (nx, ny) = self.pad_nose, self.hanger_n
        fx, fy = self.hanger_start
        return (fx - self.t / 2 * nx - cx) * nx + (fy - self.t / 2 * ny - cy) * ny

    def _pad_fillet(self, side: int) -> tuple[Pt, Pt, Pt]:
        """The concave fillet above (side -1) or below (+1) the nose: its
        centre, pad_fillet off the hanger's rail-side face and pad_r +
        pad_fillet from the nose's centre, and its tangent points on the
        face and on the nose."""
        (cx, cy), (nx, ny), (dx, dy) = self.pad_nose, self.hanger_n, self.hanger_dir
        r, f = self.pad_r, self.pad_fillet
        a = self.pad_gap - f
        b = side * math.sqrt((r + f) ** 2 - a**2)
        kx, ky = cx + a * nx + b * dx, cy + a * ny + b * dy
        on_face = (kx + f * nx, ky + f * ny)
        on_nose = (cx + r * (kx - cx) / (r + f), cy + r * (ky - cy) / (r + f))
        return (kx, ky), on_face, on_nose

    @property
    def pad_blend(self) -> tuple[Pt, Pt]:
        """Where the pad's fillets meet the hanger's rail-side face, above
        and below."""
        return self._pad_fillet(-1)[1], self._pad_fillet(1)[1]

    @property
    def pad_thick(self) -> float:
        """The pad's span from the rail face to the hanger's rail-side face."""
        return self.hanger_at(-self.pad_y)[0] - self.t / 2 / math.cos(self._a)

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
        # from the J's far end, heading back up the hanger
        tw = Turtle(self.world(self.j_r, 0), UP + self._a)
        tw.line(self.lip_base).arc(self.lip_r, math.radians(self.lip_lean)).line(straight)
        tw.arc(self.lip_flare_r, -math.radians(self.lip_flare_deg)).line(self.lip_tip)
        return tw.segs

    @cached_property
    def lip_straight(self) -> float:
        """The straight after the lip's lean, solved so the lip's inside
        reaches lip_pre into the device. Its innermost point is where the
        flare turns it back parallel to the hanger. Worked across the slot
        (u in the pocket's frame), so it holds at any hanger lean."""
        target = -self.gap / 2 + self.device_t - self.lip_pre
        a = math.radians(self.lip_lean)
        x0 = self.j_r - self.lip_r * (1 - math.cos(a))
        # walking up, the device is on the left
        innermost = x0 - self.lip_flare_r * (1 - math.cos(a)) - self.t / 2
        return (innermost - target) / math.sin(a) if a > 0 else math.nan

    @property
    def lip_contact(self) -> Pt:
        pts = sample(self._lip(self.lip_straight), self.t / 2)
        return min(pts, key=lambda q: self.local(q)[0])

    @property
    def lip_arm(self) -> float:
        return self.local(self.lip_contact)[1]

    @property
    def lip_stress(self) -> float:
        return 3 * self.modulus * (self.t / 2) * self.lip_pre / self.lip_arm**2

    # --- checks ------------------------------------------------------------

    def validate(self) -> None:
        dims = ("rail_t", "mattress_clear", "device_t", "slot_clearance", "drop", "t", "bend_ri", "inner_len",
                "inner_pre", "inner_flare_r", "inner_flare_deg", "lip_base", "lip_r", "lip_lean", "lip_pre",
                "lip_flare_r", "lip_flare_deg", "lip_tip", "length", "label_depth", "label_size",
                "modulus", "creep_limit", "max_size", "lean", "rail_h", "pad_y", "pad_r", "pad_fillet")
        bad = [d for d in dims if getattr(self, d) <= 0]
        if bad:
            raise ValueError(f"must be positive: {', '.join(bad)}")
        if min(self.inner_flare_r, self.lip_r, self.lip_flare_r) <= self.t / 2:
            raise ValueError("every arc's radius must exceed t / 2, or the strip folds over itself on the inside")
        if self.lip_flare_deg <= self.lip_lean:
            raise ValueError("lip_flare_deg must exceed lip_lean, or the lip never turns back from the device")
        if self.label_depth >= min(self.t, self.length):
            raise ValueError(
                f"label_depth {self.label_depth:g} must be less than t {self.t:g} and length {self.length:g}"
            )
        if math.isnan(self.inner_lean):
            raise ValueError(
                f"the inner leaf cannot lean in {self.inner_pre:g} within 45 deg: lengthen inner_len or cut inner_pre"
            )
        if not self.lip_straight > 0:
            raise ValueError(
                "the lip reaches the device before it stops leaning: cut lip_r or lip_lean, or add lip_pre"
            )
        if self.pad_y + self.pad_r > self.rail_h:
            raise ValueError(
                f"the pad hangs off the bottom of the rail ({self.pad_y + self.pad_r:g} below its top, on a "
                f"{self.rail_h:g} rail): raise pad_y or shrink pad_r"
            )
        if self.pad_gap <= self.pad_r:
            raise ValueError(
                f"lean {self.lean:g} is too small to hold the hanger off the rail at the pad: "
                "lean more, lower the pad, or shrink pad_r"
            )
        if self.pad_gap >= self.pad_r + 2 * self.pad_fillet:
            raise ValueError(
                f"pad_fillet {self.pad_fillet:g} is too small to reach the hanger from the pad's nose: grow it"
            )
        up, down = self.pad_blend
        if not (self.hanger_end[1] < down[1] and up[1] < self.hanger_start[1]):
            raise ValueError(
                "the pad must meet the hanger between the rail top and the pocket: move pad_y or deepen drop"
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
            f"for a {self.device_t:g} device on a {self.rail_t:g} rail, seated {self.drop:g} down, "
            f"leaning {self.lean:g} deg on a {self.pad_thick:.1f} pad, "
            f"{self.t:g} strip x {self.length:g}: inner leaf leans {math.degrees(self.inner_lean):.1f} deg, "
            f"{self.inner_stress:.1f} MPa, stands {self.protrusion:.2f} off the rail; lip {self.lip_stress:.1f} MPa; "
            f"creep ceiling {self.creep_limit:g}"
        )


def centreline(p: HolderParams) -> list[Seg]:
    """The strip's centreline, from the inner leaf's tip to the lip's tip."""
    leaf = p._leaf(p.inner_lean)
    tw = Turtle(leaf[-1].end, leaf[-1].h1 + math.pi).replay_reversed(leaf)
    tw.arc(p.rc, -math.pi / 2)  # the rest of the inner corner bend, to heading +x
    tw.line(p.rail_t - 2 * p._k)
    tw.arc(p.rc, -(math.pi / 2 - p._a))  # stops lean short of vertical
    tw.line(p.hanger_len)
    tw.arc(p.j_r, math.pi)
    return tw.segs + p._lip(p.lip_straight)


def _wire(segs: list[Seg]) -> Wire:
    edges = [ThreePointArc(s.start, s.mid, s.end) if s.is_arc else Line(s.start, s.end) for s in segs]
    return Wire(edges)


def profile(p: HolderParams) -> Sketch:
    p.validate()
    wire = _wire(centreline(p))
    strip = Sketch([make_face(wire.offset_2d(p.t / 2, kind=Kind.ARC, side=Side.BOTH, closed=True))])
    # close the pad's outline inside the strip, along its centreline
    (_, up, _), (_, down, _) = p._pad_fillet(-1), p._pad_fillet(1)
    nx, ny = p.hanger_n
    up_in, down_in = (up[0] + p.t / 2 * nx, up[1] + p.t / 2 * ny), (down[0] + p.t / 2 * nx, down[1] + p.t / 2 * ny)
    edges = pad_outline(p) + [Line(down, down_in), Line(down_in, up_in), Line(up_in, up)]
    return strip + Sketch([make_face(Wire(edges))])


def pad_outline(p: HolderParams) -> list[Edge]:
    """The pad's exposed outline, from where it leaves the hanger's rail-side
    face above the nose to where it rejoins it below: the upper fillet, the
    nose round the rail side, the lower fillet."""
    (cx, cy), (nx, ny), r, f = p.pad_nose, p.hanger_n, p.pad_r, p.pad_fillet

    def fillet(side: int) -> tuple[Pt, Pt, Pt]:
        (kx, ky), on_face, on_nose = p._pad_fillet(side)
        # midway round the short arc: between the directions to its two ends
        mx, my = nx + (cx - kx) / (r + f), ny + (cy - ky) / (r + f)
        m = math.hypot(mx, my)
        return on_face, (kx + f * mx / m, ky + f * my / m), on_nose

    face_up, mid_up, nose_up = fillet(-1)
    face_dn, mid_dn, nose_dn = fillet(1)
    return [
        ThreePointArc(face_up, mid_up, nose_up),
        ThreePointArc(nose_up, (cx - r * nx, cy - r * ny), nose_dn),  # the long way, round the rail side
        ThreePointArc(nose_dn, mid_dn, face_dn),
    ]


def label_plane(p: HolderParams) -> tuple[Plane, float]:
    """Where the ID goes, and its text size, centred on the hanger between
    the rail top and the pad. A real part carries it in the hanger's
    rail-side face, hidden in use, reading down the hanger. A slice too thin
    for that (a coupon) carries it in its top face, reading up the hanger,
    small enough to fit the strip's width."""
    (x, y), (dx, dy), (nx, ny) = p.hanger_at((p.hanger_start[1] + p.pad_blend[0][1]) / 2), p.hanger_dir, p.hanger_n
    if p.length < p.label_size + 1:
        return Plane(origin=(x, y, p.length), x_dir=(-dx, -dy, 0), z_dir=(0, 0, 1)), p.t - 1
    origin = (x - p.t / 2 * nx, y - p.t / 2 * ny, p.length / 2)
    return Plane(origin=origin, x_dir=(dx, dy, 0), z_dir=(-nx, -ny, 0)), p.label_size


def holder(p: HolderParams) -> Part:
    body = extrude(profile(p), amount=p.length)
    if p.label:
        plane, size = label_plane(p)
        text = plane * Text(p.label, font_size=size, font_style=FontStyle.BOLD)
        body -= extrude(text, amount=-p.label_depth)
    return body


def _svg(p: HolderParams, out: Path) -> None:
    """The profile, relaxed, over the rail (dashed) with the device ghosted."""
    from build123d import ExportSVG, LineType, Location, Polygon, Rectangle

    rail = Rectangle(p.rail_t, p.rail_h).moved(Location((-p.rail_t / 2, -p.rail_h / 2)))
    back = -p.gap / 2
    dev = Polygon(*[p.world(u, v) for u, v in ((back, 0), (back + p.device_t, 0), (back + p.device_t, 60), (back, 60))],
                  align=None)
    svg = ExportSVG(scale=2, margin=6, line_weight=0.35)
    svg.add_layer("rail", line_color=(150, 150, 150), line_type=LineType.ISO_DASH, line_weight=0.2)
    svg.add_layer("device", line_color=(190, 190, 190), line_type=LineType.ISO_DOT, line_weight=0.2)
    svg.add_shape(rail, layer="rail")
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
