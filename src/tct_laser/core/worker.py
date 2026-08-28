import logging
import time
from collections.abc import Callable
from threading import Event
from typing import Any

from tct_laser.core.geometry import Vector3

from .actors import LaserActor, PowerMeterActor, ScopeActor
from .context import RunOperationEvent
from .context import WorkerContext as Context
from .events import (
    ConfigureEvent,
    ConnectEvent,
    DisconnectEvent,
    LaserMetrics,
    LaserMetricsEvent,
    MoveAbsoluteAxisEvent,
    MoveAbsoluteEvent,
    MoveRelativeEvent,
    PositionChangedEvent,
    PowerMeterMetrics,
    PowerMeterMetricsEvent,
    SetLaserFrequency,
    SetLaserOutput,
    SetLaserTune,
    SetPowerMeterAverageCount,
    SetPowerMeterWavelength,
)
from .lease import LeaseTimeoutError
from .service import BackgroundService, ServiceGroup
from .session import Session
from .station import Role

logger = logging.getLogger(__name__)

__all__ = ["Worker"]


class Worker:
    def __init__(self, context: Context) -> None:
        self.context = context
        self.shutdown_event = Event()
        self.services = [
            BackgroundService("metrics", MetricsWorker(context)),
            BackgroundService("waveform", WaveformWorker(context)),
        ]

    def stop(self) -> None:
        self.shutdown_event.set()

    def run(self) -> None:
        logger.info("starting worker thread...")

        while not self.shutdown_event.is_set():
            try:
                with ServiceGroup(self.services):
                    self.run_message_loop()
            except Exception as exc:
                self.handle_failure(exc)

        logger.info("stopped worker thread.")

    def run_message_loop(self) -> None:
        while not self.shutdown_event.is_set():
            event = self.context.next_event(timeout=0.1)

            if event is None:
                continue

            try:
                self.handle_event(event)
            except Exception as exc:
                logger.exception("Failed to run operation")
                self.handle_failure(exc)
            finally:
                self.context.finish()
                self.context.cancel_abort()

    def handle_event(self, event: Any) -> None:
        match event:
            case ConnectEvent(instrument):
                run_connect(self.context, instrument)
            case DisconnectEvent(instrument):
                run_disconnect(self.context, instrument)
            case ConfigureEvent(data):
                run_configure(self.context, data)
            case MoveRelativeEvent(offset):
                run_move_relative(self.context, offset)
            case MoveAbsoluteEvent(position):
                run_move_absolute(self.context, position)
            case MoveAbsoluteAxisEvent(axis, value):
                run_move_absolute_axis(self.context, axis, value)
            case RunOperationEvent(operation_runner):
                try:
                    self.context.set_live_waveform_allowed(False)
                    operation_runner(self.context)
                finally:
                    self.context.set_live_waveform_allowed(True)
            case _:
                logger.error("Invalid event: %r", event)

    def handle_failure(self, exc: Exception) -> None:
        self.context.fail(exc)
        self.context.set_status_message("Error")
        self.context.drain_inbox()
        self.context.sleep(1)


def run_connect(context: Context, instrument: str) -> None:
    with context.station[instrument].acquire(timeout=10) as actor:
        actor.connect()


def run_disconnect(context: Context, instrument: str) -> None:
    with context.station[instrument].acquire(timeout=10) as actor:
        actor.disconnect()


def configure_laser(laser: LaserActor, parameter) -> None:
    match parameter:
        case SetLaserOutput(enabled):
            laser.set_output(enabled)
        case SetLaserFrequency(frequency):
            laser.set_frequency(frequency)
        case SetLaserTune(tune):
            laser.set_tune(tune)
        case _:
            logger.error("unsupported laser parameter: %s", parameter)


def configure_power_meter(power_meter: PowerMeterActor, parameter) -> None:
    match parameter:
        case SetPowerMeterWavelength(wavelength):
            power_meter.set_wavelength(wavelength)
        case SetPowerMeterAverageCount(average_count):
            power_meter.set_average_count(average_count)
        case _:
            logger.error("unsupported power meter parameter: %s", parameter)


def run_configure(context: Context, config: list[tuple[str, Any]]) -> None:
    context.set_status_message("Configure...")
    context.set_status_progress(0, 0)

    station = context.station
    timeout = 10.0

    configure_callbacks: dict[str, Callable] = {
        Role.LASER: configure_laser,
        Role.POWER_METER_1: configure_power_meter,
        Role.POWER_METER_2: configure_power_meter,
        Role.POWER_METER_3: configure_power_meter,
    }

    for instrument, parameter in config:
        logger.info("configure: %s = %s", instrument, parameter)
        lease = station[instrument]

        with lease.acquire(timeout=timeout) as actor:
            configure_callbacks[instrument](actor, parameter)

    context.set_status_message("Configure done.")


def run_move_relative(context: Context, offset: Vector3) -> None:
    context.set_status_message("Move relative...")
    context.set_status_progress(0, 0)
    Session(context).move_relative(offset)
    context.set_status_message("Move relative done.")


