from collections.abc import Iterable
from typing import Any, cast

import msgspec
import numpy as np
import pyqtgraph as pg
from numpy.lib.stride_tricks import sliding_window_view
from numpy.typing import NDArray
from PySide6 import QtCore, QtGui, QtWidgets

from tct_laser.core.messages import EnabledChannelsChanged

from ..core.rasterscan import (
    RasterScanOperation,
    RasterType,
    SetRaster,
    UpdateRasterValue,
    create_raster,
)

RASTER_UPDATE_INTERVAL: float = 1.0


def get_levels_ignore_nan(data: NDArray) -> tuple[float, float]:
    """Return min and max of a given raster"""
    if data.size == 0:
        return (0, 1)
    if np.all(np.isnan(data)):
        return (0, 1)
    return float(np.nanmin(data)), float(np.nanmax(data))


def smooth_box(a, size=3):
    # pad so borders are handled
    pad = size // 2
    a_padded = np.pad(a, pad, mode="edge")

    # create sliding window view
    windows = sliding_window_view(a_padded, (size, size))

    # windows is shape (N, N, size, size)
    return windows.mean(axis=(-1, -2))


class RasterAxisBinding(QtCore.QObject):
    """Keeps spin boxes synchronized for one raster axis."""

    def __init__(
        self,
        negative_offset: QtWidgets.QSpinBox,
        positive_offset: QtWidgets.QSpinBox,
        n_points: QtWidgets.QSpinBox,
        step_size: QtWidgets.QSpinBox,
        parent=None,
    ):
        super().__init__(parent)

        self.negative_offset = negative_offset
        self.positive_offset = positive_offset
        self.n_points = n_points
        self.step_size = step_size

        self.n_points.setMinimum(1)
        self.step_size.setMinimum(1)

        self.negative_offset.valueChanged.connect(self.update_step_size)
        self.positive_offset.valueChanged.connect(self.update_step_size)

        self.n_points.valueChanged.connect(self.update_step_size)
        self.step_size.valueChanged.connect(self.update_n_points)

        self.update_step_size()

    def size(self) -> int:
        return abs(self.positive_offset.value() - self.negative_offset.value())

    @QtCore.Slot()
    @QtCore.Slot(int)
    def update_step_size(self, _value=None):
        size = self.size()
        n_points = self.n_points.value()

        new_step_size = max(1, round(size / n_points))

        with QtCore.QSignalBlocker(self.step_size):
            self.step_size.setValue(new_step_size)

    @QtCore.Slot()
    @QtCore.Slot(int)
    def update_n_points(self, _value=None):
        size = self.size()
        step_size = self.step_size.value()

        new_n_points = max(1, round(size / step_size))

        with QtCore.QSignalBlocker(self.n_points):
            self.n_points.setValue(new_n_points)


class RasterPlotWidget(pg.GraphicsLayoutWidget):
    def __init__(
        self, raster_type: RasterType, parent: QtWidgets.QWidget | None = None
    ) -> None:
        super().__init__(parent)

        self.raster_type: RasterType = raster_type
        self.raster_version = 0

        self.plot = self.addPlot()  # type: ignore
        self.plot.setAspectLocked(True)
        self.img = pg.ImageItem()
        self.plot.addItem(self.img)

        self.plot.setLabel("left", "X [um]")
        self.plot.setLabel("bottom", "Y [um]")

        top_axis = self.plot.getAxis("top")
        top_axis.setStyle(showValues=True)
        top_axis.show()

        right_axis = self.plot.getAxis("right")
        right_axis.setStyle(showValues=True)
        right_axis.show()

        self.plot.showGrid(x=True, y=True, alpha=0.4)
        self.plot.invertY(False)

        self.cbar = pg.ColorBarItem(
            values=(0, 1),
            width=10,
            interactive=False,
        )
        self.cbar.setImageItem(self.img, insert_in=self.plot)

        self.addItem(self.plot)
        # self.addItem(self.cbar)


