"""Environment-driven configuration, read once at import time."""

import os


class Settings:
    """All runtime configuration for the app, sourced from environment
    variables with sane local-dev defaults. Instantiated once below as
    `settings` and imported everywhere else in the app."""

    DATABASE_URL = os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://triage:triage@localhost:5432/triage"
    )
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
    MODEL_ID = os.environ.get("MODEL_ID", "claude-sonnet-5")
    CONFIDENCE_THRESHOLD = float(os.environ.get("CONFIDENCE_THRESHOLD", "0.75"))
    SEED_ON_START = os.environ.get("SEED_ON_START", "false").lower() == "true"


settings = Settings()
