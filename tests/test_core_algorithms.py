import numpy as np
import pytest

from tct_laser.core import algorithms


def test_xy_range():
    xy = algorithms.xy_range(2, 2, mode="linear")
    np.testing.assert_array_equal(xy, np.array([[0, 0], [1, 0], [0, 1], [1, 1]]))
    xy = algorithms.xy_range(2, 2, mode="zigzag")
    np.testing.assert_array_equal(xy, np.array([[0, 0], [1, 0], [1, 1], [0, 1]]))


def test_xy_range_invalid_mode():
    with pytest.raises(ValueError):
        algorithms.xy_range(2, 2, mode="shrubbery")


def test_xy_range_linear():
    xy = algorithms.xy_range_linear(2, 2)
    np.testing.assert_array_equal(xy, np.array([[0, 0], [1, 0], [0, 1], [1, 1]]))


def test_xy_range_zigzag():
    xy = algorithms.xy_range_zigzag(2, 2)
    np.testing.assert_array_equal(xy, np.array([[0, 0], [1, 0], [1, 1], [0, 1]]))


def test_xy_range_random_uniform():
    w, h = 10, 20
    n = w * h

    xy = algorithms.xy_range_random_uniform(w, h)

    # correct shape
    assert xy.shape == (n, 2)

    # values within bounds (depending on your design, either [0,1) or pixel coords)
    assert np.all(xy[:, 0] >= 0)
    assert np.all(xy[:, 1] >= 0)
    assert np.all(xy[:, 0] < w)
    assert np.all(xy[:, 1] < h)

    # randomness: two independent calls should not be identical too often
    xy2 = algorithms.xy_range_random_uniform(w, h)
    # They should differ in at least one coordinate (not a strict guarantee, but statistically safe)
    assert not np.array_equal(xy, xy2)


def test_xy_range_hilbert_properties():
    w = h = 4
    n = w * h

    xy = algorithms.xy_range_hilbert(w, h)

    # correct shape
    assert xy.shape == (n, 2)

    # coordinates within bounds
    assert np.all((0 <= xy) & (xy < 4))

    # all coordinates unique
    uniq = np.unique(xy, axis=0)
    assert uniq.shape[0] == n

    # deterministic: calling twice should return identical sequences
    xy2 = algorithms.xy_range_hilbert(w, h)
    np.testing.assert_array_equal(xy, xy2)
