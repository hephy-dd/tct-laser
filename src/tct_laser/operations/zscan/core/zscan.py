import logging
import math
import sys
from datetime import timedelta

import msgspec
import numpy as np
from comet.estimate import Estimate
from numpy.typing import NDArray

from tct_laser.core.context import WorkerContext as Context
from tct_laser.core.session import Session
from tct_laser.core.utils import Vector3, Waveform

from .utils import focus_slope, path_distance, vector_length

__all__ = [
    "AutoFocusZ",
    "ZScanOperation",
    "ZScanSeries",
    "ZScanXYSeries",
]

logger = logging.getLogger(__name__)

type FloatArray = NDArray[np.float64]

UM_TO_MM = 1e-3
POSITION_TOLERANCE_MM = 1e-9
MOVE_SETTLING_TIME_S = 0.05


class ZScanOperation(msgspec.Struct, frozen=True):
    """
    Find the best relative Z focus by scanning an XY line at several Z offsets.

    All configured offsets are expressed in micrometres. Stage positions and
    movement commands are expressed in millimetres.

    ``z_steps`` and ``xy_steps`` are inclusive point counts. For example,
    ``z_steps=5`` produces five Z coordinates including the configured start
    and stop offsets.
    """

    z_start_offset_um: int
    z_stop_offset_um: int
    z_steps: int

    start_x_offset_um: int
    start_y_offset_um: int
    stop_x_offset_um: int
    stop_y_offset_um: int
    xy_steps: int

    source_channel: str
    average_count: int

    def run(self, context: Context) -> None:
        run_initialize(context, self)
        run_z_scan(context, self)


class AutoFocusZ(msgspec.Struct, frozen=True):
    """Best absolute stage Z position found by the scan, in millimetres."""

    z_mm: float


class ZScanXYSeries(msgspec.Struct, frozen=True):
    """
    Live XY amplitude samples acquired at one relative Z offset.

    Repeated messages with the same ``z_um`` update the same live plot series.
    A new ``z_um`` value starts a new XY series.
    """

    z_um: float
    xy_um: FloatArray
    amplitude_v: FloatArray


class ZScanSeries(msgspec.Struct, frozen=True):
    """Accumulated relative Z offsets and their autofocus slopes."""

    z_um: FloatArray
    slope_v_per_um: FloatArray


def run_initialize(context: Context, config: ZScanOperation) -> None:
    validate_config(config)

    station = context.station

    with station.laser.acquire(timeout=context.timeout) as laser:
        if not laser.get_output():
            raise RuntimeError("Laser not enabled, operation aborted.")

    with station.scope.acquire(timeout=context.timeout) as scope:
        logger.info("configure scope")
        scope.configure()
        logger.info("set scope average count: %d", config.average_count)
        scope.set_average_count(config.average_count)


def validate_config(config: ZScanOperation) -> None:
    if config.z_steps <= 0:
        raise ValueError("Z scan point count must be greater than zero.")

    if config.xy_steps < 2:
        raise ValueError(
            "At least two XY points are required to calculate a focus slope."
        )

    if config.average_count <= 0:
        raise ValueError("Scope average count must be greater than zero.")

    if (
        config.start_x_offset_um == config.stop_x_offset_um
        and config.start_y_offset_um == config.stop_y_offset_um
    ):
        raise ValueError("XY scan start and stop positions must be different.")


