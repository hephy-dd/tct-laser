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
from .settingsdialog import SettingsDialog

__all__ = ["MainWindow"]


class MainWindow(QtWidgets.QMainWindow):
    run_operation = QtCore.Signal(object)
    finished = QtCore.Signal()

    def __init__(
        self, state: ContextState, parent: QtWidgets.QWidget | None = None
    ) -> None:
        super().__init__(parent)

        self.setMinimumSize(640, 480)

        self.context = MainContext(state)

        self._settings = QtCore.QSettings()

        self._create_actions()
        self._create_menus()
        self._create_dashboard()
        self._create_dock_widgets()
        self._create_status_bar()

        self.current_operation = None
        self.run_operation.connect(
            lambda operation: setattr(self, "current_operation", operation)
        )

        self.waveform_cache: dict[str, Waveform] = {}

        self.waveform_timer = QtCore.QTimer(self)
        self.waveform_timer.timeout.connect(self.update_waveform)
        self.waveform_timer.start(16)

        for widget_cls in operation_registry:
            self.add_operation(widget_cls(self))

        self._create_state_machine()

        # Sync

        self.dashboard_widget.scope_group_box.set_channels(
            self.context.scope_channels()
        )
        # self.set_parameter(messages.EnabledChannelsChanged(channels))

        # self.context.set_waveform_channels(
        #     self.dashboard_widget.scope_group_box.active_channels()
        # )

        self.read_settings(self._settings)

        self.update_timer = QtCore.QTimer(self)
        self.update_timer.timeout.connect(self.on_update_timeout)
        self.update_timer.start(250)

        # Worker thread
        self.background_service = BackgroundService(
            "worker", Worker(WorkerContext(state))
        )
        self.background_service.start()

    def _create_actions(self) -> None:
        self.quit_action = QtGui.QAction("&Quit", self)
        self.quit_action.setShortcut(QtGui.QKeySequence.StandardKey.Quit)
        self.quit_action.triggered.connect(self.close)

        self.settings_action = QtGui.QAction("&Settings...", self)
        self.settings_action.triggered.connect(self.show_settings)

        self.abort_action = QtGui.QAction("&Abort", self)

        self.contents_action = QtGui.QAction("&Contents", self)
        self.contents_action.setShortcut("F1")
        self.contents_action.triggered.connect(self.show_contents)

        self.about_qt_action = QtGui.QAction("About &Qt", self)
        self.about_qt_action.triggered.connect(self.show_about_qt)

        self.about_action = QtGui.QAction("&About", self)
        self.about_action.triggered.connect(self.show_about)

    def _create_menus(self) -> None:
        self.file_menu = self.menuBar().addMenu("&File")
        self.file_menu.addAction(self.quit_action)

        self.view_menu = self.menuBar().addMenu("&View")

        self.edit_menu = self.menuBar().addMenu("&Edit")
        self.edit_menu.addAction(self.settings_action)

        self.run_menu = self.menuBar().addMenu("&Run")
        self.run_operation_sep = self.run_menu.addSeparator()
        self.run_operation_sep.setVisible(False)
        self.run_menu.addAction(self.abort_action)

        self.help_menu = self.menuBar().addMenu("&Help")
        self.help_menu.addAction(self.contents_action)
        self.help_menu.addSeparator()
        self.help_menu.addAction(self.about_qt_action)
        self.help_menu.addAction(self.about_action)

    def _create_dashboard(self) -> None:
        self.dashboard_widget = DashboardWidget(self)
        self.setCentralWidget(self.dashboard_widget)
        self.dashboard_widget.connect_instrument.connect(self.on_connect_instrument)
        self.dashboard_widget.disconnect_instrument.connect(
            self.on_disconnect_instrument
        )
        self.dashboard_widget.sample_name_changed.connect(
            lambda sample_name: self.context.set_sample_name(sample_name)
        )
        self.dashboard_widget.output_path_changed.connect(
            lambda output_path: self.context.set_output_path(output_path)
        )

        # Scope

        self.dashboard_widget.scope_group_box.preview_toggled.connect(
            self.toggle_scope_live
        )
        self.dashboard_widget.scope_group_box.channels_changed.connect(
            self.scope_channels_changed
        )

    def _create_dock_widgets(self) -> None:
        self.log_widget = LogWidget(self)
        self.log_widget.add_logger(logging.getLogger())

        self.log_dock = QtWidgets.QDockWidget("Log Window", self)
        self.log_dock.setObjectName("LogDock")  # saveState/restoreState
        self.log_dock.setWidget(self.log_widget)
        self.log_dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea)
        self.log_dock.setFeatures(
            QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, self.log_dock)

        self.log_dock.hide()
        self.log_action = self.log_dock.toggleViewAction()
        self.view_menu.addAction(self.log_action)

    def _create_status_bar(self) -> None:
        self.message_label = QtWidgets.QLabel(self)

        self.progress_bar = QtWidgets.QProgressBar(self)
        self.progress_bar.setMaximumWidth(300)
        self.progress_bar.hide()

        self.statusBar().addPermanentWidget(self.message_label)
        self.statusBar().addPermanentWidget(self.progress_bar)

    def _create_state_machine(self) -> None:
        self.idle_state = QtStateMachine.QState()
        self.idle_state.entered.connect(self.enter_idle)

        self.configure_state = QtStateMachine.QState()
        self.configure_state.entered.connect(self.enter_configure)

        self.move_relative_state = QtStateMachine.QState()
        self.move_relative_state.entered.connect(self.enter_move_relative)

        self.operation_state = QtStateMachine.QState()
        self.operation_state.entered.connect(self.enter_operation)

        self.abort_state = QtStateMachine.QState()
        self.abort_state.entered.connect(self.enter_abort)

        self.idle_state.addTransition(
            self.dashboard_widget.configure_triggered, self.configure_state
        )
        self.idle_state.addTransition(
            self.dashboard_widget.move_relative_triggered, self.move_relative_state
        )
        self.idle_state.addTransition(self.run_operation, self.operation_state)

        self.configure_state.addTransition(self.finished, self.idle_state)

        self.move_relative_state.addTransition(self.finished, self.idle_state)
        self.move_relative_state.addTransition(
            self.abort_action.triggered, self.abort_state
        )

        self.operation_state.addTransition(self.finished, self.idle_state)
        self.operation_state.addTransition(
            self.abort_action.triggered, self.abort_state
        )

        self.abort_state.addTransition(self.finished, self.idle_state)

        self.state_machine = QtStateMachine.QStateMachine(self)
        self.state_machine.addState(self.idle_state)
        self.state_machine.addState(self.configure_state)
        self.state_machine.addState(self.move_relative_state)
        self.state_machine.addState(self.operation_state)
        self.state_machine.addState(self.abort_state)
        self.state_machine.setInitialState(self.idle_state)
        self.state_machine.start()

    def add_operation(self, widget) -> None:
        self.run_operation_sep.setVisible(True)
        self.run_menu.insertAction(self.run_operation_sep, widget.run_action)
        widget.run_action.triggered.connect(lambda: self.run_operation.emit(widget))
        widget.abort_triggered.connect(self.abort_action.trigger)
        self.dashboard_widget.operations_tab_widget.addTab(widget, widget.windowTitle())
        self.dashboard_widget.operation_widgets.append(widget)

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
            self.dashboard_widget.set_sample_name(sample_name)
        if isinstance(output_path, str):
            self.dashboard_widget.set_output_path(output_path)

        for widget in self.dashboard_widget.operation_widgets:
            if hasattr(widget, "read_settings"):
                widget.read_settings(settings)

    def write_settings(self, settings: QtCore.QSettings) -> None:
        settings.beginGroup("MainWindow")

        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("state", self.saveState())
        settings.setValue("instruments", self.save_instruments())
        settings.setValue("connections", self.save_connections())
        settings.setValue("scope_channels", self.save_scope_channels())
        settings.setValue("sample_name", self.dashboard_widget.sample_name())
        settings.setValue("output_path", self.dashboard_widget.output_path())

        settings.endGroup()

        for widget in self.dashboard_widget.operation_widgets:
            if hasattr(widget, "write_settings"):
                widget.write_settings(settings)

    def save_instruments(self) -> str:
        try:
            instruments = {
                name: msgspec.to_builtins(actor.resource_config())
                for name, actor in self.context.station.actors().items()
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

        for name, actor in self.context.station.actors().items():
            config_data = instruments.get(name, {})
            actor.set_resource_config(msgspec.convert(config_data, ResourceConfig))

    def save_connections(self) -> str:
        connections = set()
        for (
            instrument,
            button,
        ) in self.dashboard_widget.station_group_box._instrument_buttons.items():
            if button.isChecked():
                connections.add(instrument)
        return json.dumps(list(connections))

    def restore_connections(self, connections: str) -> None:
        try:
            connections_ = json.loads(connections)
        except Exception:
            connections_ = []
        for instrument in connections_:
            self.context.connect(instrument)

    def save_scope_channels(self) -> str:
        scope_channels = self.dashboard_widget.scope_group_box.active_channels()
        return json.dumps(list(scope_channels))

    def restore_scope_channels(self, data: str) -> None:
        try:
            scope_channels = json.loads(data)
        except Exception:
            scope_channels = []
        self.dashboard_widget.scope_group_box.set_active_channels(scope_channels)

    @QtCore.Slot(str)
    def on_connect_instrument(self, instrument: str) -> None:
        self.context.connect(instrument)

    @QtCore.Slot(str)
    def on_disconnect_instrument(self, instrument: str) -> None:
        self.context.disconnect(instrument)

    @QtCore.Slot()
    def on_update_timeout(self) -> None:
        self.update_instrument_state()
        self.handle_messages(1024)

    def update_instrument_state(self) -> None:
        for name, actor in self.context.station.actors().items():
            connection_state = actor.connection_state()
            self.dashboard_widget.set_instrument_state(name, connection_state)

    def handle_messages(self, max_count: int) -> None:
        for _ in range(max_count):
            message = self.context.next_message()
            if message is None:
                break
            else:
                match message:
                    case Waveform() as waveform:
                        self.set_waveform(waveform)
                    case messages.ParameterChanged(parameter):
                        self.set_parameter(parameter)
                    case messages.StatusMessage(text):
                        self.set_message(text)
                    case messages.StatusProgress(step, steps):
                        self.set_progress(step, steps)
                    case messages.Failed(exc):
                        self.set_exception(exc)
                    case messages.Finished():
                        self.finished.emit()

    @QtCore.Slot()
    def enter_idle(self) -> None:
        logging.info("entered [idle]")
        self.set_inputs_enabled(True)
        self.set_abort_enabled(False)
        self.clear_message()
        self.clear_progress()

    @QtCore.Slot()
    def enter_configure(self) -> None:
        logging.info("entered [configure]")
        self.set_inputs_enabled(False)
        self.set_abort_enabled(False)
        data = self.dashboard_widget.flush_configure_cache()
        self.context.tell(messages.ConfigureMessage(data))

    @QtCore.Slot()
    def enter_move_relative(self) -> None:
        logging.info("entered [move relative]")
        self.set_inputs_enabled(False)
        self.set_abort_enabled(False)
        pos = self.dashboard_widget.flush_move_relative_cache()
        self.context.tell(messages.MoveRelativeMessage(Vector3(pos.x, pos.y, pos.z)))

    @QtCore.Slot()
    def enter_operation(self) -> None:
        logging.info("entered [operation]")
        self.clear_exception()
        self.set_inputs_enabled(False)
        self.set_abort_enabled(True)
        current_operation = self.current_operation
        if current_operation is not None:
            self.dashboard_widget.show_operation(current_operation)
            operation = current_operation.config()
            self.context.tell(operation)

    @QtCore.Slot()
    def enter_abort(self) -> None:
        logging.info("entered [abort]")
        self.set_abort_enabled(False)
        self.context.abort()

    def set_inputs_enabled(self, enabled: bool) -> None:
        self.settings_action.setEnabled(enabled)
        self.dashboard_widget.set_inputs_enabled(enabled)

    def set_abort_enabled(self, enabled: bool) -> None:
        self.abort_action.setEnabled(enabled)
        self.dashboard_widget.set_abort_enabled(enabled)

    def set_exception(self, exc: Exception) -> None:
        self.dashboard_widget.error_label.show_exception(exc)

    def clear_exception(self) -> None:
        self.dashboard_widget.error_label.hide()

    def set_message(self, text: str) -> None:
        self.message_label.setText(text)

    def clear_message(self) -> None:
        self.message_label.clear()

    def set_progress(self, step: int, steps: int) -> None:
        self.progress_bar.setRange(0, steps)
        self.progress_bar.setValue(step)
        self.progress_bar.show()

    def clear_progress(self) -> None:
        self.progress_bar.hide()

    def set_parameter(self, parameter: Any) -> None:
        match parameter:
            case messages.PositionChanged(position):
                self.dashboard_widget.set_position(position)
            case messages.LaserMetrics() as metrics:
                self.dashboard_widget.set_laser_metrics(metrics)
            case messages.PowerMeterPower(index, value):
                self.dashboard_widget.set_laser_power(index, value)
            case messages.PowerMeterWavelength(index, value):
                self.dashboard_widget.set_power_meter_wavelength(index, value)
            case messages.PowerMeterAverageCount(index, value):
                self.dashboard_widget.set_power_meter_average_count(index, value)

        for operation in self.dashboard_widget.operation_widgets:
            if hasattr(operation, "set_parameter"):
                operation.set_parameter(parameter)

    def update_waveform(self) -> None:
        if self.waveform_cache:
            waveforms = list(self.waveform_cache.values())
            channels = self.dashboard_widget.scope_group_box.active_channels()
            filtered_waveform = []
            for waveform in waveforms:
                if waveform.channel in channels:
                    filtered_waveform.append(waveform)
                else:
                    self.waveform_cache.pop(waveform.channel, None)
            self.dashboard_widget.scope_group_box.set_waveforms(filtered_waveform)

    def set_waveform(self, waveform: Waveform):
        self.waveform_cache[waveform.channel] = waveform

    @QtCore.Slot(bool)
    def toggle_scope_live(self, toggled: bool) -> None:
        self.context.set_live_waveform(toggled)

    @QtCore.Slot(object)
    def scope_channels_changed(self, channels: Iterable[str]) -> None:
        channels = list(channels)
        self.context.set_waveform_channels(channels)
        self.set_parameter(messages.EnabledChannelsChanged(channels))

    @QtCore.Slot()
    def show_settings(self) -> None:
        dialog = SettingsDialog(self)
        dialog.read_settings(self._settings)

        for name, actor in self.context.station.actors().items():
            resource_config = actor.resource_config()
            dialog.set_instrument_model(name, resource_config.model)
            dialog.set_instrument_resource_name(name, resource_config.resource_name)
            dialog.set_instrument_termination(name, resource_config.termination)
            dialog.set_instrument_timeout(name, resource_config.timeout)
            dialog.set_instrument_baud_rate(name, resource_config.baud_rate)

        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            for name, actor in self.context.station.actors().items():
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
            self.context.shutdown()
            self.background_service.stop()
            self.state_machine.stop()
            self.write_settings(self._settings)
            event.accept()
        else:
            event.ignore()
