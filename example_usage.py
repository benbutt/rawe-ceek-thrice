import asyncio
import signal
from typing import List

from loguru import logger
from models import Message, Topic, Leader
from record import process_live_timing


class F1DataProcessor:
    """Example processor for F1 live timing data"""

    def __init__(self):
        self.leaders: List[Leader] = []
        self.messages_processed = 0

    async def process_message(self, message: Message):
        """Process a message asynchronously from the F1 timing data stream"""
        self.messages_processed += 1

        # Process leader information from TopThree topic
        if (
            message.topic == Topic.TopThree
            and isinstance(message.content, dict)
            and message.content.get("Lines")
            and "0" in message.content["Lines"]
            and message.content["Lines"]["0"].get("TeamColour")
        ):
            # Extract leader info
            leader = Leader(
                full_name=message.content["Lines"]["0"].get("FullName", ""),
                team_color=message.content["Lines"]["0"].get("TeamColour", ""),
                timestamp=message.timestamp,
            )

            self.leaders.append(leader)
            logger.info(f"New leader: {leader.full_name} ({leader.team_color})")


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
            timeout=120,
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
