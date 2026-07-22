from typing import Any

from comet.driver.hephy.pilascontroller import PilasController
from comet.driver.nkt_photonics.pilas import PILAS

__all__ = ["PILASAdapter", "PilasControllerAdapter"]


class PILASAdapter:
    def __init__(self, resource: Any) -> None:
        self._driver = PILAS(resource)

    def identify(self) -> str:
        return self._driver.identify()

    def configure(self) -> None: ...

    def get_output(self) -> bool:
        return self._driver.output

    def set_output(self, enabled: bool) -> None:
        self._driver.output = enabled

    def get_frequency(self) -> float:
        return float(self._driver.frequency)

    def set_frequency(self, frequency: float) -> None:
        self._driver.frequency = int(frequency)

    def get_tune(self) -> float:
        return self._driver.tune

    def set_tune(self, tune: float) -> None:
        self._driver.tune = tune

    def get_head_temperature(self) -> float:
        return self._driver.laser_head_temperature

    def get_diode_temperature(self) -> bool:
        return self._driver.laser_diode_temperature


class PilasControllerAdapter:
    def __init__(self, resource: Any) -> None:
        self._driver = PilasController(resource)

    def identify(self) -> str:
        return self._driver.identify()

    def configure(self) -> None: ...

    def get_output(self) -> bool:
        return self._driver.output

    def set_output(self, enabled: bool) -> None:
        self._driver.output = enabled

    def get_frequency(self) -> float:
        return float(self._driver.frequency)

    def set_frequency(self, frequency: float) -> None:
        self._driver.frequency = int(frequency)

    def get_tune(self) -> float:
        return self._driver.tune

    def set_tune(self, tune: float) -> None:
        self._driver.tune = tune

    def get_head_temperature(self) -> float:
        return self._driver.laser_head_temperature

    def get_diode_temperature(self) -> bool:
        raise NotImplementedError
