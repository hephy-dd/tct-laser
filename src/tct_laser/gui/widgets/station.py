from PySide6 import QtCore, QtWidgets

from tct_laser.core.actors.instrument import ConnectionState

__all__ = ["StationGroupBox"]


class StationGroupBox(QtWidgets.QGroupBox):
    connect_instrument = QtCore.Signal(str)
    disconnect_instrument = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.setTitle("Station")

        self._instrument_labels: dict[str, QtWidgets.QLabel] = {}
        self._instrument_buttons: dict[str, QtWidgets.QPushButton] = {}
        self._instrument_states: dict[str, ConnectionState] = {}

        self._form_layout = QtWidgets.QFormLayout(self)

    def set_inputs_enabled(self, enabled: bool) -> None:
        self.setEnabled(enabled)

    def add_instrument(self, name: str, label: str) -> None:
        if name in self._instrument_labels:
            return

        state_label = QtWidgets.QLabel(self)
        state_label.setFixedWidth(96)
        state_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        button = QtWidgets.QPushButton(self)
        button.setCheckable(True)
        button.setFixedWidth(96)
        button.toggled.connect(
            lambda checked, instrument_name=name: self._on_button_toggled(
                instrument_name,
                checked,
            )
        )

        row_widget = QtWidgets.QWidget(self)
        row_layout = QtWidgets.QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(state_label)
        row_layout.addWidget(button)
        row_layout.addStretch()

        self._instrument_labels[name] = state_label
        self._instrument_buttons[name] = button

        self._form_layout.addRow(label, row_widget)

        self.set_instrument_state(name, ConnectionState.DISCONNECTED)

    def set_instrument_state(self, name: str, state: ConnectionState) -> None:
        label = self._instrument_labels.get(name)
        button = self._instrument_buttons.get(name)

        if label is None or button is None:
            return

        self._instrument_states[name] = state

        text = state.name.replace("_", " ").title()
        label.setText(text)

        if state is ConnectionState.ERROR:
            styles = "color: white; background-color: red;"
        elif state is ConnectionState.CONNECTED:
            styles = "color: white; background-color: green;"
        elif state is ConnectionState.CONNECTING:
            styles = "color: black; background-color: orange;"
        else:
            styles = "color: black; background-color: darkgrey;"

        label.setStyleSheet(f"QLabel {{ padding: 4px; border-radius: 4px; {styles} }}")

        with QtCore.QSignalBlocker(button):
            button.setChecked(state is ConnectionState.CONNECTED)

        if state is ConnectionState.CONNECTED:
            button.setText("Disconnect")
            button.setEnabled(True)
        elif state is ConnectionState.CONNECTING:
            button.setText("Connecting")
            button.setEnabled(False)
        else:
            button.setText("Connect")
            button.setEnabled(True)

    def _on_button_toggled(self, name: str, checked: bool) -> None:
        button = self._instrument_buttons.get(name)
        if button is None:
            return

        button.setEnabled(False)

        if checked:
            button.setText("Connecting")
            self.connect_instrument.emit(name)
        else:
            button.setText("Disconnecting")
            self.disconnect_instrument.emit(name)
