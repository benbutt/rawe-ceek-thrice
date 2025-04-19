import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add the parent directory to sys.path so we can import the project modules
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from models import Message, Topic
from record import RaweCeekClient, process_live_timing


class TestRaweCeekClient:
    @pytest.fixture
    def mock_signalr_client(self):
        """Fixture to mock the SignalRClient parent class"""
        with patch(
            "record.client.SignalRClient.__init__", return_value=None
        ) as mock_init:
            # Properly mock _run method to avoid "coroutine never awaited" warnings
            run_mock = AsyncMock()
            with patch("record.client.SignalRClient._run", run_mock):
                # Mock _supervise to avoid warnings as well
                supervise_mock = AsyncMock()
                with patch("record.client.SignalRClient._supervise", supervise_mock):
                    yield mock_init, run_mock

    def test_init(self, mock_signalr_client):
        """Test the initialization of RaweCeekClient"""
        mock_init, _ = mock_signalr_client
        message_processor = AsyncMock()
        logger = MagicMock()

        # Test with explicit filename
        client = RaweCeekClient(
            filename="test.txt",
            filemode="w",
            debug=True,
            timeout=30,
            message_processor=message_processor,
            logger_instance=logger,
        )

        # Verify
        mock_init.assert_called_once()
        assert client.message_processor == message_processor
        assert client.log == logger
        assert not client.shutdown_event.is_set()
        assert client.save_to_file is True
        assert client._temp_file is None

        # Reset mock
        mock_init.reset_mock()

        # Test with no filename (should create temp file)
        client = RaweCeekClient(
            filename=None,
            message_processor=message_processor,
            logger_instance=logger,
        )

        # Verify
        mock_init.assert_called_once()
        assert client._temp_file is not None
        assert os.path.exists(client._temp_file.name)
        # Cleanup
        client._temp_file.close()
        os.unlink(client._temp_file.name)

    @pytest.mark.asyncio
    async def test_on_message(self):
        """Test the _on_message method"""
        # Setup client with a mock processor
        message_processor = AsyncMock()
        client = RaweCeekClient(
            filename=None,
            message_processor=message_processor,
        )
        client._output_file = None  # Prevent file writing
        client._t_last_message = 0  # Set initial timestamp

        # Test with valid message
        sample_message = ["TimingAppData", {"Lines": {"1": {"Line": 1}}}, 123456789]

        # First test without save_to_file
        await client._on_message(sample_message)

        # Verify
        assert client._t_last_message > 0  # Should update timestamp
        message_processor.assert_called_once()
        # Check the message passed to processor
        call_args = message_processor.call_args[0][0]
        assert isinstance(call_args, Message)
        assert call_args.topic == Topic.TimingAppData
        assert "Lines" in call_args.content

        # Reset mocks
        message_processor.reset_mock()

        # Now test with save_to_file=True using a complete mock of the parent class
        client.save_to_file = True

        # Create a fresh client with mocked parent for second test
        with patch(
            "record.client.SignalRClient._on_message", AsyncMock()
        ) as mock_parent_on_message:
            # Set the file and make the call
            client._output_file = MagicMock()
            await client._on_message(sample_message)

            # Verify
            message_processor.assert_called_once()
            mock_parent_on_message.assert_called_once_with(sample_message)

    @pytest.mark.asyncio
    async def test_on_message_exception(self):
        """Test the _on_message method with processor exception"""

        # Setup client with a failing processor
        async def failing_processor(message):
            raise ValueError("Test error")

        client = RaweCeekClient(
            filename=None,
            message_processor=failing_processor,
            logger_instance=MagicMock(),
        )
        client._output_file = None  # Prevent file writing

        # Test with processor that raises exception
        sample_message = ["TimingAppData", {"Lines": {"1": {"Line": 1}}}, 123456789]

        # Patch super method to avoid actual file writing and never awaited warnings
        with patch("record.client.SignalRClient._on_message", AsyncMock()):
            # Should not raise exception
            await client._on_message(sample_message)

        # Verify logger was called with exception
        client.log.exception.assert_called_once()

    @pytest.mark.asyncio
    async def test_run(self):
        """Test the run method"""
        # Setup client with fully mocked methods
        client = RaweCeekClient(filename=None)

        # Create separate mocks for the coroutines
        mock_supervise = MagicMock()
        supervise_future = asyncio.Future()
        supervise_future.set_result(None)
        mock_supervise.return_value = supervise_future

        mock_run = MagicMock()
        run_future = asyncio.Future()
        run_future.set_result(None)
        mock_run.return_value = run_future

        # Create mock tasks that will be returned by create_task
        mock_supervise_task = MagicMock()
        mock_run_task = MagicMock()

        # Apply the patches
        with patch.object(client, "_supervise", mock_supervise):
            with patch.object(client, "_run", mock_run):
                with patch(
                    "asyncio.create_task",
                    side_effect=[mock_supervise_task, mock_run_task],
                ):
                    # Also patch gather to avoid actually awaiting anything
                    gather_future = asyncio.Future()
                    gather_future.set_result(None)
                    mock_gather = MagicMock(return_value=gather_future)
                    with patch("asyncio.gather", mock_gather):
                        # Run the client
                        await client.run()

                        # Verify that both coroutines were created and passed to gather
                        assert mock_supervise.called
                        assert mock_run.called
                        mock_gather.assert_called_once_with(
                            mock_supervise_task, mock_run_task
                        )

    @pytest.mark.asyncio
    async def test_shutdown(self):
        """Test the shutdown method without using any AsyncMock to avoid warnings"""
        # Create a client with controlled environment
        with patch("record.client.SignalRClient.__init__", return_value=None):
            # Create the client
            client = RaweCeekClient(filename=None)

            # Create a mock shutdown_event that doesn't use AsyncMock
            # This is key - we need to completely avoid AsyncMock
            shutdown_event = MagicMock()
            # Create non-async mocks for the methods
            shutdown_event.is_set = MagicMock(return_value=False)
            shutdown_event.set = MagicMock()
            # Replace the event in the client with our controllable one
            client.shutdown_event = shutdown_event

            # Create a mock connection
            mock_connection = MagicMock()
            mock_connection.close = MagicMock()
            client._connection = mock_connection

            # Call shutdown method
            await client.shutdown()

            # Verify the event was set and connection closed
            shutdown_event.set.assert_called_once()
            mock_connection.close.assert_called_once()


