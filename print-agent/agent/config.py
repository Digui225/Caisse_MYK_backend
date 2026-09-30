from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    printer_vendor_id: int = 0x0416
    printer_product_id: int = 0x5011
    printer_in_ep: int = 0x82
    printer_out_ep: int = 0x01
    printer_width: int = 48
    printer_codepage: str = "CP858"
    drawer_pulse: str = "1b700019fa"
    printer_backend: Literal["usb", "dummy"] = "usb"

    agent_host: str = "127.0.0.1"
    agent_port: int = 8090
    agent_token: str = ""

    @field_validator("printer_vendor_id", "printer_product_id", "printer_in_ep",
                     "printer_out_ep", mode="before")
    @classmethod
    def _hex(cls, value: object) -> object:
        return int(value, 0) if isinstance(value, str) else value

    @property
    def drawer_pulse_bytes(self) -> bytes:
        return bytes.fromhex(self.drawer_pulse)


@lru_cache
def get_settings() -> AgentSettings:
    return AgentSettings()
