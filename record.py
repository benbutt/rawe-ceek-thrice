import asyncio
import datetime
import os
import signal
import tempfile
from logging import Logger
from typing import Awaitable, Callable, Optional

from fastf1.livetiming import client
from loguru import logger

from models import Message
from utils import run_with_errorhandling


class RaweCeekClient(client.SignalRClient):
    def __init__(
        self,
        filename: Optional[str] = None,
        filemode: str = "w",
        debug: bool = False,
        timeout: int = 60,
        message_processor: Optional[Callable[[Message], Awaitable[None]]] = None,
        logger_instance: Optional[Logger] = None,
    ):
        """
        Enhanced SignalRClient that processes messages using the Message model.

        Args:
            filename: Optional filename to write raw data
            filemode: One of 'w' or 'a' for file writing mode
            debug: When true, complete SignalR message is saved
            timeout: Seconds after which client exits when no message is received
            message_processor: Async callback function that accepts a Message object
            logger_instance: Optional logger instance
        """
        self.message_processor = message_processor
        self.log = logger_instance or logger
        self.shutdown_event = asyncio.Event()
        self.client_task = None
        self._temp_file = None
        self.save_to_file = filename is not None

        # FastF1 client requires a filename, create a temporary one if needed
        if filename is None:
            self._temp_file = tempfile.NamedTemporaryFile(
                delete=False, suffix=".txt", prefix="f1_timing_"
            )
            filename = self._temp_file.name
            self.log.debug(f"Created temporary file for internal use: {filename}")

        super().__init__(
            filename=filename,
            filemode=filemode,
            debug=debug,
            timeout=timeout,
            logger=logger_instance,
        )

    async def _on_message(self, msg):
        """Process message with our model and call user-provided processor"""
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

            # Only write to file if explicitly requested with a filename
            if self.save_to_file and self._output_file:
                await super()._on_message(msg)

        except Exception as e:
            self.log.exception(f"Exception while processing message: {e}")

    async def run(self):
        """Connect to the data stream and start processing messages"""
        self.log.info("Starting RaweCeek live timing client")
        try:
            # Create and run the tasks
            supervise_task = asyncio.create_task(self._supervise())
            run_task = asyncio.create_task(self._run())

            # Wait for completion
            await asyncio.gather(supervise_task, run_task)
        except asyncio.CancelledError:
            self.log.info("Client task was cancelled")
        except Exception as e:
            self.log.error(f"Error in client: {e}")
        finally:
            # Close the output file if it's still open
            if hasattr(self, "_output_file") and self._output_file:
                self._output_file.close()

            # Delete temporary file if we created one
            if self._temp_file and not self.save_to_file:
                try:
                    os.unlink(self._temp_file.name)
                    self.log.debug(f"Removed temporary file: {self._temp_file.name}")
                except Exception as e:
                    self.log.warning(f"Failed to remove temporary file: {e}")

    async def shutdown(self):
        """Gracefully shutdown the client"""
        self.log.info("Shutting down RaweCeekClient")
        self.shutdown_event.set()

        # Close the connection
        if hasattr(self, "_connection") and self._connection:
            self._connection.close()


# Simple version for backward compatibility
async def process_live_timing(
    output: Optional[str] = None,
    append: bool = False,
    debug: bool = False,
    timeout: int = 60,
    message_processor: Optional[Callable[[Message], Awaitable[None]]] = None,
    logger_instance: Optional[Logger] = None,
) -> int:
    """
    Asynchronously process live timing data.
    For new code, consider using RaweCeekClient directly with TaskManager.

    Args:
        output: Optional path to save raw data
        append: Whether to append to existing file
        debug: Whether to record debug info
        timeout: Timeout in seconds
        message_processor: Async callback function to process messages
        logger_instance: Optional logger instance for logging

    Returns:
        int: 0 on success, 1 on error
    """
    log = logger_instance or logger

    if output and os.path.dirname(output):
        os.makedirs(os.path.dirname(output), exist_ok=True)

    # Create client
    client = RaweCeekClient(
        filename=output,
        filemode="a" if append else "w",
        debug=debug,
        timeout=timeout,
        message_processor=message_processor,
        logger_instance=logger_instance,
    )

    # Setup signal handling
    shutdown = asyncio.Event()

    def signal_handler():
        shutdown.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    try:
        # Run the client in the background
        client_task = asyncio.create_task(client.run())

        # Wait for either completion or shutdown
        done, _ = await asyncio.wait(
            [client_task, shutdown.wait()], return_when=asyncio.FIRST_COMPLETED
        )

        if client_task in done:
            return 0
        else:
            # Shutdown was triggered
            client_task.cancel()
            return 0
    except Exception:
        log.exception("Error in live timing processing")
        return 1
    finally:
        # Clean up
        await run_with_errorhandling(client.shutdown(), "Error during client shutdown")
