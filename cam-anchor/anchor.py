"""A cam anchor that sets itself in the gap between two ceiling beams and
holds a hanging load by pressing on the beams' vertical sides.

Four flat cams turn on one M8 bolt, the axle, which runs along the beams.
Two cams face each wall. Along the axle they stack L R R L, so the grip is
symmetric and the unit cannot twist. Two side plates carry the axle and,
``drop`` below it, a second M8 bolt with a printed sleeve: the eye the load
hangs from.

Each cam's working edge is a logarithmic spiral, r = r0 * exp(k * psi) with
k = tan(alpha). The angle between a spiral's radius and its normal is alpha
everywhere, so the cam meets the wall at the same angle at any reach: at
the point alpha below the axle's horizontal, where the cam's normal is
horizontal. There the wall's reaction must pass through the axle, which
needs friction F = N tan(alpha). So the cam holds wherever the wall's
friction coefficient ``mu`` exceeds tan(alpha), and a load pulling the axle
down turns each cam further out: the anchor tightens itself.

Coordinates of the working drawing: x across the gap, with the walls at
x = +-gap / 2, z up, and the axle on the y axis at the origin. The +x cam's
spiral grows clockwise: its point at spiral parameter psi sits at angle
rho - psi, where rho is the cam's turn from fully retracted,
counter-clockwise positive. Its contact is at psi = rho + alpha, with reach
r(rho + alpha) * cos(alpha) from the axle, ``reach_min`` at rho = 0 and
``reach_max`` at ``rho_max``. The -x cam is its mirror: the same part,
turned over.

Each cam is a lever. A cord knotted through its trigger hole runs down the
cam's face, in the washer gap beside it, to the finger-pull; pulling it
turns the cam clockwise, retracting it. A rubber
band from its spring hole, on the inboard arm, down to the eye sleeve turns
it counter-clockwise, expanding it, until the spring hole comes directly
over the sleeve at ``rho_rest``, a little past full reach. The band has no
leverage there, so the cam rests without a stop.

Drawn as printed: every part is a flat extrusion, its profile on the bed in
XY with the drawing's z along Y, and its thickness up Z. So every hole
runs along print Z and every load stays in the printed plane.

Usage:
    python anchor.py --part cam -o cam.stl [--alpha 14] [--reach_min 34] ...
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass, fields
from pathlib import Path

from build123d import (
    Circle,
    FontStyle,
    Line,
    Location,
    Part,
    Plane,
    Polygon,
    Pos,
    Rectangle,
    Rot,
    Sketch,
    SlotCenterToCenter,
    Text,
    export_stl,
    extrude,
)

Point = tuple[float, float]


@dataclass(frozen=True)
class AnchorParams:
    """Every dimension of the anchor, in millimetres; angles in degrees."""

    # The gap between the beams, and the friction coefficient of PETG on
    # their rough-sawn sides.
    gap: float = 80.0
    mu: float = 0.4
    # The cam angle: the angle between the cam's radius and its normal.
    alpha: float = 14.0
    # Reach per side from the axle: retracted (rho = 0) and fully expanded.
    reach_min: float = 34.0
    reach_max: float = 45.0
    # How far past full reach the rubber band parks the cam.
    rest_over: float = 10.0
    # The spiral runs this far past both ends of the contact range.
    spiral_lead: float = 10.0
    spiral_tail: float = 4.0
    # Serrations cut into the spiral: tips on it, valleys tooth_d inside.
    tooth_d: float = 0.8
    tooth_pitch: float = 2.5
    cam_t: float = 10.0
    hub_r: float = 10.0
    # The bolts (metric size), their clearance holes, and the cord and band holes.
    bolt: int = 8
    hole: float = 8.4
    cord_hole: float = 3.0
    # The trigger hole's distance in from the spiral, and the spring hole's
    # radius on the inboard arm.
    trigger_in: float = 8.0
    spring_r: float = 14.0
    arm_w: float = 8.0
    # Side plates: width across the gap, thickness, axle-to-eye distance.
    plate_w: float = 24.0
    plate_t: float = 6.0
    drop: float = 80.0
    # Between the cams, and between each outer cam and its plate: two M8
    # washers, room for the trigger cords that run down the cams' faces.
    washer_t: float = 3.2
    sleeve_od: float = 14.0
    # The finger-pull's cord holes sit pull_x either side of centre, and it
    # hangs about pull_below under the eye.
    pull_x: float = 12.0
    pull_below: float = 20.0
    pull_t: float = 5.0

    @property
    def k(self) -> float:
        return math.tan(math.radians(self.alpha))

    @property
    def r0(self) -> float:
        a = math.radians(self.alpha)
        return self.reach_min / (math.cos(a) * math.exp(self.k * a))

    @property
    def rho_max(self) -> float:
        """The cam's turn from retracted to full reach, radians."""
        return math.log(self.reach_max / self.reach_min) / self.k

    @property
    def rho_rest(self) -> float:
        """Where the rubber band parks the cam, radians."""
        return self.rho_max + math.radians(self.rest_over)

    @property
    def rho_gap(self) -> float:
        """The cam's turn when it touches a wall gap / 2 away, radians."""
        return math.log(self.gap / 2 / self.reach_min) / self.k

    @property
    def psi_lo(self) -> float:
        return math.radians(self.alpha - self.spiral_lead)

    @property
    def psi_hi(self) -> float:
        # (only to full reach: past it the cam is in free air, where the
        # band parks it, and a longer lobe would hang past straight down,
        # where the trigger cord loses its leverage)
        return self.rho_max + math.radians(self.alpha + self.spiral_tail)

    @property
    def r_max(self) -> float:
        return self.r(self.psi_hi)

    @property
    def stack(self) -> float:
        """The cams and washers between the plates: L R R L, a washer each side of each."""
        return 4 * self.cam_t + 5 * self.washer_t

    def r(self, psi: float) -> float:
        return self.r0 * math.exp(self.k * psi)

    def reach(self, rho: float) -> float:
        """How far the +x cam reaches in x from the axle, turned rho from retracted."""
        return self.r(rho + math.radians(self.alpha)) * math.cos(math.radians(self.alpha))

    @property
    def trigger_r(self) -> float:
        """The trigger hole's radius: trigger_in inside the spiral's valleys."""
        return self.r(self.rho_rest / 2) - self.tooth_d - self.trigger_in

    def trigger_hole(self, rho: float = 0.0) -> Point:
        """The +x cam's trigger hole. It sits rho_rest / 2 below the axle's
        horizontal when retracted and as far above it at rest, so it stays
        outboard of the axle, and a cord pulled down from it keeps its
        leverage, over the whole working range."""
        return _polar(self.trigger_r, rho - self.rho_rest / 2)

    def spring_hole(self, rho: float = 0.0) -> Point:
        """The +x cam's spring hole, placed to come directly over the sleeve at rho_rest."""
        return _polar(self.spring_r, rho - math.pi / 2 - self.rho_rest)

    @property
    def sleeve(self) -> Point:
        return (0.0, -self.drop)

    @property
    def pull_hole(self) -> Point:
        """Where the +x cams' trigger cords end, on the finger-pull."""
        return (self.pull_x, -self.drop - self.pull_below)

    def validate(self) -> None:
        if not 2 * self.reach_min < self.gap < 2 * self.reach_max:
            raise ValueError(
                f"the cams span {2 * self.reach_min:g}-{2 * self.reach_max:g} mm, which must include the {self.gap:g} mm gap"
            )
        if self.k >= self.mu:
            raise ValueError(f"tan(alpha) = {self.k:.3f} must be under mu = {self.mu:g}, or the cams slip")
        if self.plate_w / 2 >= self.reach_min:
            raise ValueError(f"the {self.plate_w:g} mm plates must be narrower than the retracted span, {2 * self.reach_min:g} mm")
        if self.r_max + self.sleeve_od / 2 + 1 > self.drop:
            raise ValueError(f"the cams' lobes (r {self.r_max:.1f} mm) hit the eye sleeve {self.drop:g} mm below the axle")

    def report(self) -> str:
        d = math.degrees
        return "\n".join([
            f"cam angle {self.alpha:g} deg: holds while mu > tan(alpha) = {self.k:.3f} (mu = {self.mu:g})",
            f"span {2 * self.reach_min:g}-{2 * self.reach_max:g} mm over {d(self.rho_max):.1f} deg of cam turn; "
            f"in the {self.gap:g} mm gap the cams sit {d(self.rho_gap):.1f} deg out; rest at {d(self.rho_rest):.1f} deg",
            f"spiral r {self.r(self.psi_lo):.1f}-{self.r_max:.1f} mm",
            f"each wall takes {1 / (2 * self.k):.2f} x the load, shared by two cams",
            f"stack between plates {self.stack:g} mm; axle bolt >= {self.stack + 2 * self.plate_t + 8:g} mm",
        ])


