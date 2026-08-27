import msgspec
from PySide6 import QtCore, QtWidgets

from tct_laser.core.geometry import Vector3

__all__ = ["StageGroupBox"]


class StageGroupBox(QtWidgets.QGroupBox):
    move_relative_triggered = QtCore.Signal(object)
    move_absolute_triggered = QtCore.Signal(object)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.setTitle("Stage")

        self._control_widget = ControlWidget(self)
        self._control_widget.move_relative_triggered.connect(
            self.move_relative_triggered
        )
        self._control_widget.move_absolute_triggered.connect(
            self.move_absolute_triggered
        )

        self._positions_widget = PositionsWidget(self)
        self._positions_widget.move_absolute_triggered.connect(
            self.move_absolute_triggered
        )

        self._tab_widget = QtWidgets.QTabWidget(self)
        self._tab_widget.addTab(self._control_widget, "Control")
        self._tab_widget.addTab(self._positions_widget, "Positions")

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self._tab_widget)

    def set_position(self, position: Vector3) -> None:
        self._control_widget.set_position(position)
        self._positions_widget.set_current_position(position)

    def clear_position(self) -> None:
        self._control_widget.clear_position()

    def set_inputs_enabled(self, enabled: bool) -> None:
        self._control_widget.set_inputs_enabled(enabled)
        self._positions_widget.set_inputs_enabled(enabled)

    def positions(self) -> list[Position]:
        return self._positions_widget.positions()

    def clear_positions(self) -> None:
        self._positions_widget.clear_positions()

    def append_position(self, position: Position) -> None:
        self._positions_widget.append_position(position)


