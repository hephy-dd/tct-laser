from collections.abc import Iterable
from functools import partial

from PySide6 import QtCore, QtWidgets

from ..core.actors.instrument import ConnectionState
from ..core.events import (
    LaserMetrics,
    PowerMeterMetrics,
    SetLaserFrequency,
    SetLaserOutput,
    SetLaserTune,
    SetPowerMeterAverageCount,
    SetPowerMeterWavelength,
)
from ..core.geometry import Vector3
from ..core.station import Role
from ..core.waveform import Waveform
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
    configure_triggered = QtCore.Signal(str, object)
    move_relative_triggered = QtCore.Signal(object)
    move_absolute_triggered = QtCore.Signal(object)
    scope_preview_toggled = QtCore.Signal(bool)
    scope_channels_changed = QtCore.Signal(list)
    sample_name_changed = QtCore.Signal(str)
    output_path_changed = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._error_label = ErrorLabel(self)
        self._error_label.hide()

        # Laser

        self._laser_group_box = LaserGroupBox(self)
        self._laser_group_box.output_changed.connect(self.on_laser_output_changed)
        self._laser_group_box.frequency_changed.connect(self.on_laser_frequency_changed)
        self._laser_group_box.tune_changed.connect(self.on_laser_tune_changed)

        # Stage

        self._stage_group_box = StageGroupBox(self)
        self._stage_group_box.clear_position()
        self._stage_group_box.move_relative_triggered.connect(self.on_move_relative)
        self._stage_group_box.move_absolute_triggered.connect(self.on_move_absolute)

        # Power Meters

        self._power_meter_group_boxes: dict[str, PowerMeterGroupBox] = {}

        def add_power_meter_group_box(name: str, title: str) -> None:
            power_meter_group_box = PowerMeterGroupBox(self)
            power_meter_group_box.setTitle(title)
            power_meter_group_box.wavelength_changed.connect(
                partial(self.on_power_wavelength_changed, name)
            )
            power_meter_group_box.average_count_changed.connect(
                partial(self.on_power_average_count_changed, name)
            )
            self._power_meter_group_boxes[name] = power_meter_group_box

        add_power_meter_group_box(Role.POWER_METER_1, "Power Meter 1")
        add_power_meter_group_box(Role.POWER_METER_2, "Power Meter 2")
        add_power_meter_group_box(Role.POWER_METER_3, "Power Meter 3")

        # Scope

        self._scope_group_box = ScopeGroupBox(self)
        self._scope_group_box.preview_toggled.connect(self.scope_preview_toggled)
        self._scope_group_box.channels_changed.connect(self.scope_channels_changed)

        # General

        self._general_group_box = GeneralGroupBox(self)
        self._general_group_box.sample_name_changed.connect(self.sample_name_changed)
        self._general_group_box.output_path_changed.connect(self.output_path_changed)

        # Station

        self._station_group_box = StationGroupBox(self)
        self._station_group_box.add_instrument(Role.SCOPE, "Scope")
        self._station_group_box.add_instrument(Role.LASER, "Laser")
        self._station_group_box.add_instrument(Role.STAGE, "Stage")
        self._station_group_box.add_instrument(Role.POWER_METER_1, "PM1")
        self._station_group_box.add_instrument(Role.POWER_METER_2, "PM2")
        self._station_group_box.add_instrument(Role.POWER_METER_3, "PM3")
        self._station_group_box.connect_instrument.connect(self.connect_instrument)
        self._station_group_box.disconnect_instrument.connect(
            self.disconnect_instrument
        )

        # Operations

        self._operations_tab_widget = QtWidgets.QTabWidget(self)
        self._operation_widgets: list[OperationWidget] = []

        # Misc

        top_layout = QtWidgets.QHBoxLayout()
        top_layout.addWidget(self._laser_group_box)
        top_layout.addWidget(self._stage_group_box)
        for power_meter_group_box in self._power_meter_group_boxes.values():
            top_layout.addWidget(power_meter_group_box)
        top_layout.addWidget(self._station_group_box)
        top_layout.setStretch(0, 2)
        top_layout.setStretch(1, 4)
        top_layout.setStretch(2, 1)
        top_layout.setStretch(3, 1)
        top_layout.setStretch(4, 1)

        left_layout = QtWidgets.QVBoxLayout()
        left_layout.addWidget(self._scope_group_box)
        left_layout.addWidget(self._general_group_box)

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
        self._scope_group_box.set_inputs_enabled(enabled)
        self._laser_group_box.set_inputs_enabled(enabled)
        self._stage_group_box.set_inputs_enabled(enabled)
        for power_meter_group_box in self._power_meter_group_boxes.values():
            power_meter_group_box.set_inputs_enabled(enabled)
        for operation_widget in self._operation_widgets:
            operation_widget.set_inputs_enabled(enabled)
        self._station_group_box.set_inputs_enabled(enabled)
        self._general_group_box.set_inputs_enabled(enabled)

    def set_abort_enabled(self, enabled: bool) -> None:
        for operation_widget in self._operation_widgets:
            operation_widget.set_abort_enabled(enabled)

    def show_operation(self, operation: OperationWidget) -> None:
        for index in range(self._operations_tab_widget.count()):
            widget = self._operations_tab_widget.widget(index)
            if widget is operation:
                self._operations_tab_widget.setCurrentIndex(index)
                break

    def set_instrument_state(self, name: str, state: ConnectionState) -> None:
        self._station_group_box.set_instrument_state(name, state)

        enabled = state == ConnectionState.CONNECTED
        match name:
            case Role.SCOPE:
                self._scope_group_box.setEnabled(enabled)
            case Role.LASER:
                self._laser_group_box.setEnabled(enabled)
            case Role.STAGE:
                self._stage_group_box.setEnabled(enabled)
                if state != ConnectionState.CONNECTED:
                    self.clear_position()
            case Role.POWER_METER_1:
                self._power_meter_group_boxes[name].setEnabled(enabled)
            case Role.POWER_METER_2:
                self._power_meter_group_boxes[name].setEnabled(enabled)
            case Role.POWER_METER_3:
                self._power_meter_group_boxes[name].setEnabled(enabled)

    def instrument_connection_states(self) -> dict[str, ConnectionState]:
        return {
            instrument: (
                ConnectionState.CONNECTED
                if button.isChecked()
                else ConnectionState.DISCONNECTED
            )
            for instrument, button in self._station_group_box._instrument_buttons.items()
        }

    def add_operation(self, operation: OperationWidget) -> None:
        self._operations_tab_widget.addTab(operation, operation.windowTitle())
        self._operation_widgets.append(operation)

    def operation_widgets(self) -> list[OperationWidget]:
        return list(self._operation_widgets)

    def set_scope_channels(self, channels: Iterable[str]):
        self._scope_group_box.set_channels(channels)

    def scope_enabled_channels(self) -> list[str]:
        return self._scope_group_box.active_channels()

    def set_scope_enabled_channels(self, channels: list[str]) -> None:
        self._scope_group_box.set_active_channels(channels)

    def set_scope_waveform(self, waveform: Waveform) -> None:
        self._scope_group_box.set_waveform(waveform)

    def set_stage_positions(self, positions: Iterable[Position]) -> None:
        self._stage_group_box._positions_widget.clear_positions()
        for position in positions:
            self._stage_group_box._positions_widget.append_position(position)

    def stage_positions(self) -> list[Position]:
        return self._stage_group_box._positions_widget.positions()

    def set_laser_output(self, value: bool) -> None:
        self._laser_group_box.set_output(value)

    def set_stage_position(self, position: Vector3) -> None:
        self._stage_group_box.set_position(position)

    def clear_position(self) -> None:
        self._stage_group_box.clear_position()

    def set_laser_metrics(self, metrics: LaserMetrics) -> None:
        self._laser_group_box.set_metrics(metrics)

    def set_power_meter_metrics(self, name: str, metrics: PowerMeterMetrics) -> None:
        power_meter_group_box = self._power_meter_group_boxes[name]
        if metrics.power is not None:
            power_meter_group_box.set_power(metrics.power)
        if metrics.wavelength is not None:
            power_meter_group_box.update_wavelength(metrics.wavelength)
        if metrics.average_count is not None:
            power_meter_group_box.update_average_count(metrics.average_count)

    def set_power_meter_wavelength(self, name: str, wavelength: int | None) -> None:
        self._power_meter_group_boxes[name].update_wavelength(wavelength)

    def set_power_meter_average_count(
        self, name: str, average_count: int | None
    ) -> None:
        self._power_meter_group_boxes[name].update_average_count(average_count)

    @QtCore.Slot(bool)
    def on_laser_output_changed(self, enabled: bool) -> None:
        self.configure_triggered.emit(Role.LASER, SetLaserOutput(enabled))

    @QtCore.Slot(float)
    def on_laser_frequency_changed(self, frequency: float) -> None:
        self.configure_triggered.emit(Role.LASER, SetLaserFrequency(frequency))

    @QtCore.Slot(bool)
    def on_laser_tune_changed(self, tune: float) -> None:
        self.configure_triggered.emit(Role.LASER, SetLaserTune(tune))

    @QtCore.Slot(int)
    def on_power_wavelength_changed(self, name: str, wavelength: int) -> None:
        self.configure_triggered.emit(name, SetPowerMeterWavelength(wavelength))

    @QtCore.Slot(int)
    def on_power_average_count_changed(self, name: str, average_count: int) -> None:
        self.configure_triggered.emit(name, SetPowerMeterAverageCount(average_count))

    @QtCore.Slot(object)
    def on_move_relative(self, offset: Vector3) -> None:
        self.move_relative_triggered.emit(offset)

    @QtCore.Slot(object)
    def on_move_absolute(self, positon: Vector3) -> None:
        self.move_absolute_triggered.emit(positon)

    def sample_name(self) -> str:
        return self._general_group_box.sample_name()

    def set_sample_name(self, sample_name: str) -> None:
        self._general_group_box.set_sample_name(sample_name)

    def output_path(self) -> str:
        return self._general_group_box.output_path()

    def set_output_path(self, output_path: str) -> None:
        self._general_group_box.set_output_path(output_path)