def _polar(r: float, ang: float) -> Point:
    return (r * math.cos(ang), r * math.sin(ang))


def torque(p: Point, h: Point) -> float:
    """The moment about the axle of a unit-tension pull from p toward h, counter-clockwise positive."""
    fx, fz = h[0] - p[0], h[1] - p[1]
    n = math.hypot(fx, fz)
    return (p[0] * fz - p[1] * fx) / n


def tooth_tips(p: AnchorParams) -> list[float]:
    """Spiral parameters of the tooth tips, evenly spaced along the spiral's
    length from psi_lo to psi_hi. (Arc length from the pole is r sqrt(1 + k^2) / k.)"""
    c = math.sqrt(1 + p.k**2) / p.k
    s0, s1 = p.r(p.psi_lo) * c, p.r(p.psi_hi) * c
    n = max(1, round((s1 - s0) / p.tooth_pitch))
    return [math.log((s0 + (s1 - s0) * i / n) / (p.r0 * c)) / p.k for i in range(n + 1)]


def cam_outline(p: AnchorParams) -> list[Point]:
    """The +x cam's serrated spiral sector at rho = 0, closed through the axle."""
    tips = tooth_tips(p)
    pts: list[Point] = [(0.0, 0.0)]
    for i, psi in enumerate(tips):
        pts.append(_polar(p.r(psi), -psi))
        if i + 1 < len(tips):
            mid = (psi + tips[i + 1]) / 2
            pts.append(_polar(p.r(mid) - p.tooth_d, -mid))
    return pts


