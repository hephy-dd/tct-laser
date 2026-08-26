from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from queue import Empty, Queue
from threading import Event, RLock
from typing import Any

import msgspec
from pathvalidate import sanitize_filepath

from .events import (
    ConnectEvent,
    DisconnectEvent,
    FailedEvent,
    FinishedEvent,
    StatusMessageEvent,
    StatusProgressEvent,
    WaveformEvent,
)
from .station import Station
from .utils import Waveform

__all__ = ["ContextState", "MainContext", "WorkerContext", "create_contexts"]

DEFAULT_SAMPLE_NAME = "Unnamed"
DEFAULT_OUTPUT_PATH = str(Path.cwd())

type OperationRunner = Callable[[MainContext], None]


class RunOperationEvent(msgspec.Struct, frozen=True):
    operation_runner: OperationRunner


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

    def submit_event(self, event: Any) -> None:
        self._state.inbox.put_nowait(event)

    def submit_operation(self, operation_runner: OperationRunner) -> None:
        self.submit_event(RunOperationEvent(operation_runner=operation_runner))

    def connect(self, instrument: str) -> None:
        self.submit_event(ConnectEvent(instrument))

    def disconnect(self, instrument: str) -> None:
        self.submit_event(DisconnectEvent(instrument))

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

    def next_event(self) -> Any | None:
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
        self._tell(FinishedEvent())

    def fail(self, exc: Exception) -> None:
        self._tell(FailedEvent(exc))

    def set_status_message(self, text: str) -> None:
        self._tell(StatusMessageEvent(text))

    def set_status_progress(self, step: int, steps: int) -> None:
        self._tell(StatusProgressEvent(step, steps))

    def submit_event(self, event: Any) -> None:
        self._tell(event)

    def is_live_waveform(self) -> bool:
        with self._state.lock:
            return self._state.waveform_live

    def waveform_channels(self) -> list[str]:
        with self._state.lock:
            return self._state.waveform_channels.copy()

    def publish_waveform(self, waveform: Waveform) -> None:
        self._tell(WaveformEvent(waveform))

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

    def next_event(self, timeout: float) -> Any | None:
        try:
            return self._state.inbox.get(timeout=timeout)
        except Empty:
            return None

    def _tell(self, message: Any) -> None:
        self._state.outbox.put_nowait(message)


def create_contexts(station: Station) -> tuple[MainContext, WorkerContext]:
    state = ContextState(station)
    return MainContext(state), WorkerContext(state)
