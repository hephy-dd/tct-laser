from collections.abc import Callable
from typing import Any

from PySide6 import QtCore, QtWidgets

from ..core.context import WorkerContext

__all__ = ["OperationWidget"]


class OperationWidget(QtWidgets.QWidget):
    """Base class for operation widgets."""

    start_triggered = QtCore.Signal()
    abort_triggered = QtCore.Signal()
    event_submitted = QtCore.Signal(object)

    def set_inputs_enabled(self, enabled: bool) -> None: ...

    def set_abort_enabled(self, enabled: bool) -> None: ...

    def clear(self) -> None: ...

    def handle_event(self, event: Any) -> None: ...

    def submit_event(self, event: Any) -> None:
        self.event_submitted.emit(event)

    def read_settings(self, settings: QtCore.QSettings) -> None: ...

    def write_settings(self, settings: QtCore.QSettings) -> None: ...

    def create_runner(self) -> Callable[[WorkerContext], None]: ...
