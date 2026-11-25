"""A diffuser for a spherical lamp: a thin-walled tube, closed at one end by a
flat base, whose wall ripples in soft vertical flutes that sway from side
to side up its height.

Seen from above, the wall's outer face is ``lobes`` flutes round a circle
``d`` across, each standing ``ripple_a`` proud of it and sunk as far below:

    r(theta, z) = d / 2 + ripple_a * cos(lobes * (theta - s(theta, z) / (d / 2)))

The flutes do not run straight up: each is pushed sideways round the rim by

    s(theta, z) = sway * sin(2 pi * sway_periods * z / h + sway_turns * theta)

so it leans one way, then the other, ``sway_periods`` times up the
height. With ``sway_turns`` 0 every flute leans together; with 1 the lean
rolls once round the rim, so the flutes on one side lean left while those
on the other lean right, and the swaying passes round the lamp like a
ripple across water.

The wall is ``wall`` thick measured across it, level: its inner face is
the outer one offset inward in every horizontal section. The base is a
flat plate ``base`` thick under the whole outline. The other end is open.

The diffuser stands on z = 0 with the base on the bed and prints the way it
is modeled, in vase mode or with a single perimeter. Nothing leans more
than ``MAX_OVERHANG`` from vertical, so nothing needs support. To use it,
stand it over the lamp with the base on top, the cord out the open end;
or drop the lamp in base down.

Usage:
    python diffuser.py -o diffuser.stl [--d 170] [--h 150] [--lobes 24] [--ripple_a 4.5]
"""

from __future__ import annotations

import argparse
import math
import numbers
from dataclasses import dataclass, fields
from pathlib import Path

import numpy as np
from build123d import Face, GeomType, Part, Shell, Solid, Wire, export_stl

# The printer's bed, mm. The diffuser's footprint must fit on it.
BED = 256.0
# How far the outer face may stray from d, across the diameter, either way.
SPREAD = 10.0
# The steepest the outer face may lean from vertical, degrees.
MAX_OVERHANG = 45.0
# Points per flute each level section is fitted through, and how far
# apart the sections are, mm. Each section's spline is parameterized by
# theta, so the surface joins points straight above one another.
POINTS_PER_LOBE = 48
SECTION_STEP = 1.25
# Grid the validation samples the surface on: points per flute, and levels,
# at least CHECK_PER_SWAY per sway period.
CHECK_PER_LOBE = 64
CHECK_LEVELS = 121
CHECK_PER_SWAY = 64
# The shortest sway, up the height, the sections can follow, in sections.
SECTIONS_PER_SWAY = 16


