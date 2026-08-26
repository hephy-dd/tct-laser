from collections.abc import Iterable
from enum import Enum, auto
from typing import Any, cast

import msgspec
import numpy as np
import pyqtgraph as pg
from numpy.lib.stride_tricks import sliding_window_view
from numpy.typing import NDArray
from PySide6 import QtCore, QtWidgets

from tct_laser.core.events import ChannelsChangedEvent
from tct_laser.gui.operation import OperationWidget

from ..core.rasterscan import (
    CreateRaster,
    Profile,
    RasterScanOperationConfig,
    RasterScanOperationRunner,
    RasterType,
    UpdateRasterValue,
    UpdateXProfile,
    UpdateYProfile,
    create_raster,
)

RASTER_UPDATE_INTERVAL: float = 1.0


class PlotType(Enum):
    PEAK = auto()
    PEAK_XY = auto()
    AREA = auto()
    T_MAX = auto()


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


class XYProfilePlotWidget(pg.GraphicsLayoutWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.x_plot = self.addPlot(row=0, col=0)  # type: ignore
        self.x_plot.setTitle("XZ Profile")
        self.x_plot.setLabel("left", "Amplitude [V]")
        self.x_plot.setLabel("bottom", "X [um]")
        self.x_plot.showGrid(x=True, y=True, alpha=0.4)

        self.x_curve = self.x_plot.plot(pen="y")

        self.nextRow()  # type: ignore

        self.y_plot = self.addPlot(row=1, col=0)  # type: ignore
        self.y_plot.setTitle("YZ Profile")
        self.y_plot.setLabel("left", "Amplitude [V]")
        self.y_plot.setLabel("bottom", "Y [um]")
        self.y_plot.showGrid(x=True, y=True, alpha=0.4)

        self.y_curve = self.y_plot.plot(pen="c")

        # Link Y-axis scaling
        # self.y_plot.setYLink(self.x_plot)

    def set_x_profile(self, x_profile: Profile) -> None:
        self.x_curve.setData(x_profile.x, x_profile.y)

    def set_y_profile(self, y_profile: Profile) -> None:
        self.y_curve.setData(y_profile.x, y_profile.y)

    def clear(self) -> None:
        self.x_curve.clear()
        self.y_curve.clear()


class PlotStack(QtWidgets.QWidget):
    plot_changed = QtCore.Signal(object)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.raster_plot = RasterPlotWidget(RasterType.PEAK)

        self.xy_profile_plot = XYProfilePlotWidget(self)

        self.stack = QtWidgets.QStackedWidget(self)
        self.stack.addWidget(self.raster_plot)
        self.stack.addWidget(self.xy_profile_plot)

        self.plot_type_combo_box = QtWidgets.QComboBox(self)
        self.plot_type_combo_box.addItem("Peak", PlotType.PEAK)
        self.plot_type_combo_box.addItem("Peak Profiles", PlotType.PEAK_XY)
        self.plot_type_combo_box.addItem("Area", PlotType.AREA)
        self.plot_type_combo_box.addItem("t(max)", PlotType.T_MAX)
        self.plot_type_combo_box.currentIndexChanged.connect(self.on_plot_type_changed)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.plot_type_combo_box)
        layout.addWidget(self.stack)

        self.sync_plot_title()

    def set_color_map(self, color_map: str) -> None:
        cmap = pg.colormap.get(color_map)
        if cmap is not None:
            self.raster_plot.img.setColorMap(cmap)
            self.raster_plot.cbar.setColorMap(cmap)

    def sync_plot_title(self) -> None:
        text = self.plot_type_combo_box.currentText()
        self.raster_plot.plot.setTitle(text)

    @QtCore.Slot(int)
    def on_plot_type_changed(self, index: int) -> None:
        plot_type = self.plot_type_combo_box.itemData(index)
        match plot_type:
            case PlotType.PEAK:
                self.raster_plot.raster_type = RasterType.PEAK
                self.sync_plot_title()
                self.stack.setCurrentWidget(self.raster_plot)
                self.plot_changed.emit(plot_type)
            case PlotType.AREA:
                self.raster_plot.raster_type = RasterType.AREA
                self.sync_plot_title()
                self.stack.setCurrentWidget(self.raster_plot)
                self.plot_changed.emit(plot_type)
            case PlotType.T_MAX:
                self.raster_plot.raster_type = RasterType.T_MAX
                self.sync_plot_title()
                self.stack.setCurrentWidget(self.raster_plot)
                self.plot_changed.emit(plot_type)
            case PlotType.PEAK_XY:
                self.stack.setCurrentWidget(self.xy_profile_plot)
                self.plot_changed.emit(plot_type)


