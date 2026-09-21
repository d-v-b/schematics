"""A flexible clip that holds onto a beam by being stretched across it,
lying flush on the beam's face.

The clip is a flat plate ``plate`` thick. In the plane of the beam's face it
is a strip ``t`` wide following a centreline of straight runs and tangent
circular arcs, with a lip block at each end that reaches ``lip`` down the
beam's side. The runs cross the beam; between them the strip swings out
along the beam into ``loops`` loops, each three arcs of radius ``loop_r``: a
concave foot turning through ``turn`` degrees, a convex crown turning back
through twice that, and a concave foot back. Past 90 degrees the feet lean
in and each loop pinches to a neck under a round crown, which packs a lot of
arc length, and so a lot of compliance, into a short span. The whole
serpentine lies in one plane on the beam's face, so the clip is only
``plate`` proud of it.

Relaxed, the lips' inside faces are ``span`` apart, less than the beam's
``beam_w``. Pushing the clip onto the beam, the beam's edges ride the
lead-in ``chamfer`` on each lip and spread the lips by the
``interference``; the loops take that stretch as bending in the plane of
the face and pull the lips in against the beam's sides. Each lip's inside
face is drafted ``lip_relief`` back at its root, so it touches the beam only
at its tip.

The compliance model treats the strip as a thin curved beam loaded in
tension along the runs' centreline. The bending moment at any point is the
pull times its distance y from that line, so the stretch is
``P * bend_integral / (E I)``, where ``bend_integral`` is the integral of
y^2 along the centreline and I = plate * t^3 / 12. The runs lie on the line
and contribute nothing; each loop has a closed form. That gives the
``stiffness``, the ``grip`` at the interference, and the ``crown_stress``,
the peak bending stress at the crowns, where y is greatest. The stress does
not depend on ``plate``, so a thicker plate buys grip without adding creep.
``validate()`` refuses any geometry whose crown stress exceeds the
material's ``creep_limit``, because the loops are held stretched for as
long as the clip is on the beam.

Drawn as printed: the serpentine flat on the bed in XY, centred on x = 0,
its runs' centreline on y = 0 and its loops swinging towards +y, i.e. along
the beam; the plate rises ``plate`` up Z, and the lips a further ``lip``
above it. The beam's face rests on the plate's top at z = plate, with the
beam's sides at x = +-beam_w / 2 once the clip is on. Every wall is
vertical but the lips' drafted inside faces, which lean in by lip_draft
(about 10 degrees), and the chamfers face up, so nothing overhangs more than
that.

Usage:
    python clip.py -o clip.stl [--span 38] [--loops 3] [--loop_r 3.25] [--turn 125]
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass, fields
from pathlib import Path

from build123d import (
    Face,
    Kind,
    Line,
    Part,
    Plane,
    Polygon,
    Side,
    Sketch,
    ThreePointArc,
    Wire,
    export_stl,
    extrude,
    make_face,
)


@dataclass(frozen=True)
class ClipParams:
    """Every dimension of the clip, in millimetres; stress in MPa."""

    # The beam, across its top face.
    beam_w: float = 40.0
    # The relaxed gap between the lips' inside faces. beam_w - span is the
    # stretch the loops take when the clip is on.
    span: float = 38.0
    # The strip's width in the plane of the beam's face: its thickness in
    # the direction it bends.
    t: float = 1.6
    loops: int = 3
    # Centreline radius of every arc in a loop.
    loop_r: float = 3.25
    # How far each foot turns away from the run, degrees. Past 90 the loop
    # pinches to a neck under its crown.
    turn: float = 125.0
    # How far each lip reaches down the beam's side, from its face.
    lip: float = 4.0
    # The lips are wider than the strip so the loops, not the lips, flex.
    lip_t: float = 2.4
    # Each lip's inside face is drafted: set back this far at its root, where
    # the beam's face meets the plate, and leaning in to meet the beam only at
    # its tip, the foot of the lead-in chamfer. Contact is then one definite
    # line instead of a face that print tolerance makes touch anywhere.
    lip_relief: float = 0.5
    # 45 degree lead-in on each lip's inside tip: the beam's edge rides
    # it to spread the lips as the clip is pushed on.
    chamfer: float = 1.2
    # The plate's thickness off the beam's face: the print's height up to
    # the contact face. Grip scales with it; stress does not.
    plate: float = 3.0
    # Least clear gap between any two parts of the strip that must not fuse
    # when printed: about three nozzle widths.
    min_gap: float = 1.2
    # PETG, as in curtain-hanger/compliance.py.
    modulus: float = 2000.0
    creep_limit: float = 15.0

    # ----- derived: geometry -----
    @property
    def _a(self) -> float:
        return math.radians(self.turn)

    @property
    def loop_w(self) -> float:
        """Span of one loop along the flats, foot to foot."""
        return 4 * self.loop_r * math.sin(self._a)

    @property
    def loop_h(self) -> float:
        """How far a crown's centreline swings out along the beam from the
        runs' centreline."""
        return 2 * self.loop_r * (1 - math.cos(self._a))

    @property
    def flat(self) -> float:
        """Length of each flat run: the span left over, shared among the
        runs at each end and between loops."""
        return (self.span - self.loops * self.loop_w) / (self.loops + 1)

    @property
    def neck(self) -> float:
        """Clear gap where a loop's two feet pass closest, facing each other
        level with their centres. The gap between neighbouring crowns is
        this plus a flat, so it is never the tighter of the two."""
        return self.loop_w - 2 * self.loop_r - self.t

    @property
    def lip_draft(self) -> float:
        """Angle of the lips' drafted inside faces from square, degrees."""
        return math.degrees(math.atan2(self.lip_relief, self.lip - self.chamfer))

    @property
    def interference(self) -> float:
        """How far the clip is stretched once it is on the beam."""
        return self.beam_w - self.span

    # ----- derived: compliance -----
    @property
    def bend_integral(self) -> float:
        """The integral of y^2 along the centreline, y measured from the
        runs' centreline, mm^3: closed form, per loop, of its two feet
        and its crown."""
        r, a = self.loop_r, self._a
        foot = r**3 * (1.5 * a - 2 * math.sin(a) + math.sin(2 * a) / 4)
        c = 1 - 2 * math.cos(a)  # the crown's height above the line, in r, less cos(phi)
        crown = r**3 * (2 * a * c**2 + 4 * c * math.sin(a) + a + math.sin(2 * a) / 2)
        return self.loops * (2 * foot + crown)

    @property
    def inertia(self) -> float:
        """Of the strip's section, bending in the plane of the beam's face."""
        return self.plate * self.t**3 / 12

    @property
    def stiffness(self) -> float:
        """Pull per mm of stretch, N/mm."""
        return self.modulus * self.inertia / self.bend_integral

    @property
    def grip(self) -> float:
        """Pull on each lip with the clip on the beam, N."""
        return self.stiffness * self.interference

    @property
    def crown_stress(self) -> float:
        """Peak bending stress, at the tops of the crowns, MPa."""
        return self.grip * self.loop_h * (self.t / 2) / self.inertia

    def validate(self) -> None:
        if min(self.beam_w, self.span, self.t, self.loop_r, self.lip, self.lip_t, self.plate, self.modulus) <= 0:
            raise ValueError("beam_w, span, t, loop_r, lip, lip_t, plate and modulus must be positive")
        if self.loops < 1:
            raise ValueError("loops must be at least 1")
        if self.span >= self.beam_w:
            raise ValueError("span must be less than beam_w, or the clip has nothing to stretch it")
        if not 0 < self.turn < 180:
            raise ValueError("turn must be between 0 and 180 degrees, exclusive")
        if self.lip_t < self.t:
            raise ValueError("lip_t must be at least t, or the lips flex instead of the loops")
        if self.lip_relief < 0:
            raise ValueError("lip_relief must not be negative")
        if self.lip_t - self.lip_relief < self.t:
            raise ValueError("lip_relief must leave the lip at least t thick at its root")
        if self.flat < 0:
            raise ValueError(
                f"the loops do not fit: {self.loops} of {self.loop_w:.1f} need more than the {self.span:g} span"
            )
        if self.neck < self.min_gap:
            raise ValueError(
                f"the neck is {self.neck:.2f} clear, under min_gap {self.min_gap:g}: a print would fuse it shut; "
                "reduce turn or t, or grow loop_r"
            )
        if self.crown_stress > self.creep_limit:
            raise ValueError(
                f"the crowns would sit at {self.crown_stress:.1f} MPa, over the {self.creep_limit:g} MPa creep "
                "ceiling, and relax on the beam: add a loop, grow loop_r or turn, or thin the strip"
            )
        if not 0 < self.chamfer < min(self.lip_t, self.lip):
            raise ValueError("chamfer must be less than lip_t and lip, and positive")
        if self.chamfer < self.interference / 2:
            raise ValueError(
                "the lead-in chamfer must reach at least half the interference, or the beam's edge meets "
                "the flat tip of the lip instead of riding up it"
            )

    def report(self) -> str:
        return (
            f"{self.span:g} relaxed on a {self.beam_w:g} beam: {self.loops} loops R{self.loop_r:g} "
            f"turning {self.turn:g} deg, {self.t:g} strip, {self.loop_h + self.t:.1f} along the beam, "
            f"{self.plate:g} plate + {self.lip:g} lips drafted {self.lip_draft:.0f} deg to meet the beam at their tips, neck {self.neck:.2f} clear, runs {self.flat:.2f}; "
            f"grip {self.grip:.1f} N, crown stress {self.crown_stress:.1f} MPa "
            f"of {self.creep_limit:g} creep ceiling"
        )


