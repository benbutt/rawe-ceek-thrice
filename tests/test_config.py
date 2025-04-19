import os
import sys
from importlib import reload
from pathlib import Path
from unittest.mock import patch

# Add the parent directory to sys.path so we can import the project modules
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


class TestConfig:
    def test_config_loads_env_vars(self, mock_env_config):
        """Test that config loads environment variables correctly"""
        # Import here to ensure we use the mocked environment variables
        import config

        reload(config)  # Make sure we reload to get the mocked values

        assert config.HUE_BRIDGE_IP == "192.168.1.165"
        assert config.HUE_USERNAME == "testuser"
        assert config.HUE_CLIENT_KEY == "testkey"
        assert config.TV_DELAY_SECONDS == "30"  # Should be a string

    def test_config_default_values(self):
        """Test default values when environment variables are not set"""
        # Test with TV_DELAY_SECONDS not set
        with patch.dict(
            os.environ,
            {"HUE_BRIDGE_IP": "192.168.1.100", "HUE_USERNAME": "testuser"},
            clear=True,
        ):
            # Re-import to reload with new environment
            import config

            reload(config)

            assert config.TV_DELAY_SECONDS == "57"  # Default value is a string

    def test_config_validation(self):
        """Test validation of required environment variables"""
        # Mock load_dotenv to do nothing
        with patch("dotenv.load_dotenv", return_value=None):
            # Set up the empty environment
            with patch.dict(os.environ, {}, clear=True):
                # This should raise ValueError because both HUE_USERNAME and HUE_BRIDGE_IP are missing
                with pytest.raises(ValueError) as excinfo:
                    import config

                    reload(config)

                assert "HUE_USERNAME and HUE_BRIDGE_IP must be set" in str(
                    excinfo.value
                )
