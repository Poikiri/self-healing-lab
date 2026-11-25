"""All settings in one place."""

SOURCE_PLATE: str = "source"
DESTINATION_PLATE: str = "destination"
TRANSFER_WELLS: list[str] = ["A1"]
TRANSFER_VOLUME_UL: float = 100.0
SOURCE_WELL_VOLUME_UL: float = 200.0

TIP_RACK_RAIL: int = 3
PLATE_RAIL: int = 15

FAULT_PROBABILITY: float = 0.2
SEED: int = 1

MAX_PLAN_LENGTH: int = 3
MAX_RETRIES_PER_STEP: int = 1
TIP_CAPACITY_UL: float = 1000.0
MIN_HEIGHT_MM: float = 0.0
MAX_HEIGHT_MM: float = 10.0

CLAUDE_MODEL: str = "claude-haiku-5-5"
CLAUDE_MAX_TOKENS: int = 16000
CLAUDE_TIMEOUT_SECONDS: float = 60.0