def _pt(c: tuple[float, float], r: float, ang: float) -> tuple[float, float]:
    return (c[0] + r * math.cos(ang), c[1] + r * math.sin(ang))


def centreline(p: ClipParams) -> Wire:
    """The strip's centreline, lip to lip: run, loop, run, ..., run."""
    r, a, y0 = p.loop_r, p._a, 0.0
    down = -math.pi / 2
    edges = []
    x = -p.span / 2
    for i in range(p.loops):
        # the first run starts at the left lip's set-back root
        start = x - p.lip_relief if i == 0 else x
        edges.append(Line((start, y0), (x + p.flat, y0)))
        x += p.flat
        foot1 = (x, y0 + r)
        up = _pt(foot1, r, down + a)
        crown = _pt(foot1, 2 * r, down + a)
        top = (crown[0], crown[1] + r)
        over = (2 * crown[0] - up[0], up[1])
        foot2 = (x + p.loop_w, y0 + r)
        edges.append(ThreePointArc((x, y0), _pt(foot1, r, down + a / 2), up))
        edges.append(ThreePointArc(up, top, over))
        edges.append(ThreePointArc(over, _pt(foot2, r, down - a / 2), (x + p.loop_w, y0)))
        x += p.loop_w
    edges.append(Line((x, y0), (p.span / 2 + p.lip_relief, y0)))
    return Wire(edges)


