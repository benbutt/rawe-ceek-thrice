import asyncio
import json
import signal
import time
from typing import List, Tuple

from loguru import logger
from pydantic import TypeAdapter

from models import Driver, Message, Topic
from record import process_live_timing
from update_lights import create_light_state, list_lights, set_lights_states


class F1DataProcessor:
    """Example processor for F1 live timing data"""

    def __init__(self, tv_delay_seconds: int = 57):
        self.leaders: List[Driver] = []
        self.messages_processed = 0
        self.drivers = TypeAdapter(list[Driver]).validate_python(
            json.loads(open("drivers.json").read())
        )
        self.driver_lookup: dict[str, Driver] = {
            str(driver.driver_number): driver for driver in self.drivers
        }
        self.lights = list_lights()

        # TV broadcast delay settings
        self.tv_delay_seconds = tv_delay_seconds
        self.pending_light_updates: List[Tuple[float, Driver]] = []
        self.update_task = None

    async def delayed_light_updater(self):
        """Process delayed light updates to sync with TV broadcast"""
        while True:
            current_time = time.time()
            updates_to_process = []

            # Find all updates that are due to be processed
            for i, (scheduled_time, driver) in enumerate(self.pending_light_updates):
                if current_time >= scheduled_time:
                    updates_to_process.append((i, driver))

            # Process updates (from newest to oldest to avoid multiple updates)
            if updates_to_process:
                # Get the most recent update (we only need the latest leader)
                _, most_recent_driver = updates_to_process[-1]

                # Update the lights
                await set_lights_states(
                    self.lights, create_light_state(most_recent_driver)
                )
                logger.info(
                    f"New leader: {most_recent_driver.full_name} for "
                    f"{most_recent_driver.team_name}"
                )

                # Remove all processed updates
                indices_to_remove = [i for i, _ in updates_to_process]
                self.pending_light_updates = [
                    update
                    for i, update in enumerate(self.pending_light_updates)
                    if i not in indices_to_remove
                ]

            # Sleep a short time before checking again
            await asyncio.sleep(0.1)

    async def start_delayed_updater(self):
        """Start the delayed light updater task"""
        self.update_task = asyncio.create_task(self.delayed_light_updater())
        return self.update_task

    async def stop_delayed_updater(self):
        """Stop the delayed light updater task"""
        if self.update_task and not self.update_task.done():
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                logger.debug("Delayed updater task cancelled successfully")
            except Exception as e:
                logger.error(f"Error during updater task cancellation: {e}")
            # Don't re-raise, just log the error
        self.update_task = None

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
                    if not leader:
                        continue

                    # Only add if it's a different leader than last recorded
                    if (
                        not self.leaders
                        or self.leaders[-1].driver_number != leader.driver_number
                    ):
                        self.leaders.append(leader)
                        logger.debug(
                            f"New leader at {message.timestamp}: {leader.full_name}"
                        )

                        # Schedule light update with delay
                        current_time = time.time()
                        scheduled_time = current_time + self.tv_delay_seconds
                        self.pending_light_updates.append((scheduled_time, leader))
                        logger.debug(
                            f"Scheduled light update for {leader.full_name} in {self.tv_delay_seconds} seconds"
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

    async def signal_handler():
        logger.info("Shutdown signal received")
        stop_event.set()
        # Stop the delayed updater task first
        await processor.stop_delayed_updater()

    # Register signal handlers for async handling
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(signal_handler()))

    try:
        # Start the delayed light updater
        await processor.start_delayed_updater()

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
    finally:
        # Make sure to stop the updater task if it hasn't been stopped already
        if processor.update_task and not processor.update_task.done():
            await processor.stop_delayed_updater()

    # Display summary of processed data
    logger.info(f"Processed {processor.messages_processed} total messages")
    logger.info(f"Tracked {len(processor.leaders)} leader changes")


if __name__ == "__main__":
    # Run the async application
    asyncio.run(main())
