from typing import Any

from comet.driver.hephy.corvuscontroller import CorvusController
from comet.driver.itk.corvustt import CorvusTT
from comet.driver.mbi.tablecontrol import TableControl

from ..geometry import Vector3

__all__ = [
    "CorvusControllerAdapter",
    "CorvusTTAdapter",
    "TableControlAdapter",
]


class CorvusTTAdapter:
    def __init__(self, resource: Any) -> None:
        self._resource = resource
        self._driver = CorvusTT(resource)

    def identify(self) -> str:
        return self._driver.identify()

    def configure(self) -> None:
        self._resource.write("0 mode")  # host mode, writes control bytes to buffer
        self._resource.query("version")  # drain control bytes from buffer

    def get_position(self) -> Vector3:
        x, y, z = self._driver.position
        return Vector3(x, y, z)

    def is_moving(self) -> bool:
        return self._driver.is_moving

    def move_relative(self, offset: Vector3) -> None:
        self._driver.move_relative((offset.x, offset.y, offset.z))

    def move_absolute(self, position: Vector3) -> None:
        self._driver.move_absolute((position.x, position.y, position.z))


class CorvusControllerAdapter:
    def __init__(self, resource: Any) -> None:
        self._driver = CorvusController(resource)

    def identify(self) -> str:
        return self._driver.identify()

    def configure(self) -> None: ...

    def get_position(self) -> Vector3:
        x, y, z = self._driver.position
        return Vector3(x, y, z)

    def is_moving(self) -> bool:
        return self._driver.is_moving

    def move_relative(self, offset: Vector3) -> None:
        self._driver.move_relative((offset.x, offset.y, offset.z))

    def move_absolute(self, position: Vector3) -> None:
        self._driver.move_absolute((position.x, position.y, position.z))


class TableControlAdapter:
    def __init__(self, resource: Any) -> None:
        self._driver = TableControl(resource)

    def identify(self) -> str:
        return self._driver.identify()

    def configure(self) -> None: ...

    def get_position(self) -> Vector3:
        x, y, z = self._driver.position
        return Vector3(x, y, z)

    def is_moving(self) -> bool:
        return self._driver.is_moving

    def move_relative(self, offset: Vector3) -> None:
        self._driver.move_relative((offset.x, offset.y, offset.z))

    def move_absolute(self, position: Vector3) -> None:
        self._driver.move_absolute((position.x, position.y, position.z))
