import logging

from PySide6 import QtCore, QtWidgets

from ..core.resource import is_serial_resource, list_resources

__all__ = ["SettingsDialog"]


class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")

        self.scope_widget = InstrumentWidget(self)
        self.scope_widget.add_model(
            urn="urn:comet:model:rohde_schwarz:rto6",
            title="Rohde&Schwarz RTO6",
        )
        self.scope_widget.add_model(
            urn="urn:comet:model:rohde_schwarz:rtp164",
            title="Rohde&Schwarz RTP164",
        )

        self.laser_widget = InstrumentWidget(self)
        self.laser_widget.add_model(
            urn="urn:comet:model:hephy:pilascontroller",
            title="HEPHY Pilas Controller (GUI)",
        )
        self.laser_widget.add_model(
            urn="urn:comet:model:nkt_photonics:pilas",
            title="NKT Photonics PILAS",
        )

        self.stage_widget = InstrumentWidget(self)
        self.stage_widget.add_model(
            urn="urn:comet:model:mbi:tablecontrol",
            title="MBI Table-Control (GUI)",
        )
        self.stage_widget.add_model(
            urn="urn:comet:model:hephy:corvuscontroller",
            title="HEPHY Corvus Controller (GUI)",
        )
        self.stage_widget.add_model(
            urn="urn:comet:model:itk:corvustt",
            title="ITK CorvusTT",
        )

        self.power_meter_1_widget = InstrumentWidget(self)
        self.power_meter_1_widget.add_model(
            urn="urn:comet:model:thorlabs:pm100",
            title="Thorlabs PM100",
        )

        self.power_meter_2_widget = InstrumentWidget(self)
        self.power_meter_2_widget.add_model(
            urn="urn:comet:model:thorlabs:pm100",
            title="Thorlabs PM100",
        )

        self.power_meter_3_widget = InstrumentWidget(self)
        self.power_meter_3_widget.add_model(
            urn="urn:comet:model:thorlabs:pm100",
            title="Thorlabs PM100",
        )

        self.tab_widget = QtWidgets.QTabWidget(self)
        self.tab_widget.addTab(self.scope_widget, "Scope")
        self.tab_widget.addTab(self.laser_widget, "Laser")
        self.tab_widget.addTab(self.stage_widget, "Stage")
        self.tab_widget.addTab(self.power_meter_1_widget, "Power Meter 1")
        self.tab_widget.addTab(self.power_meter_2_widget, "Power Meter 2")
        self.tab_widget.addTab(self.power_meter_3_widget, "Power Meter 3")

        self.button_box = QtWidgets.QDialogButtonBox(self)
        self.button_box.addButton(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        self.button_box.addButton(QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.tab_widget)
        layout.addWidget(self.button_box)

        self.instrument_widgets: dict[str, InstrumentWidget] = {
            "scope": self.scope_widget,
            "laser": self.laser_widget,
            "stage": self.stage_widget,
            "power_meter_1": self.power_meter_1_widget,
            "power_meter_2": self.power_meter_2_widget,
            "power_meter_3": self.power_meter_3_widget,
        }

    def _instrument_widget(self, name: str):
        try:
            return self.instrument_widgets[name]
        except KeyError as exc:
            raise ValueError(f"Unknown instrument: {name}") from exc

    def read_settings(self, settings: QtCore.QSettings) -> None:
        settings.beginGroup("SettingsDialog")
        geometry = settings.value("geometry")
        settings.endGroup()
        if isinstance(geometry, QtCore.QByteArray):
            self.restoreGeometry(geometry)

    def write_settings(self, settings: QtCore.QSettings) -> None:
        settings.beginGroup("SettingsDialog")
        settings.setValue("geometry", self.saveGeometry())
        settings.endGroup()

    def instrument_model(self, name: str) -> str:
        return self._instrument_widget(name).model()

    def set_instrument_model(self, name: str, model: str) -> None:
        self._instrument_widget(name).set_model(model)

    def instrument_resource_name(self, name: str) -> str:
        return self._instrument_widget(name).resource_name()

    def set_instrument_resource_name(self, name: str, resource_name: str) -> None:
        self._instrument_widget(name).set_resource_name(resource_name)

    def instrument_baud_rate(self, name: str) -> int:
        return self._instrument_widget(name).baud_rate()

    def set_instrument_baud_rate(self, name: str, baud_rate: int) -> None:
        self._instrument_widget(name).set_baud_rate(baud_rate)

    def instrument_termination(self, name: str) -> str:
        return self._instrument_widget(name).termination()

    def set_instrument_termination(self, name: str, termination: str) -> None:
        self._instrument_widget(name).set_termination(termination)

    def instrument_timeout(self, name: str) -> float:
        return self._instrument_widget(name).timeout()

    def set_instrument_timeout(self, name: str, timeout: float) -> None:
        self._instrument_widget(name).set_timeout(timeout)


class InstrumentWidget(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.model_combo_box = QtWidgets.QComboBox(self)

        self.resource_name_line_edit = QtWidgets.QLineEdit(self)
        self.resource_name_line_edit.textChanged.connect(self._resource_name_changed)

        self.resource_button = QtWidgets.QToolButton(self)
        self.resource_button.setText("...")
        self.resource_button.setStatusTip("Search for resources")
        self.resource_button.clicked.connect(self._list_resources)

        self.resource_widget = QtWidgets.QWidget(self)

        resource_widget_layout = QtWidgets.QHBoxLayout(self.resource_widget)
        resource_widget_layout.setContentsMargins(0, 0, 0, 0)
        resource_widget_layout.addWidget(self.resource_name_line_edit)
        resource_widget_layout.addWidget(self.resource_button)

        self.baud_rate_combo_box = QtWidgets.QComboBox(self)
        self.baud_rate_combo_box.addItem("1200", 1200)
        self.baud_rate_combo_box.addItem("2400", 2400)
        self.baud_rate_combo_box.addItem("4800", 4800)
        self.baud_rate_combo_box.addItem("9600", 9600)
        self.baud_rate_combo_box.addItem("19200", 19200)
        self.baud_rate_combo_box.addItem("38400", 38400)
        self.baud_rate_combo_box.addItem("57600", 57600)
        self.baud_rate_combo_box.addItem("115200", 115200)
        self.baud_rate_combo_box.addItem("230400", 230400)
        self.baud_rate_combo_box.addItem("460800", 460800)
        self.baud_rate_combo_box.addItem("921600", 921600)
        self.baud_rate_combo_box.setCurrentText("9600")

        self.termination_combo_box = QtWidgets.QComboBox(self)
        self.termination_combo_box.addItem("LF (\\n)", "\n")
        self.termination_combo_box.addItem("CR (\\r)", "\r")
        self.termination_combo_box.addItem("CR+LF (\\r\\n)", "\r\n")

        self.timeout_spin_box = QtWidgets.QDoubleSpinBox(self)
        self.timeout_spin_box.setDecimals(1)
        self.timeout_spin_box.setRange(0, 60)
        self.timeout_spin_box.setValue(4)
        self.timeout_spin_box.setSuffix(" s")

        self.form_layout = QtWidgets.QFormLayout(self)
        self.form_layout.addRow("Model", self.model_combo_box)
        self.form_layout.addRow("Resource Name", self.resource_widget)
        self.form_layout.addRow("Baud Rate", self.baud_rate_combo_box)
        self.form_layout.addRow("Termination", self.termination_combo_box)
        self.form_layout.addRow("Timeout", self.timeout_spin_box)

        self._resource_name_changed(self.resource_name_line_edit.text())

    @QtCore.Slot(str)
    def _resource_name_changed(self, resource_name: str) -> None:
        resource_name = resource_name.strip()
        if is_serial_resource(resource_name):
            self.form_layout.setRowVisible(2, True)
        else:
            self.form_layout.setRowVisible(2, False)

    @QtCore.Slot()
    def _list_resources(self) -> None:
        dialog = SelectResourceDialog(self)
        dialog.resize(320, 240)

        try:
            for resource_name in list_resources():
                dialog.add_resource_name(resource_name)
        except Exception:
            logging.exception("Failed to load resources")

        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.set_resource_name(dialog.current_resource_name())

    def add_model(self, urn: str, title: str) -> None:
        self.model_combo_box.addItem(title, urn)

    def model(self) -> str:
        model = self.model_combo_box.currentData()
        if isinstance(model, str):
            return model
        return ""

    def set_model(self, urn: str) -> None:
        index = self.model_combo_box.findData(urn)
        if index < 0:
            index = 0
        self.model_combo_box.setCurrentIndex(index)

    def resource_name(self) -> str:
        return self.resource_name_line_edit.text()

    def set_resource_name(self, resource_name: str) -> None:
        self.resource_name_line_edit.setText(resource_name)

    def baud_rate(self) -> int:
        return int(self.baud_rate_combo_box.currentData())

    def set_baud_rate(self, baud_rate: int) -> None:
        index = self.baud_rate_combo_box.findData(baud_rate)
        if index < 0:
            index = 0
        self.baud_rate_combo_box.setCurrentIndex(index)

    def termination(self) -> str:
        return self.termination_combo_box.currentData() or ""

    def set_termination(self, termination: str) -> None:
        index = self.termination_combo_box.findData(termination)
        if index < 0:
            index = 0
        self.termination_combo_box.setCurrentIndex(index)

    def timeout(self) -> float:
        return self.timeout_spin_box.value()

    def set_timeout(self, timeout: float) -> None:
        self.timeout_spin_box.setValue(timeout)


class SelectResourceDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select Resource")

        self.resources_list_widget = QtWidgets.QListWidget(self)

        self.button_box = QtWidgets.QDialogButtonBox(self)
        self.button_box.addButton(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        self.button_box.addButton(QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.resources_list_widget)
        layout.addWidget(self.button_box)

    def add_resource_name(self, resource_name: str) -> None:
        self.resources_list_widget.addItem(resource_name)

    def current_resource_name(self) -> str:
        item = self.resources_list_widget.currentItem()
        if item is not None:
            return item.text()
        return ""
