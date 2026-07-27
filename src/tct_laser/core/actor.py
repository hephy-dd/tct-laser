from concurrent.futures import Future
from dataclasses import dataclass
from queue import Empty, Queue
from threading import Event, Thread
from typing import Any, Self


@dataclass(frozen=True, slots=True)
class Envelope:
    message: Any
    future: Future[Any]


class ThreadingActor:
    def __init__(self) -> None:
        self._inbox: Queue[Envelope] = Queue()
        self._stop_event = Event()
        self._thread = Thread(target=self._run, daemon=True)

    @classmethod
    def start(cls, *args: Any, **kwargs: Any) -> Self:
        actor = cls(*args, **kwargs)
        actor._thread.start()  # type: ignore
        return actor

    def ask(self, message: Any) -> Any:
        if self._stop_event.is_set():
            raise RuntimeError("Actor has been stopped")

        future: Future[Any] = Future()
        self._inbox.put_nowait(Envelope(message, future))
        return future.result()

    def handle_message(self, message: Any) -> Any:
        raise NotImplementedError

    def stop(self) -> None:
        self._stop_event.set()

        if self._thread.is_alive():
            self._thread.join()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                envelope = self._inbox.get(timeout=0.1)
            except Empty:
                continue

            try:
                result = self.handle_message(envelope.message)
            except BaseException as exc:
                envelope.future.set_exception(exc)
            else:
                envelope.future.set_result(result)

        self._drain_inbox()

    def _drain_inbox(self) -> None:
        while True:
            try:
                envelope = self._inbox.get_nowait()
            except Empty:
                break
            else:
                envelope.future.cancel()
