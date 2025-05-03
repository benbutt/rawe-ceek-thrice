import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add the parent directory to sys.path so we can import the project modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from rawe_ceek_thrice.core.utils import TaskManager, run_with_errorhandling


class TestTaskManager:
    async def test_task_start_and_cleanup(self):
        """Test that TaskManager properly starts and cleans up tasks"""
        # Create a mock coroutine that returns a result
        result_value = "test_result"

        async def mock_coro():
            return result_value

        # Wrap in AsyncMock for tracking calls
        wrapped_mock = AsyncMock(side_effect=mock_coro)

        # Use the TaskManager with our mock coroutine
        async with TaskManager(wrapped_mock, name="TestTask") as manager:
            # Check that task is created when entering context
            assert manager.task is not None
            assert not manager.task.done()

            # Wait a bit to ensure the task completes
            await asyncio.sleep(0.1)

        # After exiting context, task should be completed and result captured
        assert manager.task.done()
        wrapped_mock.assert_called_once()
        assert manager.result == result_value

    async def test_task_handles_exceptions(self):
        """Test that TaskManager properly handles exceptions"""

        async def failing_coro():
            raise ValueError("Test error")

        async with TaskManager(failing_coro, name="FailingTask") as manager:
            assert manager.task is not None
            # Wait for the task to complete
            await asyncio.sleep(0.1)

        # Task should be completed with an exception
        assert manager.task.done()
        assert manager.result is None  # Result should be None due to exception

    async def test_task_cancellation(self):
        """Test that TaskManager properly cancels long-running tasks"""

        # Create a task that will run until cancelled
        async def long_running_coro():
            try:
                # This will run indefinitely until cancelled
                while True:
                    await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                # Return this but it won't be captured since task is cancelled
                return "cancelled"

        # Use a very short timeout to ensure the task gets cancelled
        async with TaskManager(
            long_running_coro, name="LongTask", timeout=0.01
        ) as manager:
            assert manager.task is not None
            # Don't sleep, exit immediately to trigger cancellation

        # Wait a bit for cancellation to complete
        await asyncio.sleep(0.1)

        # Task should be done, but we can't reliably check cancelled() as it may
        # have already finished cancellation process
        assert manager.task.done()
        # Result should be None for cancelled task
        assert manager.result is None


class TestErrorHandling:
    async def test_run_with_errorhandling_success(self):
        """Test run_with_errorhandling with successful operation"""

        async def success_coro():
            return "success"

        result = await run_with_errorhandling(success_coro(), "This operation failed")
        assert result == "success"

    async def test_run_with_errorhandling_failure(self):
        """Test run_with_errorhandling with failed operation"""

        async def failure_coro():
            raise ValueError("Something went wrong")

        # Create a properly mocked logger that doesn't require awaiting
        with patch("rawe_ceek_thrice.core.utils.logger.error") as mock_logger:
            # Call the function with our failing coroutine
            result = await run_with_errorhandling(failure_coro(), "Test error")

            # Verify
            assert result is None
            mock_logger.assert_called_once()
            assert "Test error" in mock_logger.call_args[0][0]

    async def test_run_with_errorhandling_cancelled(self):
        """Test run_with_errorhandling with cancelled operation"""

        async def cancelled_coro():
            raise asyncio.CancelledError()

        with pytest.raises(asyncio.CancelledError):
            await run_with_errorhandling(cancelled_coro(), "This operation failed")
