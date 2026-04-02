"""Map board profile interfaces to plugin-consumable structures.

For the MVP this is intentionally thin – it provides a stable API so the
mapper can grow (e.g. device-tree overlay resolution) without touching
individual plugins.
"""

from __future__ import annotations

from board.schemas import BoardProfile, I2CBus, GPIOLine, UARTPort, EthernetInterface


def get_i2c_buses(profile: BoardProfile) -> list[I2CBus]:
    return profile.interfaces.i2c


def get_gpio_lines(profile: BoardProfile) -> list[GPIOLine]:
    return profile.interfaces.gpio


def get_uart_ports(profile: BoardProfile) -> list[UARTPort]:
    return profile.interfaces.uart


def get_ethernet_interfaces(profile: BoardProfile) -> list[EthernetInterface]:
    return profile.interfaces.ethernet
