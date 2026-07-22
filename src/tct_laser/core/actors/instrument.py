from dataclasses import dataclass
from enum import Enum, auto
from threading import RLock
from typing import Any

from ..actor import ThreadingActor
from ..adapters import AdapterFactory
from ..resource import (
    ResourceConfig,
    default_resource_factory,
)


class ConnectionState(Enum):
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    ERROR = auto()


@dataclass(frozen=True, slots=True)
class ConnectInstrument: ...


@dataclass(frozen=True, slots=True)
class DisconnectInstrument: ...


class InstrumentActor(ThreadingActor):
    def __init__(
        self,
        name: str,
        adapter_factory: AdapterFactory,
        resource_config: ResourceConfig | None = None,
    ) -> None:
        super().__init__()
        self._name = name

        self._adapter_factory: AdapterFactory = adapter_factory

        if resource_config is None:
            resource_config = ResourceConfig()

        self._resource_config: ResourceConfig = resource_config
        self._resource_config_lock = RLock()

        self._connection_state = ConnectionState.DISCONNECTED
        self._connection_state_lock = RLock()

        self._resource: Any | None = None
        self._instrument: Any | None = None

    def resource_config(self) -> ResourceConfig:
        with self._resource_config_lock:
            return self._resource_config

    def set_resource_config(self, resource_config: ResourceConfig) -> None:
        with self._resource_config_lock:
            self._resource_config = resource_config

    def connection_state(self) -> ConnectionState:
        with self._connection_state_lock:
            return self._connection_state

    @property
    def is_connected(self) -> bool:
        return self.connection_state() == ConnectionState.CONNECTED

    def connect(self) -> None:
        self.ask(ConnectInstrument())

    def disconnect(self) -> None:
        self.ask(DisconnectInstrument())

    def handle_message(self, message: Any) -> Any:
        match message:
            case ConnectInstrument():
                self._connect()
            case DisconnectInstrument():
                self._disconnect()
            case _:
                return self._handle(message)

    def _set_connection_state(self, connection_state: ConnectionState) -> None:
        with self._connection_state_lock:
            self._connection_state = connection_state

    def _connect(self) -> None:
        if self.connection_state() == ConnectionState.CONNECTED:
            return

        with self._resource_config_lock:
            resource_config = self._resource_config

        try:
            resource = default_resource_factory(resource_config)
        except Exception:
            self._set_connection_state(ConnectionState.ERROR)
            raise

        try:
            adapter_cls = self._adapter_factory(resource_config.model)
            instrument = adapter_cls(resource)
        except Exception:
            self._set_connection_state(ConnectionState.ERROR)
            resource.close()
            raise

        self._resource = resource
        self._instrument = instrument
        self._set_connection_state(ConnectionState.CONNECTED)

    def _disconnect(self) -> None:
        if self.connection_state() == ConnectionState.DISCONNECTED:
            return

        resource = self._resource
        if resource is not None:
            try:
                resource.close()
            finally:
                self._instrument = None
                self._resource = None
                self._set_connection_state(ConnectionState.DISCONNECTED)

    def _handle(self, message: Any) -> Any:
        if self.connection_state() == ConnectionState.CONNECTED:
            instrument = self._instrument

            if instrument is None:
                raise RuntimeError("connected state without an instrument")

            try:
                return message(instrument)
            except ConnectionError:
                self._set_connection_state(ConnectionState.ERROR)
                raise
        else:
            raise RuntimeError("not connected")
