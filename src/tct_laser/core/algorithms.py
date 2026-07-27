import numpy as np
from numpy.typing import NDArray

type CoordArray = NDArray[np.int_]


def xy_range_linear(x_steps: int, y_steps: int) -> CoordArray:
    xs = np.tile(np.arange(x_steps), y_steps)
    ys = np.repeat(np.arange(y_steps), x_steps)
    return np.stack((xs, ys), axis=1)


def xy_range_random_uniform(x_steps: int, y_steps: int) -> CoordArray:
    xs = np.tile(np.arange(x_steps), y_steps)
    ys = np.repeat(np.arange(y_steps), x_steps)
    coords = np.stack((xs, ys), axis=1)
    np.random.shuffle(coords)  # shuffles rows in-place
    return coords


def xy_range_zigzag(x_steps: int, y_steps: int) -> CoordArray:
    ys = np.repeat(np.arange(y_steps), x_steps)
    xs = np.empty_like(ys)

    for y in range(y_steps):
        row_start = y * x_steps
        row_end = row_start + x_steps
        if y % 2 == 0:
            xs[row_start:row_end] = np.arange(x_steps)
        else:
            xs[row_start:row_end] = np.arange(x_steps - 1, -1, -1)

    return np.stack((xs, ys), axis=1)


def xy_range_diagonal_zigzag(x_steps: int, y_steps: int) -> CoordArray:
    if x_steps < 0 or y_steps < 0:
        raise ValueError("x_steps and y_steps must be non-negative")

    if x_steps == 0 or y_steps == 0:
        return np.empty((0, 2), dtype=np.int_)

    coordinates: list[tuple[int, int]] = []

    # Each value of diagonal represents x + y.
    for diagonal in range(x_steps + y_steps - 1):
        x_min = max(0, diagonal - (y_steps - 1))
        x_max = min(x_steps - 1, diagonal)

        xs = range(x_min, x_max + 1)

        # Reverse alternating diagonals to avoid edge-to-edge jumps.
        if diagonal % 2 == 0:
            xs = reversed(range(x_min, x_max + 1))

        for x in xs:
            y = diagonal - x
            coordinates.append((x, y))

    return np.asarray(coordinates, dtype=np.int_)


def _next_power_of_two(n: int) -> int:
    """Smallest power of two >= n (for n >= 1)."""
    if n < 1:
        raise ValueError("n must be >= 1")
    return 1 << (n - 1).bit_length()


def _hilbert_d2xy(n: int, d: int):
    """
    Convert Hilbert distance d to (x, y) for an n x n grid,
    where n is a power of two.
    """
    x = 0
    y = 0
    t = d
    s = 1
    while s < n:
        rx = 1 & (t // 2)
        ry = 1 & (t ^ rx)
        if ry == 0:
            if rx == 1:
                x = s - 1 - x
                y = s - 1 - y
            x, y = y, x
        x += s * rx
        y += s * ry
        t //= 4
        s *= 2
    return x, y


def xy_range_hilbert_rect(size: int) -> CoordArray:
    """
    Return an (N, 2) int array of (x, y) along a Hilbert curve
    over a size x size grid. `size` must be a power of two.
    """
    n = size
    if n & (n - 1) != 0:
        raise ValueError("size must be a power of two")

    total = n * n
    coords = np.empty((total, 2), dtype=np.int_)

    for d in range(total):
        x, y = _hilbert_d2xy(n, d)
        coords[d, 0] = x
        coords[d, 1] = y

    return coords


def xy_range_hilbert(x_steps: int, y_steps: int) -> CoordArray:
    if x_steps < 1 or y_steps < 1:
        return np.empty((0, 2), dtype=np.int_)

    n = _next_power_of_two(max(x_steps, y_steps))
    total = n * n
    needed = x_steps * y_steps

    coords = np.empty((needed, 2), dtype=np.int_)
    idx = 0

    for d in range(total):
        x, y = _hilbert_d2xy(n, d)
        if x < x_steps and y < y_steps:
            coords[idx] = (x, y)
            idx += 1
            if idx == needed:
                break

    return coords


_RANGE_FUNCS = {
    "linear": xy_range_linear,
    "random_uniform": xy_range_random_uniform,
    "zigzag": xy_range_zigzag,
    "diagonal_zigzag": xy_range_diagonal_zigzag,
    "hilbert": xy_range_hilbert,
}


def xy_range(x_steps: int, y_steps: int, mode: str = "linear") -> CoordArray:
    key = mode.lower()

    if key not in _RANGE_FUNCS:
        raise ValueError(
            f"Unknown xy_range mode '{mode}'. Valid modes: {', '.join(_RANGE_FUNCS)}"
        )

    return _RANGE_FUNCS[key](x_steps, y_steps)
