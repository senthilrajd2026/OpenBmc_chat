"""Pydantic schemas for board profile YAML documents."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# Low-level interface definitions
# ---------------------------------------------------------------------------

class I2CDevice(BaseModel):
    name: str
    address: int  # stored as int; loader normalises hex strings

    @field_validator("address", mode="before")
    @classmethod
    def normalise_address(cls, v: Any) -> int:
        """Accept '0x50', 80, or '80' and return int."""
        if isinstance(v, str):
            return int(v, 0)
        return int(v)


class I2CBus(BaseModel):
    bus: int
    devices: list[I2CDevice] = []


class GPIOLine(BaseModel):
    line: int
    name: str
    direction: str = "in"  # "in" | "out"


class UARTPort(BaseModel):
    port: str
    baudrate: int = 115200
    loopback_required: bool = False


class EthernetInterface(BaseModel):
    name: str
    phy_expected: bool = True


class Interfaces(BaseModel):
    i2c: list[I2CBus] = []
    gpio: list[GPIOLine] = []
    uart: list[UARTPort] = []
    ethernet: list[EthernetInterface] = []


# ---------------------------------------------------------------------------
# Top-level board profile
# ---------------------------------------------------------------------------

class BoardMeta(BaseModel):
    name: str
    vendor: str = ""
    soc: str = ""
    os: str = ""
    revision: str = ""


class BoardProfile(BaseModel):
    board: BoardMeta
    interfaces: Interfaces = Interfaces()