class RasterScanPlotWidget(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.raster_data: dict[RasterType, NDArray] = {}
        self.x_profile = Profile.create_empty()
        self.y_profile = Profile.create_empty()

        self.plot_stack_1 = PlotStack(self)
        self.plot_stack_1.plot_changed.connect(self.on_update_plot_1)
        self.plot_stack_2 = PlotStack(self)
        self.plot_stack_2.plot_changed.connect(self.on_update_plot_2)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.plot_stack_1)
        layout.addWidget(self.plot_stack_2)
        layout.setStretch(0, 2)
        layout.setStretch(1, 2)

        self.plot_stack_1.plot_type_combo_box.setCurrentIndex(0)
        self.plot_stack_2.plot_type_combo_box.setCurrentIndex(1)

        self.raster_timer = QtCore.QTimer(self)
        self.raster_timer.timeout.connect(self.update_raster)
        self.raster_timer.start(int(RASTER_UPDATE_INTERVAL * 1000))

    def set_color_map(self, color_map: str) -> None:
        self.plot_stack_1.set_color_map(color_map)
        self.plot_stack_2.set_color_map(color_map)

    def set_raster(self, raster_type: RasterType, raster: NDArray) -> None:
        self.raster_data[raster_type] = raster

    def set_x_profile(self, x_profile: Profile) -> None:
        self.x_profile = x_profile

    def set_y_profile(self, y_profile: Profile) -> None:
        self.y_profile = y_profile

    def clear(self) -> None:
        self.raster_data.clear()

    @QtCore.Slot()
    def update_raster(self) -> None:
        self._update_raster_1()
        self._update_raster_2()
        self._update_xy_profile_1()
        self._update_xy_profile_2()

    @QtCore.Slot(object)
    def on_update_plot_1(self, plot_type: PlotType) -> None:
        match plot_type:
            case PlotType.PEAK | PlotType.AREA | PlotType.T_MAX:
                self._update_raster_1()
            case PlotType.PEAK_XY:
                self._update_xy_profile_1()

    @QtCore.Slot(object)
    def on_update_plot_2(self, plot_type: PlotType) -> None:
        match plot_type:
            case PlotType.PEAK | PlotType.AREA | PlotType.T_MAX:
                self._update_raster_2()
            case PlotType.PEAK_XY:
                self._update_xy_profile_2()

    def _select_raster(self, raster_type: RasterType) -> NDArray:
        return self.raster_data.get(raster_type, create_raster(0, 0))

    def _update_raster_1(self) -> None:
        raster_plot = self.plot_stack_1.raster_plot
        data = self._select_raster(raster_plot.raster_type)
        levels = get_levels_ignore_nan(data)
        raster_plot.img.setImage(data, auto_levels=False, levels=levels)
        raster_plot.cbar.setLevels(levels)

    def _update_raster_2(self) -> None:
        raster_plot = self.plot_stack_2.raster_plot
        data = self._select_raster(raster_plot.raster_type)
        levels = get_levels_ignore_nan(data)
        raster_plot.img.setImage(data, auto_levels=False, levels=levels)
        raster_plot.cbar.setLevels(levels)

    def _update_xy_profile_1(self) -> None:
        xy_profile_plot = self.plot_stack_1.xy_profile_plot
        xy_profile_plot.set_x_profile(self.x_profile)
        xy_profile_plot.set_y_profile(self.y_profile)

    def _update_xy_profile_2(self) -> None:
        xy_profile_plot = self.plot_stack_2.xy_profile_plot
        xy_profile_plot.set_x_profile(self.x_profile)
        xy_profile_plot.set_y_profile(self.y_profile)


