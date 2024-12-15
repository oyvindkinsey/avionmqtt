from abc import ABC, abstractmethod

from bleak import BleakClient


class Integration(ABC):
    @abstractmethod
    async def register_lights(settings: dict, location: dict):
        pass

    @abstractmethod
    async def connect(self, mesh: BleakClient, key: str, settings: dict, location: dict):
        pass

    @abstractmethod
    async def update_state(self, message: dict):
        pass
