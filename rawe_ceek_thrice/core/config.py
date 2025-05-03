import os

from dotenv import load_dotenv

load_dotenv()

TV_DELAY_SECONDS: int = int(os.getenv("TV_DELAY_SECONDS", 57))
HUE_BRIDGE_IP: str = os.getenv("HUE_BRIDGE_IP")
HUE_USERNAME: str = os.getenv("HUE_USERNAME")
HUE_CLIENT_KEY: str = os.getenv("HUE_CLIENT_KEY")

if not HUE_USERNAME or not HUE_BRIDGE_IP:
    raise ValueError("HUE_USERNAME and HUE_BRIDGE_IP must be set")