@pytest.mark.asyncio
@patch("record.RaweCeekClient")
@patch("record.run_with_errorhandling")
@patch("asyncio.create_task")
@patch("asyncio.wait")
@patch("asyncio.Event")
async def test_process_live_timing(
    mock_event, mock_wait, mock_create_task, mock_error_handling, mock_client_class
):
    """Test the process_live_timing function without any AsyncMock to avoid warnings"""
    # Case 1: Client task completes

    # Setup
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    # Make sure shutdown() returns a future that's done, not a coroutine
    shutdown_future = asyncio.Future()
    shutdown_future.set_result(None)
    mock_client.shutdown.return_value = shutdown_future

    # Setup the Event
    mock_event_instance = MagicMock()
    wait_future = asyncio.Future()
    wait_future.set_result(None)
    mock_event_instance.wait.return_value = wait_future
    mock_event_instance.set = MagicMock()
    mock_event.return_value = mock_event_instance

    # Make wait return client task in done set
    client_task = MagicMock()
    mock_wait.return_value = ({client_task}, set())

    # Make create_task return the task we can check
    mock_create_task.return_value = client_task

    # Make run_with_errorhandling return a completed future
    error_future = asyncio.Future()
    error_future.set_result(None)
    mock_error_handling.return_value = error_future

    # Call the function
    result = await process_live_timing(
        output="test_output.txt",
        append=True,
        debug=True,
        timeout=30,
        message_processor=MagicMock(),
    )

    # Verify
    assert result == 0
    mock_client_class.assert_called_once()
    mock_error_handling.assert_called_once()

    # Reset for case 2
    mock_client_class.reset_mock()
    mock_error_handling.reset_mock()
    mock_wait.reset_mock()
    mock_create_task.reset_mock()

    # Case 2: Shutdown triggered

    # Setup new mocks
    mock_client = MagicMock()
    shutdown_future = asyncio.Future()
    shutdown_future.set_result(None)
    mock_client.shutdown.return_value = shutdown_future
    mock_client_class.return_value = mock_client

    # Create tasks for wait to return
    client_task = MagicMock()
    wait_task = MagicMock()

    # Make wait return shutdown event task in done and client in pending
    mock_wait.return_value = ({wait_task}, {client_task})

    # Make create_task return the client task
    mock_create_task.return_value = client_task

    # Make run_with_errorhandling return a completed future
    error_future = asyncio.Future()
    error_future.set_result(None)
    mock_error_handling.return_value = error_future

    # Call the function again
    result = await process_live_timing()

    # Verify
    assert result == 0
    client_task.cancel.assert_called_once()
    mock_error_handling.assert_called_once()