class RasterScanPlotWidget(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.raster_data: dict[RasterType, NDArray] = {}

        self.plot1 = RasterPlotWidget(RasterType.PEAK, self)
        self.plot2 = RasterPlotWidget(RasterType.AREA, self)

        self.plot1_type_combo_box = QtWidgets.QComboBox(self)
        self.plot1_type_combo_box.addItem("Peak", RasterType.PEAK)
        self.plot1_type_combo_box.addItem("Area", RasterType.AREA)
        self.plot1_type_combo_box.addItem("t(max)", RasterType.T_MAX)
        self.plot1_type_combo_box.currentIndexChanged.connect(self._plot1_type_changed)

        self.plot2_type_combo_box = QtWidgets.QComboBox(self)
        self.plot2_type_combo_box.addItem("Peak", RasterType.PEAK)
        self.plot2_type_combo_box.addItem("Area", RasterType.AREA)
        self.plot2_type_combo_box.addItem("t(max)", RasterType.T_MAX)
        self.plot2_type_combo_box.currentIndexChanged.connect(self._plot2_type_changed)

        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.plot1_type_combo_box, 0, 0)
        layout.addWidget(self.plot2_type_combo_box, 0, 1)
        layout.addWidget(self.plot1, 1, 0)
        layout.addWidget(self.plot2, 1, 1)

        self.plot1_type_combo_box.setCurrentIndex(0)
        self.plot2_type_combo_box.setCurrentIndex(1)

        self._plot1_type_changed(self.plot1_type_combo_box.currentIndex())
        self._plot2_type_changed(self.plot2_type_combo_box.currentIndex())

        self.raster_timer = QtCore.QTimer(self)
        self.raster_timer.timeout.connect(self.update_raster)
        self.raster_timer.start(int(RASTER_UPDATE_INTERVAL * 1000))

    def set_color_map(self, color_map: str) -> None:
        cmap = pg.colormap.get(color_map)
        if cmap is not None:
            self.plot1.img.setColorMap(cmap)
            self.plot1.cbar.setColorMap(cmap)
            self.plot2.img.setColorMap(cmap)
            self.plot2.cbar.setColorMap(cmap)

    def set_raster(self, raster_type: RasterType, raster: NDArray) -> None:
        self.raster_data[raster_type] = raster

    def clear(self) -> None:
        self.raster_data.clear()

    @QtCore.Slot()
    def update_raster(self) -> None:
        self._update_raster_1()
        self._update_raster_2()

    def _update_raster_1(self) -> None:
        data = self._select_raster(self.plot1.raster_type)
        levels = get_levels_ignore_nan(data)
        self.plot1.img.setImage(data, auto_levels=False, levels=levels)
        self.plot1.cbar.setLevels(levels)

    def _update_raster_2(self) -> None:
        data = self._select_raster(self.plot2.raster_type)
        levels = get_levels_ignore_nan(data)
        self.plot2.img.setImage(data, auto_levels=False, levels=levels)
        self.plot2.cbar.setLevels(levels)

    def _select_raster(self, raster_type: RasterType) -> NDArray:
        return self.raster_data.get(raster_type, create_raster(0, 0))

    def _plot1_type_changed(self, index: int) -> None:
        self.plot1.raster_type = self.plot1_type_combo_box.itemData(index)
        text = self.plot1_type_combo_box.itemText(index)
        self.plot1.plot.setTitle(text)
        self._update_raster_1()

    def _plot2_type_changed(self, index: int) -> None:
        self.plot2.raster_type = self.plot2_type_combo_box.itemData(index)
        text = self.plot2_type_combo_box.itemText(index)
        self.plot2.plot.setTitle(text)
        self._update_raster_2()


