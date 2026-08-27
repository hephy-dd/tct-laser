from dataclasses import dataclass

from ..adapter import StageAdapter
from ..geometry import Vector3
from .instrument import InstrumentActor

__all__ = ["StageActor"]


class StageActor(InstrumentActor):
    def identify(self) -> str:
        return self.ask(Identify())

    def get_position(self) -> Vector3:
        return self.ask(GetPosition())

    def is_moving(self) -> bool:
        return self.ask(IsMoving())

    def move_relative(self, offset: Vector3) -> None:
        self.ask(MoveRelative(offset))

    def move_absolute(self, position: Vector3) -> None:
        self.ask(MoveAbsolute(position))


@dataclass(frozen=True, slots=True)
class Identify:
    def __call__(self, stage: StageAdapter) -> str:
        return stage.identify()


@dataclass(frozen=True, slots=True)
class GetPosition:
    def __call__(self, stage: StageAdapter) -> Vector3:
        return stage.get_position()


@dataclass(frozen=True, slots=True)
class IsMoving:
    def __call__(self, stage: StageAdapter) -> bool:
        return stage.is_moving()


@dataclass(frozen=True, slots=True)
class MoveRelative:
    offset: Vector3

    def __call__(self, stage: StageAdapter) -> None:
        stage.move_relative(self.offset)


@dataclass(frozen=True, slots=True)
class MoveAbsolute:
    position: Vector3

    def __call__(self, stage: StageAdapter) -> None:
        stage.move_absolute(self.position)