def run_z_scan(context: Context, config: ZScanOperation) -> None:
    session = Session(context)

    channel = config.source_channel
    if channel not in context.waveform_channels():
        raise ValueError(f"No such source channel enabled: {channel}")

    initial_position = session.position()
    initial_z_mm = initial_position.z

    z_offsets_um = np.linspace(
        config.z_start_offset_um,
        config.z_stop_offset_um,
        num=config.z_steps,
        dtype=np.float64,
    )

    x_offsets_um = np.linspace(
        config.start_x_offset_um,
        config.stop_x_offset_um,
        num=config.xy_steps,
        dtype=np.float64,
    )

    y_offsets_um = np.linspace(
        config.start_y_offset_um,
        config.stop_y_offset_um,
        num=config.xy_steps,
        dtype=np.float64,
    )

    xy_distance_um = path_distance(x_offsets_um, y_offsets_um)

    total_acquisitions = config.z_steps * config.xy_steps
    estimate = Estimate(total_acquisitions)

    scanned_z_um: list[float] = []
    focus_slopes: list[float] = []
    completed_scans: list[tuple[float, FloatArray, FloatArray]] = []

    best_z_offset_um = math.nan
    best_score = -math.inf

    completed_acquisitions = 0
    aborted = False

    context.set_status_message("Z Scan...")
    context.set_status_progress(0, total_acquisitions)
    context.publish_message(AutoFocusZ(math.nan))
    publish_focus_series(context, scanned_z_um, focus_slopes)

    try:
        for z_index, z_offset_um_value in enumerate(z_offsets_um):
            z_offset_um = float(z_offset_um_value)

            if context.is_abort():
                aborted = True
                logger.warning(
                    "Z Scan aborted before Z point %d.",
                    z_index + 1,
                )
                break

            move_to_relative_offset(
                session=session,
                initial_position=initial_position,
                target_offset_mm=Vector3(
                    float(x_offsets_um[0]) * UM_TO_MM,
                    float(y_offsets_um[0]) * UM_TO_MM,
                    z_offset_um * UM_TO_MM,
                ),
            )
            context.sleep(MOVE_SETTLING_TIME_S)

            amplitudes_v: list[float] = []
            acquired_distance_um: list[float] = []

            # Publish an empty row immediately. This allows the UI to create the
            # new Z curve before its first acquisition arrives.
            publish_xy_series(
                context=context,
                z_um=z_offset_um,
                xy_um=acquired_distance_um,
                amplitude_v=amplitudes_v,
            )

            for xy_index in range(config.xy_steps):
                if context.is_abort():
                    aborted = True
                    logger.warning(
                        "Z Scan aborted at Z point %d, XY point %d.",
                        z_index + 1,
                        xy_index + 1,
                    )
                    break

                if xy_index > 0:
                    session.move_relative(
                        Vector3(
                            (
                                float(x_offsets_um[xy_index])
                                - float(x_offsets_um[xy_index - 1])
                            )
                            * UM_TO_MM,
                            (
                                float(y_offsets_um[xy_index])
                                - float(y_offsets_um[xy_index - 1])
                            )
                            * UM_TO_MM,
                            0.0,
                        )
                    )
                    context.sleep(MOVE_SETTLING_TIME_S)

                waveform = session.acquire_waveform(channel)
                amplitude_v = waveform_amplitude(waveform)

                acquired_distance_um.append(float(xy_distance_um[xy_index]))
                amplitudes_v.append(amplitude_v)

                completed_acquisitions += 1
                estimate.advance()

                publish_xy_series(
                    context=context,
                    z_um=z_offset_um,
                    xy_um=acquired_distance_um,
                    amplitude_v=amplitudes_v,
                )

                update_progress(
                    context=context,
                    estimate=estimate,
                    completed=completed_acquisitions,
                    total=total_acquisitions,
                    z_index=z_index,
                    z_count=config.z_steps,
                    xy_index=xy_index,
                    xy_count=config.xy_steps,
                    z_offset_um=z_offset_um,
                )

            # A partially acquired row can still produce a focus score when it
            # contains at least two spatially distinct, finite measurements.
            if len(amplitudes_v) >= 2:
                slope = focus_slope(
                    distance_um=np.asarray(
                        acquired_distance_um,
                        dtype=np.float64,
                    ),
                    amplitude_v=np.asarray(
                        amplitudes_v,
                        dtype=np.float64,
                    ),
                )

                distance_array = np.asarray(
                    acquired_distance_um,
                    dtype=np.float64,
                )
                amplitude_array = np.asarray(
                    amplitudes_v,
                    dtype=np.float64,
                )
                completed_scans.append(
                    (z_offset_um, distance_array.copy(), amplitude_array.copy())
                )

                scanned_z_um.append(z_offset_um)
                focus_slopes.append(slope)

                score = abs(slope)
                if np.isfinite(score) and score > best_score:
                    best_score = score
                    best_z_offset_um = z_offset_um

                    context.publish_message(
                        AutoFocusZ(initial_z_mm + best_z_offset_um * UM_TO_MM)
                    )

                publish_focus_series(
                    context,
                    scanned_z_um,
                    focus_slopes,
                )

                logger.info(
                    "Z %.3f µm: steepest amplitude slope %.6g V/µm",
                    z_offset_um,
                    slope,
                )

            if aborted:
                break

    finally:
        scan_exception_active = sys.exc_info()[0] is not None

        try:
            restore_position(
                session=session,
                target_position=initial_position,
            )
            logger.info("Restored initial stage position.")
        except Exception:
            logger.exception("Failed to restore the initial stage position.")

            # Preserve an exception already raised by the measurement. When the
            # scan itself succeeded, restoration failure must remain visible.
            if not scan_exception_active:
                raise

    if math.isfinite(best_z_offset_um):
        best_absolute_z_mm = initial_z_mm + best_z_offset_um * UM_TO_MM
        context.publish_message(AutoFocusZ(best_absolute_z_mm))

        if aborted:
            context.set_status_message(
                f"Z Scan aborted. Best measured Z offset: {best_z_offset_um:.1f} µm."
            )
        else:
            context.set_status_message(
                f"Z Scan done. Best Z offset: {best_z_offset_um:.1f} µm."
            )
    elif aborted:
        context.set_status_message("Z Scan aborted before a focus result was found.")
    else:
        context.set_status_message("Z Scan finished without a valid focus result.")


