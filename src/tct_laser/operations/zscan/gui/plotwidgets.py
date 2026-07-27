from typing import Any

import numpy as np
import pyqtgraph as pg
from numpy.typing import ArrayLike
from PySide6 import QtGui, QtWidgets

__all__ = [
    "ZScanHPlotWidget",
    "ZScanPlotWidget",
]


class ZScanPlotWidget(QtWidgets.QWidget):
    """Accumulated XY amplitude scans, indexed by Z position in µm."""

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.plot = pg.PlotWidget(title="Z Scan")
        self.plot.setLabel("bottom", "XY distance", units="µm")
        self.plot.setLabel("left", "Amplitude", units="V")
        self.plot.showGrid(x=True, y=True, alpha=0.2)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.plot)

        # Use float keys so distinct Z values are not accidentally merged.
        self._curves: dict[float, pg.PlotDataItem] = {}

        self._z_range_um = (0.0, 1.0)
        self._color_map: Any = pg.colormap.get("viridis")

        # ColorBarItem controls ImageItems, so use a hidden ImageItem as its
        # level/colormap target. Curve colors are updated separately.
        self._color_image = pg.ImageItem(np.array([[0.0, 1.0]], dtype=np.float64))
        self._color_image.setColorMap(self._color_map)
        self._color_image.setLevels(self._z_range_um)
        self._color_image.setVisible(False)

        self._color_bar = pg.ColorBarItem(
            values=self._z_range_um,
            colorMap=self._color_map,
            width=10,
            label="Z [µm]",
            interactive=False,
        )
        self._color_bar.setImageItem(
            self._color_image,
            insert_in=self.plot.getPlotItem(),
        )

    def set_series(
        self,
        z_um: float,
        xy_um: ArrayLike,
        amplitude_v: ArrayLike,
    ) -> None:
        """Create or update the XY series for one Z position."""

        z_key = float(z_um)

        if not np.isfinite(z_key):
            raise ValueError("Z must be finite.")

        x = np.asarray(xy_um, dtype=np.float64)
        y = np.asarray(amplitude_v, dtype=np.float64)

        if x.size != y.size:
            raise ValueError("XY and amplitude arrays must have equal length.")

        valid = np.isfinite(x) & np.isfinite(y)

        curve = self._curves.get(z_key)

        if curve is None:
            # Add the curve before recalculating the Z range, because the
            # inserted Z values determine the color-bar limits.
            curve = self.plot.plot()
            self._curves[z_key] = curve

            self._update_z_range()

        curve.setData(
            x=x[valid],
            y=y[valid],
        )

    def remove_series(self, z_um: float) -> None:
        """Remove one Z series and rescale the remaining colors."""

        z_key = float(z_um)
        curve = self._curves.pop(z_key, None)

        if curve is None:
            return

        self.plot.removeItem(curve)
        self._update_z_range()

    def clear(self) -> None:
        """Remove all series and reset the color bar."""

        for curve in self._curves.values():
            self.plot.removeItem(curve)

        self._curves.clear()
        self._set_z_range(0.0, 1.0)

    def _update_z_range(self) -> None:
        """Scale the color bar to the Z values currently in the plot."""

        if not self._curves:
            self._set_z_range(0.0, 1.0)
            return

        z_values = np.asarray(
            list(self._curves.keys()),
            dtype=np.float64,
        )

        z_min = float(np.min(z_values))
        z_max = float(np.max(z_values))

        self._set_z_range(z_min, z_max)

    def _set_z_range(
        self,
        z_min_um: float,
        z_max_um: float,
    ) -> None:
        """Apply a Z range to both the color bar and line colors."""

        if z_min_um > z_max_um:
            z_min_um, z_max_um = z_max_um, z_min_um

        self._z_range_um = (z_min_um, z_max_um)

        # ColorBarItem.setLevels() updates the numerical scale represented by
        # its gradient and applies those levels to its target ImageItem.
        if np.isclose(z_min_um, z_max_um):
            # A color bar cannot have a zero-width range. Display a small
            # symmetric range around the only Z value.
            padding = max(abs(z_min_um) * 0.01, 0.5)
            display_range = (
                z_min_um - padding,
                z_max_um + padding,
            )
        else:
            display_range = self._z_range_um

        self._color_image.setImage(
            np.asarray([display_range], dtype=np.float64),
            autoLevels=False,
        )
        self._color_image.setLevels(display_range)
        self._color_bar.setLevels(display_range)

        # A changed range changes the normalized position of every series.
        for z_um, curve in self._curves.items():
            curve.setPen(self._pen(z_um))

    def _pen(self, z_um: float) -> QtGui.QPen:
        """Return the colormap pen corresponding to a Z value."""

        z_min, z_max = self._z_range_um

        if np.isclose(z_min, z_max):
            # Put a single series in the middle of the colormap.
            position = 0.5
        else:
            position = (z_um - z_min) / (z_max - z_min)
            position = float(np.clip(position, 0.0, 1.0))

        color = self._color_map[position]

        return pg.mkPen(
            color=color,
            width=1.0,
        )


class ZScanHPlotWidget(QtWidgets.QWidget):
    """Displays the accumulated autofocus slope at each Z height."""

    def __init__(
        self,
        station,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.plot = pg.PlotWidget(title="Z Scan Focus")
        self.plot.setLabel("bottom", "Z", units="µm")
        self.plot.setLabel("left", "Slope", units="V/µm")
        self.plot.addLegend()

        self._curve = self.plot.plot(
            [],
            [],
            name="Slope",
            pen=pg.mkPen(width=1),
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.plot)

    def set_series(
        self,
        z_um: ArrayLike,
        slope_v_per_um: ArrayLike,
    ) -> None:
        z = np.asarray(z_um, dtype=np.float64)
        slope = np.asarray(slope_v_per_um, dtype=np.float64)

        if z.ndim != 1 or slope.ndim != 1:
            raise ValueError("Z scan slope data must be one-dimensional.")

        if z.size != slope.size:
            raise ValueError("Z and slope arrays must have the same length.")

        valid = np.isfinite(z) & np.isfinite(slope)

        self._curve.setData(
            x=z[valid],
            y=slope[valid],
        )

    def clear(self) -> None:
        self._curve.setData([], [])
