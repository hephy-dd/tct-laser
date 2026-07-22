from PySide6 import QtCore, QtWidgets

from tct_laser.core.utils import si_format

from ..utils import update_spin_box

__all__ = ["PowerMeterGroupBox"]


class PowerMeterGroupBox(QtWidgets.QGroupBox):
    wavelength_changed = QtCore.Signal(int)
    average_count_changed = QtCore.Signal(int)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.setTitle("Power Meter")

        self._power_line_edit = QtWidgets.QLineEdit(self)
        self._power_line_edit.setReadOnly(True)
        self._power_line_edit.setToolTip("Power in Watts")

        self._wavelength_spin_box = QtWidgets.QSpinBox(self)
        self._wavelength_spin_box.setRange(350, 1100)
        self._wavelength_spin_box.setValue(370)
        self._wavelength_spin_box.setSuffix(" nm")
        self._wavelength_spin_box.setStatusTip("Wavelength (350-1100 nm)")
        self._wavelength_spin_box.editingFinished.connect(self.wavelength_editied)

        self._average_count_spin_box = QtWidgets.QSpinBox(self)
        self._average_count_spin_box.setRange(1, 1000)
        self._average_count_spin_box.setValue(100)
        self._average_count_spin_box.setStatusTip("Average Count (1-1000)")
        self._average_count_spin_box.editingFinished.connect(self.average_count_editied)

        layout = QtWidgets.QFormLayout(self)
        layout.addRow("Power", self._power_line_edit)
        layout.addRow("Wavelength", self._wavelength_spin_box)
        layout.addRow("Avg. Count", self._average_count_spin_box)

    def set_inputs_enabled(self, enabled: bool) -> None:
        self._wavelength_spin_box.setEnabled(enabled)
        self._average_count_spin_box.setEnabled(enabled)

    def set_power(self, power: float | None) -> None:
        if power is None:
            self._power_line_edit.setText("n/a")
        else:
            self._power_line_edit.setText(si_format(power, "W"))

    def wavelength(self) -> int:
        return self._wavelength_spin_box.value()

    def wavelength_editied(self) -> None:
        self.wavelength_changed.emit(self.wavelength())

    def set_wavelength(self, wavelength: int) -> None:
        self._wavelength_spin_box.setValue(wavelength)  # clamp

    def update_wavelength(self, wavelengt: int | None) -> None:
        if wavelengt is not None:
            update_spin_box(self._wavelength_spin_box, wavelengt)

    def average_count(self) -> int:
        return self._average_count_spin_box.value()

    def average_count_editied(self) -> None:
        self.average_count_changed.emit(self.average_count())

    def set_average_count(self, average_count: int) -> None:
        self._average_count_spin_box.setValue(average_count)  # clamp

    def update_average_count(self, average_count: int | None) -> None:
        if average_count is not None:
            update_spin_box(self._average_count_spin_box, average_count)