def waveform_amplitude(waveform: Waveform) -> float:
    """
    Calculate the waveform peak-to-peak amplitude in volts.

    Replace this function with a baseline-corrected or time-windowed estimator
    if the setup has a known signal window.
    """

    samples = np.asarray(waveform.y, dtype=np.float64)

    if samples.ndim != 1:
        samples = samples.reshape(-1)

    finite_samples = samples[np.isfinite(samples)]

    if finite_samples.size == 0:
        return math.nan

    return float(np.ptp(finite_samples))


def publish_xy_series(
    *,
    context: Context,
    z_um: float,
    xy_um: list[float],
    amplitude_v: list[float],
) -> None:
    """
    Publish an independent copy of the current XY row.

    Copying prevents the UI from observing list or array mutations while it is
    processing an earlier queued message.
    """

    context.publish_message(
        ZScanXYSeries(
            z_um=float(z_um),
            xy_um=np.array(
                xy_um,
                dtype=np.float64,
                copy=True,
            ),
            amplitude_v=np.array(
                amplitude_v,
                dtype=np.float64,
                copy=True,
            ),
        )
    )


def publish_focus_series(
    context: Context,
    z_um: list[float],
    slope_v_per_um: list[float],
) -> None:
    """Publish an independent copy of the accumulated autofocus results."""

    context.publish_message(
        ZScanSeries(
            z_um=np.array(
                z_um,
                dtype=np.float64,
                copy=True,
            ),
            slope_v_per_um=np.array(
                slope_v_per_um,
                dtype=np.float64,
                copy=True,
            ),
        )
    )


def update_progress(
    *,
    context: Context,
    estimate: Estimate,
    completed: int,
    total: int,
    z_index: int,
    z_count: int,
    xy_index: int,
    xy_count: int,
    z_offset_um: float,
) -> None:
    elapsed = timedelta(seconds=int(estimate.elapsed.total_seconds()))
    remaining = timedelta(seconds=int(estimate.remaining.total_seconds()))

    context.set_status_message(
        f"Z Scan ({completed}/{total}) | "
        f"Z {z_index + 1}/{z_count}: {z_offset_um:.1f} µm | "
        f"XY {xy_index + 1}/{xy_count} | "
        f"Elapsed {elapsed}, ETA {remaining}"
    )
    context.set_status_progress(completed, total)


def move_to_relative_offset(
    *,
    session: Session,
    initial_position: Vector3,
    target_offset_mm: Vector3,
) -> None:
    """
    Move to an XYZ offset relative to the operation's initial position.

    The actual current stage position is queried before calculating the move,
    preventing command or rounding errors from accumulating between rows.
    """

    initial_x, initial_y, initial_z = initial_position.to_tuple()
    offset_x, offset_y, offset_z = target_offset_mm.to_tuple()
    current_x, current_y, current_z = session.position().to_tuple()

    correction = Vector3(
        initial_x + offset_x - current_x,
        initial_y + offset_y - current_y,
        initial_z + offset_z - current_z,
    )

    if vector_length(correction) > POSITION_TOLERANCE_MM:
        session.move_relative(correction)


def restore_position(
    *,
    session: Session,
    target_position: Vector3,
) -> None:
    """Move from the actual current position back to the initial XYZ position."""

    target_x, target_y, target_z = target_position.to_tuple()
    current_x, current_y, current_z = session.position().to_tuple()

    correction = Vector3(
        target_x - current_x,
        target_y - current_y,
        target_z - current_z,
    )

    if vector_length(correction) > POSITION_TOLERANCE_MM:
        session.move_relative(correction)
