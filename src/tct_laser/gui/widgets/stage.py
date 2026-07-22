from PySide6 import QtCore, QtWidgets

__all__ = ["StageGroupBox"]


class StageGroupBox(QtWidgets.QGroupBox):
    move_relative = QtCore.Signal(float, float, float)
    move_absolute = QtCore.Signal(float, float, float)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTitle("Stage")

        self._prec: int = 4
        self._unit: str = "mm"

        self._position_label = QtWidgets.QLabel("Pos", self)
        self._position_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self._step_label = QtWidgets.QLabel("Step", self)
        self._step_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self._x_label = QtWidgets.QLabel("X", self)

        self._y_label = QtWidgets.QLabel("Y", self)

        self._z_label = QtWidgets.QLabel("Z", self)

        self._x_pos_line_edit = QtWidgets.QLineEdit(self)
        self._x_pos_line_edit.setReadOnly(True)
        self._x_pos_line_edit.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)

        self._y_pos_line_edit = QtWidgets.QLineEdit(self)
        self._y_pos_line_edit.setReadOnly(True)
        self._y_pos_line_edit.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)

        self._z_pos_line_edit = QtWidgets.QLineEdit(self)
        self._z_pos_line_edit.setReadOnly(True)
        self._z_pos_line_edit.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)

        self._x_step_spin_box = QtWidgets.QDoubleSpinBox(self)
        self._x_step_spin_box.setDecimals(self._prec)
        self._x_step_spin_box.setRange(0, 1000)
        self._x_step_spin_box.setValue(1.0)
        self._x_step_spin_box.setSuffix(f" {self._unit}")

        self._y_step_spin_box = QtWidgets.QDoubleSpinBox(self)
        self._y_step_spin_box.setDecimals(self._prec)
        self._y_step_spin_box.setRange(0, 1000)
        self._y_step_spin_box.setValue(1.0)
        self._y_step_spin_box.setSuffix(f" {self._unit}")

        self._z_step_spin_box = QtWidgets.QDoubleSpinBox(self)
        self._z_step_spin_box.setDecimals(self._prec)
        self._z_step_spin_box.setRange(0, 1000)
        self._z_step_spin_box.setValue(0.1)
        self._z_step_spin_box.setSuffix(f" {self._unit}")

        self._x_sub_button = QtWidgets.QPushButton("-", self)
        self._x_sub_button.clicked.connect(
            lambda: self.move_relative.emit(-abs(self._x_step_spin_box.value()), 0, 0)
        )

        self._x_add_button = QtWidgets.QPushButton("+", self)
        self._x_add_button.clicked.connect(
            lambda: self.move_relative.emit(+abs(self._x_step_spin_box.value()), 0, 0)
        )

        self._y_sub_button = QtWidgets.QPushButton("-", self)
        self._y_sub_button.clicked.connect(
            lambda: self.move_relative.emit(0, -abs(self._y_step_spin_box.value()), 0)
        )

        self._y_add_button = QtWidgets.QPushButton("+", self)
        self._y_add_button.clicked.connect(
            lambda: self.move_relative.emit(0, +abs(self._y_step_spin_box.value()), 0)
        )

        self._z_sub_button = QtWidgets.QPushButton("-", self)
        self._z_sub_button.clicked.connect(
            lambda: self.move_relative.emit(0, 0, -abs(self._z_step_spin_box.value()))
        )

        self._z_add_button = QtWidgets.QPushButton("+", self)
        self._z_add_button.clicked.connect(
            lambda: self.move_relative.emit(0, 0, +abs(self._z_step_spin_box.value()))
        )

        layout = QtWidgets.QGridLayout(self)
        layout.addWidget(self._position_label, 0, 1)
        layout.addWidget(self._step_label, 0, 3)

        layout.addWidget(self._x_label, 1, 0)
        layout.addWidget(self._y_label, 2, 0)
        layout.addWidget(self._z_label, 3, 0)

        layout.addWidget(self._x_pos_line_edit, 1, 1)
        layout.addWidget(self._y_pos_line_edit, 2, 1)
        layout.addWidget(self._z_pos_line_edit, 3, 1)

        layout.addWidget(self._x_sub_button, 1, 2)
        layout.addWidget(self._y_sub_button, 2, 2)
        layout.addWidget(self._z_sub_button, 3, 2)

        layout.addWidget(self._x_step_spin_box, 1, 3)
        layout.addWidget(self._y_step_spin_box, 2, 3)
        layout.addWidget(self._z_step_spin_box, 3, 3)

        layout.addWidget(self._x_add_button, 1, 4)
        layout.addWidget(self._y_add_button, 2, 4)
        layout.addWidget(self._z_add_button, 3, 4)

        layout.setRowStretch(4, 1)
        layout.setColumnStretch(5, 1)

    def set_position(self, x: float, y: float, z: float) -> None:
        self._x_pos_line_edit.setText(f"{x:.{self._prec}f} {self._unit}")
        self._y_pos_line_edit.setText(f"{y:.{self._prec}f} {self._unit}")
        self._z_pos_line_edit.setText(f"{z:.{self._prec}f} {self._unit}")

    def clear_position(self) -> None:
        self._x_pos_line_edit.setText("loading...")
        self._y_pos_line_edit.setText("loading...")
        self._z_pos_line_edit.setText("loading...")

    def set_inputs_enabled(self, enabled: bool) -> None:
        self._x_sub_button.setEnabled(enabled)
        self._x_add_button.setEnabled(enabled)
        self._y_sub_button.setEnabled(enabled)
        self._y_add_button.setEnabled(enabled)
        self._z_sub_button.setEnabled(enabled)
        self._z_add_button.setEnabled(enabled)
