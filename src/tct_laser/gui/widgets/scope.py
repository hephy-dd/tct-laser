from collections.abc import Iterable

import numpy as np
import pyqtgraph as pg
from PySide6 import QtCore, QtGui, QtWidgets

from tct_laser.core.waveform import Waveform

__all__ = ["ScopeGroupBox"]

CHANNEL_COLORS = [
    "yellow",
    "green",
    "red",
    "blue",
    "orange",
    "purple",
    "cyan",
    "magenta",
]


class ScopePlotWidget(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._colors = CHANNEL_COLORS

        self._plot_widget = pg.PlotWidget(title="Oscilloscope")
        self._plot_widget.setLabel("bottom", "Time [ns]")
        self._plot_widget.setLabel("left", "Ampl [V]")

        top_axis = self._plot_widget.getAxis("top")
        top_axis.setStyle(showValues=True)
        top_axis.show()

        right_axis = self._plot_widget.getAxis("right")
        right_axis.setStyle(showValues=True)
        right_axis.show()

        self._plot_widget.showGrid(x=True, y=True, alpha=0.4)

        self._plot_widget.addLegend()

        self._curves: dict[str, pg.PlotDataItem] = {}

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._plot_widget)

    def clear_channels(self) -> None:
        for curve in self._curves.values():
            self._plot_widget.removeItem(curve)
            curve.deleteLater()
        self._curves.clear()

    def add_channel(self, channel: str) -> None:
        i = len(self._curves)
        self._curves[channel] = self._plot_widget.plot(
            [],
            [],
            pen=pg.mkPen(color=self._colors[i % len(self._colors)], width=1),
            name=channel,
        )

    def set_waveform(self, waveform: Waveform) -> None:
        if waveform.channel not in self._curves:
            return

        x = np.asarray(waveform.x)
        y = np.asarray(waveform.y)

        if x.size == 0 or y.size == 0:
            return

        self._curves[waveform.channel].setData(x, y)

    def clear_waveform(self, channel: str) -> None:
        curve = self._curves.get(channel)
        if curve is not None:
            curve.clear()

    def clear_waveforms(self) -> None:
        for channel in self._curves:
            self.clear_waveform(channel)

    def set_enabled_channels(self, channels: list[str]) -> None:
        self._enabled_channels = set(channels)
        self.clear_disabled_channels()

    def clear_disabled_channels(self) -> None:
        for channel in self._curves:
            if channel not in self._enabled_channels:
                self.clear_waveform(channel)


class ScopeGroupBox(QtWidgets.QGroupBox):
    preview_toggled = QtCore.Signal(bool)
    channels_changed = QtCore.Signal(list)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.setTitle("Scope")

        self._colors = CHANNEL_COLORS

        self._live_preview_button = QtWidgets.QPushButton(self)
        self._live_preview_button.setText("&Live Preview")
        self._live_preview_button.setCheckable(True)
        self._live_preview_button.toggled.connect(self._on_live_preview_toggled)

        self._plot_widget = ScopePlotWidget(self)

        self._channels_label = QtWidgets.QLabel(self)
        self._channels_label.setText("Channels")

        self._channel_check_boxes: dict[str, QtWidgets.QCheckBox] = {}
        self._channel_layout = QtWidgets.QHBoxLayout()

        self.channels_changed.connect(self._plot_widget.set_enabled_channels)

        channels_layout = QtWidgets.QHBoxLayout()
        channels_layout.addWidget(self._channels_label)
        channels_layout.addLayout(self._channel_layout)

        form_layout = QtWidgets.QHBoxLayout()
        form_layout.addWidget(self._live_preview_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(channels_layout)
        layout.addLayout(form_layout)
        layout.addWidget(self._plot_widget)

    def set_channels(self, channels: Iterable[str]) -> None:
        while self._channel_layout.count():  # QtWidgets.QHBoxLayout
            item = self._channel_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is None:
                continue
            widget.setParent(None)
            widget.deleteLater()
        self._channel_check_boxes = {}
        self._plot_widget.clear_channels()
        for i, channel in enumerate(channels):
            check_box = QtWidgets.QCheckBox(self)
            check_box.setText(channel)

            color = self._colors[i % len(self._colors)]

            pixmap = QtGui.QPixmap(12, 12)
            pixmap.fill(QtGui.QColor(color))

            check_box.setIcon(QtGui.QIcon(pixmap))
            check_box.setIconSize(QtCore.QSize(12, 12))

            check_box.stateChanged.connect(self._on_channel_changed)
            self._channel_layout.addWidget(check_box)
            self._channel_check_boxes[channel] = check_box
            self._plot_widget.add_channel(channel)

    def active_channels(self) -> list[str]:
        return [
            channel
            for channel, widget in self._channel_check_boxes.items()
            if widget.isChecked()
        ]

    def disabled_channels(self) -> list[str]:
        return [
            channel
            for channel, widget in self._channel_check_boxes.items()
            if not widget.isChecked()
        ]

    def set_active_channels(self, channels: Iterable[str]) -> None:
        for channel, widget in self._channel_check_boxes.items():
            widget.setChecked(channel in channels)

    def set_inputs_enabled(self, enabled: bool) -> None:
        self._live_preview_button.setEnabled(enabled)
        for check_box in self._channel_check_boxes.values():
            check_box.setEnabled(enabled)

    @QtCore.Slot(object)
    def set_waveform(self, waveform):
        self._plot_widget.set_waveform(waveform)
        self._clear_disabled_waveforms()

    @QtCore.Slot()
    def clear_waveforms(self, waveform):
        self._plot_widget.clear_waveforms()

    @QtCore.Slot(int)
    def _on_channel_changed(self) -> None:
        channels = self.active_channels()
        self.channels_changed.emit(channels)
        self._clear_disabled_waveforms()

    @QtCore.Slot(bool)
    def _on_live_preview_toggled(self, state: bool) -> None:
        self.preview_toggled.emit(state)

    def _clear_disabled_waveforms(self) -> None:
        for channel in self.disabled_channels():
            self._plot_widget.clear_waveform(channel)
