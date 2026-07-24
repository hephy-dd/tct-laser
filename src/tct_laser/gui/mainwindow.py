import json
import logging
import webbrowser
from pathlib import Path
from typing import Any, Iterable

import msgspec
from PySide6 import QtCore, QtGui, QtStateMachine, QtWidgets

from ..core import messages
from ..core.context import ContextState, MainContext, WorkerContext
from ..core.resource import ResourceConfig
from ..core.service import BackgroundService
from ..core.utils import Vector3, Waveform
from ..core.worker import Worker
from ..operations import operation_registry
from . import config
from .dashboard import DashboardWidget
from .logwidget import LogWidget
from .operation import OperationWidget
from .settingsdialog import SettingsDialog

__all__ = ["MainWindow"]


class MainWindow(QtWidgets.QMainWindow):
    operation_started = QtCore.Signal(object)
    operation_finished = QtCore.Signal()

    def __init__(
        self, state: ContextState, parent: QtWidgets.QWidget | None = None
    ) -> None:
        super().__init__(parent)

        self.setMinimumSize(640, 480)

        self._context = MainContext(state)

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

        self._waveform_cache: dict[str, Waveform] = {}

        self._waveform_timer = QtCore.QTimer(self)
        self._waveform_timer.timeout.connect(self._on_update_waveform)
        self._waveform_timer.start(16)

        self._create_state_machine()

        # Sync

        self._dashboard_widget.set_scope_channels(self._context.scope_channels())

        self._update_timer = QtCore.QTimer(self)
        self._update_timer.timeout.connect(self._on_update_timeout)
        self._update_timer.start(250)

        # Worker thread
        self._background_service = BackgroundService(
            "worker", Worker(WorkerContext(state))
        )
        self._background_service.start()

        self._load_operations()

        self._settings = QtCore.QSettings()
        self.read_settings(self._settings)

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

        # Scope

        self._dashboard_widget.scope_group_box.preview_toggled.connect(
            self._on_toggle_scope_live
        )
        self._dashboard_widget.scope_group_box.channels_changed.connect(
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

        self._move_relative_state = QtStateMachine.QState()
        self._move_relative_state.entered.connect(self._on_enter_move_relative)

        self._operation_state = QtStateMachine.QState()
        self._operation_state.entered.connect(self._on_enter_operation)

        self._abort_state = QtStateMachine.QState()
        self._abort_state.entered.connect(self._on_enter_abort)

        self._idle_state.addTransition(
            self._dashboard_widget.configure_triggered, self._configure_state
        )
        self._idle_state.addTransition(
            self._dashboard_widget.move_relative_triggered, self._move_relative_state
        )
        self._idle_state.addTransition(self.operation_started, self._operation_state)

        self._configure_state.addTransition(self.operation_finished, self._idle_state)

        self._move_relative_state.addTransition(
            self.operation_finished, self._idle_state
        )
        self._move_relative_state.addTransition(
            self._abort_action.triggered, self._abort_state
        )

        self._operation_state.addTransition(self.operation_finished, self._idle_state)
        self._operation_state.addTransition(
            self._abort_action.triggered, self._abort_state
        )

        self._abort_state.addTransition(self.operation_finished, self._idle_state)

        self._state_machine = QtStateMachine.QStateMachine(self)
        self._state_machine.addState(self._idle_state)
        self._state_machine.addState(self._configure_state)
        self._state_machine.addState(self._move_relative_state)
        self._state_machine.addState(self._operation_state)
        self._state_machine.addState(self._abort_state)
        self._state_machine.setInitialState(self._idle_state)
        self._state_machine.start()

    def _load_operations(self) -> None:
        for widget_cls in operation_registry:
            self.add_operation(widget_cls(self))

    def add_operation(self, operation: OperationWidget) -> None:
        self._run_operation_sep.setVisible(True)
        start_action = QtGui.QAction(operation.windowTitle(), self)
        operation.start_triggered.connect(start_action.trigger)
        self._run_menu.insertAction(self._run_operation_sep, start_action)
        start_action.triggered.connect(lambda: self.operation_started.emit(operation))
        operation.abort_triggered.connect(self._abort_action.trigger)
        self._dashboard_widget.add_operation(operation)
        self._operation_start_actions.append(start_action)

    def read_settings(self, settings: QtCore.QSettings) -> None:
        settings.beginGroup("MainWindow")
        geometry = settings.value("geometry")
        state = settings.value("state")
        instruments = settings.value("instruments")
        connections = settings.value("connections")
        scope_channels = settings.value("scope_channels")
        sample_name = settings.value("sample_name", "Unnamed", type=str)
        output_path = settings.value("output_path", str(Path.home()), type=str)
        settings.endGroup()

        if isinstance(geometry, QtCore.QByteArray):
            self.restoreGeometry(geometry)
        if isinstance(state, QtCore.QByteArray):
            self.restoreState(state)
        if isinstance(instruments, str):
            self.restore_instruments(instruments)
        if isinstance(connections, str):
            self.restore_connections(connections)
        if isinstance(scope_channels, str):
            self.restore_scope_channels(scope_channels)
        if isinstance(sample_name, str):
            self._dashboard_widget.set_sample_name(sample_name)
        if isinstance(output_path, str):
            self._dashboard_widget.set_output_path(output_path)

        for widget in self._dashboard_widget.operation_widgets():
            widget.read_settings(settings)

    def write_settings(self, settings: QtCore.QSettings) -> None:
        settings.beginGroup("MainWindow")

        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("state", self.saveState())
        settings.setValue("instruments", self.save_instruments())
        settings.setValue("connections", self.save_connections())
        settings.setValue("scope_channels", self.save_scope_channels())
        settings.setValue("sample_name", self._dashboard_widget.sample_name())
        settings.setValue("output_path", self._dashboard_widget.output_path())

        settings.endGroup()

        for widget in self._dashboard_widget.operation_widgets():
            widget.write_settings(settings)

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
        connections = set()
        for (
            instrument,
            button,
        ) in self._dashboard_widget.station_group_box._instrument_buttons.items():
            if button.isChecked():
                connections.add(instrument)
        return json.dumps(list(connections))

    def restore_connections(self, connections: str) -> None:
        try:
            connections_ = json.loads(connections)
        except Exception:
            connections_ = []
        for instrument in connections_:
            self._context.connect(instrument)

    def save_scope_channels(self) -> str:
        scope_channels = self._dashboard_widget.active_scope_channels()
        return json.dumps(list(scope_channels))

    def restore_scope_channels(self, data: str) -> None:
        try:
            scope_channels = json.loads(data)
        except Exception:
            scope_channels = []
        self._dashboard_widget.set_active_scope_channels(scope_channels)

    @QtCore.Slot(str)
    def _on_connect_instrument(self, instrument: str) -> None:
        self._context.connect(instrument)

    @QtCore.Slot(str)
    def _on_disconnect_instrument(self, instrument: str) -> None:
        self._context.disconnect(instrument)

    @QtCore.Slot()
    def _on_update_timeout(self) -> None:
        self.update_instrument_state()
        self.process_pending_messages(max_count=1024)

    def update_instrument_state(self) -> None:
        for name, actor in self._context.station.actors().items():
            connection_state = actor.connection_state()
            self._dashboard_widget.set_instrument_state(name, connection_state)

    def process_pending_messages(self, max_count: int) -> None:
        """Process at most `max_count` queued messages."""
        for _ in range(max_count):
            message = self._context.next_message()

            if message is None:
                return

            self._dispatch_message(message)

    def _dispatch_message(self, message: Any) -> None:
        """Route one application message to its handler."""
        match message:
            case messages.WaveformChanged(waveform):
                self.set_waveform(waveform)

            case messages.StatusMessage(text):
                self.set_status_message(text)

            case messages.StatusProgress(step, steps):
                self.set_status_progress(step, steps)

            case messages.Failed(exception):
                self.set_exception(exception)

            case messages.Finished():
                self.operation_finished.emit()

            case messages.PositionChanged(position):
                self._dashboard_widget.set_position(position)

            case messages.LaserMetrics() as metrics:
                self._dashboard_widget.set_laser_metrics(metrics)

            case messages.PowerMeterPower(index, value):
                self._dashboard_widget.set_laser_power(index, value)

            case messages.PowerMeterWavelength(index, value):
                self._dashboard_widget.set_power_meter_wavelength(index, value)

            case messages.PowerMeterAverageCount(index, value):
                self._dashboard_widget.set_power_meter_average_count(index, value)

        for operation_widget in self._dashboard_widget.operation_widgets():
            operation_widget.handle_message(message)

    @QtCore.Slot()
    def _on_enter_idle(self) -> None:
        logging.info("entered [idle]")
        self.set_inputs_enabled(True)
        self.set_abort_enabled(False)
        self.clear_message()
        self.clear_progress()

    @QtCore.Slot()
    def _on_enter_configure(self) -> None:
        logging.info("entered [configure]")
        self.set_inputs_enabled(False)
        self.set_abort_enabled(False)
        data = self._dashboard_widget.flush_configure_cache()
        self._context.tell(messages.ConfigureMessage(data))

    @QtCore.Slot()
    def _on_enter_move_relative(self) -> None:
        logging.info("entered [move relative]")
        self.set_inputs_enabled(False)
        self.set_abort_enabled(False)
        pos = self._dashboard_widget.flush_move_relative_cache()
        self._context.tell(messages.MoveRelativeMessage(Vector3(pos.x, pos.y, pos.z)))

    @QtCore.Slot()
    def _on_enter_operation(self) -> None:
        logging.info("entered [operation]")
        self.clear_exception()
        self.set_inputs_enabled(False)
        self.set_abort_enabled(True)
        current_operation = self._current_operation
        if current_operation is not None:
            self._dashboard_widget.show_operation(current_operation)
            current_operation.clear()
            operation = current_operation.config()
            self._context.tell(operation)
        self._current_operation = None

    @QtCore.Slot()
    def _on_enter_abort(self) -> None:
        logging.info("entered [abort]")
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

    @QtCore.Slot()
    def _on_update_waveform(self) -> None:
        if self._waveform_cache:
            waveforms = list(self._waveform_cache.values())
            channels = self._dashboard_widget.active_scope_channels()
            filtered_waveform = []
            for waveform in waveforms:
                if waveform.channel in channels:
                    filtered_waveform.append(waveform)
                else:
                    self._waveform_cache.pop(waveform.channel, None)
            self._dashboard_widget.scope_group_box.set_waveforms(filtered_waveform)

    def set_waveform(self, waveform: Waveform):
        self._waveform_cache[waveform.channel] = waveform

    @QtCore.Slot(bool)
    def _on_toggle_scope_live(self, toggled: bool) -> None:
        self._context.set_live_waveform(toggled)

    @QtCore.Slot(object)
    def _on_scope_channels_changed(self, channels: Iterable[str]) -> None:
        channels = list(channels)
        self._context.set_waveform_channels(channels)
        self._dispatch_message(messages.EnabledChannelsChanged(channels))

    @QtCore.Slot()
    def show_settings(self) -> None:
        dialog = SettingsDialog(self)
        dialog.read_settings(self._settings)

        for name, actor in self._context.station.actors().items():
            resource_config = actor.resource_config()
            dialog.set_instrument_model(name, resource_config.model)
            dialog.set_instrument_resource_name(name, resource_config.resource_name)
            dialog.set_instrument_termination(name, resource_config.termination)
            dialog.set_instrument_timeout(name, resource_config.timeout)
            dialog.set_instrument_baud_rate(name, resource_config.baud_rate)

        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            for name, actor in self._context.station.actors().items():
                actor.set_resource_config(
                    ResourceConfig(
                        model=dialog.instrument_model(name),
                        resource_name=dialog.instrument_resource_name(name),
                        termination=dialog.instrument_termination(name),
                        timeout=dialog.instrument_timeout(name),
                        baud_rate=dialog.instrument_baud_rate(name),
                    )
                )

        dialog.write_settings(self._settings)

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
            self.write_settings(self._settings)
            event.accept()
        else:
            event.ignore()
