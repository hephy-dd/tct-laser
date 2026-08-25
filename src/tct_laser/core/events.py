from typing import Any

import msgspec

from .utils import Vector3, Waveform


class StatusMessageEvent(msgspec.Struct, frozen=True):
    text: str


class StatusProgressEvent(msgspec.Struct, frozen=True):
    step: int
    steps: int


class FailedEvent(msgspec.Struct, frozen=True):
    exc: Exception


class FinishedEvent(msgspec.Struct, frozen=True): ...


class ConnectEvent(msgspec.Struct, frozen=True):
    instrument: str


class DisconnectEvent(msgspec.Struct, frozen=True):
    instrument: str


class ConfigureEvent(msgspec.Struct, frozen=True):
    data: list[tuple[str, Any]]


class SetLaserOutput(msgspec.Struct, frozen=True):
    enabled: bool


class SetLaserFrequency(msgspec.Struct, frozen=True):
    frequency: float


class SetLaserTune(msgspec.Struct, frozen=True):
    tune: float


class LaserMetrics(msgspec.Struct, frozen=True):
    output: bool | None = None
    frequency: float | None = None
    tune: float | None = None
    head_temperature: float | None = None
    diode_temperature: bool | None = None


class SetPowerMeterWavelength(msgspec.Struct, frozen=True):
    wavelength: int


class SetPowerMeterAverageCount(msgspec.Struct, frozen=True):
    count: int


class PowerMeterWavelength(msgspec.Struct, frozen=True):
    index: int
    wavelength: int | None


class PowerMeterAverageCount(msgspec.Struct, frozen=True):
    index: int
    average_count: int | None


class PowerMeterPower(msgspec.Struct, frozen=True):
    index: int
    value: float | None


class PositionChangedEvent(msgspec.Struct, frozen=True):
    position: Vector3


class MoveRelativeEvent(msgspec.Struct, frozen=True):
    offset: Vector3


class MoveAbsoluteEvent(msgspec.Struct, frozen=True):
    position: Vector3


class EnabledChannelsChanged(msgspec.Struct, frozen=True):
    channels: list[str]


class WaveformEvent(msgspec.Struct, frozen=True):
    waveform: Waveform
