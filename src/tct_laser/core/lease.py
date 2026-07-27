from collections.abc import Generator
from contextlib import contextmanager
from threading import Lock


class LeaseTimeoutError(TimeoutError): ...


class Lease[T]:
    def __init__(self, resource: T) -> None:
        self._resource = resource
        self._lock = Lock()

    @contextmanager
    def acquire(self, timeout: float | None = None) -> Generator[T]:
        acquired = (
            self._lock.acquire()
            if timeout is None
            else self._lock.acquire(timeout=timeout)
        )
        if not acquired:
            raise LeaseTimeoutError()
        try:
            yield self._resource
        finally:
            self._lock.release()
