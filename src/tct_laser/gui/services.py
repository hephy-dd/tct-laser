from PySide6 import QtCore

from tct_laser.core.waveform import Waveform

__all__ = ["WaveformService"]


class WaveformService(QtCore.QObject):
    """Caches fast updating waveforms and throttles UI upates to retain performance."""

    waveform_changed = QtCore.Signal(str)

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._waveform_cache: dict[str, Waveform] = {}
        self._dirty_channels: set[str] = set()

        self._update_timer = QtCore.QTimer(self)
        self._update_timer.setInterval(33)  # 30 fps
        self._update_timer.timeout.connect(self.on_update_waveforms)
        self._update_timer.start()

    def stop(self) -> None:
        self._update_timer.stop()

    def set_interval(self, interval_ms: int) -> None:
        self._update_timer.setInterval(interval_ms)

    def clear_waveform(self, channel: str) -> None:
        self._waveform_cache.pop(channel, None)
        self._dirty_channels.discard(channel)

    def clear_waveforms(self) -> None:
        self._waveform_cache.clear()
        self._dirty_channels.clear()

    def set_waveform(self, waveform: Waveform) -> None:
        self._waveform_cache[waveform.channel] = waveform
        self._dirty_channels.add(waveform.channel)

    def get_waveform(self, channel: str) -> Waveform | None:
        return self._waveform_cache.get(channel)

    @QtCore.Slot()
    def on_update_waveforms(self) -> None:
        dirty_channels = self._dirty_channels
        self._dirty_channels = set()

        for channel in dirty_channels:
            self.waveform_changed.emit(channel)
