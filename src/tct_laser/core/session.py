import logging
import time
from dataclasses import dataclass

from .context import WorkerContext as Context
from .events import PositionChangedEvent
from .utils import Vector3, Waveform

logger = logging.getLogger(__name__)


@dataclass
class Session:
    context: Context

    def wait_moving(
        self,
        stage,
        timeout: float = 60.0,
        interval: float = 1 / 20,
    ) -> bool:
        t_timout = time.monotonic() + timeout
        while time.monotonic() < t_timout:
            if self.context.is_abort():
                return False
            self.context.sleep(interval)
            position = stage.get_position()
            self.context.submit_event(PositionChangedEvent(position))
            if not stage.is_moving():
                return True
        raise TimeoutError("Stage move timeout")

    def move_relative(self, offset: Vector3) -> bool:
        logger.info("move relative %.4G %.4G %.4G", offset.x, offset.y, offset.z)
        with self.context.station.stage.acquire(timeout=self.context.timeout) as stage:
            stage.move_relative(offset)
            return self.wait_moving(stage)

    def move_absolute(self, position: Vector3) -> bool:
        logger.info("move absolute %.4G %.4G %.4G", position.x, position.y, position.z)
        with self.context.station.stage.acquire(timeout=self.context.timeout) as stage:
            stage.move_absolute(position)
            return self.wait_moving(stage)

    def position(self) -> Vector3:
        with self.context.station.stage.acquire(timeout=self.context.timeout) as stage:
            return stage.get_position()

    def acquire_waveform(self, channel: str, timeout: float | None = None) -> Waveform:
        with self.context.station.scope.acquire(
            timeout=self.context.timeout if timeout is None else timeout
        ) as scope:
            if channel not in scope.get_channels():
                raise ValueError(f"Invalid waveform channel {channel}")

            scope.acquire()
            waveform = scope.read_waveform(channel)
            self.context.publish_waveform(waveform)
            return waveform
