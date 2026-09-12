"""Assemble each model around a solid beam, for sanity checking, and the whole
curtain hanger: beam, bolted beam clamp halves with their bolts, the rail
clamps fused to the lower half's base, and the two curtain rails snapped
into them.

Builds the beam as a box the size of the real cross-section, seats it on the
lower half's fillets (see ``seat_offset`` in beam_clamp.py), places the parts
around it, and writes:

  - a STEP file with every body as a separate, coloured solid
  - an STL of the same for quick viewing in a slicer
  - SVG line drawings from the front (looking along the beam) and an
    isometric view, hidden lines dashed

Usage:
    python assembly.py clamp|wrap|bolt|flex|hanger [-o outdir] [--param value ...]

``hanger`` takes the bolt model's parameters; give it ``rails`` (e.g.
``outer,outer``) and the lower half is rendered with the rail clamps fused to
its base, the upper half plain.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import fields
from pathlib import Path

from build123d import Align, Box, Color, Compound, ExportSVG, LineType, Location, Part, export_step, export_stl

import beam_bolt
import beam_clamp
import beam_flex
import beam_wrap
import rail_clamp

MODELS = {
    "clamp": (beam_clamp.ClampParams, lambda p: [("clamp", beam_clamp.clamp(p))]),
    "wrap": (beam_wrap.WrapParams, lambda p: list(zip(("lower", "upper"), beam_wrap.assembly(p)))),
    "flex": (beam_flex.FlexParams, lambda p: list(zip(("lower", "upper"), beam_flex.assembly(p)))),
    "hanger": (beam_bolt.BoltParams, lambda p: hanger_bodies(p)),
    "bolt": (
        beam_bolt.BoltParams,
        lambda p: list(zip(("lower", "upper"), beam_bolt.assembly(p))) + [("bolts", beam_bolt.bolt_shafts(p))],
    ),
}
BEAM_H = 206.5  # for the single clamp, whose params do not carry the beam height
COLORS = {
    "beam": (0.76, 0.6, 0.42),
    "clamp": (0.9, 0.7, 0.1),
    "lower": (0.9, 0.7, 0.1),
    "upper": (0.27, 0.51, 0.71),
    "bolts": (0.8, 0.1, 0.1),
    "rail_clamp": (0.35, 0.65, 0.35),
    "rails": (0.7, 0.7, 0.72),
}


def beam(p, margin: float = 15.0) -> Part:
    """The beam, centred in the inner span, seated on the lower fillets, and
    running past both ends of the assembly along z."""
    z_len = getattr(p, "stagger", 0.0) + p.length + 2 * margin
    beam_h = getattr(p, "beam_h", BEAM_H)
    return Box(p.beam_w, beam_h, z_len, align=(Align.MIN, Align.MIN, Align.MIN)).moved(
        Location((p.clearance / 2, p.seat, -margin))
    )


def hanger_bodies(p) -> list[tuple[str, Part]]:
    """The lower half carries the fused rail clamps; the upper half is the
    same bolt wrap without them."""
    if not p.rails:
        raise ValueError("the hanger needs rail clamps on the lower half: set rails, e.g. 'outer,outer'")
    lower = beam_bolt.half(beam_bolt.BoltParams(**{**{f.name: getattr(p, f.name) for f in fields(beam_bolt.BoltParams)}, "bolt_slot": 0}))
    plain = beam_bolt.BoltParams(**{**{f.name: getattr(p, f.name) for f in fields(beam_bolt.BoltParams)}, "rails": "", "label": "", "bolt_slot": 1})
    upper = beam_bolt.half(plain).moved(beam_bolt.mate_location(p))
    rails = None
    for r in beam_bolt.fused_rails(p):
        rails = r if rails is None else rails + r
    return [("lower", lower), ("upper", upper), ("bolts", beam_bolt.bolt_shafts(p)), ("rails", rails)]


def bodies(model: str, p) -> list[tuple[str, Part]]:
    """(name, solid) for every body in the assembly, beam first."""
    _, build = MODELS[model]
    return [("beam", beam(p))] + build(p)


def _vol(a, b) -> float:
    r = a & b
    return r.volume if hasattr(r, "volume") else sum(s.volume for s in r)


def interference(model: str, p) -> dict[str, float]:
    """Volume of overlap between the beam and each part; for the hanger also
    between the rail clamp and the beam clamp, and the rails and everything."""
    parts = bodies(model, p)
    bm = parts[0][1]
    out = {name: _vol(bm, shape) for name, shape in parts[1:]}
    if model == "hanger":
        d = dict(parts)
        out["bolts/lower"] = _vol(d["bolts"], d["lower"])
        out["bolts/upper"] = _vol(d["bolts"], d["upper"])
        out["rails/lower"] = _vol(d["rails"], d["lower"])
        out["lower/upper"] = _vol(d["lower"], d["upper"])
    return out


def export(model: str, p, outdir: Path) -> list[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    parts = bodies(model, p)
    for name, shape in parts:
        shape.label = name
        shape.color = Color(*COLORS[name])
    comp = Compound(children=[s for _, s in parts])
    written = []
    step = outdir / f"{model}_assembly.step"
    export_step(comp, str(step))
    written.append(step)
    stl = outdir / f"{model}_assembly.stl"
    export_stl(comp, str(stl), tolerance=0.02, angular_tolerance=0.2)
    written.append(stl)
    for view, (origin, up) in {"front": ((0, 0, 1), (0, 1, 0)), "iso": ((1, 1, 1), (0, 1, 0))}.items():
        svg = ExportSVG(scale=2, margin=10, line_weight=0.4)
        svg.add_layer("hidden", line_type=LineType.DASHED, line_weight=0.2)
        vis, hid = comp.project_to_viewport(viewport_origin=origin, viewport_up=up)
        svg.add_shape(vis)
        svg.add_shape(hid, layer="hidden")
        path = outdir / f"{model}_assembly_{view}.svg"
        svg.write(str(path))
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in MODELS:
        sys.exit(f"usage: assembly.py {'|'.join(MODELS)} [-o outdir] [--param value ...]")
    model = argv[0]
    params_cls, _ = MODELS[model]
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--outdir", type=Path, default=Path("assembly"))
    for f in fields(params_cls):
        ap.add_argument(f"--{f.name}", type=type(f.default), default=f.default)
    args = ap.parse_args(argv[1:])
    p = params_cls(**{f.name: getattr(args, f.name) for f in fields(params_cls)})
    for name, vol in interference(model, p).items():
        label = name if "/" in name else f"beam / {name}"
        print(f"{label} overlap: {vol:.2f} mm^3")
    for path in export(model, p, args.outdir):
        print(f"-> {path}")


if __name__ == "__main__":
    main()
