from typing import Any

from comet.driver.thorlabs.pm100 import PM100

__all__ = ["PM100Adapter"]


class PM100Adapter:
    def __init__(self, resource: Any) -> None:
        self._driver = PM100(resource)

    def identify(self) -> str:
        return self._driver.identify()

    def configure(self) -> None: ...

    def get_wavelength(self) -> float:
        return float(self._driver.wavelength)

    def set_wavelength(self, wavelength: float) -> None:
        self._driver.wavelength = int(wavelength)

    def get_average_count(self) -> int:
        return int(self._driver.average_count)

    def set_average_count(self, average_count: int) -> None:
        self._driver.average_count = int(average_count)

    def measure_power(self) -> float:
        return float(self._driver.measure_power())
