"""Flat bar with a row of slots for M6 bolts down its middle, to sit on top
of a 40 mm aluminium extrusion rail and be bolted into its T-slot anywhere
along each slot.

The bar is ``width`` x ``thickness`` in section and ``length`` long. Each
end is capped by a circular arc of radius ``end_r`` centred on the bar's
centreline ``end_r`` in from the tip, so a bar pivoting on a bolt at that
point sweeps nothing beyond a circle of that radius and can turn on the
rail without the end protruding. At the default, half the width, each end
is a full semicircle centred on the first slot. A larger radius gives a
flatter end whose corners with the long sides are rounded to ``corner_r``. Each slot is ``slot_w`` wide
(M6 clearance plus a print allowance) and ``slot_l`` long overall along
the bar, with round ends; the slots repeat on a ``pitch`` along the bar's
centreline, leaving ``pitch - slot_l`` of material between them. With
capped ends the end slots are centred on the arc centres, ``end_r`` in
from each tip, so the length must be ``2 * end_r`` plus a whole number of
pitches; with square ends the row is centred along the length so the end
slots sit at least ``end_margin`` from the ends. ``slots`` fixes the count
instead when it is positive. ``slot_l`` equal to ``slot_w`` gives plain
round holes. Each slot is countersunk 90 degrees from the top face out to
``csk_d`` wide, so M6 flat-head (countersunk) screws sit flush and the top
stays clear for whatever slides over it; 0 leaves the slots square-edged.

The bar lies in the XY plane centred on the origin, its length along X and
its width along Y, and is extruded ``thickness`` up Z. Print it flat, as
drawn: the slots run along the print's Z, so nothing overhangs.

Usage:
    python bolt_bar.py -o bar.stl [--length 200] [--pitch 40] [--slot_l 30] ...
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass, fields
from pathlib import Path

from build123d import (
    Circle,
    FontStyle,
    Location,
    Part,
    Line,
    Plane,
    RectangleRounded,
    Sketch,
    SlotOverall,
    Text,
    ThreePointArc,
    export_stl,
    extrude,
    make_face,
)


@dataclass(frozen=True)
class BarParams:
    """Every dimension of the bar, in millimetres."""

    # Extent along the rail.
    length: float = 200.0
    # Across the rail: the same as the 40 mm extrusion it sits on.
    width: float = 40.0
    thickness: float = 5.0
    # Slot width, across the bar. M6 clearance is 6.4 (ISO 273 fine); 0.2
    # more lets a printed slot, which comes out narrow, pass the bolt.
    slot_w: float = 6.6
    # Slot length along the bar, overall (round end to round end). Equal to
    # slot_w gives a round hole.
    slot_l: float = 30.0
    # Centre-to-centre distance between neighbouring slots. pitch - slot_l
    # is the material left between them.
    pitch: float = 40.0
    # Square ends only (end_r = 0): least distance from either end of the
    # bar to the nearest slot's centre. The row is centred along the bar, so
    # the actual margin is this or more. With capped ends the end slots sit
    # on the arc centres, end_r in from the tips, instead.
    end_margin: float = 20.0
    # Number of slots. 0 = as many as fit at the pitch inside the margins.
    slots: int = 0
    # Width at the top face of the 90 degree countersink along each slot,
    # for flat-head screws. An ISO 10642 M6 head is 12.0 across (theoretical
    # sharp edge); 0.4 more lets a printed countersink take it flush. The
    # countersink is (csk_d - slot_w) / 2 deep. 0 = none.
    csk_d: float = 12.4
    # Radius of the arc capping each end, centred on the centreline this far
    # in from the tip: a bolt there is the pivot the bar can turn on without
    # the end reaching past this radius. 0 = square ends. Must be at least
    # half the width so the arc spans the bar; exactly half (the default)
    # makes each end a full semicircle, centred on the first slot.
    end_r: float = 20.0
    # Radius on the four plan corners where the end arcs meet the sides.
    corner_r: float = 3.0
    # ID engraved into the top face, reading along the bar, in the strip
    # of material beside the slot row. Empty disables.
    label: str = ""
    label_depth: float = 0.4
    label_size: float = 3.0

    # ----- derived -----
    @property
    def margin(self) -> float:
        """Distance from each tip to the end slot's centre: the arc centre
        with capped ends, else the least margin asked for."""
        return self.end_r if self.end_r > 0 else self.end_margin

    @property
    def n_slots(self) -> int:
        if self.slots > 0:
            return self.slots
        span = self.length - 2 * self.margin
        if span < 0:
            return 0
        return int(math.floor(span / self.pitch + 1e-9)) + 1

    @property
    def slot_xs(self) -> list[float]:
        """Slot centres along X. With capped ends the end slots sit on the
        arc centres; otherwise the row is centred on the bar."""
        n = self.n_slots
        if self.end_r > 0 and n > 1:
            half = self.length / 2 - self.end_r
            return [-half + i * (2 * half) / (n - 1) for i in range(n)]
        return [(i - (n - 1) / 2) * self.pitch for i in range(n)]

    @property
    def end_sagitta(self) -> float:
        """How far the tip of the end arc stands proud of the corners."""
        if self.end_r <= 0:
            return 0.0
        return self.end_r - math.sqrt(self.end_r**2 - (self.width / 2) ** 2)

    @property
    def end_is_semicircle(self) -> bool:
        """end_r equals half the width: the arc meets the sides tangentially,
        so there is no corner to round."""
        return 0 < self.end_r <= self.width / 2 + 1e-9

    @property
    def csk_depth(self) -> float:
        """How far the 90 degree countersink reaches down from the top face."""
        return max(0.0, (self.csk_d - self.slot_w) / 2)

    @property
    def ligament(self) -> float:
        """Solid material between two neighbouring slots."""
        return self.pitch - self.slot_l

    @property
    def top_ligament(self) -> float:
        """Material left between neighbouring countersinks at the top face."""
        return self.ligament - 2 * self.csk_depth

    @property
    def edge_ligament(self) -> float:
        """Solid material between a slot and the bar's long edge."""
        return (self.width - self.slot_w) / 2

    def validate(self) -> None:
        if self.length <= 0 or self.width <= 0 or self.thickness <= 0:
            raise ValueError("length, width and thickness must be positive")
        if self.slot_w <= 0:
            raise ValueError("slot_w must be positive")
        if self.slot_l < self.slot_w:
            raise ValueError("slot_l must be at least slot_w")
        if self.pitch <= self.slot_l:
            raise ValueError("pitch must exceed slot_l, or the slots merge")
        if self.slot_w >= self.width:
            raise ValueError("slot_w must be less than width")
        if self.csk_d < 0 or (0 < self.csk_d <= self.slot_w):
            raise ValueError("csk_d must be 0 or wider than slot_w")
        if self.csk_d >= self.width:
            raise ValueError("csk_d must be less than width")
        if self.csk_depth >= self.thickness:
            raise ValueError("countersink must be shallower than the bar: reduce csk_d or thicken the bar")
        if self.n_slots > 1 and self.top_ligament <= 0:
            raise ValueError("the countersinks of neighbouring slots merge: widen the pitch or reduce csk_d")
        if self.end_r < 0 or (0 < self.end_r < self.width / 2):
            raise ValueError("end_r must be 0 or at least width / 2, so the arc spans the bar")
        if self.end_r > 0 and self.length < 2 * self.end_r:
            raise ValueError("length must be at least 2 * end_r, or the end arcs cross")
        if self.n_slots < 1:
            raise ValueError("no slot fits: length must be at least 2 * end_margin")
        if self.end_r > 0:
            # the end slots sit on the arc centres, so the span between them
            # must be a whole number of pitches (zero for a single slot)
            span = self.length - 2 * self.end_r
            want = (self.n_slots - 1) * self.pitch
            if abs(span - want) > 1e-6:
                k = math.floor(span / self.pitch + 1e-9)
                lo, hi = 2 * self.end_r + k * self.pitch, 2 * self.end_r + (k + 1) * self.pitch
                raise ValueError(
                    "with capped ends the end slots sit on the arc centres, so length must be "
                    f"2 * end_r + k * pitch: got {self.length}, nearest are {lo:g} and {hi:g}"
                )
        xs = self.slot_xs
        if xs[-1] + self.slot_l / 2 + self.csk_depth >= self.length / 2:
            raise ValueError("the end slots (with their countersinks) break out of the bar's ends")
        if self.corner_r < 0:
            raise ValueError("corner_r must not be negative")
        if not self.end_is_semicircle and 2 * self.corner_r > min(self.length - 2 * self.end_sagitta, self.width):
            raise ValueError("corner_r must fit within the bar")
        if self.label and self.label_depth >= self.thickness:
            raise ValueError("label_depth must be less than thickness")

    def report(self) -> str:
        xs = self.slot_xs
        text = (
            f"{self.width} x {self.thickness} x {self.length} bar, "
            f"{self.n_slots} slots {self.slot_w} x {self.slot_l} at {self.pitch} pitch, "
            f"end margin {self.length / 2 - xs[-1]:.1f}, "
            f"ligament {self.ligament:.1f} between slots, {self.edge_ligament:.1f} to the edge"
        )
        if self.end_r > 0:
            text += f"; ends capped R{self.end_r} with the end slots centred on the arcs"
        if self.csk_d > 0:
            text += (
                f"; countersunk to {self.csk_d} wide, {self.csk_depth:.1f} deep, "
                f"leaving {self.thickness - self.csk_depth:.1f} of straight wall"
            )
        return text


