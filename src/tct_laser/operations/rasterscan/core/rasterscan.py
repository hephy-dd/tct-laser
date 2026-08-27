import logging
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Self

import msgspec
import numpy as np
from comet.estimate import Estimate
from numpy.typing import NDArray

from tct_laser.core.algorithms import xy_range
from tct_laser.core.context import WorkerContext as Context
from tct_laser.core.geometry import Vector3
from tct_laser.core.session import Session
from tct_laser.core.utils import pulse_area_window

from .plots import PlotWriter
from .writer import RasterScanFileWriter

__all__ = [
    "RasterScanOperationConfig",
    "RasterScanOperationRunner",
]

logger = logging.getLogger(__name__)


class RasterType(Enum):
    PEAK = auto()
    AREA = auto()
    T_MAX = auto()


class Profile(msgspec.Struct, frozen=True):
    x: NDArray
    y: NDArray

    @classmethod
    def create_empty(cls) -> Self:
        return cls(x=np.zeros((0, 0)), y=np.zeros((0, 0)))

    @classmethod
    def create(cls, x: NDArray, y: NDArray) -> Self:
        return cls(x=x, y=y)

    def copy(self) -> Self:
        return type(self)(x=self.x.copy(), y=self.y.copy())


class RasterScanOperationConfig(msgspec.Struct, frozen=True):
    offset_left: int
    offset_right: int
    offset_top: int
    offset_bottom: int
    n_points_x: int
    n_points_y: int
    mode: str
    write_plots: bool
    write_csv: bool

    source_channel: str
    average_count: int


class RasterScanOperationRunner(msgspec.Struct, frozen=True):
    config: RasterScanOperationConfig

    def __call__(self, context: Context) -> None:
        run_initialize(context, self.config)
        run_raster_scan(context, self.config)


class CreateRaster(msgspec.Struct, frozen=True):
    raster_type: RasterType
    width: int
    height: int


class UpdateRasterValue(msgspec.Struct, frozen=True):
    raster_type: RasterType
    x: int
    y: int
    value: float


class UpdateXProfile(msgspec.Struct, frozen=True):
    x_profile: Profile


class UpdateYProfile(msgspec.Struct, frozen=True):
    y_profile: Profile


def create_raster(width: int, height: int) -> NDArray:
    return np.full((width, height), np.nan, dtype=np.float64)


def set_raster_value(raster: NDArray, x: int, y: int, value: float) -> None:
    raster[x, y] = value


def run_initialize(context: Context, config: RasterScanOperationConfig) -> None:
    station = context.station

    with station.laser.acquire(timeout=context.timeout) as laser:
        if not laser.get_output():
            raise RuntimeError("Laser not enabled, operation aborted.")

    with station.scope.acquire(timeout=context.timeout) as scope:
        logger.info("configure scope")
        scope.configure()
        logger.info("set scope average count: %d", config.average_count)
        scope.set_average_count(config.average_count)


