import msgspec
import numpy as np
from numpy.typing import NDArray

__all__ = ["Waveform"]


class Waveform(msgspec.Struct, frozen=True):
    channel: str
    x: NDArray[np.float64]
    y: NDArray[np.float64]

    def __post_init__(self) -> None:
        if self.x.ndim != 1:
            raise ValueError("x must be one-dimensional")

        if self.y.ndim != 1:
            raise ValueError("y must be one-dimensional")

        if self.x.shape != self.y.shape:
            raise ValueError("x and y must have the same shape")
