from collections.abc import Mapping
from typing import Protocol, TypeVar

from ..adapter import LaserAdapter, PowerMeterAdapter, ScopeAdapter, StageAdapter
from .laser import PILASAdapter, PilasControllerAdapter
from .powermeter import PM100Adapter
from .scope import RTO6Adapter, RTP164Adapter
from .stage import CorvusControllerAdapter, CorvusTTAdapter, TableControlAdapter

__all__ = [
    "AdapterFactory",
    "scope_adapter_factory",
    "laser_adapter_factory",
    "stage_adapter_factory",
    "power_meter_adapter_factory",
]

scope_adapter_registry: dict[str, type[ScopeAdapter]] = {
    "urn:comet:model:rohde_schwarz:rto6": RTO6Adapter,
    "urn:comet:model:rohde_schwarz:rtp164": RTP164Adapter,
}

laser_adapter_registry: dict[str, type[LaserAdapter]] = {
    "urn:comet:model:hephy:pilascontroller": PilasControllerAdapter,
    "urn:comet:model:nkt_photonics:pilas": PILASAdapter,
}


stage_adapter_registry: dict[str, type[StageAdapter]] = {
    "urn:comet:model:itk:corvustt": CorvusTTAdapter,
    "urn:comet:model:hephy:corvuscontroller": CorvusControllerAdapter,
    "urn:comet:model:mbi:tablecontrol": TableControlAdapter,
}


power_meter_adapter_registry: dict[str, type[PowerMeterAdapter]] = {
    "urn:comet:model:thorlabs:pm100": PM100Adapter,
}


T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)


class AdapterFactory(Protocol[T_co]):
    def __call__(self, urn: str) -> type[T_co]: ...


def _adapter_from_registry(
    urn: str,
    registry: Mapping[str, type[T]],
    kind: str,
) -> type[T]:
    try:
        return registry[urn]
    except KeyError:
        raise ValueError(f"No such {kind} with URN: {urn!r}") from None


def scope_adapter_factory(urn: str) -> type[ScopeAdapter]:
    return _adapter_from_registry(urn, scope_adapter_registry, "scope")


def laser_adapter_factory(urn: str) -> type[LaserAdapter]:
    return _adapter_from_registry(urn, laser_adapter_registry, "laser")


def stage_adapter_factory(urn: str) -> type[StageAdapter]:
    return _adapter_from_registry(urn, stage_adapter_registry, "stage")


def power_meter_adapter_factory(urn: str) -> type[PowerMeterAdapter]:
    return _adapter_from_registry(urn, power_meter_adapter_registry, "power meter")