def run_raster_scan(context: Context, config: RasterScanOperationConfig) -> None:
    session = Session(context)
    station = context.station

    sample_name = context.sample_name()
    base_output_path = context.output_path()
    output_path = str(Path(base_output_path) / sample_name)

    context.set_status_message("Raster Scan...")
    context.set_status_progress(0, 0)

    channel = config.source_channel
    if channel not in context.waveform_channels():
        raise ValueError(f"No such source channel enabled: {channel}")

    offsets = (
        config.offset_left,
        config.offset_right,
        config.offset_top,
        config.offset_bottom,
    )
    logger.info("offsets %s", offsets)

    scale = 1e-3  # µm to mm

    # Total dimensions of the scan window in µm.
    width_um = abs(config.offset_left - config.offset_right)
    height_um = abs(config.offset_top - config.offset_bottom)

    left = config.offset_left * scale
    right = config.offset_right * scale
    top = config.offset_top * scale
    bottom = config.offset_bottom * scale

    # Include both edges of the scan window.
    n_points_x = config.n_points_x
    n_points_y = config.n_points_y

    total_steps = n_points_x * n_points_y

    x_size = width_um * scale
    y_size = height_um * scale
    step_x_size = x_size / n_points_x
    step_y_size = y_size / n_points_y

    logger.info("create raster: peak, %d, %d", n_points_x, n_points_y)
    raster_peak = create_raster(n_points_x, n_points_y)
    context.submit_event(CreateRaster(RasterType.PEAK, n_points_x, n_points_y))

    logger.info("create raster: area, %d, %d", n_points_x, n_points_y)
    raster_area = create_raster(n_points_x, n_points_y)
    context.submit_event(CreateRaster(RasterType.AREA, n_points_x, n_points_y))

    logger.info("create raster: t_max, %d, %d", n_points_x, n_points_y)
    raster_t_max = create_raster(n_points_x, n_points_y)
    context.submit_event(CreateRaster(RasterType.T_MAX, n_points_x, n_points_y))

    context.set_status_message("Raster Scan (0, 0)")
    context.set_status_progress(0, total_steps)

    # The current stage position is the reference point around which the
    # offsets define the scan window.
    with station.stage.acquire(timeout=context.timeout) as stage:
        initial_pos = stage.get_position()

    x_coords = np.asarray([initial_pos.x]) + np.linspace(left, right, n_points_x)
    y_coords = np.asarray([initial_pos.y]) + np.linspace(top, bottom, n_points_y)
    z_coords = np.asarray([initial_pos.z])

    x_profile = Profile.create(x_coords, np.full(len(x_coords), np.nan))
    context.submit_event(UpdateXProfile(x_profile.copy()))

    y_profile = Profile.create(y_coords, np.full(len(y_coords), np.nan))
    context.submit_event(UpdateYProfile(y_profile.copy()))

    start_pos = Vector3(
        x=initial_pos.x - left,
        y=initial_pos.y - top,
        z=initial_pos.z,
    )

    logger.info(
        "raster window: initial_pos=(%s, %s, %s), start_pos=(%s, %s, %s), size=(%s mm, %s mm)",
        initial_pos.x,
        initial_pos.y,
        initial_pos.z,
        start_pos.x,
        start_pos.y,
        start_pos.z,
        x_size,
        y_size,
    )

    now = datetime.now().astimezone()

    file_writer = RasterScanFileWriter(output_path) if config.write_csv else None

    if file_writer is not None:
        file_writer = RasterScanFileWriter(output_path)
        file_writer.create_output_path()

        header = {
            "measurement": "tct_laser",
            "measurement_type": "raster_scan",
            "timestamp": now.isoformat(),
            "scan": {
                "x_size_mm": x_size,
                "y_size_mm": y_size,
                "x_step_size_mm": step_x_size,
                "y_step_size_mm": step_y_size,
                "offset_left_mm": config.offset_left * scale,
                "offset_right_mm": config.offset_right * scale,
                "offset_top_mm": config.offset_top * scale,
                "offset_bottom_mm": config.offset_bottom * scale,
                "average_count": config.average_count,
                "mode": config.mode,
            },
            "stage_position_mm": {
                # Position before the raster scan began.
                "x": float(initial_pos.x),
                "y": float(initial_pos.y),
                "z": float(initial_pos.z),
            },
            "scan_start_position_mm": {
                "x": float(start_pos.x),
                "y": float(start_pos.y),
                "z": float(start_pos.z),
            },
        }

        file_writer.write_header(header)

        table_columns = [
            "index",
            "x",
            "y",
            "stage_x_mm",
            "stage_y_mm",
            "peak_mean",
            "area_mean",
            "t_max_mean",
        ]
        file_writer.write_table_header(table_columns)

    try:
        context.set_status_message("Raster Scan moving to start...")
        session.move_absolute(start_pos)

        e = Estimate(total_steps)
        for index, (x, y) in enumerate(
            xy_range(n_points_x, n_points_y, mode=config.mode)
        ):
            if context.is_abort():
                logger.warning("Aborted Raster Scan!")
                break

            pos_x = x_coords[x].item()
            pos_y = y_coords[y].item()
            pos_z = z_coords[0].item()

            session.move_absolute(Vector3(pos_x, pos_y, pos_z))

            wf = session.acquire_waveform(channel)

            # Peak
            mean_peak = float(np.max(wf.y))
            set_raster_value(raster_peak, x, y, mean_peak)
            context.submit_event(UpdateRasterValue(RasterType.PEAK, x, y, mean_peak))
            logger.info("raster[%s,%s].peak: %.3G", x, y, mean_peak)

            if y == n_points_y // 2:
                x_profile.y[x] = mean_peak
                context.submit_event(UpdateXProfile(x_profile.copy()))
            if x == n_points_x // 2:
                y_profile.y[y] = mean_peak
                context.submit_event(UpdateYProfile(y_profile.copy()))

            # Area
            mean_area = pulse_area_window(wf.x, wf.y)
            set_raster_value(raster_area, x, y, mean_area)
            context.submit_event(UpdateRasterValue(RasterType.AREA, x, y, mean_area))
            logger.info("raster[%s,%s].area: %.3G", x, y, mean_area)

            # Time of maximum
            imax = int(np.argmax(wf.y))
            mean_t_max = float(wf.x[imax])
            set_raster_value(raster_t_max, x, y, mean_t_max)
            context.submit_event(UpdateRasterValue(RasterType.T_MAX, x, y, mean_t_max))
            logger.info("raster[%s,%s].t_max: %.3G", x, y, mean_t_max)

            e.advance()
            elapsed = timedelta(seconds=int(e.elapsed.total_seconds()))
            remaining = timedelta(seconds=int(e.remaining.total_seconds()))
            context.set_status_message(
                f"Raster Scan (x={x}, y={y}) Elapsed {elapsed}, ETA {remaining}"
            )
            context.set_status_progress(index + 1, total_steps)

            if file_writer is not None:
                file_writer.write_table_row(
                    [
                        index,
                        x,
                        y,
                        pos_x,
                        pos_y,
                        mean_peak,
                        mean_area,
                        mean_t_max,
                    ]
                )
    finally:
        # Complete the output file and always return to the position from
        # which the scan was started.
        if file_writer is not None:
            file_writer.write_footer()

        context.set_status_message("Raster Scan moving back to initial_pos position...")
        session.move_absolute(initial_pos)

    context.set_status_progress(0, 0)

    if config.write_plots:
        context.set_status_message("Writing plots...")

        logger.info("generating plots...")

        plot_writer = PlotWriter(
            raster_ampl=raster_peak[..., np.newaxis],  # add Z axis for backward compat
            x_coords=x_coords,
            y_coords=y_coords,
            z_coords=z_coords,
            output_path=output_path,
            sample_name=sample_name,
            timestamp=now,
        )

        logger.info("writing amplitude plot...")
        try:
            plot_writer.save_amplitude_map(z_index=0)
        except Exception:
            logger.exception("failed to write amplitude plot")

        logger.info("writing XZ profile plot...")
        try:
            plot_writer.save_xz_profile()
        except Exception:
            logger.exception("failed to write XZ profile plot")

        logger.info("writing YZ profile plot...")
        try:
            plot_writer.save_yz_profile()
        except Exception:
            logger.exception("failed to write YZ profile plot")

    context.set_status_message("Raster Scan done.")