class RasterScanWidget(OperationWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Raster Scan")

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

        self.write_plots_check_box = QtWidgets.QCheckBox(self)
        self.write_plots_check_box.setText("Write Plots")
        self.write_plots_check_box.setStatusTip("Write Plots to output directory")
        self.write_plots_check_box.setChecked(True)

        self.write_csv_check_box = QtWidgets.QCheckBox(self)
        self.write_csv_check_box.setText("Write CSV")
        self.write_csv_check_box.setStatusTip("Write CSV to output directory")
        self.write_csv_check_box.setChecked(True)

        self.start_button = QtWidgets.QPushButton("Raster Scan", self)
        self.start_button.clicked.connect(self.start_triggered)

        self.abort_button = QtWidgets.QPushButton("Abort", self)
        self.abort_button.clicked.connect(self.abort_triggered)

        self.plot_widget = RasterScanPlotWidget(self)
        self.plot_widget.set_color_map("viridis")

        self.x_axis_group_box = QtWidgets.QGroupBox(self)
        self.x_axis_group_box.setTitle("X-Axis")

        top_1_layout = QtWidgets.QFormLayout(self.x_axis_group_box)
        top_1_layout.addRow("Start Offset", self.left_spin_box)
        top_1_layout.addRow("Stop Offset", self.right_spin_box)
        top_1_layout.addRow("Points", self.n_points_x_spin_box)
        top_1_layout.addRow("Step Size", self.step_x_spin_box)

        self.y_axis_group_box = QtWidgets.QGroupBox(self)
        self.y_axis_group_box.setTitle("Y-Axis")

        top_2_layout = QtWidgets.QFormLayout(self.y_axis_group_box)
        top_2_layout.addRow("Start Offset", self.top_spin_box)
        top_2_layout.addRow("Stop Offset", self.bottom_spin_box)
        top_2_layout.addRow("Points", self.n_points_y_spin_box)
        top_2_layout.addRow("Step Size", self.step_y_spin_box)

        self.scan_option_group_box = QtWidgets.QGroupBox(self)
        self.scan_option_group_box.setTitle("Options")

        top_3_layout = QtWidgets.QFormLayout(self.scan_option_group_box)
        top_3_layout.addRow("Mode", self.mode_combo_box)
        top_3_layout.addWidget(self.write_plots_check_box)
        top_3_layout.addWidget(self.write_csv_check_box)

        self.scope_group_box = QtWidgets.QGroupBox(self)
        self.scope_group_box.setTitle("Scope")

        top_4_layout = QtWidgets.QFormLayout(self.scope_group_box)
        top_4_layout.addRow("Source Ch.", self.source_channel_combo_box)
        top_4_layout.addRow("Avg. Count", self.average_count_spin_box)

        top_5_layout = QtWidgets.QFormLayout()
        top_5_layout.addWidget(self.start_button)
        top_5_layout.addWidget(self.abort_button)

        top_layout = QtWidgets.QHBoxLayout()
        top_layout.addWidget(self.x_axis_group_box)
        top_layout.addWidget(self.y_axis_group_box)
        top_layout.addWidget(self.scan_option_group_box)
        top_layout.addWidget(self.scope_group_box)
        top_layout.addLayout(top_5_layout)
        top_layout.setStretch(0, 2)
        top_layout.setStretch(1, 2)
        top_layout.setStretch(2, 2)
        top_layout.setStretch(3, 2)
        top_layout.setStretch(4, 2)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(top_layout)
        layout.addWidget(self.plot_widget)

        self._raster_cache: dict[RasterType, NDArray] = {}
        self._x_profile_cache = Profile.create_empty()
        self._y_profile_cache = Profile.create_empty()

        self.raster_timer = QtCore.QTimer(self)
        self.raster_timer.timeout.connect(self.on_update_rasters)
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
    def on_update_rasters(self) -> None:
        for raster_type, raster in list(self._raster_cache.items()):
            self.plot_widget.set_raster(raster_type, raster)
        self.plot_widget.set_x_profile(self._x_profile_cache)
        self.plot_widget.set_y_profile(self._y_profile_cache)

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
        self.write_plots_check_box.setEnabled(enabled)
        self.write_csv_check_box.setEnabled(enabled)
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

    def handle_event(self, event: Any) -> None:
        match event:
            case CreateRaster(raster_type, width, height):
                self.create_raster(raster_type, width, height)
            case UpdateRasterValue(raster_type, x, y, value):
                self.update_raster_value(raster_type, x, y, value)
            case UpdateXProfile(x_profile):
                self.update_x_profiles(x_profile)
            case UpdateYProfile(y_profile):
                self.update_y_profiles(y_profile)
            case ChannelsChangedEvent(channels):
                self.set_source_channels(channels)

    def create_raster(self, raster_type: RasterType, width: int, height: int) -> None:
        self._raster_cache[raster_type] = create_raster(height, width)  # sic!

    def update_raster_value(
        self, raster_type: RasterType, x: int, y: int, value: float
    ) -> None:
        if raster_type not in self._raster_cache:
            raise ValueError(f"No such raster: {raster_type}")
        self._raster_cache[raster_type][y, x] = value

    def update_x_profiles(self, x_profile: Profile) -> None:
        self._x_profile_cache = x_profile

    def update_y_profiles(self, y_profile: Profile) -> None:
        self._y_profile_cache = y_profile

    def config(self) -> RasterScanOperationConfig:
        return RasterScanOperationConfig(
            offset_left=-abs(self.left_spin_box.value()),
            offset_right=abs(self.right_spin_box.value()),
            offset_top=-abs(self.top_spin_box.value()),
            offset_bottom=abs(self.bottom_spin_box.value()),
            n_points_x=self.n_points_x_spin_box.value(),
            n_points_y=self.n_points_y_spin_box.value(),
            mode=self.mode(),
            write_plots=self.write_plots_check_box.isChecked(),
            write_csv=self.write_csv_check_box.isChecked(),
            source_channel=self.source_channel(),
            average_count=self.average_count_spin_box.value(),
        )

    def set_config(self, config: RasterScanOperationConfig) -> None:
        self.left_spin_box.setValue(-abs(config.offset_left))
        self.right_spin_box.setValue(config.offset_right)
        self.top_spin_box.setValue(-abs(config.offset_top))
        self.bottom_spin_box.setValue(config.offset_bottom)
        self.n_points_x_spin_box.setValue(config.n_points_x)
        self.n_points_y_spin_box.setValue(config.n_points_y)
        self.set_mode(config.mode)
        self.write_plots_check_box.setChecked(config.write_plots)
        self.write_csv_check_box.setChecked(config.write_csv)
        self.set_source_channel(config.source_channel)
        self.average_count_spin_box.setValue(config.average_count)

    def create_runner(self) -> RasterScanOperationRunner:
        return RasterScanOperationRunner(config=self.config())

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

            self.set_config(msgspec.convert(base, type=RasterScanOperationConfig))
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
