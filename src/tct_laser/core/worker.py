import logging
import time
from threading import Event
from typing import Protocol, TypeVar, runtime_checkable

from pyqtgraph.graphicsItems.ImageItem import Callable

from tct_laser.core.actors.scope import ScopeActor

from .actors import LaserActor, PowerMeterActor
from .context import WorkerContext as Context
from .lease import LeaseTimeoutError
from .messages import (
    ConfigureMessage,
    Connect,
    Disconnect,
    LaserMetrics,
    MoveAbsoluteMessage,
    MoveRelativeMessage,
    PositionChanged,
    PowerMeterAverageCount,
    PowerMeterPower,
    PowerMeterWavelength,
    SetLaserFrequency,
    SetLaserOutput,
    SetLaserTune,
    SetPowerMeterAverageCount,
    SetPowerMeterWavelength,
)
from .service import BackgroundService, ServiceGroup
from .session import Session

T = TypeVar("T")

logger = logging.getLogger(__name__)


@runtime_checkable
class Operation(Protocol):
    def run(self, context: Context) -> None: ...


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
            message = self.context.next_message(timeout=0.1)

            if message is None:
                continue

            try:
                self.dispatch(message)
            except Exception as exc:
                logger.exception("Failed to run operation")
                self.handle_failure(exc)
            finally:
                self.context.finish()
                self.context.cancel_abort()

    def dispatch(self, message: object) -> None:
        if isinstance(message, Connect):
            run_connect(self.context, message)
        elif isinstance(message, Disconnect):
            run_disconnect(self.context, message)
        elif isinstance(message, ConfigureMessage):
            run_configure(self.context, message)
        elif isinstance(message, MoveRelativeMessage):
            run_move_relative(self.context, message)
        elif isinstance(message, MoveAbsoluteMessage):
            run_move_absolute(self.context, message)
        elif isinstance(message, Operation):
            try:
                self.context.set_live_waveform_allowed(False)
                message.run(self.context)
            finally:
                self.context.set_live_waveform_allowed(True)
        else:
            logger.error("Invalid message: %r", message)

    def handle_failure(self, exc: Exception) -> None:
        self.context.fail(exc)
        self.context.set_message("Error")
        self.context.drain_inbox()
        self.context.sleep(1)


def run_connect(context: Context, message: Connect) -> None:
    with context.station[message.instrument].acquire(timeout=10) as actor:
        actor.connect()


def run_disconnect(context: Context, message: Disconnect) -> None:
    with context.station[message.instrument].acquire(timeout=10) as actor:
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


def run_configure(context: Context, message: ConfigureMessage) -> None:
    context.set_message("Configure...")
    context.set_progress(0, 0)

    station = context.station
    timeout = 10.0

    configure_callbacks = {
        "laser": configure_laser,
        "power_meter_1": configure_power_meter,
        "power_meter_2": configure_power_meter,
        "power_meter_3": configure_power_meter,
    }

    for instrument, parameter in message.data:
        logger.info("configure: %s = %s", instrument, parameter)
        lease = station[instrument]

        with lease.acquire(timeout=timeout) as actor:
            configure_callbacks[instrument](actor, parameter)

    context.set_message("Configure done.")


def run_move_relative(context: Context, message: MoveRelativeMessage) -> None:
    context.set_message("Move relative...")
    context.set_progress(0, 0)
    Session(context).move_relative(message.offset)
    context.set_message("Move relative done.")


def run_move_absolute(context: Context, message: MoveAbsoluteMessage) -> None:
    context.set_message("Move absolute...")
    context.set_progress(0, 0)
    Session(context).move_absolute(message.position)
    context.set_message("Move absolute done.")


def safely_poll(
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
                self.poll_power_meter(1)
                self.poll_power_meter(2)
                self.poll_power_meter(3)
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
                    context.set_parameter(PositionChanged(position))
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
                        output=safely_poll("output", laser.get_output),
                        frequency=safely_poll("frequency", laser.get_frequency),
                        tune=safely_poll("tune", laser.get_tune),
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

        self.context.set_parameter(metrics)

    def poll_power_meter(self, index: int) -> None:
        context = self.context
        station = context.station
        instrument = f"power_meter_{index}"
        laser_power = None
        wavelength = None
        average_count = None
        try:
            with station[instrument].acquire(timeout=0) as power_meter:
                if power_meter.is_connected:
                    laser_power = power_meter.measure_power()
                    wavelength = power_meter.get_wavelength()
                    average_count = power_meter.get_average_count()
        except LeaseTimeoutError:
            ...
        except Exception:
            logger.exception("failed to poll [%s]", instrument)
        context.set_parameter(PowerMeterPower(index, laser_power))
        context.set_parameter(PowerMeterWavelength(index, wavelength))
        context.set_parameter(PowerMeterAverageCount(index, average_count))


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
                    context.set_waveform(waveform)
                except Exception:
                    ...
