import json
import logging
import webbrowser
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import msgspec
from PySide6 import QtCore, QtGui, QtStateMachine, QtWidgets

from ..core.actors.instrument import ConnectionState
from ..core.context import ContextState, MainContext, WorkerContext
from ..core.events import (
    ChannelsChangedEvent,
    ConfigureEvent,
    FailedEvent,
    FinishedEvent,
    LaserMetricsEvent,
    MoveAbsoluteAxisEvent,
    MoveAbsoluteEvent,
    MoveRelativeEvent,
    PositionChangedEvent,
    PowerMeterMetricsEvent,
    StatusMessageEvent,
    StatusProgressEvent,
    WaveformEvent,
)
from ..core.geometry import Vector3
from ..core.resource import ResourceConfig
from ..core.service import BackgroundService
from ..core.worker import Worker
from ..operations import RasterScanWidget, ZScanWidget
from . import config
from .adapters import SettingsAdapter
from .dashboard import DashboardWidget, Position
from .logwidget import LogWidget
from .operation import OperationWidget
from .services import WaveformService
from .settingsdialog import SettingsDialog

__all__ = ["MainWindow"]

logger = logging.getLogger(__name__)


class MainWindow(QtWidgets.QMainWindow):
    operation_started = QtCore.Signal(object)
    operation_finished = QtCore.Signal()

    configure_triggered = QtCore.Signal()
    move_triggered = QtCore.Signal()

    def __init__(
        self, state: ContextState, parent: QtWidgets.QWidget | None = None
    ) -> None:
        super().__init__(parent)

        self.setMinimumSize(640, 480)

        self._context = MainContext(state)
        self._configure_requests: list[Any] = []
        self._move_request = None

        self._create_actions()
        self._create_menus()
        self._create_dashboard()
        self._create_dock_widgets()
        self._create_status_bar()

        self._current_operation: Any | None = None
        self._operation_start_actions: list[QtGui.QAction] = []

        self.operation_started.connect(
            lambda operation: setattr(self, "_current_operation", operation)
        )

        self._create_state_machine()
        self._create_operations()

        # Sync

        self._dashboard_widget.set_scope_channels(self._context.scope_channels())

        self._update_timer = QtCore.QTimer(self)
        self._update_timer.timeout.connect(self._on_update_timeout)
        self._update_timer.start(250)

        # Waveforms

        self._waveform_service = WaveformService(self)

        def update_waveform(channel: str) -> None:
            waveform = self._waveform_service.get_waveform(channel)
            if waveform is not None:
                self._dashboard_widget.set_scope_waveform(waveform)

        self._waveform_service.waveform_changed.connect(update_waveform)

        # Worker thread

        self._background_service = BackgroundService(
            "worker", Worker(WorkerContext(state))
        )
        self._background_service.start()

        self.read_settings()

    def _create_actions(self) -> None:
        self._quit_action = QtGui.QAction("&Quit", self)
        self._quit_action.setShortcut(QtGui.QKeySequence.StandardKey.Quit)
        self._quit_action.triggered.connect(self.close)

        self._settings_action = QtGui.QAction("&Settings...", self)
        self._settings_action.triggered.connect(self.show_settings)

        self._abort_action = QtGui.QAction("&Abort", self)

        self._contents_action = QtGui.QAction("&Contents", self)
        self._contents_action.setShortcut("F1")
        self._contents_action.triggered.connect(self.show_contents)

        self._about_qt_action = QtGui.QAction("About &Qt", self)
        self._about_qt_action.triggered.connect(self.show_about_qt)

        self._about_action = QtGui.QAction("&About", self)
        self._about_action.triggered.connect(self.show_about)

    def _create_menus(self) -> None:
        self._file_menu = self.menuBar().addMenu("&File")
        self._file_menu.addAction(self._quit_action)

        self._view_menu = self.menuBar().addMenu("&View")

        self._edit_menu = self.menuBar().addMenu("&Edit")
        self._edit_menu.addAction(self._settings_action)

        self._run_menu = self.menuBar().addMenu("&Run")
        self._run_operation_sep = self._run_menu.addSeparator()
        self._run_operation_sep.setVisible(False)
        self._run_menu.addAction(self._abort_action)

        self._help_menu = self.menuBar().addMenu("&Help")
        self._help_menu.addAction(self._contents_action)
        self._help_menu.addSeparator()
        self._help_menu.addAction(self._about_qt_action)
        self._help_menu.addAction(self._about_action)

    def _create_dashboard(self) -> None:
        self._dashboard_widget = DashboardWidget(self)
        self.setCentralWidget(self._dashboard_widget)
        self._dashboard_widget.connect_instrument.connect(self._on_connect_instrument)
        self._dashboard_widget.disconnect_instrument.connect(
            self._on_disconnect_instrument
        )
        self._dashboard_widget.sample_name_changed.connect(
            lambda sample_name: self._context.set_sample_name(sample_name)
        )
        self._dashboard_widget.output_path_changed.connect(
            lambda output_path: self._context.set_output_path(output_path)
        )
        self._dashboard_widget.configure_triggered.connect(self.on_configure)
        self._dashboard_widget.move_relative_triggered.connect(self.on_move_relative)
        self._dashboard_widget.move_absolute_triggered.connect(self.on_move_absolute)

        # Scope

        self._dashboard_widget.scope_preview_toggled.connect(self._on_toggle_scope_live)
        self._dashboard_widget.scope_channels_changed.connect(
            self._on_scope_channels_changed
        )

    def _create_dock_widgets(self) -> None:
        self._log_widget = LogWidget(self)
        self._log_widget.add_logger(logging.getLogger())

        self._log_dock = QtWidgets.QDockWidget("Log Window", self)
        self._log_dock.setObjectName("LogDock")  # saveState/restoreState
        self._log_dock.setWidget(self._log_widget)
        self._log_dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea)
        self._log_dock.setFeatures(
            QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.addDockWidget(
            QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, self._log_dock
        )

        self._log_dock.hide()
        self._log_action = self._log_dock.toggleViewAction()
        self._view_menu.addAction(self._log_action)

    def _create_status_bar(self) -> None:
        self._message_label = QtWidgets.QLabel(self)

        self._progress_bar = QtWidgets.QProgressBar(self)
        self._progress_bar.setMaximumWidth(300)
        self._progress_bar.hide()

        self.statusBar().addPermanentWidget(self._message_label)
        self.statusBar().addPermanentWidget(self._progress_bar)

    def _create_state_machine(self) -> None:
        self._idle_state = QtStateMachine.QState()
        self._idle_state.entered.connect(self._on_enter_idle)

        self._configure_state = QtStateMachine.QState()
        self._configure_state.entered.connect(self._on_enter_configure)

        self._move_state = QtStateMachine.QState()
        self._move_state.entered.connect(self._on_enter_move)

        self._operation_state = QtStateMachine.QState()
        self._operation_state.entered.connect(self._on_enter_operation)

        self._abort_state = QtStateMachine.QState()
        self._abort_state.entered.connect(self._on_enter_abort)

        self._idle_state.addTransition(self.configure_triggered, self._configure_state)
        self._idle_state.addTransition(self.move_triggered, self._move_state)
        self._idle_state.addTransition(self.operation_started, self._operation_state)

        self._configure_state.addTransition(self.operation_finished, self._idle_state)

        self._move_state.addTransition(self.operation_finished, self._idle_state)

        self._move_state.addTransition(self._abort_action.triggered, self._abort_state)

        self._operation_state.addTransition(self.operation_finished, self._idle_state)
        self._operation_state.addTransition(
            self._abort_action.triggered, self._abort_state
        )

        self._abort_state.addTransition(self.operation_finished, self._idle_state)

        self._state_machine = QtStateMachine.QStateMachine(self)
        self._state_machine.addState(self._idle_state)
        self._state_machine.addState(self._configure_state)
        self._state_machine.addState(self._move_state)
        self._state_machine.addState(self._operation_state)
        self._state_machine.addState(self._abort_state)
        self._state_machine.setInitialState(self._idle_state)
        self._state_machine.start()

    def _create_operations(self) -> None:
        self.add_operation(RasterScanWidget(self))
        self.add_operation(ZScanWidget(self))

    def add_operation(self, operation: OperationWidget) -> None:
        self._run_operation_sep.setVisible(True)
        start_action = QtGui.QAction(operation.windowTitle(), self)
        operation.start_triggered.connect(start_action.trigger)
        self._run_menu.insertAction(self._run_operation_sep, start_action)
        start_action.triggered.connect(lambda: self.operation_started.emit(operation))
        operation.abort_triggered.connect(self._abort_action.trigger)
        operation.event_submitted.connect(self.handle_event)
        self._dashboard_widget.add_operation(operation)
        self._operation_start_actions.append(start_action)

    def read_settings(self) -> None:
        settings = SettingsAdapter(QtCore.QSettings())

        with settings.group("MainWindow"):
            geometry = settings.get("geometry", QtCore.QByteArray())
            self.restoreGeometry(geometry)

            state = settings.get("state", QtCore.QByteArray())
            self.restoreState(state)

            instruments = settings.get("instruments", "")
            self.restore_instruments(instruments)

            connections = settings.get("connections", "")
            self.restore_connections(connections)

            scope_channels = settings.get("scope_channels", "")
            self.restore_scope_channels(scope_channels)

            sample_name = settings.get("sample_name", "Unnamed")
            self._dashboard_widget.set_sample_name(sample_name)

            output_path = settings.get("output_path", str(Path.home()))
            self._dashboard_widget.set_output_path(output_path)

            stage_positions = settings.get("stage_positions", "")
            self.restore_stage_positions(stage_positions)

        for widget in self._dashboard_widget.operation_widgets():
            widget.read_settings()

    def write_settings(self) -> None:
        settings = SettingsAdapter(QtCore.QSettings())

        with settings.group("MainWindow"):
            settings.set("geometry", self.saveGeometry())
            settings.set("state", self.saveState())
            settings.set("instruments", self.save_instruments())
            settings.set("connections", self.save_connections())
            settings.set("scope_channels", self.save_scope_channels())
            settings.set("sample_name", self._dashboard_widget.sample_name())
            settings.set("output_path", self._dashboard_widget.output_path())
            settings.set("stage_positions", self.save_stage_positions())

        for widget in self._dashboard_widget.operation_widgets():
            widget.write_settings()

    def save_instruments(self) -> str:
        try:
            instruments = {
                name: msgspec.to_builtins(actor.resource_config())
                for name, actor in self._context.station.actors().items()
            }
            return json.dumps(instruments)
        except Exception:
            return "{}"

    def restore_instruments(self, data: str) -> None:
        try:
            instruments = json.loads(data)
        except Exception:
            instruments = {}

        if not isinstance(instruments, dict):
            instruments = {}

        for name, actor in self._context.station.actors().items():
            config_data = instruments.get(name, {})
            actor.set_resource_config(msgspec.convert(config_data, ResourceConfig))

    def save_connections(self) -> str:
        connections = [
            instrument
            for instrument, state in self._dashboard_widget.instrument_connection_states().items()
            if state is ConnectionState.CONNECTED
        ]
        return json.dumps(connections)

    def restore_connections(self, connections: str) -> None:
        try:
            connections_ = json.loads(connections)
        except Exception:
            connections_ = []
        for instrument in connections_:
            self._context.connect(instrument)

    def save_scope_channels(self) -> str:
        channels = self._dashboard_widget.scope_enabled_channels()
        return json.dumps(channels)

    def restore_scope_channels(self, data: str) -> None:
        try:
            channels = list(json.loads(data))
        except Exception:
            channels = []
        self._dashboard_widget.set_scope_enabled_channels(channels)

    def save_stage_positions(self) -> str:
        stage_positions = self._dashboard_widget.stage_positions()
        return json.dumps([msgspec.to_builtins(pos) for pos in stage_positions])

    def restore_stage_positions(self, data: str) -> None:
        try:
            stage_positions = list(json.loads(data))
        except Exception:
            stage_positions = []
        self._dashboard_widget.set_stage_positions(
            [msgspec.convert(pos, Position) for pos in stage_positions]
        )

    @QtCore.Slot(str)
    def _on_connect_instrument(self, instrument: str) -> None:
        self._context.connect(instrument)

    @QtCore.Slot(str)
    def _on_disconnect_instrument(self, instrument: str) -> None:
        self._context.disconnect(instrument)

    @QtCore.Slot()
    def _on_update_timeout(self) -> None:
        self.update_instrument_state()
        self.process_pending_events(max_count=1024)

    @QtCore.Slot(object)
    def on_configure(self, name: str, data: Any) -> None:
        self._configure_requests.append((name, data))
        self.configure_triggered.emit()

    @QtCore.Slot(object)
    def on_move_relative(self, offset: Vector3) -> None:
        self._move_request = MoveRelativeEvent(offset)
        self.move_triggered.emit()

    @QtCore.Slot(object)
    def on_move_absolute(self, position: Vector3) -> None:
        self._move_request = MoveAbsoluteEvent(position)
        self.move_triggered.emit()

    @QtCore.Slot(object)
    def on_move_absolute_axis(self, axis: str, value: float) -> None:
        self._move_request = MoveAbsoluteAxisEvent(axis, value)
        self.move_triggered.emit()

    def update_instrument_state(self) -> None:
        for name, actor in self._context.station.actors().items():
            connection_state = actor.connection_state()
            self._dashboard_widget.set_instrument_state(name, connection_state)

    def process_pending_events(self, max_count: int) -> None:
        """Process at most `max_count` queued messages."""
        for _ in range(max_count):
            event = self._context.next_event()

            if event is None:
                return

            self.handle_event(event)

    def handle_event(self, event: Any) -> None:
        """Route one application message to its handler."""
        match event:
            case WaveformEvent(waveform):
                self._waveform_service.set_waveform(waveform)

            case StatusMessageEvent(text):
                self.set_status_message(text)

            case StatusProgressEvent(step, steps):
                self.set_status_progress(step, steps)

            case FailedEvent(exception):
                self.set_exception(exception)

            case FinishedEvent():
                self.operation_finished.emit()

            case PositionChangedEvent(position):
                self._dashboard_widget.set_stage_position(position)

            case LaserMetricsEvent(_, metrics):
                self._dashboard_widget.set_laser_metrics(metrics)

            case PowerMeterMetricsEvent(name, metrics):
                self._dashboard_widget.set_power_meter_metrics(name, metrics)

            case MoveAbsoluteAxisEvent(axis, value):
                self.on_move_absolute_axis(axis, value)

        for operation_widget in self._dashboard_widget.operation_widgets():
            operation_widget.handle_event(event)

    @QtCore.Slot()
    def _on_enter_idle(self) -> None:
        logger.info("entered [idle]")
        self.set_inputs_enabled(True)
        self.set_abort_enabled(False)
        self.clear_message()
        self.clear_progress()

    @QtCore.Slot()
    def _on_enter_configure(self) -> None:
        logger.info("entered [configure]")
        self.set_inputs_enabled(False)
        self.set_abort_enabled(False)
        requests = list(self._configure_requests)
        self._configure_requests.clear()
        self._context.submit_event(ConfigureEvent(requests))

    @QtCore.Slot()
    def _on_enter_move(self) -> None:
        logger.info("entered [move]")
        self.set_inputs_enabled(False)
        self.set_abort_enabled(False)
        request = self._move_request
        self._move_request = None
        match request:
            case MoveRelativeEvent():
                self._context.submit_event(request)
            case MoveAbsoluteEvent():
                self._context.submit_event(request)
            case MoveAbsoluteAxisEvent():
                self._context.submit_event(request)
            case _:
                self.operation_finished.emit()

    @QtCore.Slot()
    def _on_enter_operation(self) -> None:
        logger.info("entered [operation]")
        self.clear_exception()
        self.set_inputs_enabled(False)
        self.set_abort_enabled(True)
        operation = self._current_operation
        if operation is not None:
            self._dashboard_widget.show_operation(operation)
            operation.clear()
            self._context.submit_operation(operation.create_runner())
        self._current_operation = None

    @QtCore.Slot()
    def _on_enter_abort(self) -> None:
        logger.info("entered [abort]")
        self.set_abort_enabled(False)
        self._context.abort()

    def set_inputs_enabled(self, enabled: bool) -> None:
        self._settings_action.setEnabled(enabled)
        self._dashboard_widget.set_inputs_enabled(enabled)
        for start_action in self._operation_start_actions:
            start_action.setEnabled(enabled)

    def set_abort_enabled(self, enabled: bool) -> None:
        self._abort_action.setEnabled(enabled)
        self._dashboard_widget.set_abort_enabled(enabled)

    def set_exception(self, exc: Exception) -> None:
        self._dashboard_widget.show_error(str(exc))

    def clear_exception(self) -> None:
        self._dashboard_widget.clear_error()

    def set_status_message(self, text: str) -> None:
        self._message_label.setText(text)

    def clear_message(self) -> None:
        self._message_label.clear()

    def set_status_progress(self, step: int, steps: int) -> None:
        self._progress_bar.setRange(0, steps)
        self._progress_bar.setValue(step)
        self._progress_bar.show()

    def clear_progress(self) -> None:
        self._progress_bar.hide()

    @QtCore.Slot(bool)
    def _on_toggle_scope_live(self, toggled: bool) -> None:
        self._context.set_live_waveform(toggled)

    @QtCore.Slot(object)
    def _on_scope_channels_changed(self, channels: Iterable[str]) -> None:
        channels = list(channels)
        self._context.set_waveform_channels(channels)
        self.handle_event(ChannelsChangedEvent(channels))

    @QtCore.Slot()
    def show_settings(self) -> None:
        dialog = SettingsDialog(self)
        dialog.read_settings()

        for name, actor in self._context.station.actors().items():
            resource_config = actor.resource_config()
            dialog.set_instrument_model(name, resource_config.model)
            dialog.set_instrument_resource_name(name, resource_config.resource_name)
            dialog.set_instrument_termination(name, resource_config.termination)
            dialog.set_instrument_timeout(name, resource_config.timeout)
            dialog.set_instrument_baud_rate(name, resource_config.baud_rate)
            dialog.set_instrument_serial_format(name, resource_config.serial_format)

        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            for name, actor in self._context.station.actors().items():
                actor.set_resource_config(
                    ResourceConfig(
                        model=dialog.instrument_model(name),
                        resource_name=dialog.instrument_resource_name(name),
                        termination=dialog.instrument_termination(name),
                        timeout=dialog.instrument_timeout(name),
                        baud_rate=dialog.instrument_baud_rate(name),
                        serial_format=dialog.instrument_serial_format(name),
                    )
                )

        dialog.write_settings()

    @QtCore.Slot()
    def show_contents(self) -> None:
        webbrowser.open(config.CONTENTS_URL)

    @QtCore.Slot()
    def show_about_qt(self) -> None:
        QtWidgets.QMessageBox.aboutQt(self, "About Qt")

    @QtCore.Slot()
    def show_about(self) -> None:
        QtWidgets.QMessageBox.about(self, "About", config.ABOUT_TEXT)

    def closeEvent(self, event) -> None:
        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Exit",
            "Are you sure you want to quit?",
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            # Graceful shutdown
            self._context.shutdown()
            self._background_service.stop()
            self._state_machine.stop()
            self.write_settings()
            event.accept()
        else:
            event.ignore()
