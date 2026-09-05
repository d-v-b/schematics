"""Compliance of a clamp arm treated as a cantilever (Euler-Bernoulli).

The arm is a rectangular beam of thickness ``wall`` (in the bending direction,
across the beam) and depth ``length`` (along the beam), fixed at the elbow and
loaded at its tip. For a tip deflection d over a free length L:

    I     = length * wall^3 / 12
    force = 3 E I d / L^3
    stress at the root = 3 E wall d / (2 L^2)      (independent of depth)

Materials are typical values for printed parts; strength along the layers
(the arm bends within a layer, which is the strong direction). PLA creeps
under sustained stress, so a permanently deflected arm should stay well
below its short-term strength: ``creep_limit`` is a rule-of-thumb ceiling.

Usage:
    python compliance.py --wall 5 --length 50 --arm_len 90 --deflection 5.3
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass


@dataclass(frozen=True)
class Material:
    name: str
    E: float  # Young's modulus, MPa
    strength: float  # short-term tensile strength, MPa
    creep_limit: float  # sustained stress to stay under, MPa


MATERIALS = {
    "pla": Material("PLA", E=3300.0, strength=50.0, creep_limit=12.0),
    "petg": Material("PETG", E=2000.0, strength=45.0, creep_limit=15.0),
    "abs": Material("ABS", E=2100.0, strength=35.0, creep_limit=15.0),
}


@dataclass(frozen=True)
class ArmFlex:
    wall: float  # thickness across the beam, mm
    length: float  # depth along the beam, mm
    arm_len: float  # free length from the elbow to the load, mm
    deflection: float  # tip deflection, mm
    material: Material

    @property
    def inertia(self) -> float:
        return self.length * self.wall**3 / 12

    @property
    def force(self) -> float:
        """Tip force needed to hold the deflection, N."""
        return 3 * self.material.E * self.inertia * self.deflection / self.arm_len**3

    @property
    def stiffness(self) -> float:
        """N per mm of tip deflection."""
        return 3 * self.material.E * self.inertia / self.arm_len**3

    @property
    def stress(self) -> float:
        """Peak bending stress at the root, MPa."""
        return 3 * self.material.E * self.wall * self.deflection / (2 * self.arm_len**2)

    @property
    def safety_vs_strength(self) -> float:
        return self.material.strength / self.stress if self.stress > 0 else float("inf")

    @property
    def safety_vs_creep(self) -> float:
        return self.material.creep_limit / self.stress if self.stress > 0 else float("inf")

    def max_deflection(self, stress_limit: float | None = None) -> float:
        """Tip deflection at which the root reaches stress_limit (default: creep_limit)."""
        limit = self.material.creep_limit if stress_limit is None else stress_limit
        return 2 * limit * self.arm_len**2 / (3 * self.material.E * self.wall)

    def report(self) -> str:
        m = self.material
        return (
            f"{m.name}: wall {self.wall} mm, depth {self.length} mm, free length {self.arm_len} mm, "
            f"deflection {self.deflection} mm\n"
            f"  force {self.force:.1f} N ({self.stiffness:.2f} N/mm), root stress {self.stress:.1f} MPa\n"
            f"  safety vs strength {self.safety_vs_strength:.1f}x, vs creep limit {self.safety_vs_creep:.1f}x\n"
            f"  deflection for creep limit {self.max_deflection():.1f} mm, for strength {self.max_deflection(m.strength):.1f} mm"
        )


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--wall", type=float, default=5.0)
    ap.add_argument("--length", type=float, default=50.0)
    ap.add_argument("--arm_len", type=float, default=90.0)
    ap.add_argument("--deflection", type=float, default=5.3)
    ap.add_argument("--material", choices=sorted(MATERIALS), default="pla")
    a = ap.parse_args(argv)
    print(ArmFlex(a.wall, a.length, a.arm_len, a.deflection, MATERIALS[a.material]).report())


if __name__ == "__main__":
    main()