def outline(p: BarParams) -> Sketch:
    """The bar's plan without the slots: a rectangle, its ends trimmed to
    the arcs, its corners rounded."""
    if p.end_r <= 0:
        return Sketch(list(RectangleRounded(p.length, p.width, p.corner_r).faces()))
    xc, yc, xt = p.length / 2 - p.end_sagitta, p.width / 2, p.length / 2  # corner and tip
    arcs = [ThreePointArc((xc, -yc), (xt, 0), (xc, yc)), ThreePointArc((-xc, yc), (-xt, 0), (-xc, -yc))]
    if xc < 1e-9:  # the two arcs meet: no straight sides (a circle, for a semicircular cap)
        face = make_face(arcs).face()
    else:
        face = make_face([Line((-xc, -yc), (xc, -yc)), arcs[0], Line((xc, yc), (-xc, yc)), arcs[1]]).face()
    if p.corner_r > 0 and not p.end_is_semicircle:  # a semicircle is already tangent to the sides
        face = face.fillet_2d(p.corner_r, face.vertices())
    return Sketch([face])


def _stadium(length: float, width: float):
    """A slot outline length long overall and width wide, or a circle when
    they are equal (SlotOverall refuses a zero-length slot)."""
    if length <= width + 1e-9:
        return Circle(width / 2)
    return SlotOverall(length, width)


