"""Cross-sections of the IKEA FRAMFUSIG curtain rail.

FRAMFUSIG is a telescopic single-track ceiling rail: two nested steel tubes
with a rounded-rectangle (near-stadium) section and a slot along the
underside for the curtain gliders. The dimensions here were measured with
calipers on 2026-09-05; IKEA publishes none.

The profile is drawn in the XY plane with the rail's axis along Z, the slot
facing -Y (down) and the section centred on X = 0, Y = 0.

Usage:
    python framfusig.py -o rail_profiles.svg
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from build123d import Align, ExportSVG, Location, Rectangle, RectangleRounded, Sketch


@dataclass(frozen=True)
class RailProfile:
    """One tube of the rail, in millimetres."""

    name: str
    width: float
    height: float
    corner_r: float
    # Width of the glider slot in the underside.
    slot_w: float
    # Depth of the slot cut, i.e. the tube's wall thickness. Estimated.
    wall: float = 0.8

    @property
    def radius(self) -> float:
        """Corner radius, capped at half the height so the section stays valid."""
        return min(self.corner_r, self.height / 2 - 1e-6, self.width / 2 - 1e-6)

    def envelope(self) -> Sketch:
        """The outside of the tube, ignoring the slot: what a clamp grips."""
        return RectangleRounded(self.width, self.height, self.radius)

    def section(self) -> Sketch:
        """The outside with the slot cut into the underside."""
        slot = Rectangle(self.slot_w, self.wall + 1e-3, align=(Align.CENTER, Align.MIN)).moved(
            Location((0, -self.height / 2 - 1e-3))
        )
        return Sketch(list((self.envelope() - slot).faces()))


INNER = RailProfile("inner", width=17.4, height=10.0, corner_r=5.0, slot_w=6.75)
# The outer tube's radius was estimated at ~5.5 mm by eye; a first clamp cut
# for that let the rail slip through, so it is modelled as a full stadium
# (radius = half the height), which is the narrowest the rail can be at the
# lips and therefore the safe assumption for grip.
OUTER = RailProfile("outer", width=19.5, height=12.2, corner_r=6.1, slot_w=6.75)
PROFILES = {p.name: p for p in (INNER, OUTER)}


def export_svg(path: Path) -> None:
    """Both sections side by side, at 4x, for the README."""
    svg = ExportSVG(scale=4, margin=10, line_weight=0.4)
    svg.add_shape(INNER.section().moved(Location((-15, 0))))
    svg.add_shape(OUTER.section().moved(Location((15, 0))))
    svg.write(str(path))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("-o", "--output", type=Path, required=True, help=".svg drawing path")
    args = ap.parse_args(argv)
    export_svg(args.output)
    for p in PROFILES.values():
        print(f"{p.name}: {p.width} x {p.height} mm, r {p.radius:.2f}, slot {p.slot_w}, area {p.section().area:.1f} mm^2")
    print(f"-> {args.output}")


if __name__ == "__main__":
    main()
