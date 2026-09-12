"""Flat bar with a row of slots for M6 bolts down its middle, to sit on top
of a 40 mm aluminium extrusion rail and be bolted into its T-slot anywhere
along each slot.

The bar is ``width`` x ``thickness`` in section and ``length`` long. Each
end is capped by a circular arc of radius ``end_r`` centred on the bar's
centreline ``end_r`` in from the tip, so a bar pivoting on a bolt at that
point sweeps nothing beyond a circle of that radius and can turn on the
rail without the end protruding. The corners where the arcs meet the long
sides are rounded to ``corner_r``. Each slot is ``slot_w`` wide
(M6 clearance plus a print allowance) and ``slot_l`` long overall along
the bar, with round ends; the slots repeat on a ``pitch`` along the bar's
centreline, leaving ``pitch - slot_l`` of material between them, and the
row is centred along the length so the end slots sit at least
``end_margin`` from the ends. ``slots`` fixes the count instead when it is
positive. ``slot_l`` equal to ``slot_w`` gives plain round holes.

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
    thickness: float = 4.0
    # Slot width, across the bar. M6 clearance is 6.4 (ISO 273 fine); 0.2
    # more lets a printed slot, which comes out narrow, pass the bolt.
    slot_w: float = 6.6
    # Slot length along the bar, overall (round end to round end). Equal to
    # slot_w gives a round hole.
    slot_l: float = 30.0
    # Centre-to-centre distance between neighbouring slots. pitch - slot_l
    # is the material left between them.
    pitch: float = 40.0
    # Least distance from either end of the bar to the nearest slot's
    # centre. The row is centred along the bar, so the actual margin is this
    # or more.
    end_margin: float = 20.0
    # Number of slots. 0 = as many as fit at the pitch inside the margins.
    slots: int = 0
    # Radius of the arc capping each end, centred on the centreline this far
    # in from the tip: a bolt there is the pivot the bar can turn on without
    # the end reaching past this radius. 0 = square ends. Must be at least
    # half the width so the arc spans the bar.
    end_r: float = 40.0
    # Radius on the four plan corners where the end arcs meet the sides.
    corner_r: float = 3.0
    # ID engraved into the top face, reading along the bar, in the strip
    # of material beside the slot row. Empty disables.
    label: str = ""
    label_depth: float = 0.4
    label_size: float = 3.0

    # ----- derived -----
    @property
    def n_slots(self) -> int:
        if self.slots > 0:
            return self.slots
        span = self.length - 2 * self.end_margin
        if span < 0:
            return 0
        return int(math.floor(span / self.pitch + 1e-9)) + 1

    @property
    def slot_xs(self) -> list[float]:
        """Slot centres along X, centred on the bar."""
        n = self.n_slots
        return [(i - (n - 1) / 2) * self.pitch for i in range(n)]

    @property
    def end_sagitta(self) -> float:
        """How far the tip of the end arc stands proud of the corners."""
        if self.end_r <= 0:
            return 0.0
        return self.end_r - math.sqrt(self.end_r**2 - (self.width / 2) ** 2)

    @property
    def ligament(self) -> float:
        """Solid material between two neighbouring slots."""
        return self.pitch - self.slot_l

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
        if self.end_r < 0 or (0 < self.end_r < self.width / 2):
            raise ValueError("end_r must be 0 or at least width / 2, so the arc spans the bar")
        if self.end_r > 0 and self.length < 2 * self.end_r:
            raise ValueError("length must be at least 2 * end_r, or the end arcs cross")
        if self.n_slots < 1:
            raise ValueError("no slot fits: length must be at least 2 * end_margin")
        xs = self.slot_xs
        if xs[-1] + self.slot_l / 2 >= self.length / 2:
            raise ValueError("the end slots break out of the bar's ends")
        if self.corner_r < 0 or 2 * self.corner_r > min(self.length - 2 * self.end_sagitta, self.width):
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
            where = "in a slot" if self.pivot_in_slot else "between slots, so no bolt can sit there"
            text += f"; ends capped R{self.end_r}, pivot {self.end_r} from each tip is {where}"
        return text

    @property
    def pivot_in_slot(self) -> bool:
        """Whether a bolt can be centred end_r in from the tip, i.e. whether
        some slot's straight run covers that point."""
        x = self.length / 2 - self.end_r
        reach = (self.slot_l - self.slot_w) / 2
        return any(abs(x - c) <= reach + 1e-9 for c in self.slot_xs)


def outline(p: BarParams) -> Sketch:
    """The bar's plan without the slots: a rectangle, its ends trimmed to
    the arcs, its corners rounded."""
    if p.end_r <= 0:
        return Sketch(list(RectangleRounded(p.length, p.width, p.corner_r).faces()))
    xc, yc, xt = p.length / 2 - p.end_sagitta, p.width / 2, p.length / 2  # corner and tip
    face = make_face(
        [
            Line((-xc, -yc), (xc, -yc)),
            ThreePointArc((xc, -yc), (xt, 0), (xc, yc)),
            Line((xc, yc), (-xc, yc)),
            ThreePointArc((-xc, yc), (-xt, 0), (-xc, -yc)),
        ]
    )
    face = face.face()
    if p.corner_r > 0:
        face = face.fillet_2d(p.corner_r, face.vertices())
    return Sketch([face])


def _slot(p: BarParams):
    if p.slot_l <= p.slot_w:  # a round hole; SlotOverall refuses a zero-length slot
        return Circle(p.slot_w / 2)
    return SlotOverall(p.slot_l, p.slot_w)


def slots(p: BarParams) -> Sketch:
    return Sketch([_slot(p).moved(Location((x, 0))).face() for x in p.slot_xs])


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


def bar(p: BarParams) -> Part:
    body = extrude(profile(p), amount=p.thickness, dir=(0, 0, 1))
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
