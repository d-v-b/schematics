"""Strength and grip of the cam anchor under a hanging load.

A load W hangs from the eye. Each wall carries half of it, as friction F on
the cams that bear on it. Each cam is a two-force member: the wall's
reaction and the axle's push must be equal, opposite and collinear, so the
reaction runs through the axle at the cam angle alpha:

    F = W / (2 n)      N = F / tan(alpha)      R = F / sin(alpha)

Here n is the number of cams bearing on each wall. Two are fitted, but the
beams are not flat along their length, so the default assumes only one per
wall bears.

Failure modes, each as a stress, or a ratio, against its limit:

- **slip:** the walls must supply mu >= tan(alpha). This doesn't depend on
  the load.
- **cam bearing:** R on the axle hole, R / (d t). The pin always pushes
  into the solid lobe (the contact lies on the spiral sector), so bearing is
  the only hub check.
- **axle bending:** the M6 axle spans the plates as a simply supported beam.
  Each bearing cam pushes it with (-+N, F), inward from its wall and up. The
  horizontal pushes cancel in total but sit at different stations, so they
  bend the axle too. The check takes the worst combination of bearing cams
  and the M6 thread's minor diameter.
- **eye bolt bending:** W at mid-span of the M6 eye bolt, W L / 4.
- **plate lugs:** each plate hangs from the axle and carries the eye. At
  each hole the checks are net-section tension, (P / ((w - d) t)), shear-out
  of the rounded end, (P / (2 (w/2 - d/2) t)), and bearing, (P / (d t)).
  P is the larger plate reaction.
- **wall indent:** the cam crushes the wood across the grain until the
  contact is wide enough to carry N:
  - The contact width needed is w = N / (sigma_wood t).
  - First a single tooth sinks in, to a depth of tooth_d w / pitch.
  - Once the teeth are buried, the spiral's rounded envelope (radius of
    curvature r sqrt(1 + k^2)) flattens a further w^2 / (8 rho) or so.
  - Every mm of indent turns the cam further out, and it runs out of reach
    at reach_max. The reserve is reach_max - gap / 2.
  - This mode is rough, and it isn't linear in the load.

PETG limits are for sustained load (the anchor holds its load
indefinitely), so they are the creep ceiling, not the short-term strength.
The printed parts carry every load in their printed plane, along the
layers.

Usage:
    python mechanics.py [--load_kg 10] [--cams_per_wall 1] [--sf 3] [any anchor.py --param]
"""

from __future__ import annotations

import argparse
import itertools
import math
from dataclasses import dataclass, fields

from anchor import AnchorParams, torque

G = 9.81
PETG_SUSTAINED = 15.0  # MPa, the creep ceiling used across this repo
STEEL_8_8_YIELD = 640.0  # MPa
M6_MINOR = 4.773  # mm, the thread's minor diameter
WOOD_PERP_GRAIN = 2.5  # MPa, softwood compression across the grain


@dataclass(frozen=True)
class Loading:
    load_kg: float = 10.0
    # Cams bearing on each wall: 2 fitted, but assume 1 (beams aren't flat).
    cams_per_wall: int = 1
    # Rubber band tension on each cam, N.
    band_n: float = 5.0
    # The safety factor the rated load keeps on every mode.
    sf: float = 3.0

    @property
    def W(self) -> float:
        return self.load_kg * G

    def validate(self) -> None:
        if self.cams_per_wall not in (1, 2):
            raise ValueError(f"cams_per_wall must be 1 or 2 (two cams face each wall), not {self.cams_per_wall}")


@dataclass(frozen=True)
class Mode:
    name: str
    demand: float
    limit: float
    unit: str
    # slip's margin is a friction margin, the same at any load, so it is
    # guarded by AnchorParams.validate() and kept out of the rated load
    scales: bool = True

    @property
    def sf(self) -> float:
        return math.inf if self.demand == 0 else self.limit / self.demand


def cam_forces(p: AnchorParams, W: float, n: int) -> tuple[float, float, float]:
    """(F, N, R) on each bearing cam: friction up the wall, normal into it, and their resultant."""
    a = math.radians(p.alpha)
    F = W / (2 * n)
    return F, F / math.tan(a), F / math.sin(a)


