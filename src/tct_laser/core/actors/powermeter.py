from dataclasses import dataclass

from ..adapter import PowerMeterAdapter
from .instrument import InstrumentActor

__all__ = ["PowerMeterActor"]


class PowerMeterActor(InstrumentActor):
    def identify(self) -> str:
        return self.ask(Identify())

    def get_wavelength(self) -> float:
        return self.ask(GetWavelength())

    def set_wavelength(self, wavelength: float) -> None:
        self.ask(SetWavelength(wavelength))

    def get_average_count(self) -> int:
        return self.ask(GetAverageCount())

    def set_average_count(self, average_count: int) -> None:
        self.ask(SetAverageCount(average_count))

    def measure_power(self) -> float:
        return self.ask(MeasurePower())


@dataclass(frozen=True, slots=True)
class Identify:
    def __call__(self, power_meter: PowerMeterAdapter) -> str:
        return power_meter.identify()


@dataclass(frozen=True, slots=True)
class GetWavelength:
    def __call__(self, power_meter: PowerMeterAdapter) -> float:
        return power_meter.get_wavelength()


@dataclass(frozen=True, slots=True)
class SetWavelength:
    wavelength: float

    def __call__(self, power_meter: PowerMeterAdapter) -> None:
        power_meter.set_wavelength(self.wavelength)


@dataclass(frozen=True, slots=True)
class GetAverageCount:
    def __call__(self, power_meter: PowerMeterAdapter) -> int:
        return power_meter.get_average_count()


@dataclass(frozen=True, slots=True)
class SetAverageCount:
    average_count: int

    def __call__(self, power_meter: PowerMeterAdapter) -> None:
        power_meter.set_average_count(self.average_count)


@dataclass(frozen=True, slots=True)
class MeasurePower:
    def __call__(self, power_meter: PowerMeterAdapter) -> float:
        return power_meter.measure_power()
