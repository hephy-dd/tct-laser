from PySide6 import QtCore, QtWidgets

__all__ = ["GeneralGroupBox"]


class GeneralGroupBox(QtWidgets.QGroupBox):
    sample_name_changed = QtCore.Signal(str)
    output_path_changed = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.setTitle("General")

        self._sample_name_line_edit = QtWidgets.QLineEdit(self)
        self._sample_name_line_edit.setToolTip("Name of current sample")
        self._sample_name_line_edit.textChanged.connect(self.sample_name_changed.emit)

        self._output_path_line_edit = QtWidgets.QLineEdit(self)
        self._output_path_line_edit.setStatusTip("Base output path")
        self._output_path_line_edit.textChanged.connect(self.output_path_changed.emit)

        self._output_path_button = QtWidgets.QToolButton(self)
        self._output_path_button.setText("...")
        self._output_path_button.setStatusTip("Select an output path")
        self._output_path_button.clicked.connect(self.on_select_output_path)

        layout = QtWidgets.QGridLayout(self)
        layout.addWidget(QtWidgets.QLabel("Sample Name"), 0, 0)
        layout.addWidget(self._sample_name_line_edit, 0, 1, 1, 2)
        layout.addWidget(QtWidgets.QLabel("Output Path"), 1, 0)
        layout.addWidget(self._output_path_line_edit, 1, 1)
        layout.addWidget(self._output_path_button, 1, 2)

    def set_inputs_enabled(self, enabled: bool) -> None:
        self._sample_name_line_edit.setEnabled(enabled)
        self._output_path_line_edit.setEnabled(enabled)
        self._output_path_button.setEnabled(enabled)

    def sample_name(self) -> str:
        return self._sample_name_line_edit.text()

    def set_sample_name(self, sample_name: str) -> None:
        self._sample_name_line_edit.setText(sample_name)

    def output_path(self) -> str:
        return self._output_path_line_edit.text()

    def set_output_path(self, output_path: str) -> None:
        self._output_path_line_edit.setText(output_path)

    @QtCore.Slot()
    def on_select_output_path(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            self.output_path(),
            QtWidgets.QFileDialog.Option.ShowDirsOnly
            | QtWidgets.QFileDialog.Option.DontResolveSymlinks,
        )
        if path:
            self.set_output_path(path)
