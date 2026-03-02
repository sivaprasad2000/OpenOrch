"""Consumer service configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict

from consumer.playwright_service import BrowserConfig


class ConsumerSettings(BaseSettings):
    """Settings for the consumer service — reads from the same .env as the backend."""

    # ── Message queue ──────────────────────────────────────────────────────────
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    RABBITMQ_TEST_RUNS_QUEUE: str = "test_runs"

    # ── Backend API ────────────────────────────────────────────────────────────
    BE_BASE_URL: str = "http://localhost:8000"

    # ── Internal service authentication ───────────────────────────────────────
    # Must match INTERNAL_SERVICE_SECRET in the backend .env.
    INTERNAL_SERVICE_SECRET: str  # required — no default

    # ── Browser (Playwright) ───────────────────────────────────────────────────
    BROWSER_VIEWPORT_WIDTH: int = 1280   # pixels; also used for video recording
    BROWSER_VIEWPORT_HEIGHT: int = 720   # pixels; also used for video recording
    BROWSER_HEADLESS: bool = True        # set False to watch the browser locally
    BROWSER_SLOW_MO: int = 0             # ms delay between actions (0 = full speed)

    # ── Storage ────────────────────────────────────────────────────────────────
    STORAGE_BACKEND: str = "local"       # "local" | "s3"
    LOCAL_RECORDINGS_DIR: str = "./recordings"

    # ── S3 (only used when STORAGE_BACKEND="s3") ──────────────────────────────
    S3_BUCKET: str = ""
    S3_REGION: str = "us-east-1"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # backend-only vars (DATABASE_URL, SECRET_KEY …) live in the same .env
    )

    @property
    def browser_config(self) -> BrowserConfig:
        """Construct a BrowserConfig from current settings."""
        return BrowserConfig(
            viewport_width=self.BROWSER_VIEWPORT_WIDTH,
            viewport_height=self.BROWSER_VIEWPORT_HEIGHT,
            headless=self.BROWSER_HEADLESS,
            slow_mo=self.BROWSER_SLOW_MO,
        )


settings = ConsumerSettings()
