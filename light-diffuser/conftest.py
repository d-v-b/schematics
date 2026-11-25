"""Shared test helpers."""


def volume(part, eps: float = 1e-6) -> float:
    """The part's volume, integrated to a relative error of eps. The
    default integration is off by a factor of four on the lofted wall."""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(part.wrapped, props, eps)
    return props.Mass()