@dataclass(frozen=True)
class DiffuserParams:
    """Every dimension of the diffuser, in millimeters."""

    # Diameter of the wall's outer face, before the ripple.
    d: float = 170.0
    h: float = 150.0
    # The wall, measured level across it, and the base.
    wall: float = 1.0
    base: float = 1.0
    # Flutes round the rim, and how far each stands in and out of d / 2.
    lobes: int = 24
    ripple_a: float = 4.5
    # How far the flutes sway sideways, round the rim; how many times they
    # sway back and forth up the height; and how many times the sway's
    # phase winds round the rim.
    sway: float = 16.0
    sway_periods: float = 1.0
    sway_turns: int = 1

    # ----- derived -----
    @property
    def r0(self) -> float:
        return self.d / 2

    def _phase(self, theta, z):
        """The flute's phase and the sway's, at (theta, z)."""
        sway = 2 * np.pi * self.sway_periods * np.asarray(z) / self.h + self.sway_turns * np.asarray(theta)
        s = self.sway * np.sin(sway)
        return self.lobes * (np.asarray(theta) - s / self.r0), sway

    def r(self, theta, z):
        """Radius of the wall's outer face at angle theta, height z."""
        phi, _ = self._phase(theta, z)
        return self.r0 + self.ripple_a * np.cos(phi)

    def dr_dtheta(self, theta, z):
        phi, sway = self._phase(theta, z)
        dphi = self.lobes * (1 - self.sway * self.sway_turns * np.cos(sway) / self.r0)
        return -self.ripple_a * np.sin(phi) * dphi

    def outer_xy(self, theta, z):
        """Points on the outer face, as arrays of x and y."""
        r = self.r(theta, z)
        return r * np.cos(theta), r * np.sin(theta)

    def inner_xy(self, theta, z):
        """Points on the inner face: the outer face's points at the same
        (theta, z), moved wall inward along the level section's normal."""
        r, dr = self.r(theta, z), self.dr_dtheta(theta, z)
        c, s = np.cos(theta), np.sin(theta)
        tx, ty = dr * c - r * s, dr * s + r * c
        n = np.hypot(tx, ty)
        # the section runs anticlockwise, so its inside is to the left
        return r * c - self.wall * ty / n, r * s + self.wall * tx / n

    def _grid(self):
        theta = np.linspace(0, 2 * np.pi, self.lobes * CHECK_PER_LOBE, endpoint=False)
        z = np.linspace(0, self.h, max(CHECK_LEVELS, math.ceil(CHECK_PER_SWAY * self.sway_periods) + 1))
        return np.meshgrid(theta, z)

    def steepest(self) -> float:
        """The steepest either face of the wall leans from vertical anywhere,
        degrees, from its normal on the sample grid."""
        t, z = self._grid()
        worst = 0.0
        for xy in (self.outer_xy, self.inner_xy):
            x, y = xy(t, z)
            # tangents round the rim and up the height
            pt = np.stack([np.roll(x, -1, 1) - np.roll(x, 1, 1), np.roll(y, -1, 1) - np.roll(y, 1, 1),
                           np.zeros_like(x)], -1)
            pz = np.stack([np.gradient(x, z[:, 0], axis=0), np.gradient(y, z[:, 0], axis=0),
                           np.ones_like(x)], -1)
            n = np.cross(pt, pz)
            worst = max(worst, float((np.abs(n[..., 2]) / np.linalg.norm(n, axis=-1)).max()))
        return math.degrees(math.asin(worst))

    def tightest(self) -> float:
        """The smallest radius any flute's crest is curved to, seen from
        above: the inner face's offset only holds while it exceeds wall."""
        t, z = self._grid()
        r, dr = self.r(t, z), self.dr_dtheta(t, z)
        h = 2 * np.pi / t.shape[1]
        d2r = (np.roll(r, -1, axis=1) - 2 * r + np.roll(r, 1, axis=1)) / h**2
        k = (r**2 + 2 * dr**2 - r * d2r) / (r**2 + dr**2) ** 1.5
        return float(1 / k.max())

    def validate(self) -> None:
        if min(self.d, self.h, self.wall, self.base) <= 0:
            raise ValueError("d, h, wall and base must be positive")
        if not all(isinstance(n, numbers.Integral) and not isinstance(n, bool)
                   for n in (self.lobes, self.sway_turns)):
            raise ValueError("lobes and sway_turns must be whole numbers")
        if self.lobes < 1:
            raise ValueError("lobes must be at least 1")
        if self.ripple_a < 0 or self.sway < 0 or self.sway_periods < 0:
            raise ValueError("ripple_a, sway and sway_periods must not be negative")
        if self.base >= self.h:
            raise ValueError("base must be thinner than h")
        if 2 * self.ripple_a > SPREAD:
            raise ValueError(
                f"the ripple spans {4 * self.ripple_a:g} across, over the {2 * SPREAD:g} "
                f"allowed ({SPREAD:g} either side of d)")
        if self.ripple_a + self.wall >= self.r0:
            raise ValueError("the ripple and wall must leave room inside")
        if self.sway_periods and self.h / self.sway_periods < SECTIONS_PER_SWAY * SECTION_STEP:
            raise ValueError(
                f"the flutes sway every {self.h / self.sway_periods:g}, too short for sections "
                f"{SECTION_STEP:g} apart: sway fewer times")
        steepest = self.steepest()
        if steepest > MAX_OVERHANG + 1e-9:
            raise ValueError(
                f"the flutes lean up to {steepest:.1f} degrees, over {MAX_OVERHANG:g}: "
                "shrink sway or ripple_a, or sway fewer times")
        tightest = self.tightest()
        if tightest <= self.wall:
            raise ValueError(
                f"the flutes' crests curve as tight as R{tightest:.2f}, "
                f"too tight for the {self.wall:g} wall: use fewer lobes or less ripple or sway")
        if self.d + 2 * self.ripple_a > BED:
            raise ValueError(f"the diffuser is {self.d + 2 * self.ripple_a:g} across, over the {BED:g} bed")

    def report(self) -> str:
        return (
            f"diffuser {self.d - 2 * self.ripple_a:g}-{self.d + 2 * self.ripple_a:g} across, "
            f"{self.h:g} tall, {self.wall:g} wall, {self.base:g} base; {self.lobes} flutes "
            f"swaying {self.sway:g} {self.sway_periods:g} times up, leaning at most "
            f"{self.steepest():.0f} degrees, crests R{self.tightest():.1f} or more"
        )


def _section(p: DiffuserParams, z: float, inner: bool):
    """A level section of the outer or inner face at height z: a periodic
    cubic B-spline through POINTS_PER_LOBE points per flute, parameterized
    by theta / 2 pi, so every section has the same knots."""
    from OCP.GeomAPI import GeomAPI_Interpolate
    from OCP.TColgp import TColgp_HArray1OfPnt
    from OCP.TColStd import TColStd_HArray1OfReal
    from OCP.gp import gp_Pnt

    n = p.lobes * POINTS_PER_LOBE
    theta = np.linspace(0, 2 * np.pi, n, endpoint=False)
    x, y = (p.inner_xy if inner else p.outer_xy)(theta, z)
    pts, par = TColgp_HArray1OfPnt(1, n), TColStd_HArray1OfReal(1, n + 1)
    for i in range(n):
        pts.SetValue(i + 1, gp_Pnt(float(x[i]), float(y[i]), z))
    for i in range(n + 1):
        par.SetValue(i + 1, i / n)
    fit = GeomAPI_Interpolate(pts, par, True, 1e-9)
    fit.Perform()
    return fit.Curve()


