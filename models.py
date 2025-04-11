from typing import Annotated
from datetime import datetime
from typing_extensions import Self
from typing import Union
from enum import Enum
import ast

from pydantic import BaseModel, AfterValidator


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


class Leader(BaseModel):
    full_name: Annotated[str, AfterValidator(lambda x: x.title())]
    team_color: str
    timestamp: datetime
