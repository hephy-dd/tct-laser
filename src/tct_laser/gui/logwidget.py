"""
Qt widget for real-time display of Python logging output.

Provides `LoggerWidget`, a `QTextEdit` subclass that attaches to one or
more Python loggers and streams their records into the GUI. Messages are
formatted, color-coded per log level, and buffered to avoid UI bursts.
Useful for embedding live logs inside Qt applications.
"""

import logging
from collections import deque

from PySide6 import QtCore, QtGui, QtWidgets

__all__ = ["LogWidget"]


class _SignalHandler(logging.Handler):
    """A logging handler that forwards records via a Qt signal."""

    def __init__(
        self, signal: QtCore.SignalInstance, level: int = logging.NOTSET
    ) -> None:
        super().__init__(level)
        self._signal = signal

    def emit(self, record: logging.LogRecord) -> None:
        self._signal.emit(record)


class LogWidget(QtWidgets.QTextEdit):
    """A QTextEdit that displays Python logging records in real time."""

    record = QtCore.Signal(object)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setLineWrapMode(QtWidgets.QTextEdit.LineWrapMode.NoWrap)
        self._formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
        self._handlers: dict[logging.Logger, logging.Handler] = {}
        self._level_foregrounds: dict[int, QtGui.QColor] = {}

        # buffering
        self._queue: deque[logging.LogRecord] = deque()
        self._max_queue: int = 4096

        # flush timer (prevent UI bursts)
        self._interval_ms: int = 100
        self._flush_timer = QtCore.QTimer(self)
        self._flush_timer.setInterval(self._interval_ms)
        self._flush_timer.timeout.connect(self.flush_buffer)
        self._flush_timer.start()

        self.record.connect(
            self.enqueue_record, QtCore.Qt.ConnectionType.QueuedConnection
        )
        self.set_maximum_records(1024)

    def add_logger(self, logger: logging.Logger, *, level: int | None = None) -> None:
        """Attach the widget to a Python logger.

        Records from the logger will start appearing in this widget.
        Calling this multiple times with the same logger is a no-op.
        """
        if logger in self._handlers:
            return
        handler = _SignalHandler(self.record)
        handler.setFormatter(self._formatter)
        logger.addHandler(handler)
        if level is not None:
            handler.setLevel(level)
        self._handlers[logger] = handler

    def remove_logger(self, logger: logging.Logger) -> None:
        """Detach the widget from a previously added logger."""
        handler = self._handlers.pop(logger, None)
        if handler is not None:
            try:
                logger.removeHandler(handler)
            finally:
                handler.close()

    def set_maximum_records(self, count: int) -> None:
        """Limit the number of visible lines (Qt 'blocks') kept in the document."""
        self.document().setMaximumBlockCount(count)

    def set_formatter(self, formatter: logging.Formatter) -> None:
        """Set the formatter used to render records."""
        self._formatter = formatter
        # Update all existing handlers too
        for h in self._handlers.values():
            h.setFormatter(formatter)

    def set_foreground(self, level: int, color: QtGui.QColor) -> None:
        """Set the foreground color for a logging level."""
        self._level_foregrounds[level] = color

    def set_update_interval(self, ms: int) -> None:
        """How often the widget flushes queued records to the UI (milliseconds)."""
        self._interval_ms = max(10, int(ms))
        self._flush_timer.setInterval(self._interval_ms)

    def set_max_queue(self, size: int) -> None:
        """Set the maximum number of records kept in the buffer before flushing/dropping."""
        self._max_queue = max(1, int(size))

    @QtCore.Slot(logging.LogRecord)
    def enqueue_record(self, record: logging.LogRecord) -> None:
        """Receive a record (via signal) and buffer it to avoid UI bursts."""
        if len(self._queue) >= self._max_queue:
            # drop oldest to prevent unbounded growth
            self._queue.popleft()
        self._queue.append(record)

    @QtCore.Slot()
    def flush_buffer(self) -> None:
        """Drain buffered records and append to the view in one pass."""
        if not self._queue:
            return

        # snapshot & clear quickly to minimize time spent holding data
        records: list[logging.LogRecord] = list(self._queue)
        self._queue.clear()

        # scroll behavior: follow tail only if already at bottom
        sb = self.verticalScrollBar()
        at_bottom = sb.value() >= sb.maximum() - 2

        doc = self.document()
        cursor = QtGui.QTextCursor(doc)
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)

        # Ensure no leading blank line on an empty document
        last = doc.lastBlock()
        need_new_block = last.isValid() and last.length() > 1

        # Append all records
        for i, record in enumerate(records):
            if need_new_block or i > 0:
                cursor.insertBlock()

            fmt = QtGui.QTextCharFormat()
            color = self._level_foregrounds.get(
                getattr(record, "levelno", logging.INFO)
            )
            if color is not None:
                fmt.setForeground(color)

            try:
                text = self._formatter.format(record)
            except Exception:
                text = f"{record.levelname}: {record.getMessage()}"

            cursor.insertText(text, fmt)

        if at_bottom:
            sb.setValue(sb.maximum())
