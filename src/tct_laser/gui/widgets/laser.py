import math

from PySide6 import QtCore, QtWidgets

from tct_laser.core.events import LaserMetrics

from ..utils import update_check_box, update_double_spin_box

__all__ = ["LaserGroupBox"]


class LaserGroupBox(QtWidgets.QGroupBox):
    output_changed = QtCore.Signal(bool)
    frequency_changed = QtCore.Signal(float)
    tune_changed = QtCore.Signal(float)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.setTitle("Laser")

        self._last_output = None
        self._last_frequency = None
        self._last_tune = None

        self._output_button = QtWidgets.QCheckBox(self)
        self._output_button.setText("Enabled")
        self._output_button.setCheckable(True)
        self._output_button.toggled.connect(self._on_output_changed)

        self._frequency_spin_box = QtWidgets.QDoubleSpinBox(self)
        self._frequency_spin_box.setDecimals(0)
        self._frequency_spin_box.setSuffix(" Hz")
        self._frequency_spin_box.setRange(1, 1_000_000)
        self._frequency_spin_box.setValue(1_000)
        self._frequency_spin_box.editingFinished.connect(self._on_frequency_editied)

        self._tune_spin_box = QtWidgets.QDoubleSpinBox(self)
        self._tune_spin_box.setDecimals(1)
        self._tune_spin_box.setSuffix(" %")
        self._tune_spin_box.setRange(0, 100)
        self._tune_spin_box.setValue(50)
        self._tune_spin_box.editingFinished.connect(self._on_tune_editied)

        self._laser_head_temperature_line_edit = QtWidgets.QLineEdit(self)
        self._laser_head_temperature_line_edit.setReadOnly(True)

        self._laser_diode_temperature_line_edit = QtWidgets.QLineEdit(self)
        self._laser_diode_temperature_line_edit.setReadOnly(True)

        layout = QtWidgets.QFormLayout(self)
        layout.addWidget(self._output_button)
        layout.addRow("Frequency", self._frequency_spin_box)
        layout.addRow("Tune", self._tune_spin_box)
        layout.addRow("Head Temp.", self._laser_head_temperature_line_edit)
        layout.addRow("Diode Temp.", self._laser_diode_temperature_line_edit)

    def output(self) -> bool:
        return self._output_button.isChecked()

    def set_output(self, enabled: bool) -> None:
        return self._output_button.setChecked(enabled)

    def frequency(self) -> float:
        return self._frequency_spin_box.value()

    def tune(self) -> float:
        return self._tune_spin_box.value()

    def set_inputs_enabled(self, enabled: bool) -> None:
        self._output_button.setEnabled(enabled)
        self._frequency_spin_box.setEnabled(enabled)
        self._tune_spin_box.setEnabled(enabled)

    def set_metrics(self, metrics: LaserMetrics) -> None:
        if metrics.output is not None:
            update_check_box(self._output_button, metrics.output)
        if metrics.frequency is not None:
            update_double_spin_box(self._frequency_spin_box, metrics.frequency)
        if metrics.tune is not None:
            update_double_spin_box(self._tune_spin_box, metrics.tune)
        if metrics.head_temperature is not None:
            if math.isfinite(metrics.head_temperature):
                self._laser_head_temperature_line_edit.setText(
                    f"{metrics.head_temperature:.1f} °C"
                )
            else:
                self._laser_head_temperature_line_edit.setText("n/a")
        else:
            self._laser_head_temperature_line_edit.setText("n/a")
        if metrics.diode_temperature is not None:
            text = {True: "Good", False: "Bad"}.get(metrics.diode_temperature, "")
            self._laser_diode_temperature_line_edit.setText(text)
        else:
            self._laser_diode_temperature_line_edit.setText("n/a")

    @QtCore.Slot(bool)
    def _on_output_changed(self, state: bool) -> None:
        if self._last_output != state:
            self._last_output = state
            self.output_changed.emit(state)

    @QtCore.Slot()
    def _on_frequency_editied(self) -> None:
        value = self._frequency_spin_box.value()
        if self._last_frequency != value:
            self._last_frequency = value
            self.frequency_changed.emit(value)

    @QtCore.Slot()
    def _on_tune_editied(self) -> None:
        value = self._tune_spin_box.value()
        if self._last_tune != value:
            self._last_tune = value
            self.tune_changed.emit(value)
