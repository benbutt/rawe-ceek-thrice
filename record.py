import asyncio
import datetime
import os
import signal
import tempfile
from logging import Logger
from tempfile import NamedTemporaryFile
from typing import Awaitable, Callable, List, Optional

from fastf1.livetiming import client
from loguru import logger

from models import Message


class RaweCeekClient(client.SignalRClient):
    def __init__(
        self,
        filename: str = None,
        filemode: str = "w",
        debug: bool = False,
        timeout: int = 60,
        message_processor: Optional[Callable[[Message], Awaitable[None]]] = None,
        logger_instance: Optional[Logger] = None,
    ):
        """
        Enhanced SignalRClient that can process messages using the Message model.

        Args:
            filename: Optional filename to write raw data
            filemode: One of 'w' or 'a' for file writing mode
            debug: When true, complete SignalR message is saved
            timeout: Seconds after which client exits when no message is received
            message_processor: Async callback function that accepts a Message object
            logger_instance: Optional logger instance
        """
        self.message_processor = message_processor
        self.shutdown_event = asyncio.Event()
        self.log = logger_instance or logger
        self._temp_file: Optional[NamedTemporaryFile] = None
        self._tasks: List[asyncio.Task] = []

        # Create a temporary file if no filename provided
        if not filename:
            self._temp_file = tempfile.NamedTemporaryFile(
                mode=filemode, delete=False, suffix=".txt", prefix="f1_timing_"
            )
            filename = self._temp_file.name
            self.log.debug(f"Created temporary file: {filename}")

        super().__init__(
            filename=filename,
            filemode=filemode,
            debug=debug,
            timeout=timeout,
            logger=logger_instance,
        )

    async def _on_message(self, msg):
        """Override the message handler to process with our model"""
        if self.shutdown_event.is_set():
            return

        self._t_last_message = datetime.datetime.now().timestamp()

        try:
            # Extract the topic and content from the message
            topic_str = msg[0] if isinstance(msg, list) and len(msg) > 0 else ""
            content = msg[1] if isinstance(msg, list) and len(msg) > 1 else msg

            # Create a Message object using our model
            message = Message(
                topic=topic_str, content=content, timestamp=datetime.datetime.now()
            )

            # Process the message if we have a processor
            if self.message_processor:
                await self.message_processor(message)

            # Still write to file if a filename was provided
            if hasattr(self, "_output_file") and self._output_file:
                await super()._on_message(msg)

        except Exception as e:
            self.log.exception(f"Exception while processing message: {e}")

    async def _async_start(self):
        """Override to track tasks for clean cancellation"""
        self.log.info("Starting RaweCeek live timing client")

        # Create the tasks and track them for later cancellation
        supervise_task = asyncio.create_task(self._supervise())
        run_task = asyncio.create_task(self._run())

        self._tasks = [supervise_task, run_task]

        # Wait for both tasks to complete
        await asyncio.gather(*self._tasks)

        # Close the output file if it's still open
        if hasattr(self, "_output_file") and self._output_file:
            self._output_file.close()

    async def async_start(self):
        """
        Connect to the data stream and start processing messages.
        Overridden to handle task cancellation gracefully.
        """
        try:
            await self._async_start()
        except asyncio.CancelledError:
            # Suppress the warning from parent class
            pass

    async def shutdown(self):
        """Gracefully shutdown the client"""
        self.log.info("Shutting down RaweCeekClient...")
        self.shutdown_event.set()

        # Cancel all tracked tasks that are still running
        pending_tasks = [task for task in self._tasks if not task.done()]

        for task in pending_tasks:
            task.cancel()

        if pending_tasks:
            try:
                await asyncio.wait(pending_tasks, timeout=1.0)
            except asyncio.CancelledError:
                pass

        # Close the connection
        if hasattr(self, "_connection") and self._connection:
            self.log.debug("Closing SignalR connection...")
            self._connection.close()

        # Close the output file if it's still open
        if hasattr(self, "_output_file") and self._output_file:
            self.log.debug("Closing output file...")
            self._output_file.close()

        # Clean up temporary file if we created one
        if self._temp_file:
            try:
                self.log.debug(f"Removing temporary file: {self._temp_file.name}")
                os.unlink(self._temp_file.name)
            except Exception as e:
                self.log.warning(f"Failed to remove temporary file: {e}")

        self.log.info("Shutdown complete")


async def process_live_timing(
    output: Optional[str] = None,
    append: bool = False,
    debug: bool = False,
    timeout: int = 60,
    message_processor: Optional[Callable[[Message], Awaitable[None]]] = None,
    logger_instance: Optional[Logger] = None,
) -> int:
    """
    Asynchronously process live timing data with a callback function and/or save it to a file.

    Args:
        output: Optional path to save raw data
        append: Whether to append to existing file
        debug: Whether to record debug info
        timeout: Timeout in seconds
        message_processor: Async callback function to process messages
        logger_instance: Optional logger instance for logging
    """
    # Use provided logger or default
    log = logger_instance or logger

    # Create directory if output is specified
    if output:
        os.makedirs(os.path.dirname(output), exist_ok=True)

    # Set file mode
    mode = "a" if append else "w"

    # Create the client
    action = "saving to file" if output else "processing"
    log.info(f"Starting live timing client, {action}")
    log.info(
        "Note: Default FastF1 client records all topics (topics parameter is ignored)"
    )

    # Create our enhanced client
    client = RaweCeekClient(
        filename=output,
        filemode=mode,
        debug=debug,
        timeout=timeout,
        message_processor=message_processor,
        logger_instance=logger_instance,
    )

    # Setup signal handling for graceful shutdown
    loop = asyncio.get_running_loop()
    shutdown_complete = loop.create_future()

    async def handle_shutdown():
        log.info("Received signal, shutting down...")
        await client.shutdown()
        shutdown_complete.set_result(True)

    # Register signal handlers for graceful shutdown
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(handle_shutdown()))

    try:
        # Start the client asynchronously
        log.info("Connected to F1 live timing. Press Ctrl+C to stop.")

        # Run until shutdown is triggered
        client_task = asyncio.create_task(client.async_start())

        # Wait for either client task to complete or shutdown signal
        done, _ = await asyncio.wait(
            [client_task, shutdown_complete], return_when=asyncio.FIRST_COMPLETED
        )

        # If client task completed normally (not by shutdown)
        if client_task in done and not shutdown_complete.done():
            # Check for exceptions
            try:
                await client_task
            except Exception as e:
                log.error(f"Client task ended with error: {e}")
                await client.shutdown()
                return 1

            # If we got here without shutdown being triggered, do it now
            log.info("Client task completed normally, shutting down...")
            await client.shutdown()

        return 0

    except asyncio.CancelledError:
        # Handle task cancellation gracefully
        log.info("Process was cancelled, shutting down...")
        await client.shutdown()
        return 0
    except Exception as e:
        log.error(f"Error processing live timing data: {e}")
        await client.shutdown()
        return 1
