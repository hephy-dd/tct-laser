from PySide6 import QtWidgets

__all__ = ["ErrorLabel"]


class ErrorLabel(QtWidgets.QLabel):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            "QLabel{color: white; background-color: rgb(200,0,0); padding: 8px;}"
        )

        self.close_button = QtWidgets.QPushButton("x", self)
        self.close_button.setFixedSize(20, 20)
        self.close_button.clicked.connect(self.hide)
        self.close_button.clicked.connect(self.clear)

    def show_exception(self, exc: Exception) -> None:
        self.setText(f"ERROR: {exc}")
        self.show()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Position button on the right inside label
        self.close_button.move(self.width() - 24, (self.height() - 20) // 2)
