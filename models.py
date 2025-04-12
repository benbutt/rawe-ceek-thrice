import ast
from datetime import datetime
from enum import Enum
from typing import Annotated, Union

from pydantic import AfterValidator, BaseModel, TypeAdapter
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


class Message(BaseModel):
    topic: str
    content: Union[str, dict]
    timestamp: datetime

    @classmethod
    def from_line(cls, line: str) -> Self:
        topic, content, timestamp = ast.literal_eval(line)
        return cls(topic=topic, content=content, timestamp=timestamp)


class Driver(BaseModel):
    broadcast_name: str
    full_name: Annotated[str, AfterValidator(lambda x: x.title())]
    driver_number: int
    team_colour: str
    team_name: str


driver_adapter = TypeAdapter(list[Driver])
