import sys
from pathlib import Path

# Add the parent directory to sys.path so we can import the project modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from colormath.color_objects import xyYColor

from models import Device, Driver, Message, TimingAppContent, TimingCarData, Topic


class TestModels:
    def test_topic_enum(self):
        """Test that Topic enum contains expected values"""
        assert Topic.TimingAppData == "TimingAppData"
        assert Topic.CarData_z == "CarData.z"
        assert Topic.TrackStatus == "TrackStatus"

    def test_timing_car_data(self):
        """Test TimingCarData model validation"""
        # Test valid data
        data = {"Line": 1, "Position": 1, "GapToLeader": "", "LapTime": "1:32.123"}
        car_data = TimingCarData(**data)
        assert car_data.Line == 1
        assert car_data.Position == 1
        assert car_data.GapToLeader == ""
        assert car_data.LapTime == "1:32.123"
        assert car_data.Sectors == {}

        # Test with missing optional fields
        partial_data = {"Position": 1}
        car_data = TimingCarData(**partial_data)
        assert car_data.Line is None
        assert car_data.Position == 1
        assert car_data.GapToLeader is None
        assert car_data.LapTime is None

    def test_timing_app_content(self):
        """Test TimingAppContent model validation"""
        data = {
            "Lines": {
                "1": {
                    "Line": 1,
                    "Position": 1,
                    "GapToLeader": "",
                    "LapTime": "1:32.123",
                },
                "44": {
                    "Line": 2,
                    "Position": 2,
                    "GapToLeader": "+2.345",
                    "LapTime": "1:32.456",
                },
            }
        }
        content = TimingAppContent(**data)
        assert len(content.Lines) == 2
        assert content.Lines["1"].Line == 1
        assert content.Lines["44"].Line == 2

    def test_message(self):
        """Test Message model validation"""
        # Test with string content
        message = Message(
            topic=Topic.Heartbeat, content="ping", timestamp="2023-04-01T12:34:56.789Z"
        )
        assert message.topic == Topic.Heartbeat
        assert message.content == "ping"

        # Test with dict content
        timing_data = {
            "Lines": {
                "1": {
                    "Line": 1,
                    "Position": 1,
                    "GapToLeader": "",
                    "LapTime": "1:32.123",
                },
            }
        }
        message = Message(
            topic=Topic.TimingAppData,
            content=timing_data,
            timestamp="2023-04-01T12:34:56.789Z",
        )
        assert message.topic == Topic.TimingAppData
        assert isinstance(message.content, dict)
        assert "Lines" in message.content

    def test_driver(self):
        """Test Driver model validation and computed fields"""
        driver = Driver(
            broadcast_name="VER",
            full_name="max verstappen",  # Should be automatically capitalized
            driver_number=1,
            team_colour="#0600EF",  # Red Bull blue
            team_name="Red Bull Racing",
        )
        assert driver.broadcast_name == "VER"
        assert driver.full_name == "Max Verstappen"  # Title case via validator
        assert driver.driver_number == 1
        assert driver.team_name == "Red Bull Racing"

        # Check that xy_colour is computed correctly
        assert hasattr(driver.xy_colour, "xyy_x")
        assert hasattr(driver.xy_colour, "xyy_y")
        assert isinstance(driver.xy_colour, xyYColor)

    def test_device(self):
        """Test Device model with is_light property"""
        # Device with light service
        device_with_light = Device(
            id="test-id-1",
            product_data={
                "model_id": "LCT007",
                "manufacturer_name": "Signify Netherlands B.V.",
                "product_name": "Hue color lamp",
                "product_archetype": "sultan_bulb",
                "certified": True,
                "software_version": "1.88.1",
            },
            metadata={
                "name": "Living Room Light",
                "archetype": "sultan_bulb",
            },
            services=[
                {"rid": "12345", "rtype": "light"},
                {"rid": "67890", "rtype": "zigbee_connectivity"},
            ],
            type="device",
        )
        assert device_with_light.is_light is True

        # Device without light service
        device_without_light = Device(
            id="test-id-2",
            product_data={
                "model_id": "BSB002",
                "manufacturer_name": "Signify Netherlands B.V.",
                "product_name": "Hue bridge",
                "product_archetype": "bridge_v2",
                "certified": True,
                "software_version": "1.88.1",
            },
            metadata={
                "name": "Hue Bridge",
                "archetype": "bridge_v2",
            },
            services=[
                {"rid": "12345", "rtype": "bridge"},
                {"rid": "67890", "rtype": "zigbee_connectivity"},
            ],
            type="device",
        )
        assert device_without_light.is_light is False
