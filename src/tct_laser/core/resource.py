import re
from typing import Any

import msgspec
from pyvisa import ResourceManager

__all__ = ["ResourceConfig", "parse_resource"]


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
    termination: str = "\n"
    timeout: float = 4.0
    baud_rate: int = 9600


def default_resource_factory(resource_config: ResourceConfig) -> Any:
    resource_name, visa_library = parse_resource(resource_config.resource_name)

    resource_manager = create_resource_manager(visa_library)

    resource = resource_manager.open_resource(
        resource_name,
        read_termination=resource_config.termination,
        write_termination=resource_config.termination,
        timeout=int(resource_config.timeout * 1000),
    )

    try:
        configure_resource(resource, resource_config)
    except BaseException:
        resource.close()
        raise

    return resource


def configure_resource(resource: Any, resource_config: ResourceConfig) -> None:
    if hasattr(resource, "baud_rate"):
        resource.baud_rate = resource_config.baud_rate


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
