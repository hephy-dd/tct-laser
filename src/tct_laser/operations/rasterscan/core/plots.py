from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from numpy.typing import NDArray
from pathvalidate import sanitize_filename

__all__ = ["PlotWriter"]


@dataclass
class PlotWriter:
    raster_ampl: NDArray[np.floating]
    x_coords: NDArray[np.floating]
    y_coords: NDArray[np.floating]
    z_coords: NDArray[np.floating]
    sample_name: str
    timestamp: datetime
    output_path: str

    @property
    def fmt_timestamp(self) -> str:
        return self.timestamp.strftime("%Y%m%dT%H%M%S")

    def save_amplitude_map(self, z_index: int = 0) -> None:
        output_directory = Path(self.output_path)
        output_directory.mkdir(parents=True, exist_ok=True)

        fig, ax = plt.subplots()

        image = ax.imshow(
            1e3 * self.raster_ampl[:, :, z_index],
            extent=(
                self.y_coords[0],
                self.y_coords[-1],
                self.x_coords[0],
                self.x_coords[-1],
            ),
            origin="lower",
            cmap="viridis",
            interpolation="none",
            aspect="equal",
        )

        fig.colorbar(image, ax=ax, label="Amplitude [mV]")
        ax.set_xlabel("Y [mm]")
        ax.set_ylabel("X [mm]")

        filename = sanitize_filename(
            f"amplitude_map_{self.sample_name}_{self.fmt_timestamp}.png"
        )
        fig.savefig(
            output_directory / filename,
            dpi=1000,
            bbox_inches="tight",
        )

        plt.close(fig)

    def save_yz_profile(self) -> None:
        output_directory = Path(self.output_path)
        output_directory.mkdir(parents=True, exist_ok=True)

        fig, ax = plt.subplots()

        middle_x_index = len(self.x_coords) // 2
        number_of_z_points = len(self.z_coords)

        for z_index in range(number_of_z_points):
            ax.plot(
                self.y_coords,
                self.raster_ampl[middle_x_index, :, z_index],
                label=f"z = {self.z_coords[z_index]}",
                color=plt.cm.hsv(z_index / number_of_z_points),
            )

        ax.legend()
        ax.set_xlabel("Y [mm]")
        ax.set_ylabel("Amplitude [V]")
        ax.set_title("YZ scan")
        ax.grid()

        filename = sanitize_filename(
            f"YZ_profile_{self.sample_name}_{self.fmt_timestamp}.svg"
        )
        fig.savefig(
            output_directory / filename,
            bbox_inches="tight",
        )

        plt.close(fig)

    def save_xz_profile(self) -> None:
        output_directory = Path(self.output_path)
        output_directory.mkdir(parents=True, exist_ok=True)

        fig, ax = plt.subplots()

        middle_y_index = len(self.y_coords) // 2
        number_of_z_points = len(self.z_coords)

        for z_index in range(number_of_z_points):
            ax.plot(
                self.x_coords,
                self.raster_ampl[:, middle_y_index, z_index],
                label=f"z = {self.z_coords[z_index]}",
                color=plt.cm.hsv(z_index / number_of_z_points),
            )

        ax.legend()
        ax.set_xlabel("X [mm]")
        ax.set_ylabel("Amplitude [V]")
        ax.set_title("XZ scan")
        ax.grid()

        filename = sanitize_filename(
            f"XZ_profile_{self.sample_name}_{self.fmt_timestamp}.svg"
        )
        fig.savefig(
            output_directory / filename,
            bbox_inches="tight",
        )

        plt.close(fig)