def cam_sketch(p: AnchorParams, rho: float = 0.0, mirror: bool = False) -> Sketch:
    """The cam's profile in the drawing's xz, as the +x cam turned rho (or its mirror)."""
    p.validate()
    sx, sz = p.spring_hole()
    arm_len = p.spring_r
    # (wound counter-clockwise, or build123d won't fuse it with the hub)
    body = Sketch() + Polygon(*cam_outline(p)[::-1], align=None)
    body += Circle(p.hub_r)
    arm_ang = math.degrees(math.atan2(sz, sx))
    body += Rot(0, 0, arm_ang) * SlotCenterToCenter(arm_len, p.arm_w).moved(Location((arm_len / 2, 0)))
    body -= Circle(p.hole / 2)
    body -= Pos(*p.trigger_hole()) * Circle(p.cord_hole / 2)
    body -= Pos(sx, sz) * Circle(p.cord_hole / 2)
    body = Rot(0, 0, math.degrees(rho)) * body
    return body.mirror(Plane.YZ) if mirror else body


def plate_sketch(p: AnchorParams) -> Sketch:
    p.validate()
    s = SlotCenterToCenter(p.drop, p.plate_w, rotation=90).moved(Location((0, -p.drop / 2)))
    s -= Circle(p.hole / 2)
    s -= Pos(*p.sleeve) * Circle(p.hole / 2)
    return Sketch() + s


def cam(p: AnchorParams) -> Part:
    """One cam, as printed. Print four; turn two over for the -x wall."""
    return extrude(cam_sketch(p), amount=p.cam_t)


def plate(p: AnchorParams) -> Part:
    """One side plate, as printed. Print two."""
    return extrude(plate_sketch(p), amount=p.plate_t)


def sleeve(p: AnchorParams) -> Part:
    """The eye: a tube over the lower bolt, printed upright."""
    p.validate()
    return extrude(Circle(p.sleeve_od / 2) - Circle(p.hole / 2), amount=p.stack)


def finger_pull(p: AnchorParams) -> Part:
    """A bar with a cord hole each side (tie both of that side's cams' cords
    through it) over a finger ring."""
    p.validate()
    bar_h = 8.0
    bar = Rectangle(2 * p.pull_x + 10, bar_h)
    ring_r = 14.0
    ring = Pos(0, -bar_h / 2 - ring_r + 3) * (Circle(ring_r) - Circle(ring_r - 4.5))
    s = Sketch() + [bar, ring]
    s -= [Pos(x, 0) * Circle(p.cord_hole / 2) for x in (-p.pull_x, p.pull_x)]
    return extrude(s, amount=p.pull_t)


