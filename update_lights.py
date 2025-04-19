import asyncio
from typing import Any, Dict, List

import aiohttp
import requests
import urllib3
from loguru import logger
from pydantic import TypeAdapter

from config import HUE_BRIDGE_IP, HUE_USERNAME
from models import Color, Device, Dimming, Driver, LightState, Power, XYColor

# Disable insecure request warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

devices_adapter = TypeAdapter(list[Device])


def list_devices() -> List[Device]:
    """Fetch all devices from the Hue Bridge.

    Returns:
        List[Device]: List of all devices connected to the Hue Bridge
    """
    response = requests.get(
        f"https://{HUE_BRIDGE_IP}/clip/v2/resource/device",
        headers={"hue-application-key": HUE_USERNAME},
        verify=False,
    )
    return devices_adapter.validate_python(response.json()["data"])


def list_lights() -> List[Device]:
    """Fetch all light devices from the Hue Bridge.

    Returns:
        List[Device]: List of light devices connected to the Hue Bridge
    """
    lights = [device for device in list_devices() if device.is_light]
    logger.info(f"Found {len(lights)} Hue lights")
    return lights


def create_light_state(driver: Driver) -> LightState:
    return LightState(
        on=Power(),
        dimming=Dimming(),
        color=Color(
            xy=XYColor(
                x=driver.xy_colour.xyy_x,
                y=driver.xy_colour.xyy_y,
            )
        ),
    )


async def set_light_state(
    light: Device, state: LightState, session: aiohttp.ClientSession = None
) -> Dict[str, Any]:
    """Set the state of a single light device.

    Args:
        light: The light device to update
        state: The state to apply to the light
        session: Optional aiohttp session to reuse

    Returns:
        Dict[str, Any]: Response from the Hue API
    """
    # Find the light service ID
    light_id = None
    for service in light.services:
        if service.rtype == "light":
            light_id = service.rid
            break

    if not light_id:
        logger.warning(f"No light service found for device {light.metadata.name}")
        return None

    # Create a session if one wasn't provided
    should_close_session = False
    if session is None:
        session = aiohttp.ClientSession()
        should_close_session = True

    try:
        async with session.put(
            f"https://{HUE_BRIDGE_IP}/clip/v2/resource/light/{light_id}",
            headers={"hue-application-key": HUE_USERNAME},
            json=state.model_dump(),
            ssl=False,
        ) as response:
            return await response.json()
    finally:
        # Only close the session if we created it in this function
        if should_close_session:
            await session.close()


async def set_lights_states(lights: List[Device], state: LightState) -> None:
    """Set the state of multiple light devices to the same value in parallel.

    Args:
        lights: List of light devices to update
        state: The state to apply to all lights
    """
    if not lights:
        return

    # Use a single shared session for all requests
    async with aiohttp.ClientSession() as session:
        # Create a list of coroutines for all light updates
        update_tasks = [set_light_state(light, state, session) for light in lights]

        # Run all updates concurrently
        await asyncio.gather(*update_tasks)

    logger.debug(f"Updated {len(lights)} lights in parallel")
