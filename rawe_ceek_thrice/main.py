import asyncio
import signal
from contextlib import AsyncExitStack

from loguru import logger

from rawe_ceek_thrice.core.utils import TaskManager
from rawe_ceek_thrice.data.processor import F1DataProcessor


async def main():
    # Create the data processor
    processor = F1DataProcessor()
    logger.info("Starting F1 live timing data processing")

    # Exit stack for managing multiple context managers
    async with AsyncExitStack() as exit_stack:
        # Start the delayed light updater using the property-based approach
        await exit_stack.enter_async_context(processor.updater)
        logger.debug("Started delayed light updater")

        # Start the connection health monitor
        await exit_stack.enter_async_context(processor.connection_monitor)
        logger.debug("Started connection health monitor")

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
    logger.info(f"Final connection state: {processor.connection_state.value}")


if __name__ == "__main__":
    # Run the async application
    asyncio.run(main())
