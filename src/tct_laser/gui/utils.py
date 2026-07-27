from importlib import resources

from PySide6 import QtCore, QtGui, QtWidgets

__all__ = [
    "load_icon",
    "load_text",
    "update_check_box",
    "update_double_spin_box",
    "update_spin_box",
]


def load_icon(filename: str) -> QtGui.QIcon:
    data = resources.read_binary("tct_laser.assets.icons", filename)
    pixmap = QtGui.QPixmap()
    pixmap.loadFromData(data)

    icon = QtGui.QIcon(pixmap)
    return icon


def load_text(filename: str) -> str:
    return (
        resources.files("tct_laser.assets")
        .joinpath(filename)
        .read_text(encoding="utf-8")
    )


def update_check_box(check_box: QtWidgets.QCheckBox, value: bool) -> None:
    if value == check_box.isChecked():
        return
    with QtCore.QSignalBlocker(check_box):
        check_box.setChecked(value)


def update_spin_box(spin_box: QtWidgets.QSpinBox, value: int) -> None:
    if value == spin_box.value():
        return
    if spin_box.hasFocus():
        return
    with QtCore.QSignalBlocker(spin_box):
        spin_box.setValue(value)


def update_double_spin_box(
    double_spin_box: QtWidgets.QDoubleSpinBox, value: float
) -> None:
    if value == double_spin_box.value():
        return
    if double_spin_box.hasFocus():
        return
    with QtCore.QSignalBlocker(double_spin_box):
        double_spin_box.setValue(value)
