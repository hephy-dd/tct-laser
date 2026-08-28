from enum import Enum, auto

import numpy as np
import pyqtgraph as pg
from numpy.typing import NDArray
from PySide6 import QtCore, QtWidgets

from ..core.rasterscan import (
    Profile,
    Raster,
    RasterType,
)

__all__ = ["RasterScanPlotWidget"]

RASTER_UPDATE_INTERVAL: float = 1.0


class PlotType(Enum):
    PEAK = auto()
    PEAK_XY = auto()
    AREA = auto()
    T_MAX = auto()


def get_levels_ignore_nan(data: NDArray) -> tuple[float, float]:
    """Return min and max of a given raster"""
    if data.size == 0:
        return (0, 1)
    if np.all(np.isnan(data)):
        return (0, 1)
    return float(np.nanmin(data)), float(np.nanmax(data))


class RasterPlotWidget(pg.GraphicsLayoutWidget):
    def __init__(
        self, raster_type: RasterType, parent: QtWidgets.QWidget | None = None
    ) -> None:
        super().__init__(parent)

        self.raster_type: RasterType = raster_type
        self.raster_version = 0

        self.plot = self.addPlot()  # type: ignore
        self.plot.setAspectLocked(True)
        self.img = pg.ImageItem()
        self.plot.addItem(self.img)

        self.plot.setLabel("left", "X [um]")
        self.plot.setLabel("bottom", "Y [um]")

        top_axis = self.plot.getAxis("top")
        top_axis.setStyle(showValues=True)
        top_axis.show()

        right_axis = self.plot.getAxis("right")
        right_axis.setStyle(showValues=True)
        right_axis.show()

        self.plot.showGrid(x=True, y=True, alpha=0.4)
        self.plot.invertY(False)

        self.cbar = pg.ColorBarItem(
            values=(0, 1),
            width=10,
            interactive=False,
        )
        self.cbar.setImageItem(self.img, insert_in=self.plot)

        self.addItem(self.plot)
        # self.addItem(self.cbar)


class XYProfilePlotWidget(pg.GraphicsLayoutWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.x_plot = self.addPlot(row=0, col=0)  # type: ignore
        self.x_plot.setTitle("XZ Profile")
        self.x_plot.setLabel("left", "Amplitude [V]")
        self.x_plot.setLabel("bottom", "X [um]")
        self.x_plot.showGrid(x=True, y=True, alpha=0.4)

        self.x_curve = self.x_plot.plot(pen="y")

        self.nextRow()  # type: ignore

        self.y_plot = self.addPlot(row=1, col=0)  # type: ignore
        self.y_plot.setTitle("YZ Profile")
        self.y_plot.setLabel("left", "Amplitude [V]")
        self.y_plot.setLabel("bottom", "Y [um]")
        self.y_plot.showGrid(x=True, y=True, alpha=0.4)

        self.y_curve = self.y_plot.plot(pen="c")

        # Link Y-axis scaling
        # self.y_plot.setYLink(self.x_plot)

    def set_x_profile(self, x_profile: Profile) -> None:
        self.x_curve.setData(x_profile.x, x_profile.y)

    def set_y_profile(self, y_profile: Profile) -> None:
        self.y_curve.setData(y_profile.x, y_profile.y)

    def clear(self) -> None:
        self.x_curve.clear()
        self.y_curve.clear()


class PlotStack(QtWidgets.QWidget):
    plot_changed = QtCore.Signal(object)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.raster_plot = RasterPlotWidget(RasterType.PEAK)

        self.xy_profile_plot = XYProfilePlotWidget(self)

        self.stack = QtWidgets.QStackedWidget(self)
        self.stack.addWidget(self.raster_plot)
        self.stack.addWidget(self.xy_profile_plot)

        self.plot_type_combo_box = QtWidgets.QComboBox(self)
        self.plot_type_combo_box.addItem("Peak", PlotType.PEAK)
        self.plot_type_combo_box.addItem("Peak Profiles", PlotType.PEAK_XY)
        self.plot_type_combo_box.addItem("Area", PlotType.AREA)
        self.plot_type_combo_box.addItem("t(max)", PlotType.T_MAX)
        self.plot_type_combo_box.currentIndexChanged.connect(self.on_plot_type_changed)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.plot_type_combo_box)
        layout.addWidget(self.stack)

        self.sync_plot_title()

    def set_color_map(self, color_map: str) -> None:
        cmap = pg.colormap.get(color_map)
        if cmap is not None:
            self.raster_plot.img.setColorMap(cmap)
            self.raster_plot.cbar.setColorMap(cmap)

    def sync_plot_title(self) -> None:
        text = self.plot_type_combo_box.currentText()
        self.raster_plot.plot.setTitle(text)

    @QtCore.Slot(int)
    def on_plot_type_changed(self, index: int) -> None:
        plot_type = self.plot_type_combo_box.itemData(index)
        match plot_type:
            case PlotType.PEAK:
                self.raster_plot.raster_type = RasterType.PEAK
                self.sync_plot_title()
                self.stack.setCurrentWidget(self.raster_plot)
                self.plot_changed.emit(plot_type)
            case PlotType.AREA:
                self.raster_plot.raster_type = RasterType.AREA
                self.sync_plot_title()
                self.stack.setCurrentWidget(self.raster_plot)
                self.plot_changed.emit(plot_type)
            case PlotType.T_MAX:
                self.raster_plot.raster_type = RasterType.T_MAX
                self.sync_plot_title()
                self.stack.setCurrentWidget(self.raster_plot)
                self.plot_changed.emit(plot_type)
            case PlotType.PEAK_XY:
                self.stack.setCurrentWidget(self.xy_profile_plot)
                self.plot_changed.emit(plot_type)


