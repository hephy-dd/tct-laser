import logging

import matplotlib
from PySide6 import QtWidgets

from .. import __version__
from ..core.context import ContextState
from ..core.station import Station
from .mainwindow import MainWindow
from .utils import load_icon

__all__ = ["main"]

# Set before importing pyplot.
matplotlib.use("Agg")


def main():
    logging.basicConfig(level=logging.INFO)

    app = QtWidgets.QApplication([])
    app.setApplicationName("tct-laser")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("MBI")
    app.setOrganizationDomain("mbi.oeaw.ac.at")
    app.setApplicationDisplayName(f"TCT-Laser {__version__}")
    app.setWindowIcon(load_icon("tct-laser.svg"))

    station = Station()
    state = ContextState(station)

    window = MainWindow(state)
    window.show()

    app.exec()
