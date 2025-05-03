import ast
from datetime import datetime
from enum import Enum
from functools import cached_property
from typing import Annotated, Any, Dict, List, Optional, Union

from colormath import color_conversions, color_objects
from pydantic import AfterValidator, BaseModel, TypeAdapter, computed_field
from pydantic_extra_types.color import Color
from typing_extensions import Self


class Topic(str, Enum):
    TimingAppData = "TimingAppData"
    CarData_z = "CarData.z"
    Position_z = "Position.z"
    WeatherData = "WeatherData"
    Heartbeat = "Heartbeat"
    TopThree = "TopThree"
    LapCount = "LapCount"
    DriverList = "DriverList"
    TimingData = "TimingData"
    RaceControlMessages = "RaceControlMessages"
    SessionData = "SessionData"
    TimingStats = "TimingStats"
    ExtrapolatedClock = "ExtrapolatedClock"
    RcmSeries = "RcmSeries"
    TrackStatus = "TrackStatus"
    SessionInfo = "SessionInfo"


class TimingCarData(BaseModel):
    """Type definition for car data in timing messages"""

    Line: Optional[int] = None
    Position: Optional[int] = None
    GapToLeader: Optional[str] = None
    LapTime: Optional[str] = None
    Sectors: Dict[str, Any] = {}


class TimingAppContent(BaseModel):
    """Type definition for TimingAppData message content"""

    Lines: Dict[str, TimingCarData]


class Message(BaseModel):
    topic: Topic
    content: Union[str, Dict[str, Any]]
    timestamp: datetime

    @classmethod
    def from_line(cls, line: str) -> Self:
        topic, content, timestamp = ast.literal_eval(line)
        return cls(topic=topic, content=content, timestamp=timestamp)


class Driver(BaseModel):
    broadcast_name: str
    full_name: Annotated[str, AfterValidator(lambda x: x.title())]
    driver_number: int
    team_colour: Color
    team_name: str

    @computed_field
    def xy_colour(self) -> str:
        xy = color_conversions.convert_color(
            color_objects.sRGBColor(*self.team_colour.as_rgb_tuple()),
            color_objects.xyYColor,
        )
        return xy


driver_adapter = TypeAdapter(list[Driver])


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


class IdentifyData(BaseModel):
    """Type for the identify field in Device model"""

    action_values: Optional[List[str]] = None
    actions: Optional[List[str]] = None


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
    identify: IdentifyData = IdentifyData()
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
