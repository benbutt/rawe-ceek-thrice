from functools import cached_property
from typing import List, Optional

from pydantic import BaseModel


class Service(BaseModel):
    """
    Represents a service offered by a Philips Hue device.

    Each service has a unique resource identifier and a type that defines
    its functionality within the Hue ecosystem.
    """

    rid: str
    rtype: str


class ProductData(BaseModel):
    """
    Contains detailed product information for a Philips Hue device.

    Includes manufacturer details, model information, and software/hardware
    versioning data.
    """

    model_id: str
    manufacturer_name: str
    product_name: str
    product_archetype: str
    certified: bool
    software_version: str
    hardware_platform_type: Optional[str] = None


class Metadata(BaseModel):
    """
    Metadata associated with a Philips Hue device.

    Contains user-facing information like device name and archetype.
    """

    name: str
    archetype: str


class Device(BaseModel):
    """
    Represents a Philips Hue device with all associated data.

    Contains comprehensive information about a device including its
    identification, capabilities, and available services.
    """

    id: str
    id_v1: Optional[str] = None
    product_data: ProductData
    metadata: Metadata
    identify: dict = {}
    services: List[Service]
    type: str

    @cached_property
    def is_light(self) -> bool:
        """
        Determine if this device is a light by checking its services.

        Returns:
            bool: True if the device has a light service, False otherwise
        """
        return any(service.rtype == "light" for service in self.services)


class Dimming(BaseModel):
    """
    Controls the brightness setting for a light.

    Defines the intensity of the light output as a percentage.
    """

    brightness: float = 100


class XYColor(BaseModel):
    """
    Represents a color in the CIE XY color space used by Philips Hue.

    Contains x and y coordinates in the CIE 1931 color space.
    """

    x: float
    y: float


class Power(BaseModel):
    """
    Represents the power state of a light.

    Controls whether the light is turned on or off.
    """

    on: bool = True


class Color(BaseModel):
    """
    Defines the color properties of a light.

    Contains the xy color space representation for Philips Hue lights.
    """

    xy: XYColor


class LightState(BaseModel):
    """
    Represents the complete state of a Philips Hue light.

    Combines power, brightness, and color settings into a single state
    that can be applied to a light.
    """

    on: Power
    dimming: Dimming
    color: Color
