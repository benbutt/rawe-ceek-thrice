import os
from typing import Any, Dict, List

import aiohttp
import requests
import urllib3
from dotenv import load_dotenv
from loguru import logger
from pydantic import TypeAdapter

import light_models as models
from models import Driver

env = load_dotenv()
HUE_USERNAME = os.getenv("HUE_USERNAME")
HUE_CLIENT_KEY = os.getenv("HUE_CLIENT_KEY")
HUE_BRIDGE_IP = os.getenv("HUE_BRIDGE_IP")

# Disable insecure request warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

devices_adapter = TypeAdapter(list[models.Device])


def list_devices() -> List[models.Device]:
    """Fetch all devices from the Hue Bridge.

    Returns:
        List[models.Device]: List of all devices connected to the Hue Bridge
    """
    response = requests.get(
        f"https://{HUE_BRIDGE_IP}/clip/v2/resource/device",
        headers={"hue-application-key": HUE_USERNAME},
        verify=False,
    )
    return devices_adapter.validate_python(response.json()["data"])


def list_lights() -> List[models.Device]:
    """Fetch all light devices from the Hue Bridge.

    Returns:
        List[models.Device]: List of light devices connected to the Hue Bridge
    """
    lights = [device for device in list_devices() if device.is_light]
    logger.info(f"Found {len(lights)} Hue lights")
    return lights


def create_light_state(driver: Driver) -> models.LightState:
    return models.LightState(
        on=models.Power(),
        dimming=models.Dimming(),
        color=models.Color(
            xy=models.XYColor(
                x=driver.xy_colour.xyy_x,
                y=driver.xy_colour.xyy_y,
            )
        ),
    )


async def set_light_state(
    light: models.Device, state: models.LightState
) -> Dict[str, Any]:
    """Set the state of a single light device.

    Args:
        light: The light device to update
        state: The state to apply to the light

    Returns:
        Dict[str, Any]: Response from the Hue API
    """
    for service in light.services:
        if service.rtype == "light":
            id = service.rid

    async with aiohttp.ClientSession() as session:
        async with session.put(
            f"https://{HUE_BRIDGE_IP}/clip/v2/resource/light/{id}",
            headers={"hue-application-key": HUE_USERNAME},
            json=state.model_dump(),
            ssl=False,
        ) as response:
            return await response.json()


async def set_lights_states(
    lights: List[models.Device], state: models.LightState
) -> None:
    """Set the state of multiple light devices to the same value.

    Args:
        lights: List of light devices to update
        state: The state to apply to all lights
    """
    for light in lights:
        await set_light_state(light, state)