def stations(p: AnchorParams) -> tuple[list[float], float]:
    """The cams' mid-planes along the axle (L R R L), and the span between the plates' mid-planes."""
    pitch = p.cam_t + p.washer_t
    y0 = p.plate_t / 2 + p.washer_t + p.cam_t / 2
    return [y0 + i * pitch for i in range(4)], p.stack + p.plate_t


# which wall each cam in the stack faces: L R R L, L on -x
SIDES = (-1, 1, 1, -1)


def axle_loads(p: AnchorParams, W: float, bearing: tuple[int, ...]) -> list[tuple[float, float, float]]:
    """(y, fx, fz) that each bearing cam puts on the axle. A cam on the s wall
    is pushed by it (-s N, F) and passes that straight to the axle."""
    n = len(bearing) // 2
    F, N, _ = cam_forces(p, W, n)
    ys, _ = stations(p)
    return [(ys[i], -SIDES[i] * N, F) for i in bearing]


def beam(loads: list[tuple[float, float, float]], span: float, samples: int = 400) -> tuple[float, float, float]:
    """A simply supported beam from y = 0 to span under point loads
    (y, fx, fz): the peak resultant bending moment, and the two supports'
    resultant reactions."""
    reactions = []
    for k in (1, 2):
        total = sum(l[k] for l in loads)
        about0 = sum(l[k] * l[0] for l in loads)
        r1 = -about0 / span
        reactions.append((-total - r1, r1))
    peak = 0.0
    for i in range(samples + 1):
        y = span * i / samples
        mx = reactions[0][0] * y + sum(l[1] * (y - l[0]) for l in loads if l[0] < y)
        mz = reactions[1][0] * y + sum(l[2] * (y - l[0]) for l in loads if l[0] < y)
        peak = max(peak, math.hypot(mx, mz))
    r_a = math.hypot(reactions[0][0], reactions[1][0])
    r_b = math.hypot(reactions[0][1], reactions[1][1])
    return peak, r_a, r_b


def bearing_sets(n: int) -> list[tuple[int, ...]]:
    """Every choice of n cams on each wall."""
    left = [i for i, s in enumerate(SIDES) if s < 0]
    right = [i for i, s in enumerate(SIDES) if s > 0]
    return [tuple(sorted(a + b)) for a in itertools.combinations(left, n) for b in itertools.combinations(right, n)]


def indent(p: AnchorParams, N: float) -> float:
    """Roughly how far a cam sinks into the wall to carry N, mm."""
    w = N / (WOOD_PERP_GRAIN * p.cam_t)
    if w <= p.tooth_pitch:
        return p.tooth_d * w / p.tooth_pitch
    rho = p.r(p.rho_gap + math.radians(p.alpha)) * math.sqrt(1 + p.k**2)
    return p.tooth_d + w**2 / (8 * rho)


def modes(p: AnchorParams, ld: Loading, W: float | None = None) -> list[Mode]:
    p.validate()
    ld.validate()
    W = ld.W if W is None else W
    n = ld.cams_per_wall
    _, N, R = cam_forces(p, W, n)
    ys, span = stations(p)
    s_bolt = math.pi * M6_MINOR**3 / 32

    worst_m, plate_p = 0.0, 0.0
    for b in bearing_sets(n):
        m, ra, rb = beam(axle_loads(p, W, b), span)
        worst_m = max(worst_m, m)
        plate_p = max(plate_p, ra, rb)
    # the eye bolt carries W over the same span, its reactions W / 2 each
    plate_p = max(plate_p, W / 2)

    lig = p.plate_w / 2 - p.hole / 2
    return [
        Mode("slip (mu needed)", p.k, p.mu, "", scales=False),
        Mode("cam bearing", R / (p.hole * p.cam_t), PETG_SUSTAINED, "MPa"),
        Mode("axle bending", worst_m / s_bolt, STEEL_8_8_YIELD, "MPa"),
        Mode("eye bolt bending", W * span / 4 / s_bolt, STEEL_8_8_YIELD, "MPa"),
        Mode("plate net tension", plate_p / ((p.plate_w - p.hole) * p.plate_t), PETG_SUSTAINED, "MPa"),
        Mode("plate shear-out", plate_p / (2 * lig * p.plate_t), PETG_SUSTAINED / math.sqrt(3), "MPa"),
        Mode("plate bearing", plate_p / (p.hole * p.plate_t), PETG_SUSTAINED, "MPa"),
        Mode("wall indent", indent(p, N), p.reach_max - p.gap / 2, "mm"),
    ]


