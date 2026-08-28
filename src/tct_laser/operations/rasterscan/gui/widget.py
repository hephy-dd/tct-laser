from collections.abc import Iterable
from typing import Any, cast

import msgspec
from PySide6 import QtCore, QtGui, QtWidgets

from tct_laser.core.events import ChannelsChangedEvent
from tct_laser.gui.operation import OperationWidget

from ..core.rasterscan import (
    CreateRaster,
    Profile,
    Raster,
    RasterScanOperationConfig,
    RasterScanOperationRunner,
    RasterType,
    Rect,
    UpdateRasterValue,
    UpdateXProfile,
    UpdateYProfile,
)
from .plots import RasterScanPlotWidget

__all__ = ["RasterScanWidget"]

RASTER_UPDATE_INTERVAL: float = 1.0


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


class RasterScanWidget(OperationWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Raster Scan")

        self.presets_label = QtWidgets.QLabel(self)
        self.presets_label.setText("Presets")

        self.presets_combo_box = QtWidgets.QComboBox(self)
        self.presets_combo_box.setPlaceholderText("No preset selected")

        self._presets: dict[str, RasterScanOperationConfig] = {}
        self._inputs_enabled = True
        self._updating_form = False

        self.add_preset_action = QtGui.QAction(self)
        self.add_preset_action.setText("&Add")

        self.save_preset_action = QtGui.QAction(self)
        self.save_preset_action.setText("&Save")

        self.remove_preset_action = QtGui.QAction(self)
        self.remove_preset_action.setText("&Remove")

        self.presets_menu = QtWidgets.QMenu(self)
        self.presets_menu.addAction(self.add_preset_action)
        self.presets_menu.addAction(self.save_preset_action)
        self.presets_menu.addAction(self.remove_preset_action)

        self.presets_add_button = QtWidgets.QToolButton(self)
        self.presets_add_button.setDefaultAction(self.add_preset_action)

        self.presets_save_button = QtWidgets.QToolButton(self)
        self.presets_save_button.setDefaultAction(self.save_preset_action)

        self.presets_remove_button = QtWidgets.QToolButton(self)
        self.presets_remove_button.setDefaultAction(self.remove_preset_action)

        self.min_offset_x = QtWidgets.QSpinBox(self)
        self.min_offset_x.setRange(-1_000_000, 0)
        self.min_offset_x.setValue(-60)
        self.min_offset_x.setSuffix(" um")

        self.max_offset_x = QtWidgets.QSpinBox(self)
        self.max_offset_x.setRange(0, 1_000_000)
        self.max_offset_x.setValue(60)
        self.max_offset_x.setSuffix(" um")

        self.min_offset_y = QtWidgets.QSpinBox(self)
        self.min_offset_y.setRange(-1_000_000, 0)
        self.min_offset_y.setValue(-60)
        self.min_offset_y.setSuffix(" um")

        self.max_offset_y = QtWidgets.QSpinBox(self)
        self.max_offset_y.setRange(0, 1_000_000)
        self.max_offset_y.setValue(60)
        self.max_offset_y.setSuffix(" um")

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

        presets_layout = QtWidgets.QHBoxLayout()
        presets_layout.addWidget(self.presets_label)
        presets_layout.addWidget(self.presets_combo_box)
        presets_layout.addWidget(self.presets_add_button)
        presets_layout.addWidget(self.presets_save_button)
        presets_layout.addWidget(self.presets_remove_button)
        presets_layout.addStretch()
        presets_layout.setStretch(1, 1)
        presets_layout.setStretch(5, 1)

        self.x_axis_group_box = QtWidgets.QGroupBox(self)
        self.x_axis_group_box.setTitle("X-Axis")

        top_1_layout = QtWidgets.QFormLayout(self.x_axis_group_box)
        top_1_layout.addRow("Offset Top", self.min_offset_x)
        top_1_layout.addRow("Offset Bottom", self.max_offset_x)
        top_1_layout.addRow("Point Count", self.n_points_x_spin_box)
        top_1_layout.addRow("Step Size", self.step_x_spin_box)

        self.y_axis_group_box = QtWidgets.QGroupBox(self)
        self.y_axis_group_box.setTitle("Y-Axis")

        top_2_layout = QtWidgets.QFormLayout(self.y_axis_group_box)
        top_2_layout.addRow("Offset Left", self.min_offset_y)
        top_2_layout.addRow("Offset Right", self.max_offset_y)
        top_2_layout.addRow("Point Count", self.n_points_y_spin_box)
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
        layout.addLayout(presets_layout)
        layout.addLayout(top_layout)
        layout.addWidget(self.plot_widget)

        self._raster_cache: dict[RasterType, Raster] = {}
        self._x_profile_cache = Profile.create_empty()
        self._y_profile_cache = Profile.create_empty()

        self.raster_timer = QtCore.QTimer(self)
        self.raster_timer.timeout.connect(self.on_update_rasters)
        self.raster_timer.start(int(RASTER_UPDATE_INTERVAL * 1000))

        self.x_raster_binding = RasterAxisBinding(
            negative_offset=self.min_offset_x,
            positive_offset=self.max_offset_x,
            n_points=self.n_points_x_spin_box,
            step_size=self.step_x_spin_box,
            parent=self,
        )

        self.y_raster_binding = RasterAxisBinding(
            negative_offset=self.min_offset_y,
            positive_offset=self.max_offset_y,
            n_points=self.n_points_y_spin_box,
            step_size=self.step_y_spin_box,
            parent=self,
        )

        self.presets_combo_box.currentIndexChanged.connect(self._preset_selected)
        self.add_preset_action.triggered.connect(self._add_preset)
        self.save_preset_action.triggered.connect(self._save_preset)
        self.remove_preset_action.triggered.connect(self._remove_preset)

        for widget in (
            self.min_offset_x,
            self.max_offset_x,
            self.min_offset_y,
            self.max_offset_y,
            self.n_points_x_spin_box,
            self.n_points_y_spin_box,
            self.average_count_spin_box,
        ):
            widget.valueChanged.connect(self._config_changed)

        self.mode_combo_box.currentIndexChanged.connect(self._config_changed)
        self.source_channel_combo_box.currentIndexChanged.connect(self._config_changed)
        self.write_plots_check_box.toggled.connect(self._config_changed)
        self.write_csv_check_box.toggled.connect(self._config_changed)

        self._update_preset_controls()

    def _selected_preset_name(self) -> str | None:
        index = self.presets_combo_box.currentIndex()
        if index < 0:
            return None
        name = self.presets_combo_box.itemData(index)
        return name if isinstance(name, str) and name in self._presets else None

    def _preset_is_dirty(self) -> bool:
        name = self._selected_preset_name()
        return name is not None and self.config() != self._presets[name]

    @QtCore.Slot()
    @QtCore.Slot(int)
    @QtCore.Slot(bool)
    def _config_changed(self, _value=None) -> None:
        if not self._updating_form:
            self._update_preset_controls()

    def _update_preset_controls(self) -> None:
        selected = self._selected_preset_name() is not None
        dirty = selected and self._preset_is_dirty()

        self.presets_combo_box.setEnabled(self._inputs_enabled)
        self.add_preset_action.setEnabled(self._inputs_enabled)
        self.save_preset_action.setEnabled(self._inputs_enabled and dirty)
        self.remove_preset_action.setEnabled(self._inputs_enabled and selected)

        if selected and dirty:
            self.presets_label.setText("Presets (modified)")
            self.presets_combo_box.setToolTip(
                "The form differs from the selected preset. Save to update it."
            )
        else:
            self.presets_label.setText("Presets")
            self.presets_combo_box.setToolTip("")

    @QtCore.Slot(int)
    def _preset_selected(self, index: int) -> None:
        if self._updating_form or index < 0:
            self._update_preset_controls()
            return

        name = self.presets_combo_box.itemData(index)
        config = self._presets.get(name)
        if config is None:
            self._update_preset_controls()
            return

        self.set_config(config)
        self._update_preset_controls()

    @QtCore.Slot()
    def _add_preset(self) -> None:
        name, accepted = QtWidgets.QInputDialog.getText(
            self, "Add Raster Scan Preset", "Preset name:"
        )
        name = name.strip()
        if not accepted or not name:
            return

        if name in self._presets:
            QtWidgets.QMessageBox.information(
                self,
                "Preset already exists",
                f'A preset named "{name}" already exists. Select it and use Save to update it.',
            )
            return

        self._presets[name] = self.config()
        self.presets_combo_box.addItem(name, name)
        self.presets_combo_box.setCurrentIndex(self.presets_combo_box.count() - 1)
        self._update_preset_controls()

    @QtCore.Slot()
    def _save_preset(self) -> None:
        name = self._selected_preset_name()
        if name is None:
            return
        self._presets[name] = self.config()
        self._update_preset_controls()

    @QtCore.Slot()
    def _remove_preset(self) -> None:
        index = self.presets_combo_box.currentIndex()
        name = self._selected_preset_name()
        if name is None or index < 0:
            return

        del self._presets[name]
        self.presets_combo_box.removeItem(index)
        if self.presets_combo_box.count() == 0:
            self.presets_combo_box.setCurrentIndex(-1)
        self._update_preset_controls()

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
        self._inputs_enabled = enabled
        self.min_offset_x.setEnabled(enabled)
        self.max_offset_x.setEnabled(enabled)
        self.min_offset_y.setEnabled(enabled)
        self.max_offset_y.setEnabled(enabled)
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
        self._update_preset_controls()

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

        self._config_changed()

    def mode(self) -> str:
        index = self.mode_combo_box.currentIndex()
        return self.mode_combo_box.itemData(index) or ""

    def set_mode(self, mode: str) -> None:
        index = self.mode_combo_box.findData(mode)
        self.mode_combo_box.setCurrentIndex(index)

    def handle_event(self, event: Any) -> None:
        match event:
            case CreateRaster(raster_type, width, height, raster_extent):
                self.create_raster(raster_type, width, height, raster_extent)
            case UpdateRasterValue(raster_type, x, y, value):
                self.update_raster_value(raster_type, x, y, value)
            case UpdateXProfile(x_profile):
                self.update_x_profiles(x_profile)
            case UpdateYProfile(y_profile):
                self.update_y_profiles(y_profile)
            case ChannelsChangedEvent(channels):
                self.set_source_channels(channels)

    def create_raster(
        self, raster_type: RasterType, width: int, height: int, raster_extent: Rect
    ) -> None:
        inverted_extent = Rect(
            raster_extent.y, raster_extent.x, raster_extent.height, raster_extent.width
        )
        self._raster_cache[raster_type] = Raster.create(
            height, width, inverted_extent
        )  # sic!

    def update_raster_value(
        self, raster_type: RasterType, x: int, y: int, value: float
    ) -> None:
        if raster_type not in self._raster_cache:
            raise ValueError(f"No such raster: {raster_type}")
        self._raster_cache[raster_type].set_value(y, x, value)

    def update_x_profiles(self, x_profile: Profile) -> None:
        self._x_profile_cache = x_profile

    def update_y_profiles(self, y_profile: Profile) -> None:
        self._y_profile_cache = y_profile

    def config(self) -> RasterScanOperationConfig:
        return RasterScanOperationConfig(
            offset_left=-abs(self.min_offset_x.value()),
            offset_right=abs(self.max_offset_x.value()),
            offset_top=-abs(self.min_offset_y.value()),
            offset_bottom=abs(self.max_offset_y.value()),
            n_points_x=self.n_points_x_spin_box.value(),
            n_points_y=self.n_points_y_spin_box.value(),
            mode=self.mode(),
            write_plots=self.write_plots_check_box.isChecked(),
            write_csv=self.write_csv_check_box.isChecked(),
            source_channel=self.source_channel(),
            average_count=self.average_count_spin_box.value(),
        )

    def set_config(self, config: RasterScanOperationConfig) -> None:
        self._updating_form = True
        try:
            self.min_offset_x.setValue(-abs(config.offset_left))
            self.max_offset_x.setValue(config.offset_right)
            self.min_offset_y.setValue(-abs(config.offset_top))
            self.max_offset_y.setValue(config.offset_bottom)
            self.n_points_x_spin_box.setValue(config.n_points_x)
            self.n_points_y_spin_box.setValue(config.n_points_y)
            self.set_mode(config.mode)
            self.write_plots_check_box.setChecked(config.write_plots)
            self.write_csv_check_box.setChecked(config.write_csv)
            self.set_source_channel(config.source_channel)
            self.average_count_spin_box.setValue(config.average_count)
        finally:
            self._updating_form = False
        self._update_preset_controls()

    def create_runner(self) -> RasterScanOperationRunner:
        return RasterScanOperationRunner(config=self.config())

    def _decode_config(self, raw: str) -> RasterScanOperationConfig | None:
        try:
            loaded = msgspec.json.decode(raw or "{}")
            if not isinstance(loaded, dict):
                return None
            base = msgspec.to_builtins(self.config())
            base.update(loaded)
            return msgspec.convert(base, type=RasterScanOperationConfig)
        except msgspec.DecodeError, msgspec.ValidationError, TypeError, ValueError:
            return None

    def read_settings(self, settings: QtCore.QSettings) -> None:
        settings.beginGroup("RasterScan")
        try:
            raw_config = cast(str, settings.value("config", "", type=str))
            raw_presets = cast(str, settings.value("presets", "", type=str))
            selected_preset = cast(str, settings.value("selected_preset", "", type=str))
        finally:
            settings.endGroup()

        # Keep the legacy/current config as the fallback when there is no valid preset.
        config = self._decode_config(raw_config)
        if config is not None:
            self.set_config(config)

        presets: dict[str, RasterScanOperationConfig] = {}
        try:
            loaded_presets = msgspec.json.decode(raw_presets or "{}")
            if isinstance(loaded_presets, dict):
                for name, value in loaded_presets.items():
                    if not isinstance(name, str) or not isinstance(value, dict):
                        continue
                    try:
                        presets[name] = msgspec.convert(
                            value, type=RasterScanOperationConfig
                        )
                    except msgspec.ValidationError, TypeError, ValueError:
                        continue
        except msgspec.DecodeError:
            pass

        self._presets = presets
        with QtCore.QSignalBlocker(self.presets_combo_box):
            self.presets_combo_box.clear()
            for name in self._presets:
                self.presets_combo_box.addItem(name, name)

            index = self.presets_combo_box.findData(selected_preset)
            self.presets_combo_box.setCurrentIndex(index)

        if index >= 0:
            self.set_config(self._presets[selected_preset])
        else:
            self._update_preset_controls()

    def write_settings(self, settings: QtCore.QSettings) -> None:
        presets = {
            name: msgspec.to_builtins(config) for name, config in self._presets.items()
        }

        settings.beginGroup("RasterScan")
        try:
            settings.setValue(
                "config",
                msgspec.json.encode(self.config()).decode("utf-8"),
            )
            settings.setValue(
                "presets",
                msgspec.json.encode(presets).decode("utf-8"),
            )
            settings.setValue(
                "selected_preset",
                self._selected_preset_name() or "",
            )
        finally:
            settings.endGroup()
