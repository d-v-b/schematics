"""Write animation.html: the anchor, looking along the axle, going through a
full cycle between the beams. The animation is drawn from the real part
outlines and the mechanics model.

The cycle:
1. Pull the trigger, retracting the cams.
2. Push the anchor up into the gap.
3. Let go: the bands swing the cams out to the walls.
4. Hang a load: the cams bite and turn a little further out as the wood
   dents under them.
5. Unload, pull the trigger and take the anchor out.

The page takes its geometry from ``AnchorParams`` and its forces and indent
from ``mechanics``, so it follows any parameter change.

Usage:
    python animate.py [-o animation.html] [any anchor.py --param]
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import fields
from pathlib import Path

from build123d import GeomType, Wire

from anchor import AnchorParams, cam_sketch, plate_sketch
from mechanics import Loading, cam_forces, indent, rated_kg

TEMPLATE = Path(__file__).with_name("animation.template.html")


def _path(w: Wire, arc_steps: int = 24) -> str:
    """An SVG path (drawing coordinates, z up) tracing a closed wire."""
    pts = []
    for e in w.order_edges():
        if e.geom_type == GeomType.LINE:
            pts.append(e.position_at(0))
        else:
            pts += [e.position_at(i / arc_steps) for i in range(arc_steps)]
    return "M" + " L".join(f"{v.X:.2f},{v.Y:.2f}" for v in pts) + " Z"


def _outline(sketch) -> str:
    f = sketch.faces()[0]
    return " ".join(_path(w) for w in [f.outer_wire(), *f.inner_wires()])


def geometry(p: AnchorParams) -> dict:
    """Everything the page draws and computes with."""
    ld = Loading()
    # the cam's turn per mm of extra reach, near where it sets in the gap
    dreach = p.reach(p.rho_gap + 0.01) - p.reach(p.rho_gap)
    indent_rho = [
        {"kg": kg, "indent": indent(p, cam_forces(p, kg * 9.81, 1)[1]),
         "rho": indent(p, cam_forces(p, kg * 9.81, 1)[1]) / dreach * 0.01}
        for kg in range(0, 41)
    ]
    return {
        "cam": _outline(cam_sketch(p)),
        "plate": _outline(plate_sketch(p)),
        "gap": p.gap, "alpha": p.alpha, "k": p.k, "mu": p.mu,
        "reach_min": p.reach_min, "reach_max": p.reach_max, "r0": p.r0,
        "rho_max": p.rho_max, "rho_rest": p.rho_rest, "rho_gap": p.rho_gap,
        "trigger": p.trigger_hole(0), "spring": p.spring_hole(0),
        "pull": p.pull_hole, "drop": p.drop, "sleeve_od": p.sleeve_od, "hole": p.hole,
        "plate_w": p.plate_w, "bolt": p.bolt,
        "rated_kg": rated_kg(p, ld), "sf": ld.sf,
        "indent": indent_rho,
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("-o", "--output", type=Path, default=Path("animation.html"))
    for f in fields(AnchorParams):
        ap.add_argument(f"--{f.name}", type=type(f.default), default=f.default)
    args = ap.parse_args(argv)
    p = AnchorParams(**{f.name: getattr(args, f.name) for f in fields(AnchorParams)})
    p.validate()
    html = TEMPLATE.read_text().replace("/*GEOMETRY*/null", json.dumps(geometry(p)))
    args.output.write_text(html)
    print(f"-> {args.output}")


if __name__ == "__main__":
    main()
