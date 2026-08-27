from dataclasses import dataclass

from ..adapter import LaserAdapter
from .instrument import InstrumentActor

__all__ = ["LaserActor"]


class LaserActor(InstrumentActor):
    def identify(self) -> str:
        return self.ask(Identify())

    def get_output(self) -> bool:
        return self.ask(GetOutput())

    def set_output(self, enabled: bool) -> None:
        self.ask(SetOutput(enabled))

    def get_frequency(self) -> float:
        return self.ask(GetFrequency())

    def set_frequency(self, frequency: float) -> None:
        self.ask(SetFrequency(frequency))

    def get_tune(self) -> float:
        return self.ask(GetTune())

    def set_tune(self, tune: float) -> None:
        self.ask(SetTune(tune))

    def get_head_temperature(self) -> float:
        return self.ask(GetHeadTemperature())

    def get_diode_temperature(self) -> bool | None:
        return self.ask(GetDiodeTemperature())


@dataclass(frozen=True, slots=True)
class Identify:
    def __call__(self, laser: LaserAdapter) -> str:
        return laser.identify()


@dataclass(frozen=True, slots=True)
class GetOutput:
    def __call__(self, laser: LaserAdapter) -> float:
        return laser.get_output()


@dataclass(frozen=True, slots=True)
class SetOutput:
    enabled: bool

    def __call__(self, laser: LaserAdapter) -> None:
        return laser.set_output(self.enabled)


@dataclass(frozen=True, slots=True)
class GetFrequency:
    def __call__(self, laser: LaserAdapter) -> float:
        return laser.get_frequency()


@dataclass(frozen=True, slots=True)
class SetFrequency:
    frequency: float

    def __call__(self, laser: LaserAdapter) -> None:
        return laser.set_frequency(self.frequency)


@dataclass(frozen=True, slots=True)
class GetTune:
    def __call__(self, laser: LaserAdapter) -> float:
        return laser.get_tune()


@dataclass(frozen=True, slots=True)
class SetTune:
    tune: float

    def __call__(self, laser: LaserAdapter) -> None:
        return laser.set_tune(self.tune)


@dataclass(frozen=True, slots=True)
class GetHeadTemperature:
    def __call__(self, laser: LaserAdapter) -> float:
        return laser.get_head_temperature()


@dataclass(frozen=True, slots=True)
class GetDiodeTemperature:
    def __call__(self, laser: LaserAdapter) -> bool | None:
        return laser.get_diode_temperature()
