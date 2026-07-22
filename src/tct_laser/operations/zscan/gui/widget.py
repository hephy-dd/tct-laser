import math
from typing import Any, cast

import msgspec
from PySide6 import QtCore, QtGui, QtWidgets

from ..core.zscan import AutoFocusZ, ZScanOperation, ZScanSeries, ZScanXYSeries
from .plotwidgets import ZScanHPlotWidget, ZScanPlotWidget


class ZScanWidget(QtWidgets.QWidget):
    start_triggered = QtCore.Signal()
    abort_triggered = QtCore.Signal()

    def __init__(self, station, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Z Scan")

        self.run_action = QtGui.QAction("&Z Scan", self)
        self.start_triggered.connect(self.run_action.trigger)

        self.z_start_offset_spin_box = QtWidgets.QSpinBox(self)
        self.z_start_offset_spin_box.setRange(-10_000, 10_000)
        self.z_start_offset_spin_box.setValue(-100)
        self.z_start_offset_spin_box.setSuffix(" um")

        self.z_stop_offset_spin_box = QtWidgets.QSpinBox(self)
        self.z_stop_offset_spin_box.setRange(-10_000, 10_000)
        self.z_stop_offset_spin_box.setValue(+100)
        self.z_stop_offset_spin_box.setSuffix(" um")

        self.z_steps_spin_box = QtWidgets.QSpinBox(self)
        self.z_steps_spin_box.setRange(1, 1_000)
        self.z_steps_spin_box.setValue(10)

        self.start_x_offset_spin_box = QtWidgets.QSpinBox(self)
        self.start_x_offset_spin_box.setRange(-1_000, 1_000)
        self.start_x_offset_spin_box.setValue(-100)
        self.start_x_offset_spin_box.setSuffix(" um")

        self.start_y_offset_spin_box = QtWidgets.QSpinBox(self)
        self.start_y_offset_spin_box.setRange(-1_000, 1_000)
        self.start_y_offset_spin_box.setValue(-100)
        self.start_y_offset_spin_box.setSuffix(" um")

        self.stop_x_offset_spin_box = QtWidgets.QSpinBox(self)
        self.stop_x_offset_spin_box.setRange(-1_000, 1_000)
        self.stop_x_offset_spin_box.setValue(100)
        self.stop_x_offset_spin_box.setSuffix(" um")

        self.stop_y_offset_spin_box = QtWidgets.QSpinBox(self)
        self.stop_y_offset_spin_box.setRange(-1_000, 1_000)
        self.stop_y_offset_spin_box.setValue(100)
        self.stop_y_offset_spin_box.setSuffix(" um")

        self.xy_steps_spin_box = QtWidgets.QSpinBox(self)
        self.xy_steps_spin_box.setRange(1, 1_000_000)
        self.xy_steps_spin_box.setValue(100)

        self.average_count_spin_box = QtWidgets.QSpinBox(self)
        self.average_count_spin_box.setRange(1, 1_000)
        self.average_count_spin_box.setValue(1)

        self.autofocus_line_edit = QtWidgets.QLineEdit(self)
        self.autofocus_line_edit.setReadOnly(True)

        self.start_button = QtWidgets.QPushButton("Z Scan", self)
        self.start_button.clicked.connect(self.start_triggered)

        self.abort_button = QtWidgets.QPushButton("Abort", self)
        self.abort_button.clicked.connect(self.abort_triggered)

        self.z_scan_plot = ZScanPlotWidget(self)

        self.z_scan_h_plot = ZScanHPlotWidget(self)

        top_1_layout = QtWidgets.QFormLayout()
        top_1_layout.addRow("Z Start", self.z_start_offset_spin_box)
        top_1_layout.addRow("Z Stop", self.z_stop_offset_spin_box)
        top_1_layout.addRow("Z Steps", self.z_steps_spin_box)

        top_2_layout = QtWidgets.QFormLayout()
        top_2_layout.addRow("Start Offset X", self.start_x_offset_spin_box)
        top_2_layout.addRow("Start Offset Y", self.start_y_offset_spin_box)

        top_3_layout = QtWidgets.QFormLayout()
        top_3_layout.addRow("Stop Offset X", self.stop_x_offset_spin_box)
        top_3_layout.addRow("Stop Offset Y", self.stop_y_offset_spin_box)

        top_4_layout = QtWidgets.QFormLayout()
        top_4_layout.addRow("XY Steps", self.xy_steps_spin_box)
        top_4_layout.addRow("Avg. Count", self.average_count_spin_box)
        top_4_layout.addRow("Autofocus:", self.autofocus_line_edit)

        top_5_layout = QtWidgets.QFormLayout()
        top_5_layout.addWidget(self.start_button)
        top_5_layout.addWidget(self.abort_button)

        top_layout = QtWidgets.QHBoxLayout()
        top_layout.addLayout(top_1_layout)
        top_layout.addLayout(top_2_layout)
        top_layout.addLayout(top_3_layout)
        top_layout.addLayout(top_4_layout)
        top_layout.addLayout(top_5_layout)
        top_layout.setStretch(0, 2)
        top_layout.setStretch(1, 2)
        top_layout.setStretch(2, 2)
        top_layout.setStretch(3, 2)
        top_layout.setStretch(4, 2)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(top_layout)
        layout.addWidget(self.z_scan_plot)
        layout.addWidget(self.z_scan_h_plot)

    def set_inputs_enabled(self, enabled: bool) -> None:
        self.z_start_offset_spin_box.setEnabled(enabled)
        self.z_stop_offset_spin_box.setEnabled(enabled)
        self.z_steps_spin_box.setEnabled(enabled)
        self.start_x_offset_spin_box.setEnabled(enabled)
        self.start_y_offset_spin_box.setEnabled(enabled)
        self.stop_x_offset_spin_box.setEnabled(enabled)
        self.stop_y_offset_spin_box.setEnabled(enabled)
        self.xy_steps_spin_box.setEnabled(enabled)
        self.average_count_spin_box.setEnabled(enabled)
        self.start_button.setEnabled(enabled)

    def set_abort_enabled(self, enabled: bool) -> None:
        self.abort_button.setEnabled(enabled)

    def set_autofocus_z_um(self, autofocus: float) -> None:
        if math.isfinite(autofocus):
            self.autofocus_line_edit.setText(f"{autofocus:.4f} mm")
        else:
            self.autofocus_line_edit.setText(f"{autofocus}")

    def set_z_scan_xy_series(self, series: ZScanXYSeries) -> None:
        self.z_scan_plot.set_series(
            z_um=series.z_um,
            xy_um=series.xy_um,
            amplitude_v=series.amplitude_v,
        )

    def set_z_scan_series(self, series: ZScanSeries) -> None:
        self.z_scan_h_plot.set_series(
            z_um=series.z_um,
            slope_v_per_um=series.slope_v_per_um,
        )

    def set_parameter(self, parameter: Any) -> None:
        match parameter:
            case AutoFocusZ(autofocus):
                self.set_autofocus_z_um(autofocus)
            case ZScanXYSeries() as series:
                self.set_z_scan_xy_series(series)
            case ZScanSeries() as series:
                self.set_z_scan_series(series)

    def clear(self) -> None:
        self.z_scan_plot.clear()
        self.z_scan_h_plot.clear()

    def config(self) -> ZScanOperation:
        return ZScanOperation(
            z_start_offset_um=self.z_start_offset_spin_box.value(),
            z_stop_offset_um=self.z_stop_offset_spin_box.value(),
            z_steps=self.z_steps_spin_box.value(),
            start_x_offset_um=self.start_x_offset_spin_box.value(),
            start_y_offset_um=self.start_y_offset_spin_box.value(),
            stop_x_offset_um=self.stop_x_offset_spin_box.value(),
            stop_y_offset_um=self.stop_y_offset_spin_box.value(),
            xy_steps=self.xy_steps_spin_box.value(),
            average_count=self.average_count_spin_box.value(),
        )

    def setConfig(self, config: ZScanOperation) -> None:
        self.z_start_offset_spin_box.setValue(config.z_start_offset_um)
        self.z_stop_offset_spin_box.setValue(config.z_stop_offset_um)
        self.z_steps_spin_box.setValue(config.z_steps)
        self.start_x_offset_spin_box.setValue(config.start_x_offset_um)
        self.start_y_offset_spin_box.setValue(config.start_y_offset_um)
        self.stop_x_offset_spin_box.setValue(config.stop_x_offset_um)
        self.stop_y_offset_spin_box.setValue(config.stop_y_offset_um)
        self.xy_steps_spin_box.setValue(config.xy_steps)
        self.average_count_spin_box.setValue(config.average_count)

    def read_settings(self, settings: QtCore.QSettings) -> None:
        settings.beginGroup("ZScan")
        try:
            raw = cast(str, settings.value("config", "", type=str))
        finally:
            settings.endGroup()

        try:
            loaded = msgspec.json.decode(raw or "{}")
            base = msgspec.to_builtins(self.config())
            base.update(loaded)

            self.setConfig(msgspec.convert(base, type=ZScanOperation))
        except msgspec.DecodeError, msgspec.ValidationError, TypeError:
            # Ignore invalid or incompatible settings.
            pass

    def write_settings(self, settings: QtCore.QSettings) -> None:
        settings.beginGroup("ZScan")
        try:
            settings.setValue(
                "config",
                msgspec.json.encode(self.config()).decode("utf-8"),
            )
        finally:
            settings.endGroup()