def strip(p: ClipParams) -> Face:
    """The strip alone: the centreline thickened t / 2 either side, with
    round ends that the lips swallow."""
    return make_face(centreline(p).offset_2d(p.t / 2, kind=Kind.ARC, side=Side.BOTH, closed=True))


def lips(p: ClipParams) -> Part:
    """A block at each end, as wide along the beam as the serpentine, rising
    lip above the plate to reach down the beam's side. Its inside face is
    set back lip_relief at the root and leans in to the tip, where it meets
    the beam at the foot of the lead-in chamfer."""
    s, lt, c, top, r = p.span / 2, p.lip_t, p.chamfer, p.plate + p.lip, p.lip_relief
    y0, y1 = -p.t / 2, p.loop_h + p.t / 2
    # in the XZ plane: the right lip's section, drafted from its root at the
    # plate's top to its tip, then chamfered
    right = [(s + lt, 0), (s + lt, top), (s + c, top), (s, top - c), (s + r, p.plate), (s + r, 0)]
    # mirrored in x, and reversed so both wind the same way
    left = [(-x, z) for x, z in reversed(right)]
    blocks = []
    for pts in (left, right):
        section = Plane.XZ.offset(-y0) * Polygon(*pts, align=None)
        blocks.append(extrude(section, amount=-(y1 - y0)))
    return blocks[0] + blocks[1]


def profile(p: ClipParams) -> Sketch:
    """The serpentine in plan."""
    p.validate()
    return Sketch([strip(p)])


def clip(p: ClipParams) -> Part:
    return extrude(profile(p), amount=p.plate) + lips(p)


def _iso_svg(p: ClipParams, out: Path) -> None:
    """The part as printed, seen from above one corner, hidden edges dashed."""
    from build123d import Compound, ExportSVG, LineType

    visible, hidden = clip(p).project_to_viewport((60, -70, 80), viewport_up=(0, 0, 1))
    span = Compound(visible).bounding_box().size
    svg = ExportSVG(scale=160 / max(span.X, span.Y), margin=5, line_weight=0.35)
    svg.add_layer("hidden", line_color=(170, 170, 170), line_type=LineType.ISO_DASH, line_weight=0.15)
    svg.add_shape(visible)
    svg.add_shape(hidden, layer="hidden")
    svg.write(str(out))


def _cli() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("-o", "--output", type=Path, required=True, help=".stl, .step or .svg path")
    ap.add_argument("--iso", action="store_true", help="draw an .svg as an isometric view of the part, not its plan")
    for f in fields(ClipParams):
        ap.add_argument(f"--{f.name}", type=type(f.default), default=f.default)
    return ap


def main(argv: list[str] | None = None) -> None:
    args = _cli().parse_args(argv)
    p = ClipParams(**{f.name: getattr(args, f.name) for f in fields(ClipParams)})
    out: Path = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix == ".svg" and args.iso:
        _iso_svg(p, out)
    elif out.suffix == ".svg":
        from build123d import ExportSVG, LineType, Location, Rectangle

        # in plan, relaxed, over the beam it will be stretched onto; the
        # lips' footprints outlined at each end
        s_, lt, y0, y1 = p.span / 2, p.lip_t, -p.t / 2, p.loop_h + p.t / 2
        beam = Rectangle(p.beam_w, y1 - y0 + 12).moved(Location((0, (y0 + y1) / 2)))
        feet = [Rectangle(lt, y1 - y0).moved(Location((x, (y0 + y1) / 2))) for x in (-s_ - lt / 2, s_ + lt / 2)]
        svg = ExportSVG(scale=6, margin=6, line_weight=0.35)
        svg.add_layer("beam", line_color=(150, 150, 150), line_type=LineType.ISO_DASH, line_weight=0.2)
        svg.add_shape(beam, layer="beam")
        svg.add_shape(Sketch([strip(p)]) + Sketch([f.face() for f in feet]))
        svg.write(str(out))
    elif out.suffix == ".step":
        from build123d import export_step

        export_step(clip(p), str(out))
    else:
        export_stl(clip(p), str(out), tolerance=0.01, angular_tolerance=0.1)
    print(f"-> {out}")
    print(p.report())


if __name__ == "__main__":
    main()