class RasterScanWidget(QtWidgets.QWidget):
    start_triggered = QtCore.Signal()
    abort_triggered = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Raster Scan")

        self.run_action = QtGui.QAction("&Raster Scan", self)
        self.start_triggered.connect(self.run_action.trigger)

        self.left_spin_box = QtWidgets.QSpinBox(self)
        self.left_spin_box.setRange(-1_000_000, 0)
        self.left_spin_box.setValue(-60)
        self.left_spin_box.setSuffix(" um")

        self.right_spin_box = QtWidgets.QSpinBox(self)
        self.right_spin_box.setRange(0, 1_000_000)
        self.right_spin_box.setValue(60)
        self.right_spin_box.setSuffix(" um")

        self.top_spin_box = QtWidgets.QSpinBox(self)
        self.top_spin_box.setRange(-1_000_000, 0)
        self.top_spin_box.setValue(-60)
        self.top_spin_box.setSuffix(" um")

        self.bottom_spin_box = QtWidgets.QSpinBox(self)
        self.bottom_spin_box.setRange(0, 1_000_000)
        self.bottom_spin_box.setValue(60)
        self.bottom_spin_box.setSuffix(" um")

        self.n_points_x_spin_box = QtWidgets.QSpinBox(self)
        self.n_points_x_spin_box.setRange(1, 1_000_000)
        self.n_points_x_spin_box.setValue(10)

        self.step_x_spin_box = QtWidgets.QSpinBox(self)
        self.step_x_spin_box.setRange(1, 1_000_000)
        self.step_x_spin_box.setSuffix(" um")

        self.n_points_y_spin_box = QtWidgets.QSpinBox(self)
        self.n_points_y_spin_box.setRange(1, 1_000_000)
        self.n_points_y_spin_box.setValue(10)

        self.step_y_spin_box = QtWidgets.QSpinBox(self)
        self.step_y_spin_box.setRange(1, 1_000_000)
        self.step_y_spin_box.setSuffix(" um")

        self.source_channel_combo_box = QtWidgets.QComboBox(self)

        self.average_count_spin_box = QtWidgets.QSpinBox(self)
        self.average_count_spin_box.setRange(1, 1000)
        self.average_count_spin_box.setValue(100)
        self.average_count_spin_box.setStatusTip("Set scope waveform average count")

        self.mode_combo_box = QtWidgets.QComboBox(self)
        self.mode_combo_box.setStatusTip("Select scan mode pattern")
        self.mode_combo_box.addItem("Serpentine (Zig-Zag)", "zigzag")
        self.mode_combo_box.addItem("Linear", "linear")
        self.mode_combo_box.addItem("Hilbert Curve (Fit)", "hilbert")
        self.mode_combo_box.addItem("Random (Uniform)", "random_uniform")

        self.start_button = QtWidgets.QPushButton("Raster Scan", self)
        self.start_button.clicked.connect(self.start_triggered)

        self.abort_button = QtWidgets.QPushButton("Abort", self)
        self.abort_button.clicked.connect(self.abort_triggered)

        self.plot_widget = RasterScanPlotWidget(self)
        self.plot_widget.set_color_map("viridis")

        top_1_layout = QtWidgets.QFormLayout()
        top_1_layout.addRow("X- Offset", self.left_spin_box)
        top_1_layout.addRow("X+ Offset", self.right_spin_box)
        top_1_layout.addRow("X Points", self.n_points_x_spin_box)
        top_1_layout.addRow("X Step Size", self.step_x_spin_box)

        top_2_layout = QtWidgets.QFormLayout()
        top_2_layout.addRow("Y- Offset", self.top_spin_box)
        top_2_layout.addRow("Y+ Offset", self.bottom_spin_box)
        top_2_layout.addRow("Y Points", self.n_points_y_spin_box)
        top_2_layout.addRow("Y Step Size", self.step_y_spin_box)

        top_3_layout = QtWidgets.QFormLayout()
        top_3_layout.addRow("Source Ch.", self.source_channel_combo_box)
        top_3_layout.addRow("Avg. Count", self.average_count_spin_box)
        top_3_layout.addRow("Scan Mode", self.mode_combo_box)

        top_4_layout = QtWidgets.QFormLayout()
        top_4_layout.addWidget(self.start_button)
        top_4_layout.addWidget(self.abort_button)

        top_layout = QtWidgets.QHBoxLayout()
        top_layout.addLayout(top_1_layout)
        top_layout.addLayout(top_2_layout)
        top_layout.addLayout(top_3_layout)
        top_layout.addLayout(top_4_layout)
        top_layout.setStretch(0, 1)
        top_layout.setStretch(1, 1)
        top_layout.setStretch(2, 2)
        top_layout.setStretch(3, 1)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(top_layout)
        layout.addWidget(self.plot_widget)

        self._raster_cache: dict[RasterType, NDArray] = {}

        self.raster_timer = QtCore.QTimer(self)
        self.raster_timer.timeout.connect(self.update_rasters)
        self.raster_timer.start(int(RASTER_UPDATE_INTERVAL * 1000))

        self.x_raster_binding = RasterAxisBinding(
            negative_offset=self.left_spin_box,
            positive_offset=self.right_spin_box,
            n_points=self.n_points_x_spin_box,
            step_size=self.step_x_spin_box,
            parent=self,
        )

        self.y_raster_binding = RasterAxisBinding(
            negative_offset=self.top_spin_box,
            positive_offset=self.bottom_spin_box,
            n_points=self.n_points_y_spin_box,
            step_size=self.step_y_spin_box,
            parent=self,
        )

    def raster_width(self) -> int:
        return self.x_raster_binding.size()

    def raster_height(self) -> int:
        return self.y_raster_binding.size()

    @QtCore.Slot()
    def update_rasters(self) -> None:
        for raster_type, raster in list(self._raster_cache.items()):
            self.plot_widget.set_raster(raster_type, raster)

    def set_inputs_enabled(self, enabled: bool) -> None:
        self.left_spin_box.setEnabled(enabled)
        self.right_spin_box.setEnabled(enabled)
        self.top_spin_box.setEnabled(enabled)
        self.bottom_spin_box.setEnabled(enabled)
        self.n_points_x_spin_box.setEnabled(enabled)
        self.step_x_spin_box.setEnabled(enabled)
        self.n_points_y_spin_box.setEnabled(enabled)
        self.step_y_spin_box.setEnabled(enabled)
        self.mode_combo_box.setEnabled(enabled)
        self.source_channel_combo_box.setEnabled(enabled)
        self.average_count_spin_box.setEnabled(enabled)
        self.start_button.setEnabled(enabled)

    def set_abort_enabled(self, enabled: bool) -> None:
        self.abort_button.setEnabled(enabled)

    def source_channel(self) -> str:
        index = self.source_channel_combo_box.currentIndex()
        return self.source_channel_combo_box.itemData(index) or ""

    def set_source_channel(self, channel: str) -> None:
        index = self.source_channel_combo_box.findData(channel)
        self.source_channel_combo_box.setCurrentIndex(index)

    def set_source_channels(self, channels: Iterable[str]) -> None:
        channels = list(channels)
        current_channel = self.source_channel_combo_box.currentData()

        with QtCore.QSignalBlocker(self.source_channel_combo_box):
            self.source_channel_combo_box.clear()
            for channel in channels:
                self.source_channel_combo_box.addItem(f"{channel}", channel)

            index = self.source_channel_combo_box.findData(current_channel)

            if index >= 0:
                self.source_channel_combo_box.setCurrentIndex(index)
            elif self.source_channel_combo_box.count() > 0:
                self.source_channel_combo_box.setCurrentIndex(0)
            else:
                self.source_channel_combo_box.setCurrentIndex(-1)

    def mode(self) -> str:
        index = self.mode_combo_box.currentIndex()
        return self.mode_combo_box.itemData(index) or ""

    def set_mode(self, mode: str) -> None:
        index = self.mode_combo_box.findData(mode)
        self.mode_combo_box.setCurrentIndex(index)

    def set_parameter(self, parameter: Any) -> None:
        match parameter:
            case SetRaster(raster_type, raster):
                self.set_raster(raster_type, raster)
            case UpdateRasterValue(raster_type, x, y, value):
                self.update_raster_value(raster_type, x, y, value)
            case EnabledChannelsChanged(channels):
                self.set_source_channels(channels)

    def set_raster(self, raster_type: RasterType, raster: NDArray) -> None:
        self._raster_cache[raster_type] = raster

    def update_raster_value(
        self, raster_type: RasterType, x: int, y: int, value: float
    ) -> None:
        if raster_type not in self._raster_cache:
            raise ValueError(f"No such raster: {raster_type}")
        self._raster_cache[raster_type][y, x] = value

    def config(self) -> RasterScanOperation:
        return RasterScanOperation(
            offset_left=-abs(self.left_spin_box.value()),
            offset_right=abs(self.right_spin_box.value()),
            offset_top=-abs(self.top_spin_box.value()),
            offset_bottom=abs(self.bottom_spin_box.value()),
            n_points_x=self.n_points_x_spin_box.value(),
            n_points_y=self.n_points_y_spin_box.value(),
            source_channel=self.source_channel(),
            average_count=self.average_count_spin_box.value(),
            mode=self.mode(),
        )

    def setConfig(self, config: RasterScanOperation) -> None:
        self.left_spin_box.setValue(-abs(config.offset_left))
        self.right_spin_box.setValue(config.offset_right)
        self.top_spin_box.setValue(-abs(config.offset_top))
        self.bottom_spin_box.setValue(config.offset_bottom)
        self.n_points_x_spin_box.setValue(config.n_points_x)
        self.n_points_y_spin_box.setValue(config.n_points_y)
        self.set_source_channel(config.source_channel)
        self.average_count_spin_box.setValue(config.average_count)
        self.set_mode(config.mode)

    def read_settings(self, settings: QtCore.QSettings) -> None:
        settings.beginGroup("RasterScan")
        try:
            raw = cast(str, settings.value("config", "", type=str))
        finally:
            settings.endGroup()

        try:
            loaded = msgspec.json.decode(raw or "{}")
            base = msgspec.to_builtins(self.config())
            base.update(loaded)

            self.setConfig(msgspec.convert(base, type=RasterScanOperation))
        except msgspec.DecodeError, msgspec.ValidationError, TypeError:
            # Ignore invalid or incompatible settings.
            pass

    def write_settings(self, settings: QtCore.QSettings) -> None:
        settings.beginGroup("RasterScan")
        try:
            settings.setValue(
                "config",
                msgspec.json.encode(self.config()).decode("utf-8"),
            )
        finally:
            settings.endGroup()