class ControlWidget(QtWidgets.QWidget):
    move_relative_triggered = QtCore.Signal(object)
    move_absolute_triggered = QtCore.Signal(object)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._prec = 4
        self._unit = "mm"

        self._position_label = QtWidgets.QLabel("Pos", self)
        self._position_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self._step_label = QtWidgets.QLabel("Step", self)
        self._step_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self._x_label = QtWidgets.QLabel("X", self)
        self._y_label = QtWidgets.QLabel("Y", self)
        self._z_label = QtWidgets.QLabel("Z", self)

        self._x_pos_line_edit = self._create_position_line_edit()
        self._y_pos_line_edit = self._create_position_line_edit()
        self._z_pos_line_edit = self._create_position_line_edit()

        self._x_step_spin_box = self._create_step_spin_box(0.1)
        self._y_step_spin_box = self._create_step_spin_box(0.1)
        self._z_step_spin_box = self._create_step_spin_box(0.1)

        self._x_sub_button = QtWidgets.QPushButton("-", self)
        self._x_sub_button.setMaximumWidth(32)
        self._x_sub_button.clicked.connect(
            lambda: self.move_relative_triggered.emit(
                Vector3(-abs(self._x_step_spin_box.value()), 0, 0)
            )
        )

        self._x_add_button = QtWidgets.QPushButton("+", self)
        self._x_add_button.setMaximumWidth(32)
        self._x_add_button.clicked.connect(
            lambda: self.move_relative_triggered.emit(
                Vector3(+abs(self._x_step_spin_box.value()), 0, 0)
            )
        )

        self._y_sub_button = QtWidgets.QPushButton("-", self)
        self._y_sub_button.setMaximumWidth(32)
        self._y_sub_button.clicked.connect(
            lambda: self.move_relative_triggered.emit(
                Vector3(0, -abs(self._y_step_spin_box.value()), 0)
            )
        )

        self._y_add_button = QtWidgets.QPushButton("+", self)
        self._y_add_button.setMaximumWidth(32)
        self._y_add_button.clicked.connect(
            lambda: self.move_relative_triggered.emit(
                Vector3(0, +abs(self._y_step_spin_box.value()), 0)
            )
        )

        self._z_sub_button = QtWidgets.QPushButton("-", self)
        self._z_sub_button.setMaximumWidth(32)
        self._z_sub_button.clicked.connect(
            lambda: self.move_relative_triggered.emit(
                Vector3(0, 0, -abs(self._z_step_spin_box.value()))
            )
        )

        self._z_add_button = QtWidgets.QPushButton("+", self)
        self._z_add_button.setMaximumWidth(32)
        self._z_add_button.clicked.connect(
            lambda: self.move_relative_triggered.emit(
                Vector3(0, 0, +abs(self._z_step_spin_box.value()))
            )
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

    def _create_position_line_edit(self) -> QtWidgets.QLineEdit:
        line_edit = QtWidgets.QLineEdit(self)
        line_edit.setReadOnly(True)
        line_edit.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        return line_edit

    def _create_step_spin_box(self, value: float) -> QtWidgets.QDoubleSpinBox:
        spin_box = QtWidgets.QDoubleSpinBox(self)
        spin_box.setDecimals(self._prec)
        spin_box.setRange(0, 1000)
        spin_box.setValue(value)
        spin_box.setSuffix(f" {self._unit}")
        return spin_box

    def set_position(self, position: Vector3) -> None:
        self._x_pos_line_edit.setText(f"{position.x:.{self._prec}f} {self._unit}")
        self._y_pos_line_edit.setText(f"{position.y:.{self._prec}f} {self._unit}")
        self._z_pos_line_edit.setText(f"{position.z:.{self._prec}f} {self._unit}")

    def clear_position(self) -> None:
        self._x_pos_line_edit.setText("loading...")
        self._y_pos_line_edit.setText("loading...")
        self._z_pos_line_edit.setText("loading...")

    def set_inputs_enabled(self, enabled: bool) -> None:
        for widget in (
            self._x_sub_button,
            self._x_add_button,
            self._y_sub_button,
            self._y_add_button,
            self._z_sub_button,
            self._z_add_button,
            self._x_step_spin_box,
            self._y_step_spin_box,
            self._z_step_spin_box,
        ):
            widget.setEnabled(enabled)


class Position(msgspec.Struct):
    name: str
    x: float
    y: float
    z: float
    comment: str = ""


class PositionsWidget(QtWidgets.QWidget):
    move_absolute_triggered = QtCore.Signal(object)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._current_position = Vector3(0, 0, 0)

        self._positions_tree_widget = QtWidgets.QTreeWidget(self)
        self._positions_tree_widget.setHeaderLabels(["Name", "X", "Y", "Z", "Comment"])
        self._positions_tree_widget.setRootIsDecorated(False)
        self._positions_tree_widget.setAlternatingRowColors(True)
        self._positions_tree_widget.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        self._positions_tree_widget.itemDoubleClicked.connect(
            lambda _item, _column: self.on_move_to()
        )
        self._positions_tree_widget.itemSelectionChanged.connect(
            self._update_action_states
        )

        self._add_button = QtWidgets.QPushButton("&Add...", self)
        self._edit_button = QtWidgets.QPushButton("&Edit...", self)
        self._remove_button = QtWidgets.QPushButton("&Remove", self)
        self._up_button = QtWidgets.QPushButton("&Up", self)
        self._down_button = QtWidgets.QPushButton("&Down", self)
        self._move_button = QtWidgets.QPushButton("&Move", self)
        self._move_button.setStatusTip("Move to selected position")

        self._add_button.clicked.connect(self.on_add_position)
        self._edit_button.clicked.connect(self.on_edit_position)
        self._remove_button.clicked.connect(self.on_remove_position)
        self._up_button.clicked.connect(self.on_move_up)
        self._down_button.clicked.connect(self.on_move_down)
        self._move_button.clicked.connect(self.on_move_to)

        layout = QtWidgets.QGridLayout(self)
        layout.addWidget(self._positions_tree_widget, 0, 0, 8, 1)
        layout.addWidget(self._add_button, 0, 1)
        layout.addWidget(self._edit_button, 1, 1)
        layout.addWidget(self._remove_button, 2, 1)
        layout.addWidget(self._up_button, 4, 1)
        layout.addWidget(self._down_button, 5, 1)
        layout.addWidget(self._move_button, 7, 1)
        layout.setColumnStretch(0, 1)

        self._inputs_enabled = True
        self._update_action_states()

    def set_inputs_enabled(self, enabled: bool) -> None:
        self._inputs_enabled = enabled
        self._positions_tree_widget.setEnabled(enabled)
        self._add_button.setEnabled(enabled)
        self._update_action_states()

    def set_current_position(self, position: Vector3) -> None:
        self._current_position = position.copy()

    def current_position_item(self) -> QtWidgets.QTreeWidgetItem | None:
        return self._positions_tree_widget.currentItem()

    @QtCore.Slot()
    def on_add_position(self) -> None:
        pos = self._current_position
        dialog = PositionDialog(self)
        dialog.setWindowTitle("Add Position")
        dialog.set_position(Position("Unnamed", pos.x, pos.y, pos.z, ""))
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.append_position(dialog.position())

    @QtCore.Slot()
    def on_edit_position(self) -> None:
        item = self.current_position_item()
        if item is None:
            return

        dialog = PositionDialog(self)
        dialog.setWindowTitle("Edit Position")
        dialog.set_position(self._position_from_item(item))
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._update_position_item(item, dialog.position())

    @QtCore.Slot()
    def on_remove_position(self) -> None:
        item = self.current_position_item()
        if item is None:
            return

        index = self._positions_tree_widget.indexOfTopLevelItem(item)
        self._positions_tree_widget.takeTopLevelItem(index)
        self._select_index(
            min(index, self._positions_tree_widget.topLevelItemCount() - 1)
        )
        self._update_action_states()

    @QtCore.Slot()
    def on_move_up(self) -> None:
        item = self.current_position_item()
        if item is None:
            return

        index = self._positions_tree_widget.indexOfTopLevelItem(item)
        if index <= 0:
            return

        item = self._positions_tree_widget.takeTopLevelItem(index)
        if item is not None:
            self._positions_tree_widget.insertTopLevelItem(index - 1, item)
            self._positions_tree_widget.setCurrentItem(item)
        self._update_action_states()

    @QtCore.Slot()
    def on_move_down(self) -> None:
        item = self.current_position_item()
        if item is None:
            return

        index = self._positions_tree_widget.indexOfTopLevelItem(item)
        if index < 0 or index >= self._positions_tree_widget.topLevelItemCount() - 1:
            return

        item = self._positions_tree_widget.takeTopLevelItem(index)
        if item is not None:
            self._positions_tree_widget.insertTopLevelItem(index + 1, item)
            self._positions_tree_widget.setCurrentItem(item)
        self._update_action_states()

    @QtCore.Slot()
    def on_move_to(self) -> None:
        item = self.current_position_item()
        if item is None:
            return

        position = self._position_from_item(item)
        self.move_absolute_triggered.emit(Vector3(position.x, position.y, position.z))

    def positions(self) -> list[Position]:
        positions = []
        for index in range(self._positions_tree_widget.topLevelItemCount()):
            item = self._positions_tree_widget.topLevelItem(index)
            if item is not None:
                positions.append(self._position_from_item(item))
        return positions

    def clear_positions(self) -> None:
        self._positions_tree_widget.clear()
        self._update_action_states()

    def append_position(self, position: Position) -> None:
        item = QtWidgets.QTreeWidgetItem()
        self._update_position_item(item, position)
        self._positions_tree_widget.addTopLevelItem(item)
        self._positions_tree_widget.setCurrentItem(item)
        self._positions_tree_widget.resizeColumnToContents(0)
        self._update_action_states()

    def _update_position_item(
        self, item: QtWidgets.QTreeWidgetItem, position: Position
    ) -> None:
        item.setText(0, position.name)
        item.setText(1, f"{position.x:.4f}")
        item.setText(2, f"{position.y:.4f}")
        item.setText(3, f"{position.z:.4f}")
        item.setText(4, position.comment)
        item.setData(0, 0x2000, position)

        for column in (1, 2, 3):
            item.setTextAlignment(column, QtCore.Qt.AlignmentFlag.AlignRight)

    def _position_from_item(self, item: QtWidgets.QTreeWidgetItem) -> Position:
        stored = item.data(0, 0x2000)
        if isinstance(stored, Position):
            return stored

        return Position(
            name=item.text(0),
            x=float(item.text(1)),
            y=float(item.text(2)),
            z=float(item.text(3)),
            comment=item.text(4),
        )

    def _select_index(self, index: int) -> None:
        if index >= 0:
            item = self._positions_tree_widget.topLevelItem(index)
            if item is not None:
                self._positions_tree_widget.setCurrentItem(item)

    @QtCore.Slot()
    def _update_action_states(self) -> None:
        item = self.current_position_item()
        has_selection = self._inputs_enabled and item is not None
        index = (
            self._positions_tree_widget.indexOfTopLevelItem(item)
            if item is not None
            else -1
        )
        count = self._positions_tree_widget.topLevelItemCount()

        self._edit_button.setEnabled(has_selection)
        self._remove_button.setEnabled(has_selection)
        self._move_button.setEnabled(has_selection)
        self._up_button.setEnabled(has_selection and index > 0)
        self._down_button.setEnabled(has_selection and 0 <= index < count - 1)


class PositionDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._prec = 4
        self._unit = "mm"

        self.setWindowTitle("Position")
        self.setModal(True)

        self._name_line_edit = QtWidgets.QLineEdit(self)
        self._name_line_edit.setClearButtonEnabled(True)

        self._pos_x_spin_box = self._create_position_spin_box()
        self._pos_y_spin_box = self._create_position_spin_box()
        self._pos_z_spin_box = self._create_position_spin_box()

        self._comment_line_edit = QtWidgets.QLineEdit(self)
        self._comment_line_edit.setClearButtonEnabled(True)

        self._button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self._button_box.accepted.connect(self.accept)
        self._button_box.rejected.connect(self.reject)

        ok_button = self._button_box.button(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
        )
        ok_button.setEnabled(False)
        self._name_line_edit.textChanged.connect(
            lambda text: ok_button.setEnabled(bool(text.strip()))
        )

        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow("&Name", self._name_line_edit)
        form_layout.addRow("&X", self._pos_x_spin_box)
        form_layout.addRow("&Y", self._pos_y_spin_box)
        form_layout.addRow("&Z", self._pos_z_spin_box)
        form_layout.addRow("&Comment", self._comment_line_edit)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addWidget(self._button_box)

        self._name_line_edit.setFocus()

    def _create_position_spin_box(self) -> QtWidgets.QDoubleSpinBox:
        spin_box = QtWidgets.QDoubleSpinBox(self)
        spin_box.setRange(-1000, 1000)
        spin_box.setDecimals(self._prec)
        spin_box.setSuffix(f" {self._unit}")
        return spin_box

    def position(self) -> Position:
        return Position(
            name=self._name_line_edit.text().strip(),
            x=self._pos_x_spin_box.value(),
            y=self._pos_y_spin_box.value(),
            z=self._pos_z_spin_box.value(),
            comment=self._comment_line_edit.text().strip(),
        )

    def set_position(self, position: Position) -> None:
        self._name_line_edit.setText(position.name)
        self._pos_x_spin_box.setValue(position.x)
        self._pos_y_spin_box.setValue(position.y)
        self._pos_z_spin_box.setValue(position.z)
        self._comment_line_edit.setText(position.comment)
