from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET_KEY = "dev-only-secret-change-me-before-real-use-0123456789"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://clinic:clinic@localhost:5432/clinic"
    redis_url: str = "redis://localhost:6379/0"
    environment: str = "development"
    secret_key: str = DEFAULT_SECRET_KEY
    cors_origins: str = "http://localhost:3000"
    sms_provider: str = "none"  # "none" sends nothing; a real provider name comes later
    reminder_interval_seconds: int = 30
    # Render's free plan has no background workers (Week 12): true runs the reminder
    # worker inside the API process instead. Keep false when a separate worker runs.
    run_worker_in_api: bool = False
    # Teleconsult video (Week 9): "jitsi" makes private Jitsi Meet rooms, "fake" is for tests,
    # "none" turns video off (consults then run on chat).
    video_provider: str = "jitsi"
    # The public meet.jit.si works for a pilot; a clinic going live should run its own Jitsi
    # server (or JaaS) so calls stay on infrastructure it controls.
    jitsi_base_url: str = "https://meet.jit.si"
    # Online payment (Week 10): "paystack", or "none" for cash and transfer only.
    # Use Paystack TEST keys (sk_test_...) until the clinic goes live. Never commit keys.
    payment_gateway: str = "none"
    paystack_secret_key: str = ""
    paystack_base_url: str = "https://api.paystack.co"
    paystack_callback_url: str = ""  # where Paystack sends the patient after paying
    # Paystack needs an email for every payment; this one is used when the patient has none.
    payment_fallback_email: str = "payments@lafiya.example"

    @field_validator("database_url")
    @classmethod
    def use_psycopg(cls, value: str) -> str:
        """Hosts such as Render give postgres:// or postgresql:// addresses; SQLAlchemy
        needs to be told to use the psycopg driver we install."""
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value.removeprefix(prefix)
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()