import math
from collections.abc import Iterator

import msgspec

__all__ = ["Vector3"]


class Vector3(msgspec.Struct, frozen=True):
    x: float
    y: float
    z: float

    def __iter__(self) -> Iterator[float]:
        yield self.x
        yield self.y
        yield self.z

    def to_tuple(self) -> tuple[float, float, float]:
        return self.x, self.y, self.z

    def __add__(self, other: Vector3) -> Vector3:
        return Vector3(
            self.x + other.x,
            self.y + other.y,
            self.z + other.z,
        )

    def __sub__(self, other: Vector3) -> Vector3:
        return Vector3(
            self.x - other.x,
            self.y - other.y,
            self.z - other.z,
        )

    def __mul__(self, other: float | Vector3) -> Vector3:
        if isinstance(other, Vector3):
            return Vector3(
                self.x * other.x,
                self.y * other.y,
                self.z * other.z,
            )

        if isinstance(other, (int, float)):
            return Vector3(
                self.x * other,
                self.y * other,
                self.z * other,
            )

        return NotImplemented

    def __rmul__(self, other: float) -> Vector3:
        return self * other

    @property
    def magnitude(self) -> float:
        return math.hypot(self.x, self.y, self.z)

    def distance_to(self, other: Vector3) -> float:
        return (self - other).magnitude

    def copy(self) -> Vector3:
        return type(self)(
            x=self.x,
            y=self.y,
            z=self.z,
        )
