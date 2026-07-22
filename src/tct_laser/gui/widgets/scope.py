from collections.abc import Iterable

import numpy as np
import pyqtgraph as pg
from PySide6 import QtCore, QtWidgets

from tct_laser.core.utils import Waveform

__all__ = ["ScopeGroupBox"]


class ScopePlotWidget(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._colors = [
            "yellow",
            "green",
            "red",
            "blue",
            "orange",
            "purple",
            "cyan",
            "magenta",
        ]

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

    def set_channels(self, channels: Iterable[str]) -> None:
        for channel, curve in self._curves.items():
            self._plot_widget.removeItem(curve)
            curve.deleteLater()
        self._curves.clear()

        for i, channel in enumerate(channels):
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

    def clear_waveforms(self) -> None:
        for curve in self._curves.values():
            curve.clear()


class ScopeGroupBox(QtWidgets.QGroupBox):
    preview_toggled = QtCore.Signal(bool)
    channels_changed = QtCore.Signal(list)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.setTitle("Scope")

        self._live_preview_button = QtWidgets.QPushButton(self)
        self._live_preview_button.setText("&Live Preview")
        self._live_preview_button.setCheckable(True)
        self._live_preview_button.toggled.connect(self.preview_toggled)

        self._plot_widget = ScopePlotWidget(self)

        self._channel_check_boxes: dict[str, QtWidgets.QCheckBox] = {}
        self._channel_layout = QtWidgets.QHBoxLayout()

        form_layout = QtWidgets.QFormLayout()
        form_layout.addWidget(self._live_preview_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(self._channel_layout)
        layout.addLayout(form_layout)
        layout.addWidget(self._plot_widget)

    def set_channels(self, channels: Iterable[str]) -> None:
        channels_ = list(channels)
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
        for channel in channels_:
            widget = QtWidgets.QCheckBox(self)
            widget.setText(channel)
            widget.stateChanged.connect(self._channel_changed)
            self._channel_layout.addWidget(widget)
            self._channel_check_boxes[channel] = widget
        self._plot_widget.set_channels(channels_)

    def active_channels(self) -> list[str]:
        return [
            channel
            for channel, widget in self._channel_check_boxes.items()
            if widget.isChecked()
        ]

    def set_active_channels(self, channels: Iterable[str]) -> None:
        for channel, widget in self._channel_check_boxes.items():
            widget.setChecked(channel in channels)

    def set_inputs_enabled(self, enabled: bool) -> None:
        self._live_preview_button.setEnabled(enabled)
        for check_box in self._channel_check_boxes.values():
            check_box.setEnabled(enabled)

    def set_waveform(self, waveform):
        self._plot_widget.clear_waveforms()
        self._plot_widget.set_waveform(waveform)

    def set_waveforms(self, waveforms: list[Waveform]):
        self._plot_widget.clear_waveforms()
        for waveform in waveforms:
            self._plot_widget.set_waveform(waveform)

    @QtCore.Slot(int)
    def _channel_changed(self) -> None:
        channels = self.active_channels()
        self.channels_changed.emit(channels)
