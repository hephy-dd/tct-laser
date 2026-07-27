import logging
from threading import Thread
from types import TracebackType
from typing import Protocol, Self

logger = logging.getLogger(__name__)


class Worker(Protocol):
    def run(self) -> None: ...
    def stop(self) -> None: ...


class BackgroundService:
    def __init__(self, name: str, worker: Worker) -> None:
        self.name = name
        self.worker = worker
        self.thread = Thread(target=worker.run, name=name)

    def start(self) -> None:
        logger.info("starting [%s] thread...", self.name)
        self.thread.start()

    def stop(self) -> None:
        logger.info("stopping [%s] thread...", self.name)
        self.worker.stop()
        self.thread.join(timeout=10)

        if self.thread.is_alive():
            logger.warning("[%s] thread did not stop within timeout.", self.name)
        else:
            logger.info("stopped [%s] thread.", self.name)


class ServiceGroup:
    def __init__(self, services: list[BackgroundService]) -> None:
        self.services = services

    def __enter__(self) -> Self:
        for service in self.services:
            service.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        for service in reversed(self.services):
            service.stop()
