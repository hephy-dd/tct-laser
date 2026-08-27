import pytest

from tct_laser.core.geometry import Vector3


def test_vector3_coordinates():
    vector = Vector3(1.0, 2.0, 3.0)

    assert vector.x == 1.0
    assert vector.y == 2.0
    assert vector.z == 3.0


def test_vector3_is_frozen():
    vector = Vector3(1.0, 2.0, 3.0)

    with pytest.raises(AttributeError):
        vector.x = 4.0  # type: ignore


def test_vector3_iteration():
    vector = Vector3(1.0, 2.0, 3.0)

    assert list(vector) == [1.0, 2.0, 3.0]


def test_vector3_unpacking():
    vector = Vector3(1.0, 2.0, 3.0)

    x, y, z = vector

    assert (x, y, z) == (1.0, 2.0, 3.0)


def test_vector3_to_tuple():
    vector = Vector3(1.0, 2.0, 3.0)

    assert vector.to_tuple() == (1.0, 2.0, 3.0)


def test_vector3_scalar_multiplication():
    vector = Vector3(1.0, 2.0, 3.0)

    assert vector * 2 == Vector3(2.0, 4.0, 6.0)


def test_vector3_reverse_scalar_multiplication():
    vector = Vector3(1.0, 2.0, 3.0)

    assert 2 * vector == Vector3(2.0, 4.0, 6.0)


def test_vector3_component_wise_multiplication():
    vector = Vector3(2.0, 3.0, 4.0)

    assert vector * Vector3(5.0, 6.0, 7.0) == Vector3(10.0, 18.0, 28.0)


def test_vector3_component_wise_multiplication_can_mask_axes():
    vector = Vector3(10.0, 20.0, 30.0)

    assert vector * Vector3(1.0, 1.0, 0.0) == Vector3(10.0, 20.0, 0.0)


def test_vector3_subtraction():
    a = Vector3(10.0, 20.0, 30.0)
    b = Vector3(1.0, 2.0, 3.0)

    assert a - b == Vector3(9.0, 18.0, 27.0)


def test_vector3_magnitude():
    vector = Vector3(3.0, 4.0, 12.0)

    assert vector.magnitude == pytest.approx(13.0)


def test_vector3_zero_magnitude():
    assert Vector3(0.0, 0.0, 0.0).magnitude == 0.0


def test_vector3_distance_to():
    a = Vector3(1.0, 2.0, 3.0)
    b = Vector3(4.0, 6.0, 3.0)

    assert a.distance_to(b) == pytest.approx(5.0)


def test_vector3_distance_to_is_symmetric():
    a = Vector3(1.0, 2.0, 3.0)
    b = Vector3(7.0, -2.0, 5.0)

    assert a.distance_to(b) == pytest.approx(b.distance_to(a))


def test_vector3_distance_to_self_is_zero():
    vector = Vector3(1.0, 2.0, 3.0)

    assert vector.distance_to(vector) == 0.0


def test_vector3_copy():
    vector = Vector3(1.0, 2.0, 3.0)

    copied = vector.copy()

    assert copied == vector
    assert copied is not vector