class RasterScanPlotWidget(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.raster_data: dict[RasterType, Raster] = {}
        self.x_profile = Profile.create_empty()
        self.y_profile = Profile.create_empty()

        self.plot_stack_1 = PlotStack(self)
        self.plot_stack_1.plot_changed.connect(self.on_update_plot_1)
        self.plot_stack_2 = PlotStack(self)
        self.plot_stack_2.plot_changed.connect(self.on_update_plot_2)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.plot_stack_1)
        layout.addWidget(self.plot_stack_2)
        layout.setStretch(0, 2)
        layout.setStretch(1, 2)

        self.plot_stack_1.plot_type_combo_box.setCurrentIndex(0)
        self.plot_stack_2.plot_type_combo_box.setCurrentIndex(1)

        self.raster_timer = QtCore.QTimer(self)
        self.raster_timer.timeout.connect(self.update_raster)
        self.raster_timer.start(int(RASTER_UPDATE_INTERVAL * 1000))

    def set_color_map(self, color_map: str) -> None:
        self.plot_stack_1.set_color_map(color_map)
        self.plot_stack_2.set_color_map(color_map)

    def set_raster(self, raster_type: RasterType, raster: Raster) -> None:
        self.raster_data[raster_type] = raster

    def set_x_profile(self, x_profile: Profile) -> None:
        self.x_profile = x_profile

    def set_y_profile(self, y_profile: Profile) -> None:
        self.y_profile = y_profile

    def clear(self) -> None:
        self.raster_data.clear()

    @QtCore.Slot()
    def update_raster(self) -> None:
        self._update_raster_1()
        self._update_raster_2()
        self._update_xy_profile_1()
        self._update_xy_profile_2()

    @QtCore.Slot(object)
    def on_update_plot_1(self, plot_type: PlotType) -> None:
        match plot_type:
            case PlotType.PEAK | PlotType.AREA | PlotType.T_MAX:
                self._update_raster_1()
            case PlotType.PEAK_XY:
                self._update_xy_profile_1()

    @QtCore.Slot(object)
    def on_update_plot_2(self, plot_type: PlotType) -> None:
        match plot_type:
            case PlotType.PEAK | PlotType.AREA | PlotType.T_MAX:
                self._update_raster_2()
            case PlotType.PEAK_XY:
                self._update_xy_profile_2()

    def _update_raster(self, raster_plot) -> None:
        raster = self.raster_data.get(raster_plot.raster_type)
        if raster is None:
            raster_plot.img.clear()
        else:
            data = raster.data
            levels = get_levels_ignore_nan(data)
            raster_plot.img.setImage(data, auto_levels=False, levels=levels)
            rect = raster.raster_extent
            raster_plot.img.setRect(
                QtCore.QRectF(rect.x, rect.y, rect.width, rect.height)
            )
            raster_plot.cbar.setLevels(levels)

    def _update_raster_1(self) -> None:
        self._update_raster(self.plot_stack_1.raster_plot)

    def _update_raster_2(self) -> None:
        self._update_raster(self.plot_stack_2.raster_plot)

    def _update_xy_profile_1(self) -> None:
        xy_profile_plot = self.plot_stack_1.xy_profile_plot
        xy_profile_plot.set_x_profile(self.x_profile)
        xy_profile_plot.set_y_profile(self.y_profile)

    def _update_xy_profile_2(self) -> None:
        xy_profile_plot = self.plot_stack_2.xy_profile_plot
        xy_profile_plot.set_x_profile(self.x_profile)
        xy_profile_plot.set_y_profile(self.y_profile)
