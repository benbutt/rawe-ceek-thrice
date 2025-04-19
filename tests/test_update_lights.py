import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add the parent directory to sys.path so we can import the project modules
sys.path.insert(0, str(Path(__file__).parent.parent))

import aiohttp
import pytest

from models import Color, Device, Dimming, LightState, Power, Service, XYColor
from update_lights import (
    create_light_state,
    list_devices,
    list_lights,
    set_light_state,
    set_lights_states,
)


class TestLightFunctions:
    @patch("update_lights.requests.get")
    def test_list_devices(self, mock_get, sample_devices):
        """Test list_devices function"""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [device.model_dump() for device in sample_devices]
        }
        mock_get.return_value = mock_response

        # Call function
        devices = list_devices()

        # Verify
        mock_get.assert_called_once()
        assert len(devices) == len(sample_devices)
        assert all(isinstance(device, Device) for device in devices)
        assert devices[0].id == sample_devices[0].id

    @patch("update_lights.list_devices")
    def test_list_lights(self, mock_list_devices, sample_devices):
        """Test list_lights function"""
        # Mock list_devices to return our sample devices
        mock_list_devices.return_value = sample_devices

        # Call function
        lights = list_lights()

        # Verify
        assert len(lights) == len(sample_devices)  # All sample devices are lights
        assert all(device.is_light for device in lights)

    def test_create_light_state(self, sample_drivers):
        """Test create_light_state function"""
        driver = sample_drivers[0]  # Max Verstappen

        # Call function
        light_state = create_light_state(driver)

        # Verify
        assert isinstance(light_state, LightState)
        assert light_state.on.on is True  # Default power is on
        assert light_state.dimming.brightness == 100  # Default brightness is 100%
        assert light_state.color.xy.x == driver.xy_colour.xyy_x
        assert light_state.color.xy.y == driver.xy_colour.xyy_y

    @pytest.mark.asyncio
    @patch("update_lights.HUE_BRIDGE_IP", "192.168.1.165")
    @patch("update_lights.HUE_USERNAME", "testuser")
    async def test_set_light_state(self):
        """Test set_light_state function"""
        # Create a device with proper Service objects
        light = Device(
            id="test-device-1",
            product_data={
                "model_id": "LCT007",
                "manufacturer_name": "Signify Netherlands B.V.",
                "product_name": "Hue color lamp",
                "product_archetype": "sultan_bulb",
                "certified": True,
                "software_version": "1.88.1",
            },
            metadata={
                "name": "Test Light",
                "archetype": "sultan_bulb",
            },
            services=[
                Service(rid="test-light-1", rtype="light"),
                Service(rid="test-conn-1", rtype="zigbee_connectivity"),
            ],
            type="device",
        )

        state = LightState(
            on=Power(on=True),
            dimming=Dimming(brightness=75),
            color=Color(xy=XYColor(x=0.3, y=0.6)),
        )

        # Method 1: Using patch to mock the entire aiohttp.ClientSession.put
        mock_response = AsyncMock()
        mock_response.json.return_value = {"success": True}

        # Create a proper session with a mocked put method using patching
        with patch("aiohttp.ClientSession.put") as mock_put:
            # Setup the mock to return our response in the context manager
            mock_put.return_value.__aenter__.return_value = mock_response

            # Call function with a real session (that has mocked put)
            async with aiohttp.ClientSession() as session:
                result = await set_light_state(light, state, session)

            # Verify
            assert result == {"success": True}
            mock_put.assert_called_once()
            # Check that the URL contains our test light ID
            assert "test-light-1" in mock_put.call_args[0][0]

    @pytest.mark.asyncio
    async def test_set_light_state_no_light_service(self):
        """Test set_light_state with a device that has no light service"""
        # Create a device with no light service
        device_no_light = Device(
            id="test-device-2",
            product_data={
                "model_id": "other_device",
                "manufacturer_name": "Signify Netherlands B.V.",
                "product_name": "Non-light device",
                "product_archetype": "other",
                "certified": True,
                "software_version": "1.0.0",
            },
            metadata={
                "name": "Test Non-Light",
                "archetype": "other",
            },
            services=[
                Service(rid="test-other-1", rtype="other_service"),
            ],
            type="device",
        )

        state = LightState(
            on=Power(on=True),
            dimming=Dimming(brightness=75),
            color=Color(xy=XYColor(x=0.3, y=0.6)),
        )

        # Create a mock session
        mock_session = AsyncMock()

        # Call function with mocked session
        result = await set_light_state(device_no_light, state, mock_session)

        # Verify
        assert result is None  # Should return None for non-light devices
        mock_session.put.assert_not_called()

    @pytest.mark.asyncio
    @patch("update_lights.set_light_state")
    async def test_set_lights_states(self, mock_set_light_state, sample_devices):
        """Test set_lights_states function"""
        lights = sample_devices
        state = LightState(
            on=Power(on=True),
            dimming=Dimming(brightness=75),
            color=Color(xy=XYColor(x=0.3, y=0.6)),
        )

        # Mock set_light_state to return success
        mock_set_light_state.return_value = {"success": True}

        # Call function
        await set_lights_states(lights, state)

        # Verify
        assert mock_set_light_state.call_count == len(lights)
        # Each light should have been updated with the same state
        for call_args in mock_set_light_state.call_args_list:
            assert call_args[0][1] is state