def slots(p: BarParams) -> Sketch:
    return Sketch([_stadium(p.slot_l, p.slot_w).moved(Location((x, 0))).face() for x in p.slot_xs])


def profile(p: BarParams) -> Sketch:
    """The bar's plan with the slots cut."""
    p.validate()
    return Sketch(list((outline(p) - slots(p)).faces()))


def _label_cut(p: BarParams) -> Part | None:
    if not p.label:
        return None
    # in the strip of material beside the slot row (+y side), reading along the bar
    y_mid = (p.slot_w / 2 + p.width / 2) / 2
    size = min(p.label_size, p.edge_ligament - 1.0)
    plane = Plane(origin=(0, y_mid, p.thickness), x_dir=(1, 0, 0), z_dir=(0, 0, 1))
    text = plane * Text(p.label, font_size=size, font_style=FontStyle.BOLD)
    return extrude(text, amount=-p.label_depth)


def _countersink(p: BarParams, body: Part) -> Part:
    """Cut a 90 degree countersink the whole way round each slot: a stadium
    csk_d wide at the top face, tapering at 45 degrees down to the slot
    at csk_depth (run a hair past, inside the slot's void, so no faces
    coincide)."""
    d = p.csk_depth
    if d <= 0:
        return body
    top = Plane.XY.offset(p.thickness)
    for x in p.slot_xs:
        wide = top * _stadium(p.slot_l + 2 * d, p.csk_d).moved(Location((x, 0)))
        body = body - extrude(wide, amount=-(d + 0.01), taper=45)
    return body


def bar(p: BarParams) -> Part:
    body = extrude(profile(p), amount=p.thickness, dir=(0, 0, 1))
    body = _countersink(p, body)
    cut = _label_cut(p)
    if cut is not None:
        body = body - cut
    return body


def _cli() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("-o", "--output", type=Path, required=True, help=".stl, .step or .svg path")
    for f in fields(BarParams):
        ap.add_argument(f"--{f.name}", type=type(f.default), default=f.default)
    return ap


def main(argv: list[str] | None = None) -> None:
    args = _cli().parse_args(argv)
    p = BarParams(**{f.name: getattr(args, f.name) for f in fields(BarParams)})
    out: Path = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix == ".svg":
        from build123d import ExportSVG

        svg = ExportSVG(scale=2, margin=10, line_weight=0.4)
        svg.add_shape(profile(p))
        svg.write(str(out))
    elif out.suffix == ".step":
        from build123d import export_step

        export_step(bar(p), str(out))
    else:
        export_stl(bar(p), str(out), tolerance=0.01, angular_tolerance=0.1)
    print(f"-> {out}")
    print(p.report())


if __name__ == "__main__":
    main()
