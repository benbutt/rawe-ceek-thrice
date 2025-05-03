# Rawe Ceek Thrice

**F1 Live Timing to Philips Hue Bridge**

This application connects to the F1 live timing data stream and controls Philips Hue lights based on the current race leader. It changes the color of your lights to match the team color of the current race leader with a configurable delay to match TV broadcast.

## Installation

```bash
# Install the package
uv pip install git@https://github.com/yourusername/rawe_ceek_thrice.git
```

## Configuration

Create a `.env` file in the project root with the following variables:

```
HUE_BRIDGE_IP=your_bridge_ip
HUE_USERNAME=your_hue_username
TV_DELAY_SECONDS=57
```

- `HUE_BRIDGE_IP`: The IP address of your Philips Hue Bridge
- `HUE_USERNAME`: Your Hue Bridge username/API key
- `TV_DELAY_SECONDS`: Delay in seconds to match TV broadcast (default: 57)

## Usage

Run the application with:

```bash
uv run main.py
```

## Project Structure

```
rawe_ceek_thrice/
├── main.py                  # Entry point wrapper
├── rawe_ceek_thrice/        # Main package
│   ├── __init__.py
│   ├── main.py              # Application entry point
│   ├── core/                # Core utilities
│   │   ├── __init__.py
│   │   ├── config.py        # Configuration
│   │   └── utils.py         # Utility functions
│   ├── data/                # Data processing
│   │   ├── __init__.py
│   │   ├── models.py        # Data models
│   │   ├── processor.py     # F1 data processor
│   │   └── record.py        # Live timing client
│   └── lights/              # Light control
│       ├── __init__.py
│       └── update_lights.py # Philips Hue control
├── drivers.json             # Driver data
└── pyproject.toml           # Project configuration
```