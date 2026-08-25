from collections.abc import Iterable
from typing import Any

from PySide6 import QtCore, QtWidgets

from ..core.actors.instrument import ConnectionState
from ..core.events import (
    LaserMetrics,
    SetLaserFrequency,
    SetLaserOutput,
    SetLaserTune,
    SetPowerMeterAverageCount,
    SetPowerMeterWavelength,
)
from ..core.utils import Vector3
from .operation import OperationWidget
from .widgets.general import GeneralGroupBox
from .widgets.labels import ErrorLabel
from .widgets.laser import LaserGroupBox
from .widgets.powermeter import PowerMeterGroupBox
from .widgets.scope import ScopeGroupBox
from .widgets.stage import Position, StageGroupBox
from .widgets.station import StationGroupBox

__all__ = ["DashboardWidget"]


class DashboardWidget(QtWidgets.QWidget):
    connect_instrument = QtCore.Signal(str)
    disconnect_instrument = QtCore.Signal(str)
    configure_triggered = QtCore.Signal()
    move_relative_triggered = QtCore.Signal()
    move_absolute_triggered = QtCore.Signal()
    sample_name_changed = QtCore.Signal(str)
    output_path_changed = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._configure_cache: list[tuple[str, Any]] = []
        self._move_relative_cache: Vector3 | None = None
        self._move_absolute_cache: Vector3 | None = None

        self._error_label = ErrorLabel(self)
        self._error_label.hide()

        # Laser

        self.laser_group_box = LaserGroupBox(self)
        self.laser_group_box.output_changed.connect(self.laser_output_changed)
        self.laser_group_box.frequency_changed.connect(self.laser_frequency_changed)
        self.laser_group_box.tune_changed.connect(self.laser_tune_changed)

        # Stage

        self.stage_group_box = StageGroupBox(self)
        self.stage_group_box.clear_position()
        self.stage_group_box.move_relative.connect(self.move_relative)
        self.stage_group_box.move_absolute.connect(self.move_absolute)

        self.power_meter_group_box: dict[int, PowerMeterGroupBox] = {}

        # Power Meter 1

        self.power_meter_group_box[1] = PowerMeterGroupBox(self)
        self.power_meter_group_box[1].setTitle("Power Meter 1")
        self.power_meter_group_box[1].wavelength_changed.connect(
            self.power_wavelength_changed
        )
        self.power_meter_group_box[1].average_count_changed.connect(
            self.power_average_count_changed
        )

        # Power Meter 2

        self.power_meter_group_box[2] = PowerMeterGroupBox(self)
        self.power_meter_group_box[2].setTitle("Power Meter 2")
        self.power_meter_group_box[2].wavelength_changed.connect(
            self.power_wavelength_2_changed
        )
        self.power_meter_group_box[2].average_count_changed.connect(
            self.power_average_count_2_changed
        )

        # Power Meter 3

        self.power_meter_group_box[3] = PowerMeterGroupBox(self)
        self.power_meter_group_box[3].setTitle("Power Meter 3")
        self.power_meter_group_box[3].wavelength_changed.connect(
            self.power_wavelength_3_changed
        )
        self.power_meter_group_box[3].average_count_changed.connect(
            self.power_average_count_3_changed
        )

        # Scope

        self.scope_group_box = ScopeGroupBox(self)
        # self.scope_group_box.preview_toggled.connect(self.toggle_scope_live)
        # self.scope_group_box.channel_changed.connect(self.scope_channel_changed)

        # General

        self.general_group_box = GeneralGroupBox(self)
        self.general_group_box.sample_name_changed.connect(self.sample_name_changed)
        self.general_group_box.output_path_changed.connect(self.output_path_changed)

        # Station

        self.station_group_box = StationGroupBox(self)
        self.station_group_box.add_instrument("scope", "Scope")
        self.station_group_box.add_instrument("laser", "Laser")
        self.station_group_box.add_instrument("stage", "Stage")
        self.station_group_box.add_instrument("power_meter_1", "PM1")
        self.station_group_box.add_instrument("power_meter_2", "PM2")
        self.station_group_box.add_instrument("power_meter_3", "PM3")
        self.station_group_box.connect_instrument.connect(self.connect_instrument)
        self.station_group_box.disconnect_instrument.connect(self.disconnect_instrument)

        # Operations

        self._operations_tab_widget = QtWidgets.QTabWidget(self)
        self._operation_widgets: list[OperationWidget] = []

        # Misc

        top_layout = QtWidgets.QHBoxLayout()
        top_layout.addWidget(self.laser_group_box)
        top_layout.addWidget(self.stage_group_box)
        top_layout.addWidget(self.power_meter_group_box[1])
        top_layout.addWidget(self.power_meter_group_box[2])
        top_layout.addWidget(self.power_meter_group_box[3])
        top_layout.addWidget(self.station_group_box)
        top_layout.setStretch(0, 2)
        top_layout.setStretch(1, 4)
        top_layout.setStretch(2, 1)
        top_layout.setStretch(3, 1)
        top_layout.setStretch(4, 1)

        left_layout = QtWidgets.QVBoxLayout()
        left_layout.addWidget(self.scope_group_box)
        left_layout.addWidget(self.general_group_box)

        bottom_layout = QtWidgets.QHBoxLayout()
        bottom_layout.addLayout(left_layout)
        bottom_layout.addWidget(self._operations_tab_widget)
        bottom_layout.setStretch(0, 1)
        bottom_layout.setStretch(1, 2)

        inner_layout = QtWidgets.QVBoxLayout()
        inner_layout.setContentsMargins(8, 8, 8, 8)
        inner_layout.addLayout(top_layout)
        inner_layout.addLayout(bottom_layout)
        inner_layout.setStretch(0, 1)
        inner_layout.setStretch(1, 3)
        inner_layout.setStretch(2, 0)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._error_label)
        layout.addLayout(inner_layout)

    def show_error(self, text: str) -> None:
        self._error_label.show_error(text)

    def clear_error(self) -> None:
        self._error_label.hide()

    def set_inputs_enabled(self, enabled: bool) -> None:
        self.scope_group_box.set_inputs_enabled(enabled)
        self.laser_group_box.set_inputs_enabled(enabled)
        self.stage_group_box.set_inputs_enabled(enabled)
        self.power_meter_group_box[1].set_inputs_enabled(enabled)
        self.power_meter_group_box[2].set_inputs_enabled(enabled)
        self.power_meter_group_box[3].set_inputs_enabled(enabled)
        for operation_widget in self._operation_widgets:
            operation_widget.set_inputs_enabled(enabled)
        self.station_group_box.set_inputs_enabled(enabled)
        self.general_group_box.set_inputs_enabled(enabled)

    def set_abort_enabled(self, enabled: bool) -> None:
        for operation_widget in self._operation_widgets:
            operation_widget.set_abort_enabled(enabled)

    def show_operation(self, operation: OperationWidget) -> None:
        for index in range(self._operations_tab_widget.count()):
            widget = self._operations_tab_widget.widget(index)
            if widget is operation:
                self._operations_tab_widget.setCurrentIndex(index)
                break

    def flush_configure_cache(self) -> list[Any]:
        configure_cache = self._configure_cache
        self._configure_cache = []
        return configure_cache

    def flush_move_relative_cache(self) -> Vector3:
        move_relative_cache = self._move_relative_cache
        self._move_relative_cache = None
        if move_relative_cache is None:
            return Vector3(0, 0, 0)
        return move_relative_cache

    def flush_move_absolute_cache(self) -> Vector3 | None:
        move_absolute_cache = self._move_absolute_cache
        self._move_absolute_cache = None
        return move_absolute_cache

    def set_instrument_state(self, name: str, state: ConnectionState) -> None:
        self.station_group_box.set_instrument_state(name, state)

        enabled = state == ConnectionState.CONNECTED
        match name:
            case "scope":
                self.scope_group_box.setEnabled(enabled)
            case "laser":
                self.laser_group_box.setEnabled(enabled)
            case "stage":
                self.stage_group_box.setEnabled(enabled)
                if state != ConnectionState.CONNECTED:
                    self.clear_position()
            case "power_meter_1":
                self.power_meter_group_box[1].setEnabled(enabled)
            case "power_meter_2":
                self.power_meter_group_box[2].setEnabled(enabled)
            case "power_meter_3":
                self.power_meter_group_box[3].setEnabled(enabled)

    def add_operation(self, operation: OperationWidget) -> None:
        self._operations_tab_widget.addTab(operation, operation.windowTitle())
        self._operation_widgets.append(operation)

    def operation_widgets(self) -> list[OperationWidget]:
        return list(self._operation_widgets)

    def set_scope_channels(self, channels: Iterable[str]):
        self.scope_group_box.set_channels(channels)

    def set_active_scope_channels(self, channels: Iterable[str]) -> None:
        self.scope_group_box.set_active_channels(channels)

    def active_scope_channels(self) -> list[str]:
        return self.scope_group_box.active_channels()

    def set_stage_positions(self, positions: Iterable[Position]) -> None:
        self.stage_group_box._positions_widget.clear_positions()
        for position in positions:
            self.stage_group_box._positions_widget.append_position(position)

    def stage_positions(self) -> list[Position]:
        return self.stage_group_box._positions_widget.positions()

    def set_laser_output(self, value: bool) -> None:
        self.laser_group_box.set_output(value)

    def set_position(self, position: Vector3) -> None:
        self.stage_group_box.set_position(position.x, position.y, position.z)

    def clear_position(self) -> None:
        self.stage_group_box.clear_position()

    def set_laser_metrics(self, metrics: LaserMetrics) -> None:
        self.laser_group_box.set_metrics(metrics)

    def set_laser_power(self, index: int, power: float | None) -> None:
        self.power_meter_group_box[index].set_power(power)

    def set_power_meter_wavelength(self, index: int, wavelength: int | None) -> None:
        self.power_meter_group_box[index].update_wavelength(wavelength)

    def set_power_meter_average_count(
        self, index: int, average_count: int | None
    ) -> None:
        self.power_meter_group_box[index].update_average_count(average_count)

    @QtCore.Slot(bool)
    def laser_output_changed(self, enabled: bool) -> None:
        self._configure_cache.append(("laser", SetLaserOutput(enabled)))
        self.configure_triggered.emit()

    @QtCore.Slot(float)
    def laser_frequency_changed(self, frequency: float) -> None:
        self._configure_cache.append(("laser", SetLaserFrequency(frequency)))
        self.configure_triggered.emit()

    @QtCore.Slot(bool)
    def laser_tune_changed(self, tune: float) -> None:
        self._configure_cache.append(("laser", SetLaserTune(tune)))
        self.configure_triggered.emit()

    @QtCore.Slot(int)
    def power_wavelength_changed(self, wavelength: int) -> None:
        self._configure_cache.append(
            ("power_meter_1", SetPowerMeterWavelength(wavelength))
        )
        self.configure_triggered.emit()

    @QtCore.Slot(int)
    def power_average_count_changed(self, average_count: int) -> None:
        self._configure_cache.append(
            ("power_meter_1", SetPowerMeterAverageCount(average_count))
        )
        self.configure_triggered.emit()

    @QtCore.Slot(int)
    def power_wavelength_2_changed(self, wavelength: int) -> None:
        self._configure_cache.append(
            ("power_meter_2", SetPowerMeterWavelength(wavelength))
        )
        self.configure_triggered.emit()

    @QtCore.Slot(int)
    def power_average_count_2_changed(self, average_count: int) -> None:
        self._configure_cache.append(
            ("power_meter_2", SetPowerMeterAverageCount(average_count))
        )
        self.configure_triggered.emit()

    @QtCore.Slot(int)
    def power_wavelength_3_changed(self, wavelength: int) -> None:
        self._configure_cache.append(
            ("power_meter_3", SetPowerMeterWavelength(wavelength))
        )
        self.configure_triggered.emit()

    @QtCore.Slot(int)
    def power_average_count_3_changed(self, average_count: int) -> None:
        self._configure_cache.append(
            ("power_meter_3", SetPowerMeterAverageCount(average_count))
        )
        self.configure_triggered.emit()

    def move_relative(self, x, y, z) -> None:
        self._move_relative_cache = Vector3(x, y, z)
        self.move_relative_triggered.emit()

    def move_absolute(self, x, y, z) -> None:
        self._move_absolute_cache = Vector3(x, y, z)
        self.move_absolute_triggered.emit()

    def sample_name(self) -> str:
        return self.general_group_box.sample_name()

    def set_sample_name(self, sample_name: str) -> None:
        self.general_group_box.set_sample_name(sample_name)

    def output_path(self) -> str:
        return self.general_group_box.output_path()

    def set_output_path(self, output_path: str) -> None:
        self.general_group_box.set_output_path(output_path)

    def handle_event(self, event: Any) -> None:
        for operation_widget in self.operation_widgets():
            operation_widget.handle_event(event)