COUPON_CLEARANCES = (0.2, 0.4, 0.6)


def coupon(p: AnchorParams) -> Part:
    """A strip with a trial clearance hole for the bolt at each size, the size engraved under each."""
    COUPON_HOLES = [p.bolt + c for c in COUPON_CLEARANCES]
    t, pitch = 4.0, 16.0
    s = Rectangle(pitch * len(COUPON_HOLES) + 4, 20)
    xs = [(i - (len(COUPON_HOLES) - 1) / 2) * pitch for i in range(len(COUPON_HOLES))]
    s -= [Pos(x, 3) * Circle(d / 2) for x, d in zip(xs, COUPON_HOLES)]
    body = extrude(s, amount=t)
    for x, d in zip(xs, COUPON_HOLES):
        label = Plane.XY.offset(t) * Pos(x, -6) * Text(f"{d:g}", font_size=4, font_style=FontStyle.BOLD)
        body -= extrude(label, amount=-0.6)
    return body


def assembly_sketch(p: AnchorParams, rho: float) -> tuple[Sketch, list]:
    """Looking along the axle: the parts, then the walls, trigger cords and
    rubber bands to draw dashed."""
    solid = plate_sketch(p) + cam_sketch(p, rho) + cam_sketch(p, rho, mirror=True)
    solid += Pos(*p.sleeve) * (Circle(p.sleeve_od / 2) - Circle(p.hole / 2))
    top, bottom = p.r_max * 0.6, -p.drop - p.pull_below - 5
    walls = [Pos(x * (p.gap / 2 + 2), (top + bottom) / 2) * Rectangle(4, top - bottom) for x in (-1, 1)]
    lines = []
    for m in (1, -1):
        (tx, tz), (fx, fz), (sx, sz) = p.trigger_hole(rho), p.pull_hole, p.spring_hole(rho)
        lines.append(Line((m * tx, tz), (m * fx, fz)))
        lines.append(Line((m * sx, sz), (0, -p.drop + p.sleeve_od / 2)))
    return solid, [Sketch() + walls, *lines]


def _svg(p: AnchorParams, part: str, rho: float, out: Path) -> None:
    from build123d import ExportSVG, LineType

    svg = ExportSVG(scale=1.5, margin=4, line_weight=0.3)
    svg.add_layer("dash", line_color=(150, 150, 150), line_type=LineType.ISO_DASH, line_weight=0.2)
    if part == "assembly":
        solid, dashed = assembly_sketch(p, rho)
        svg.add_shape(dashed, layer="dash")
        svg.add_shape(solid)
    else:
        svg.add_shape({"cam": cam_sketch(p), "plate": plate_sketch(p)}[part])
    svg.write(str(out))


PARTS = {"cam": cam, "plate": plate, "sleeve": sleeve, "pull": finger_pull, "coupon": coupon}


def _cli() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("-o", "--output", type=Path, required=True, help=".stl, .step or .svg path")
    ap.add_argument("--part", choices=[*PARTS, "assembly"], default="cam")
    ap.add_argument("--rho", type=float, default=None, help="assembly .svg only: cam turn, degrees (default: set in the gap)")
    for f in fields(AnchorParams):
        ap.add_argument(f"--{f.name}", type=type(f.default), default=f.default)
    return ap


def main(argv: list[str] | None = None) -> None:
    args = _cli().parse_args(argv)
    p = AnchorParams(**{f.name: getattr(args, f.name) for f in fields(AnchorParams)})
    p.validate()
    out: Path = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix == ".svg":
        rho = p.rho_gap if args.rho is None else math.radians(args.rho)
        _svg(p, args.part, rho, out)
    elif out.suffix == ".step":
        from build123d import export_step

        export_step(PARTS[args.part](p), str(out))
    else:
        export_stl(PARTS[args.part](p), str(out), tolerance=0.01, angular_tolerance=0.1)
    print(f"-> {out}")
    print(p.report())


if __name__ == "__main__":
    main()
