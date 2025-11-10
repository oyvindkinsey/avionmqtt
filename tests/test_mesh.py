from unittest.mock import Mock

import pytest
from bleak import BleakClient

from avionmqtt.Mesh import Mesh, _get_date_packet, _get_time_packet


class TestCreateMeshPackets:
    @pytest.fixture
    def mesh(self):
        """Create a Mesh instance with mocked BLE client."""
        mock_ble = Mock(spec=BleakClient)
        mock_ble.is_connected = True
        return Mesh(mock_ble, passphrase="test_passphrase")

    def test_write_date_command(self):
        control = bytearray([0x0, 0x0, 0x73, 0x0, 0x15, 0x0, 0x0, 0x0, 0x19, 0x0B, 0x9, 0x0, 0x0])
        test = _get_date_packet(2025, 11, 9)
        assert test == control

    def test_write_time_command(self):
        control = bytearray([0x0, 0x0, 0x73, 0x0, 0x16, 0x0, 0x0, 0x0, 0x15, 0xC, 0x2D, 0x0, 0x0])
        test = _get_time_packet(21, 12, 45)
        assert test == control
