from dataclasses import dataclass

from ..adapter import ScopeAdapter
from ..waveform import Waveform
from .instrument import InstrumentActor

__all__ = ["ScopeActor"]


class ScopeActor(InstrumentActor):
    def identify(self) -> str:
        return self.ask(Identify())

    def get_channels(self) -> list[str]:
        return self.ask(GetChannels())

    def acquire(self) -> None:
        self.ask(Acquire())

    def read_waveform(self, channel: str) -> Waveform:
        return self.ask(ReadWaveform(channel))

    def set_average_count(self, average_count: int) -> None:
        self.ask(SetAverageCount(average_count))

    def configure(self) -> None:
        self.ask(Configure())


@dataclass(frozen=True, slots=True)
class Identify:
    def __call__(self, scope: ScopeAdapter) -> str:
        return scope.identify()


@dataclass(frozen=True, slots=True)
class GetChannels:
    def __call__(self, scope: ScopeAdapter) -> list[str]:
        return scope.get_channels()


@dataclass(frozen=True, slots=True)
class Acquire:
    def __call__(self, scope: ScopeAdapter) -> None:
        scope.acquire()


@dataclass(frozen=True, slots=True)
class ReadWaveform:
    channel: str

    def __call__(self, scope: ScopeAdapter) -> Waveform:
        return scope.read_waveform(self.channel)


@dataclass(frozen=True, slots=True)
class SetAverageCount:
    average_count: int

    def __call__(self, scope: ScopeAdapter) -> None:
        return scope.set_average_count(self.average_count)


@dataclass(frozen=True, slots=True)
class Configure:
    def __call__(self, scope: ScopeAdapter) -> None:
        return scope.configure()
