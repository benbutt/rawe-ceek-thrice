import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add the parent directory to sys.path so we can import the project modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from rawe_ceek_thrice.data.models import Device, Driver, Message, Topic


@pytest.fixture
def sample_drivers():
    """Fixture to provide sample driver data"""
    return [
        Driver(
            broadcast_name="VER",
            full_name="Max Verstappen",
            driver_number=1,
            team_colour="#0600EF",  # Red Bull blue
            team_name="Red Bull Racing",
        ),
        Driver(
            broadcast_name="HAM",
            full_name="Lewis Hamilton",
            driver_number=44,
            team_colour="#00D2BE",  # Mercedes teal
            team_name="Mercedes",
        ),
        Driver(
            broadcast_name="LEC",
            full_name="Charles Leclerc",
            driver_number=16,
            team_colour="#DC0000",  # Ferrari red
            team_name="Ferrari",
        ),
    ]


@pytest.fixture
def sample_timing_data():
    """Fixture to provide sample F1 timing data"""
    return {
        "Lines": {
            "1": {"Line": 1, "Position": 1, "GapToLeader": "", "LapTime": "1:32.123"},
            "44": {
                "Line": 2,
                "Position": 2,
                "GapToLeader": "+2.345",
                "LapTime": "1:32.456",
            },
            "16": {
                "Line": 3,
                "Position": 3,
                "GapToLeader": "+5.678",
                "LapTime": "1:32.789",
            },
        }
    }


@pytest.fixture
def sample_message(sample_timing_data):
    """Fixture to provide a sample message from F1 timing data stream"""
    return Message(
        topic=Topic.TimingAppData,
        content=sample_timing_data,
        timestamp="2023-04-01T12:34:56.789Z",
    )


@pytest.fixture
def sample_devices():
    """Fixture to provide sample Hue light devices"""
    return [
        Device(
            id="01234567-89ab-cdef-0123-456789abcdef",
            product_data={
                "model_id": "LCT007",
                "manufacturer_name": "Signify Netherlands B.V.",
                "product_name": "Hue color lamp",
                "product_archetype": "sultan_bulb",
                "certified": True,
                "software_version": "1.88.1",
            },
            metadata={
                "name": "Living Room Light 1",
                "archetype": "sultan_bulb",
            },
            services=[
                {"rid": "12345", "rtype": "light"},
                {"rid": "67890", "rtype": "zigbee_connectivity"},
            ],
            type="device",
        ),
        Device(
            id="fedcba98-7654-3210-fedc-ba9876543210",
            product_data={
                "model_id": "LCT007",
                "manufacturer_name": "Signify Netherlands B.V.",
                "product_name": "Hue color lamp",
                "product_archetype": "sultan_bulb",
                "certified": True,
                "software_version": "1.88.1",
            },
            metadata={
                "name": "Living Room Light 2",
                "archetype": "sultan_bulb",
            },
            services=[
                {"rid": "abcde", "rtype": "light"},
                {"rid": "fghij", "rtype": "zigbee_connectivity"},
            ],
            type="device",
        ),
    ]


@pytest.fixture
def mock_env_config():
    """Mock environment configuration"""
    with patch.dict(
        os.environ,
        {
            "HUE_BRIDGE_IP": "192.168.1.165",
            "HUE_USERNAME": "testuser",
            "HUE_CLIENT_KEY": "testkey",
            "TV_DELAY_SECONDS": "30",
        },
    ):
        yield
