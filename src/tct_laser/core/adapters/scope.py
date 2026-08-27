from typing import Any, ClassVar

import numpy as np
from comet.driver.rohde_schwarz.rto6 import RTO6
from comet.driver.rohde_schwarz.rtp164 import RTP164
from numpy.typing import NDArray

from ..waveform import Waveform

__all__ = ["RTO6Adapter", "RTP164Adapter"]


class RTBaseAdapter:
    CHANNELS: ClassVar = {
        "CHAN1": "CHAN1",
        "CHAN2": "CHAN2",
        "CHAN3": "CHAN3",
        "CHAN4": "CHAN4",
    }

    def __init__(self, resource: Any, driver: RTO6 | RTP164) -> None:
        self._resource = resource
        self._driver = driver

    def identify(self) -> str:
        return self._driver.identify()

    def get_channels(self) -> list[str]:
        return list(self.CHANNELS)

    def configure(self) -> None:
        self.configure_binary_transfer()
        self.configure_waveform_export()
        self.set_average_count(1)

    def configure_binary_transfer(self) -> None:
        self._resource.write("FORM REAL,32")
        self._resource.write("FORM:BORD LSBFirst")
        self._resource.query("*OPC?")

    def configure_waveform_export(self) -> None:
        self._resource.write("EXP:WAV:MULT OFF")
        self._resource.write("EXP:WAV:RAW OFF")
        self._resource.write("EXP:WAV:INCX OFF")
        self._resource.query("*OPC?")

    def set_average_count(self, average_count: int) -> None:
        self._resource.write(f"AQC:COUN {average_count:d}")
        self._resource.query("*OPC?")

    def acquire(self) -> None:
        self._resource.write("SING")
        self._resource.query("*OPC?")

    def read_waveform(self, channel: str) -> Waveform:
        channel = self._resolve_channel(channel)
        x = self._read_waveform_header(channel)
        y = self._read_waveform_samples(channel)
        return Waveform(channel, x, y)

    def _resolve_channel(self, channel: str) -> str:
        try:
            return self.CHANNELS[channel]
        except KeyError:
            valid_channels = ", ".join(self.get_channels())
            raise ValueError(
                f"Unknown channel {channel!r}; expected on of: {valid_channels}"
            ) from None

    def _read_waveform_header(self, channel: str) -> NDArray:
        head = self._resource.query(f":{channel}:DATA:HEAD?")
        xmin, xmax, pts = [float(x) for x in head.split(",")[:3]]
        return np.linspace(xmin, xmax, int(pts), endpoint=True)

    def _read_waveform_samples(self, channel: str) -> NDArray:
        samples = self._resource.query_binary_values(
            f":{channel}:DATA?", datatype="f", is_big_endian=False
        )
        return np.asarray(samples)


class RTO6Adapter(RTBaseAdapter):
    def __init__(self, resource: Any) -> None:
        super().__init__(
            resource,
            driver=RTO6(resource),
        )


class RTP164Adapter(RTBaseAdapter):
    def __init__(self, resource: Any) -> None:
        super().__init__(
            resource,
            driver=RTP164(resource),
        )
