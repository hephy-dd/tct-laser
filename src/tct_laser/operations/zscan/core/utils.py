import math
from typing import TypeAlias

import numpy as np
from numpy.typing import NDArray

from tct_laser.core.utils import Vector3

FloatArray: TypeAlias = NDArray[np.float64]

__all__ = ["focus_slope", "path_distance"]


def vector_length(vector: Vector3) -> float:
    x, y, z = vector.to_tuple()
    return math.sqrt(x * x + y * y + z * z)


def focus_slope(
    distance_um: FloatArray,
    amplitude_v: FloatArray,
) -> float:
    """
    Return the signed steepest amplitude gradient along the XY scan.

    The autofocus score uses the absolute value of this slope. The signed value
    is retained for the Z-versus-slope plot.
    """

    valid = np.isfinite(distance_um) & np.isfinite(amplitude_v)
    distance = distance_um[valid]
    amplitude = amplitude_v[valid]

    if distance.size < 2:
        return math.nan

    # np.gradient requires distinct coordinates.
    unique_distance, unique_indices = np.unique(
        distance,
        return_index=True,
    )
    unique_amplitude = amplitude[unique_indices]

    if unique_distance.size < 2:
        return math.nan

    gradient = np.gradient(unique_amplitude, unique_distance)
    finite_gradient = gradient[np.isfinite(gradient)]

    if finite_gradient.size == 0:
        return math.nan

    steepest_index = int(np.argmax(np.abs(finite_gradient)))
    return float(finite_gradient[steepest_index])


def path_distance(
    x_um: FloatArray,
    y_um: FloatArray,
) -> FloatArray:
    """Calculate cumulative distance along the configured XY line."""

    if x_um.size == 0:
        return np.empty(0, dtype=np.float64)

    segment_lengths = np.hypot(
        np.diff(x_um),
        np.diff(y_um),
    )

    return np.concatenate(
        (
            np.zeros(1, dtype=np.float64),
            np.cumsum(segment_lengths, dtype=np.float64),
        )
    )
