import asyncio
import json
import signal
from typing import List

from loguru import logger
from pydantic import TypeAdapter

from models import Driver, Message, Topic
from record import process_live_timing


class F1DataProcessor:
    """Example processor for F1 live timing data"""

    def __init__(self):
        self.leaders: List[Driver] = []
        self.messages_processed = 0
        self.drivers = TypeAdapter(list[Driver]).validate_python(
            json.loads(open("drivers.json").read())
        )
        self.driver_lookup: dict[str, Driver] = {
            str(driver.driver_number): driver for driver in self.drivers
        }

    async def process_message(self, message: Message):
        """Process a message asynchronously from the F1 timing data stream"""
        self.messages_processed += 1

        # Log debug message every 1000 messages to show progress
        if self.messages_processed % 1000 == 0:
            logger.debug(f"Processed {self.messages_processed} messages so far...")

        # Process leader information from TimingAppData
        if (
            message.topic == Topic.TimingAppData
            and isinstance(message.content, dict)
            and message.content.get("Lines")
        ):
            # Loop through all cars in this update
            for car_number, car_data in message.content["Lines"].items():
                # Check if this car has Line position 1 (the leader)
                if car_data.get("Line") == 1:
                    # Create and store the leader information
                    leader = self.driver_lookup.get(car_number)

                    # Only add if it's a different leader than last recorded
                    if (
                        not self.leaders
                        or self.leaders[-1].driver_number != leader.driver_number
                    ):
                        self.leaders.append(leader)
                        logger.info(
                            f"New leader at {message.timestamp}: {leader.full_name}"
                        )
                    break


async def main():
    # Create the data processor
    processor = F1DataProcessor()

    # Start processing data
    logger.info("Starting F1 live timing data processing")

    # Setup a way to handle cancellation
    stop_event = asyncio.Event()

    # Handle signals for graceful shutdown
    loop = asyncio.get_running_loop()

    def signal_handler():
        logger.info("Shutdown signal received")
        stop_event.set()

    # Register signal handlers
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    try:
        # Process messages without saving to file
        await process_live_timing(
            output=None,  # No file output
            timeout=1800,
            message_processor=processor.process_message,
            logger_instance=logger,
        )
    except asyncio.CancelledError:
        logger.info("Main task was cancelled")
    except Exception as e:
        logger.error(f"Error during processing: {e}")

    # Display summary of processed data
    logger.info(f"Processed {processor.messages_processed} total messages")
    logger.info(f"Tracked {len(processor.leaders)} leader changes")


if __name__ == "__main__":
    # Run the async application
    asyncio.run(main())
