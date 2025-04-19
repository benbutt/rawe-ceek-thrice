import asyncio
import json
import signal
import time
from contextlib import AsyncExitStack
from typing import Dict, List, Optional, Tuple

from loguru import logger
from pydantic import TypeAdapter

from config import TV_DELAY_SECONDS
from models import Driver, Message, TimingAppContent, TimingCarData, Topic
from record import RaweCeekClient
from update_lights import create_light_state, list_lights, set_lights_states
from utils import TaskManager, run_with_errorhandling


class F1DataProcessor:
    """Example processor for F1 live timing data"""

    def __init__(self, tv_delay_seconds: int = TV_DELAY_SECONDS):
        self.leaders: List[Driver] = []
        self.messages_processed = 0
        # TODO: Get this via API call
        # Use https://openf1.org/#drivers
        self.drivers = TypeAdapter(list[Driver]).validate_python(
            json.loads(open("drivers.json").read())
        )
        self.driver_lookup: Dict[str, Driver] = {
            str(driver.driver_number): driver for driver in self.drivers
        }
        self.lights = list_lights()

        # TV broadcast delay settings
        self.tv_delay_seconds = tv_delay_seconds
        self.pending_light_updates: List[Tuple[float, Driver]] = []

    @property
    def updater(self) -> TaskManager:
        """Get a TaskManager for the delayed light updater.

        Returns:
            A TaskManager that can be used with async with
        """
        return TaskManager(self.delayed_light_updater, name="LightUpdater", timeout=1.0)

    async def delayed_light_updater(self):
        while True:
            await self._process_due_updates()
            await asyncio.sleep(0.1)

    async def _process_due_updates(self):
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
            await run_with_errorhandling(
                set_lights_states(self.lights, create_light_state(most_recent_driver)),
                f"Failed to update lights for {most_recent_driver.full_name}",
            )
            logger.info(
                f"New leader: {most_recent_driver.full_name} for "
                f"{most_recent_driver.team_name}"
            )

            # Remove all processed updates
            indices_to_remove = [i for i, _ in updates_to_process]
            remove_set = set(indices_to_remove)
            self.pending_light_updates = [
                update
                for i, update in enumerate(self.pending_light_updates)
                if i not in remove_set
            ]

    def _extract_leader_from_timing_data(
        self, data: Dict[str, TimingCarData]
    ) -> Optional[str]:
        """Extract the car number of the current leader from timing data.

        Args:
            data: The Lines dictionary from TimingAppData

        Returns:
            The car number of the leader or None if not found
        """
        for car_number, car_data in data.items():
            if car_data.Line == 1:
                return car_number
        return None

    def _schedule_light_update(self, leader: Driver) -> None:
        """Schedule a light update for the given leader.

        Args:
            leader: The driver who is now the leader
        """
        current_time = time.time()
        scheduled_time = current_time + self.tv_delay_seconds
        self.pending_light_updates.append((scheduled_time, leader))
        logger.debug(
            f"Scheduled light update for {leader.full_name} in {self.tv_delay_seconds} seconds"
        )

    async def process_message(self, message: Message):
        """Process a message asynchronously from the F1 timing data stream"""
        self.messages_processed += 1

        # Log debug message every 1000 messages to show progress
        if self.messages_processed % 1000 == 0:
            logger.debug(f"Processed {self.messages_processed} messages so far...")

        # Only process TimingAppData messages
        if message.topic != Topic.TimingAppData:
            return

        # Ensure content is the expected format
        if not isinstance(message.content, dict) or "Lines" not in message.content:
            return

        # Parse the content as a TimingAppContent model
        try:
            timing_content = TimingAppContent.model_validate(message.content)
        except Exception as e:
            logger.warning(f"Failed to parse timing content: {e}")
            return

        # Extract the car number of the current leader
        leader_car_number = self._extract_leader_from_timing_data(timing_content.Lines)
        if not leader_car_number:
            return

        # Look up the driver information
        leader = self.driver_lookup.get(leader_car_number)
        if not leader:
            return

        # Check if this is a new leader
        is_new_leader = (
            not self.leaders or self.leaders[-1].driver_number != leader.driver_number
        )
        if is_new_leader:
            self.leaders.append(leader)
            logger.debug(f"New leader at {message.timestamp}: {leader.full_name}")
            self._schedule_light_update(leader)

    async def create_timing_client(self) -> RaweCeekClient:
        """Create and configure F1 timing client for data processing"""
        # Return a RaweCeekClient configured for our needs
        return RaweCeekClient(
            filename=None,  # No file output
            timeout=1800,
            message_processor=self.process_message,
            logger_instance=logger,
        )


async def main():
    # Create the data processor
    processor = F1DataProcessor()
    logger.info("Starting F1 live timing data processing")

    # Exit stack for managing multiple context managers
    async with AsyncExitStack() as exit_stack:
        # Start the delayed light updater using the property-based approach
        await exit_stack.enter_async_context(processor.updater)
        logger.debug("Started delayed light updater")

        # Setup signal handling for clean shutdown
        shutdown_requested = asyncio.Event()
        loop = asyncio.get_running_loop()

        async def handle_signal():
            logger.info("Shutdown signal received")
            shutdown_requested.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(handle_signal()))

        # Start the live timing processor
        client = await processor.create_timing_client()
        client_task = TaskManager(client.run, name="LiveTimingClient", timeout=2.0)
        await exit_stack.enter_async_context(client_task)

        # Wait for shutdown signal
        await shutdown_requested.wait()

    # Context managers have been exited, tasks cleaned up

    # Display summary of processed data
    logger.info(f"Processed {processor.messages_processed} total messages")
    logger.info(f"Tracked {len(processor.leaders)} leader changes")


if __name__ == "__main__":
    # Run the async application
    asyncio.run(main())
