from dataclasses import dataclass, field
from pathlib import Path
from queue import Empty, Queue
from threading import Event, RLock
from typing import Any, Iterable

from pathvalidate import sanitize_filepath

from .messages import (
    Connect,
    Disconnect,
    Failed,
    Finished,
    ParameterChanged,
    StatusMessage,
    StatusProgress,
)
from .station import Station
from .utils import Waveform

__all__ = ["ContextState", "MainContext", "WorkerContext", "create_contexts"]

DEFAULT_SAMPLE_NAME = "Unnamed"
DEFAULT_OUTPUT_PATH = str(Path.cwd())


@dataclass(slots=True)
class ContextState:
    station: Station
    inbox: Queue[Any] = field(default_factory=Queue)
    outbox: Queue[Any] = field(default_factory=Queue)
    shutdown_event: Event = field(default_factory=Event)
    abort_event: Event = field(default_factory=Event)
    lock: RLock = field(default_factory=RLock)
    waveform_live: bool = False
    waveform_channels: list[str] = field(default_factory=list)
    live_waveform_allowed: bool = True
    sample_name: str = DEFAULT_SAMPLE_NAME
    output_path: str = DEFAULT_OUTPUT_PATH


@dataclass(slots=True)
class MainContext:
    _state: ContextState

    @property
    def station(self) -> Station:
        return self._state.station

    def abort(self) -> None:
        self._state.abort_event.set()

    def shutdown(self) -> None:
        self._state.abort_event.set()
        self._state.shutdown_event.set()

    def tell(self, message: Any) -> None:
        self._state.inbox.put_nowait(message)

    def connect(self, instrument: str) -> None:
        self.tell(Connect(instrument))

    def disconnect(self, instrument: str) -> None:
        self.tell(Disconnect(instrument))

    def scope_channels(self) -> list[str]:
        return ["CHAN1", "CHAN2", "CHAN3", "CHAN4"]  # TODO

    def set_live_waveform(self, enabled: bool) -> None:
        with self._state.lock:
            self._state.waveform_live = enabled

    def set_waveform_channels(self, channels: Iterable[str]) -> None:
        with self._state.lock:
            self._state.waveform_channels = list(channels)

    def set_sample_name(self, sample_name: str) -> None:
        with self._state.lock:
            self._state.sample_name = sample_name.strip() or DEFAULT_SAMPLE_NAME

    def set_output_path(self, output_path: str) -> None:
        with self._state.lock:
            self._state.output_path = (
                str(sanitize_filepath(output_path)) or DEFAULT_OUTPUT_PATH
            )

    def drain_outbox(self):
        while True:
            try:
                self._state.outbox.get_nowait()
            except Empty:
                break

    def next_message(self) -> Any | None:
        try:
            return self._state.outbox.get_nowait()
        except Empty:
            return None


@dataclass(slots=True)
class WorkerContext:
    _state: ContextState
    timeout: float = 10.0

    @property
    def station(self) -> Station:
        return self._state.station

    def sleep(self, seconds: float) -> bool:
        return not self._state.abort_event.wait(seconds)

    def is_abort(self) -> bool:
        return self._state.abort_event.is_set()

    def cancel_abort(self) -> None:
        self._state.abort_event.clear()

    def is_shutdown(self) -> bool:
        return self._state.shutdown_event.is_set()

    def finish(self) -> None:
        self._tell(Finished())

    def fail(self, exc: Exception) -> None:
        self._tell(Failed(exc))

    def set_message(self, text: str) -> None:
        self._tell(StatusMessage(text))

    def set_progress(self, step: int, steps: int) -> None:
        self._tell(StatusProgress(step, steps))

    def set_parameter(self, parameter: Any) -> None:
        self._tell(ParameterChanged(parameter))

    def is_live_waveform(self) -> bool:
        with self._state.lock:
            return self._state.waveform_live

    def waveform_channels(self) -> list[str]:
        with self._state.lock:
            return self._state.waveform_channels.copy()

    def set_waveform(self, waveform: Waveform) -> None:
        self._tell(waveform)

    def set_live_waveform_allowed(self, state: bool) -> None:
        with self._state.lock:
            self._state.live_waveform_allowed = state

    def is_live_waveform_allowed(self) -> bool:
        with self._state.lock:
            return self._state.live_waveform_allowed

    def sample_name(self) -> str:
        with self._state.lock:
            return self._state.sample_name

    def output_path(self) -> str:
        with self._state.lock:
            return self._state.output_path

    def drain_inbox(self):
        while True:
            try:
                self._state.inbox.get_nowait()
            except Empty:
                break

    def next_message(self, timeout: float) -> Any | None:
        try:
            return self._state.inbox.get(timeout=timeout)
        except Empty:
            return None

    def _tell(self, message: Any) -> None:
        self._state.outbox.put_nowait(message)


def create_contexts(station: Station) -> tuple[MainContext, WorkerContext]:
    state = ContextState(station)
    return MainContext(state), WorkerContext(state)
