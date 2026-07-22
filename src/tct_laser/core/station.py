from .actors import LaserActor, PowerMeterActor, ScopeActor, StageActor
from .actors.instrument import InstrumentActor
from .adapters import (
    laser_adapter_factory,
    power_meter_adapter_factory,
    scope_adapter_factory,
    stage_adapter_factory,
)
from .lease import Lease

__all__ = ["Station"]


class Station:
    def __init__(self) -> None:
        self._scope_actor = ScopeActor.start(
            name="scope",
            adapter_factory=scope_adapter_factory,
        )
        self._laser_actor = LaserActor.start(
            name="laser",
            adapter_factory=laser_adapter_factory,
        )
        self._stage_actor = StageActor.start(
            name="stage",
            adapter_factory=stage_adapter_factory,
        )
        self._power_meter_actor_1 = PowerMeterActor.start(
            name="power_meter_1",
            adapter_factory=power_meter_adapter_factory,
        )
        self._power_meter_actor_2 = PowerMeterActor.start(
            name="power_meter_2",
            adapter_factory=power_meter_adapter_factory,
        )
        self._power_meter_actor_3 = PowerMeterActor.start(
            name="power_meter_3",
            adapter_factory=power_meter_adapter_factory,
        )

        self.scope = Lease(self._scope_actor)
        self.laser = Lease(self._laser_actor)
        self.stage = Lease(self._stage_actor)
        self.power_meter_1 = Lease(self._power_meter_actor_1)
        self.power_meter_2 = Lease(self._power_meter_actor_2)
        self.power_meter_3 = Lease(self._power_meter_actor_3)

        self._actors = {
            "scope": self._scope_actor,
            "laser": self._laser_actor,
            "stage": self._stage_actor,
            "power_meter_1": self._power_meter_actor_1,
            "power_meter_2": self._power_meter_actor_2,
            "power_meter_3": self._power_meter_actor_3,
        }

    def leases(self) -> dict[str, Lease]:
        return {
            "scope": self.scope,
            "laser": self.laser,
            "stage": self.stage,
            "power_meter_1": self.power_meter_1,
            "power_meter_2": self.power_meter_2,
            "power_meter_3": self.power_meter_3,
        }

    def actors(self) -> dict[str, InstrumentActor]:
        return {name: actor for name, actor in self._actors.items()}

    def get_channels(self):
        return self._scope_actor.get_channels()

    def shutdown(self) -> None:
        self._scope_actor.stop()
        self._laser_actor.stop()
        self._stage_actor.stop()
        self._power_meter_actor_1.stop()
        self._power_meter_actor_2.stop()
        self._power_meter_actor_3.stop()

    def __getitem__(self, key: str) -> Lease:
        return self.leases()[key]
