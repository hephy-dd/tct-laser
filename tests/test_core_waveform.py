import numpy as np
import pytest

from tct_laser.core.waveform import Waveform


def test_waveform_creation():
    x = np.array([0.0, 1.0, 2.0], dtype=np.float64)
    y = np.array([10.0, 20.0, 30.0], dtype=np.float64)

    waveform = Waveform(channel="CH1", x=x, y=y)

    assert waveform.channel == "CH1"
    np.testing.assert_array_equal(waveform.x, x)
    np.testing.assert_array_equal(waveform.y, y)


def test_waveform_empty_arrays():
    waveform = Waveform(
        channel="CH1",
        x=np.array([], dtype=np.float64),
        y=np.array([], dtype=np.float64),
    )

    assert waveform.x.size == 0
    assert waveform.y.size == 0


def test_waveform_rejects_multidimensional_x():
    x = np.array([[0.0, 1.0], [2.0, 3.0]], dtype=np.float64)
    y = np.array([10.0, 20.0], dtype=np.float64)

    with pytest.raises(ValueError, match="x must be one-dimensional"):
        Waveform(channel="CH1", x=x, y=y)


def test_waveform_rejects_multidimensional_y():
    x = np.array([0.0, 1.0], dtype=np.float64)
    y = np.array([[10.0, 20.0], [30.0, 40.0]], dtype=np.float64)

    with pytest.raises(ValueError, match="y must be one-dimensional"):
        Waveform(channel="CH1", x=x, y=y)


def test_waveform_rejects_different_shapes():
    x = np.array([0.0, 1.0, 2.0], dtype=np.float64)
    y = np.array([10.0, 20.0], dtype=np.float64)

    with pytest.raises(ValueError, match="x and y must have the same shape"):
        Waveform(channel="CH1", x=x, y=y)


def test_waveform_is_frozen():
    waveform = Waveform(
        channel="CH1",
        x=np.array([0.0], dtype=np.float64),
        y=np.array([1.0], dtype=np.float64),
    )

    with pytest.raises(AttributeError):
        waveform.channel = "CH2"  # type: ignore
