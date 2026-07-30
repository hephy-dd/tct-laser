import re
from enum import StrEnum
from typing import Any

import msgspec
from pyvisa import ResourceManager
from pyvisa.constants import Parity, StopBits

__all__ = ["ResourceConfig", "parse_resource"]


class Termination(StrEnum):
    LF = "\n"
    CR = "\r"
    CRLF = "\r\n"
    NONE = ""


class SerialFormat(StrEnum):
    E8N1 = "8N1"
    E8E1 = "8E1"
    E8O1 = "8O1"
    E8N2 = "8N2"
    E7E1 = "7E1"
    E7O1 = "7O1"


SERIAL_FORMATS: dict[SerialFormat, tuple[int, Parity, StopBits]] = {
    SerialFormat.E8N1: (8, Parity.none, StopBits.one),
    SerialFormat.E8E1: (8, Parity.even, StopBits.one),
    SerialFormat.E8O1: (8, Parity.odd, StopBits.one),
    SerialFormat.E8N2: (8, Parity.none, StopBits.two),
    SerialFormat.E7E1: (7, Parity.even, StopBits.one),
    SerialFormat.E7O1: (7, Parity.odd, StopBits.one),
}


class ResourceError(Exception): ...


def create_resource_manager(visa_library: str) -> ResourceManager:
    if not visa_library:
        return ResourceManager()
    return ResourceManager(visa_library)


def list_resources() -> list[str]:
    rm = ResourceManager()
    return list(rm.list_resources())


class ResourceConfig(msgspec.Struct, frozen=True):
    model: str = ""
    resource_name: str = ""
    termination: Termination = Termination.LF
    timeout: float = 4.0
    baud_rate: int = 9600
    serial_format: SerialFormat = SerialFormat.E8N1


def default_resource_factory(resource_config: ResourceConfig) -> Any:
    resource_name, visa_library = parse_resource(resource_config.resource_name)

    try:
        resource_manager = create_resource_manager(visa_library)
    except Exception as exc:
        raise ResourceError(
            f"Failed to create resource manager for {visa_library!r}"
        ) from exc

    try:
        resource = resource_manager.open_resource(
            resource_name,
            read_termination=resource_config.termination,
            write_termination=resource_config.termination,
            timeout=int(resource_config.timeout * 1000),
        )
    except Exception as exc:
        raise ResourceError(f"Failed to open resource {resource_name!r}") from exc

    try:
        configure_resource(resource, resource_config)
    except Exception as exc:
        resource.close()
        raise ResourceError(f"Failed to configure resource {resource_name!r}") from exc

    return resource


def configure_resource(resource: Any, resource_config: ResourceConfig) -> None:
    if hasattr(resource, "baud_rate"):
        resource.baud_rate = resource_config.baud_rate

    data_bits, parity, stop_bits = SERIAL_FORMATS[resource_config.serial_format]

    if hasattr(resource, "data_bits"):
        resource.data_bits = data_bits
        resource.parity = parity
        resource.stop_bits = stop_bits


def parse_resource(resource_name: str) -> tuple[str, str]:
    """Create valid VISA resource name for short descriptors."""
    resource_name = resource_name.strip()

    if m := re.match(r"^(\d+)$", resource_name):
        resource_name = f"GPIB0::{m.group(1)}::INSTR"

    if m := re.match(r"^COM(\d+)$", resource_name):
        resource_name = f"ASRL{m.group(1)}::INSTR"

    if m := re.match(r"^ASRL(\d+)$", resource_name):
        resource_name = f"ASRL{m.group(1)}::INSTR"

    if m := re.match(r"^(\d+\.\d+\.\d+\.\d+)\:(\d+)$", resource_name):
        resource_name = f"TCPIP0::{m.group(1)}::{m.group(2)}::SOCKET"

    if m := re.match(r"^(\w+)\:(\d+)$", resource_name):
        resource_name = f"TCPIP0::{m.group(1)}::{m.group(2)}::SOCKET"

    visa_library = ""
    if resource_name.startswith("ASRL"):
        visa_library = "@py"
    if resource_name.startswith("TCPIP"):
        visa_library = "@py"

    return resource_name, visa_library


def is_serial_resource(resource_name: str) -> bool:
    return resource_name.strip().startswith(("ASRL", "COM"))