def run_move_absolute(context: Context, position: Vector3) -> None:
    context.set_status_message("Move absolute...")
    context.set_status_progress(0, 0)
    Session(context).move_absolute(position)
    context.set_status_message("Move absolute done.")


def run_move_absolute_axis(context: Context, axis: str, value: float) -> None:
    context.set_status_message("Move absolute axis...")
    context.set_status_progress(0, 0)
    Session(context).move_absolute_axis(axis, value)
    context.set_status_message("Move absolute axis done.")


def safely_poll[T](
    name: str,
    getter: Callable[[], T],
) -> T | None:
    try:
        return getter()
    except Exception:
        logger.error("failed to poll laser metric [%s]", name)
        return None


class MetricsWorker:
    def __init__(self, context: Context) -> None:
        self.context = context
        self.shutdown_event = Event()
        self.slow_interval = 1.0
        self.last_slow_poll = 0.0

    def stop(self) -> None:
        self.shutdown_event.set()

    def run(self) -> None:
        while not self.shutdown_event.is_set():
            try:
                self.poll_once()
            except Exception:
                logger.exception("Failed to poll")
                self.shutdown_event.wait(1.0)
            else:
                self.shutdown_event.wait(0.1)

    def poll_once(self) -> None:
        dt = time.monotonic() - self.last_slow_poll

        if dt > self.slow_interval:
            try:
                self.poll_scope()
                self.poll_stage()
                self.poll_laser()
                self.poll_power_meter(Role.POWER_METER_1)
                self.poll_power_meter(Role.POWER_METER_2)
                self.poll_power_meter(Role.POWER_METER_3)
            finally:
                self.last_slow_poll = time.monotonic()

    def poll_scope(self) -> None: ...

    def poll_stage(self) -> None:
        context = self.context
        station = context.station
        try:
            with station.stage.acquire(timeout=0) as stage:
                if stage.is_connected:
                    position = stage.get_position()
                    context.submit_event(PositionChangedEvent(position))
        except LeaseTimeoutError:
            ...
        except Exception:
            logger.exception("failed to poll [stage]")

    def poll_laser(self) -> None:
        station = self.context.station
        metrics = LaserMetrics()

        try:
            with station.laser.acquire(timeout=0) as laser:
                if laser.is_connected:
                    metrics = LaserMetrics(
                        output=safely_poll(
                            "output",
                            laser.get_output,
                        ),
                        frequency=safely_poll(
                            "frequency",
                            laser.get_frequency,
                        ),
                        tune=safely_poll(
                            "tune",
                            laser.get_tune,
                        ),
                        head_temperature=safely_poll(
                            "head_temperature",
                            laser.get_head_temperature,
                        ),
                        diode_temperature=safely_poll(
                            "diode_temperature",
                            laser.get_diode_temperature,
                        ),
                    )
        except LeaseTimeoutError:
            logger.debug("laser is currently leased")
        except Exception:
            logger.exception("failed to poll [laser]")

        self.context.submit_event(LaserMetricsEvent(Role.LASER, metrics))

    def poll_power_meter(self, name: str) -> None:
        context = self.context
        station = context.station
        metrics = PowerMeterMetrics()

        try:
            with station[name].acquire(timeout=0) as power_meter:
                if power_meter.is_connected:
                    metrics = PowerMeterMetrics(
                        power=power_meter.measure_power(),
                        wavelength=power_meter.get_wavelength(),
                        average_count=power_meter.get_average_count(),
                    )
        except LeaseTimeoutError:
            ...
        except Exception:
            logger.exception("failed to poll [%s]", name)

        context.submit_event(PowerMeterMetricsEvent(name, metrics))


class WaveformWorker:
    def __init__(self, context: Context) -> None:
        self.context = context
        self.shutdown_event = Event()
        self.throttle_delay = 0.001
        self.error_delay = 1.0

    def stop(self) -> None:
        self.shutdown_event.set()

    def run(self) -> None:
        needs_configure = True
        while not self.shutdown_event.is_set():
            try:
                needs_configure = self._poll_once(needs_configure)
            except LeaseTimeoutError:
                needs_configure = True
            except Exception:
                logger.exception("Failed to acquire waveform")
                self.shutdown_event.wait(self.error_delay)
                needs_configure = True
            finally:
                self.shutdown_event.wait(self.throttle_delay)

    def _poll_once(self, needs_configure: bool) -> bool:
        """Acquire and process one waveform cycle. Returns the updated
        needs_configure state for the next iteration."""
        context = self.context

        if not context.is_live_waveform_allowed():
            return True  # force reconfigure once it's allowed again

        with context.station.scope.acquire(timeout=0) as scope:
            if not context.is_live_waveform():
                return True

            if needs_configure:
                logger.info("configure scope for live waveform")
                self.configure(scope)
                needs_configure = False

            self.acquire_waveforms(scope)
            return needs_configure

    def configure(self, scope: ScopeActor) -> None:
        scope.configure()

    def acquire_waveforms(self, scope: ScopeActor) -> None:
        context = self.context
        for channel in context.waveform_channels():
            if channel in scope.get_channels():
                try:
                    scope.acquire()
                    waveform = scope.read_waveform(channel)
                    context.publish_waveform(waveform)
                except Exception:
                    ...
