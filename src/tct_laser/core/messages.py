from typing import Any

import msgspec

from .utils import Vector3


class ConfigureMessage(msgspec.Struct, frozen=True):
    data: list[tuple[str, Any]]


class SetLaserOutput(msgspec.Struct, frozen=True):
    enabled: bool


class SetLaserFrequency(msgspec.Struct, frozen=True):
    frequency: float


class SetLaserTune(msgspec.Struct, frozen=True):
    tune: float


class SetPowerMeterWavelength(msgspec.Struct, frozen=True):
    wavelength: float


class SetPowerMeterAverageCount(msgspec.Struct, frozen=True):
    count: int


class MoveRelativeMessage(msgspec.Struct, frozen=True):
    offset: Vector3


class MoveAbsoluteMessage(msgspec.Struct, frozen=True):
    position: Vector3


class Connect(msgspec.Struct, frozen=True):
    instrument: str


class Disconnect(msgspec.Struct, frozen=True):
    instrument: str


class StatusMessage(msgspec.Struct, frozen=True):
    text: str


class StatusProgress(msgspec.Struct, frozen=True):
    step: int
    steps: int


class PositionChanged(msgspec.Struct, frozen=True):
    position: Vector3


class ParameterChanged(msgspec.Struct, frozen=True):
    parameter: Any


class Failed(msgspec.Struct, frozen=True):
    exc: Exception


class Finished(msgspec.Struct, frozen=True): ...


class PowerMeterPower(msgspec.Struct, frozen=True):
    index: int
    value: float | None


class EnabledChannelsChanged(msgspec.Struct, frozen=True):
    channels: list[str]


class LaserMetrics(msgspec.Struct, frozen=True):
    output: bool | None = None
    frequency: float | None = None
    tune: float | None = None
    head_temperature: float | None = None
    diode_temperature: bool | None = None


class PowerMeterWavelength(msgspec.Struct, frozen=True):
    index: int
    wavelength: int | None


class PowerMeterAverageCount(msgspec.Struct, frozen=True):
    index: int
    average_count: int | None
