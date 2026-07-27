import math
from datetime import datetime

import msgspec
import numpy as np
from numpy.typing import NDArray

SI_PREFIXES = [
    (1e-12, "p"),  # pico
    (1e-9, "n"),  # nano
    (1e-6, "µ"),  # micro
    (1e-3, "m"),  # milli
    (1, ""),  # base
    (1e3, "k"),  # kilo
    (1e6, "M"),  # mega
    (1e9, "G"),  # giga
    (1e12, "T"),  # tera
]


def si_format(value: float, unit: str) -> str:
    if not math.isfinite(value):
        return str(value)

    if value == 0:
        return f"0 {unit}"

    abs_val = abs(value)

    # find the best SI scale
    for factor, prefix in SI_PREFIXES:
        if abs_val < factor * 1000:
            scaled = value / factor
            return f"{scaled:G} {prefix}{unit}"

    # fallback (beyond T)
    factor, prefix = SI_PREFIXES[-1]
    scaled = value / factor
    return f"{scaled:G} {prefix}{unit}"


def safe_iso_timestamp(dt: datetime | None = None) -> str:
    if dt is None:
        dt = datetime.now().astimezone()
    return dt.strftime("%Y-%m-%dT%H-%M-%S")


def pulse_area_window(
    t: NDArray[np.float64],
    y: NDArray[np.float64],
    threshold_factor: float = 0.1,
    baseline_samples: int = 50,
) -> float:
    baseline = np.mean(y[:baseline_samples])
    y_corr = y - baseline

    peak = np.max(y_corr)
    threshold = threshold_factor * peak

    mask = y_corr > threshold
    if not np.any(mask):
        return 0.0  # no pulse detected

    i0, i1 = np.where(mask)[0][[0, -1]]
    return np.trapezoid(y_corr[i0 : i1 + 1], x=t[i0 : i1 + 1]).item()


class Vector3(msgspec.Struct, frozen=True):
    x: float
    y: float
    z: float

    def __iter__(self):
        return iter((self.x, self.y, self.z))

    def to_tuple(self) -> tuple[float, float, float]:
        return self.x, self.y, self.z


class Waveform(msgspec.Struct, frozen=True):
    channel: str
    x: NDArray[np.float64]
    y: NDArray[np.float64]