def capacity_kg(p: AnchorParams, ld: Loading, name: str, sf: float = 1.0) -> float:
    """The load (kg) at which mode `name` reaches safety factor sf (bisection:
    every mode's demand rises with the load)."""
    def ok(kg: float) -> bool:
        return next(m for m in modes(p, ld, kg * G) if m.name == name).sf >= sf
    if not ok(1e-6):
        return 0.0
    lo, hi = 0.0, 1.0
    while ok(hi):
        lo, hi = hi, hi * 2
        if hi > 1e6:
            return math.inf
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if ok(mid) else (lo, mid)
    return lo


def rated_kg(p: AnchorParams, ld: Loading) -> float:
    """The largest load that keeps every load-bearing mode at safety factor ld.sf or better."""
    return min(capacity_kg(p, ld, m.name, ld.sf) for m in modes(p, ld) if m.scales)


def trigger_pull(p: AnchorParams, ld: Loading) -> float:
    """The most force (N) on the finger-pull needed to hold all four cams
    against their bands, anywhere from retracted to set in the gap."""
    worst = 0.0
    for i in range(41):
        rho = p.rho_gap * i / 40
        spring = torque(p.spring_hole(rho), p.sleeve)
        lever = -torque(p.trigger_hole(rho), p.pull_hole)
        worst = max(worst, 4 * ld.band_n * spring / lever)
    return worst


def check(p: AnchorParams, ld: Loading) -> None:
    """Refuse a loading the anchor can't carry at safety factor ld.sf."""
    rated = rated_kg(p, ld)
    if ld.load_kg > rated:
        weakest = min((m for m in modes(p, ld) if m.scales), key=lambda m: m.sf)
        raise ValueError(f"{ld.load_kg:g} kg exceeds the rated {rated:.1f} kg at SF {ld.sf:g}; weakest: {weakest.name}")


def report(p: AnchorParams, ld: Loading) -> str:
    F, N, R = cam_forces(p, ld.W, ld.cams_per_wall)
    lines = [
        f"{ld.load_kg:g} kg ({ld.W:.0f} N), {ld.cams_per_wall} cam(s) bearing per wall: "
        f"each carries F {F:.0f} N up, N {N:.0f} N into the wall, R {R:.0f} N on the axle",
        f"{'mode':<20}{'demand':>10}{'limit':>10}  {'SF':>6}{'fails at':>11}",
    ]
    for m in modes(p, ld):
        cap = capacity_kg(p, ld, m.name)
        cap_s = "-" if not m.scales else f"{cap:.0f} kg"
        lines.append(f"{m.name:<20}{m.demand:>10.3g}{m.limit:>10.3g}  {m.sf:>6.1f}{cap_s:>11}  {m.unit}")
    lines.append(f"rated load at SF {ld.sf:g}: {rated_kg(p, ld):.1f} kg")
    lines.append(f"trigger pull with {ld.band_n:g} N bands: up to {trigger_pull(p, ld):.0f} N")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    for cls in (Loading, AnchorParams):
        for f in fields(cls):
            ap.add_argument(f"--{f.name}", type=type(f.default), default=f.default)
    args = ap.parse_args(argv)
    p = AnchorParams(**{f.name: getattr(args, f.name) for f in fields(AnchorParams)})
    ld = Loading(**{f.name: getattr(args, f.name) for f in fields(Loading)})
    print(report(p, ld))


if __name__ == "__main__":
    main()
