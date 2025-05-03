import asyncio
from types import TracebackType
from typing import Awaitable, Callable, Optional, Type, TypeVar

from loguru import logger

T = TypeVar("T")


class TaskManager:
    """
    Context manager for handling async tasks gracefully.
    Automatically cancels and cleans up tasks on exit.
    """

    def __init__(
        self,
        coro: Callable[[], Awaitable[T]],
        name: Optional[str] = None,
        timeout: float = 0.5,
    ):
        """
        Initialize with a coroutine factory and optional name.

        Args:
            coro: Factory function that returns a coroutine to run
            name: Optional name for logging purposes
            timeout: Seconds to wait for task to clean up on exit
        """
        self.coro_factory = coro
        self.name = name or "Task"
        self.task: Optional[asyncio.Task] = None
        self.timeout = timeout
        self.result: Optional[T] = None

    async def __aenter__(self) -> "TaskManager":
        """Start the task when entering the context"""
        self.task = asyncio.create_task(self.coro_factory())
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Cancel and clean up the task when exiting the context"""
        if not self.task:
            return

        # If task completed successfully, store result
        if self.task.done() and not self.task.cancelled():
            try:
                self.result = self.task.result()
            except Exception:
                # Ignore exceptions in result retrieval
                pass

        # Cancel if still running
        if not self.task.done():
            self.task.cancel()
            try:
                # Shield prevents this cleanup from being cancelled
                await asyncio.shield(asyncio.wait([self.task], timeout=self.timeout))
            except Exception:
                # Just swallow exceptions during cleanup
                pass

    @property
    def done(self) -> bool:
        """Check if the task is done"""
        return self.task is not None and self.task.done()


async def run_with_errorhandling(
    coro: Awaitable[T], error_message: str = "Operation failed"
) -> Optional[T]:
    """
    Run a coroutine with standardized error handling.

    Args:
        coro: The coroutine to run
        error_message: Message to log if the operation fails

    Returns:
        The result of the coroutine or None if it failed
    """
    try:
        return await coro
    except asyncio.CancelledError:
        # Re-raise cancellation for proper cleanup
        raise
    except Exception as e:
        logger.error(f"{error_message}: {e}")
        return None