def _tube(p: DiffuserParams, z0: float, z1: float, inner: bool) -> Solid:
    """The solid inside the outer or inner face from z0 to z1. Its side is
    one B-spline surface: periodic cubic round the rim, through the level
    sections every SECTION_STEP, and cubic up the height, through each
    column of the sections' poles. So it passes exactly through every
    section. (OCCT's loft fits one high-degree surface instead, which rings
    near its ends: it strayed 0.14 mm there on the inner face.) Its ends
    are flat."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.Geom import Geom_BSplineSurface
    from OCP.GeomAPI import GeomAPI_Interpolate
    from OCP.TColgp import TColgp_Array2OfPnt, TColgp_HArray1OfPnt
    from OCP.TColStd import TColStd_HArray1OfReal

    m = max(3, math.ceil((z1 - z0) / SECTION_STEP))
    sections = [_section(p, z0 + (z1 - z0) * j / m, inner) for j in range(m + 1)]
    nu = sections[0].NbPoles()
    vpar = TColStd_HArray1OfReal(1, m + 1)
    for j in range(m + 1):
        vpar.SetValue(j + 1, j / m)
    columns = []
    for i in range(1, nu + 1):
        col = TColgp_HArray1OfPnt(1, m + 1)
        for j, c in enumerate(sections):
            col.SetValue(j + 1, c.Pole(i))
        fit = GeomAPI_Interpolate(col, vpar, False, 1e-9)
        fit.Perform()
        columns.append(fit.Curve())
    nv = columns[0].NbPoles()
    poles = TColgp_Array2OfPnt(1, nu, 1, nv)
    for i, c in enumerate(columns):
        for j in range(1, nv + 1):
            poles.SetValue(i + 1, j, c.Pole(j))
    u, v = sections[0], columns[0]
    surface = Geom_BSplineSurface(poles, u.Knots(), v.Knots(), u.Multiplicities(), v.Multiplicities(),
                                  u.Degree(), v.Degree(), True, False)
    side = Face(BRepBuilderAPI_MakeFace(surface, 1e-7).Face())
    rims = [Face(Wire([e])) for e in side.edges() if e.geom_type != GeomType.LINE
            and abs(e.bounding_box().size.Z) < 1e-6]
    return Solid(Shell([side, *rims]))


def diffuser(p: DiffuserParams) -> Part:
    p.validate()
    # the hollow runs out past the top, so the cut leaves that end open
    body = _tube(p, 0, p.h, inner=False).cut(_tube(p, p.base, p.h + 1, inner=True))
    if len(body.solids()) != 1:
        raise RuntimeError(f"the cut left {len(body.solids())} solids, not 1")
    return Part([body.solids()[0]])


def _png(p: DiffuserParams, out: Path) -> None:
    """A shaded three-quarter view of the diffuser's mesh."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    verts, tris = diffuser(p).tessellate(0.05, 0.2)
    v = np.array([(q.X, q.Y, q.Z) for q in verts])
    f = v[np.array(tris)]
    n = np.cross(f[:, 1] - f[:, 0], f[:, 2] - f[:, 0])
    n /= np.linalg.norm(n, axis=1, keepdims=True)
    light = np.array([-0.5, -0.7, 0.5]) / np.linalg.norm([-0.5, -0.7, 0.5])
    shade = 0.25 + 0.75 * np.clip(n @ light, 0, 1)
    fig = plt.figure(figsize=(6, 6))
    ax = fig.add_subplot(projection="3d", computed_zorder=False)
    ax.add_collection3d(Poly3DCollection(f, facecolors=np.outer(shade, (1.0, 0.97, 0.9)), linewidths=0))
    rr = p.r0 + p.ripple_a
    ax.set(xlim=(-rr, rr), ylim=(-rr, rr), zlim=(0, p.h))
    ax.set_box_aspect((1, 1, p.h / (2 * rr)))
    ax.view_init(elev=22, azim=-60)
    ax.set_axis_off()
    fig.savefig(out, dpi=110, bbox_inches="tight", facecolor="white")


def _cli() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("-o", "--output", type=Path, required=True, help=".stl, .step or .png path")
    for f in fields(DiffuserParams):
        ap.add_argument(f"--{f.name}", type=type(f.default), default=f.default)
    return ap


def main(argv: list[str] | None = None) -> None:
    args = _cli().parse_args(argv)
    p = DiffuserParams(**{f.name: getattr(args, f.name) for f in fields(DiffuserParams)})
    p.validate()
    out: Path = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix == ".png":
        _png(p, out)
    elif out.suffix == ".step":
        from build123d import export_step

        export_step(diffuser(p), str(out))
    else:
        export_stl(diffuser(p), str(out), tolerance=0.02, angular_tolerance=0.2)
    print(f"-> {out}")
    print(p.report())


if __name__ == "__main__":
    main()
