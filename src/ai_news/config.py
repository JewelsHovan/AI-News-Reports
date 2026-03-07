from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class PipelineConfig:
    """Configuration for the AI News pipeline."""

    days: int = 2
    project_root: Path = field(default_factory=lambda: Path(__file__).resolve().parents[2])
    reports_dir: Path = field(default=None)  # type: ignore[assignment]
    admin_api_secret: str | None = None
    api_base_url: str = "https://ai-news-signup.julienh15.workers.dev"
    email_config_path: Path = field(default=None)  # type: ignore[assignment]
    max_budget_usd: float = 5.0
    dry_run: bool = False

    def __post_init__(self) -> None:
        if self.reports_dir is None:
            self.reports_dir = self.project_root / "reports"
        if self.email_config_path is None:
            self.email_config_path = self.project_root / "email_config.json"

    @classmethod
    def from_env(cls, env_file: str | Path | None = None) -> PipelineConfig:
        """Create a PipelineConfig populated from environment variables and .env file."""
        if env_file is not None:
            load_dotenv(env_file)
        else:
            load_dotenv()

        project_root = Path(
            os.getenv("AI_NEWS_PROJECT_ROOT", Path(__file__).resolve().parents[2])
        )

        reports_dir_env = os.getenv("AI_NEWS_REPORTS_DIR")
        reports_dir = Path(reports_dir_env) if reports_dir_env else project_root / "reports"

        email_config_env = os.getenv("AI_NEWS_EMAIL_CONFIG_PATH")
        email_config_path = (
            Path(email_config_env) if email_config_env else project_root / "email_config.json"
        )

        return cls(
            days=int(os.getenv("AI_NEWS_DAYS", "2")),
            project_root=project_root,
            reports_dir=reports_dir,
            admin_api_secret=os.getenv("ADMIN_API_SECRET"),
            api_base_url=os.getenv(
                "AI_NEWS_API_BASE_URL",
                "https://ai-news-signup.julienh15.workers.dev",
            ),
            email_config_path=email_config_path,
            max_budget_usd=float(os.getenv("AI_NEWS_MAX_BUDGET_USD", "5.0")),
            dry_run=os.getenv("AI_NEWS_DRY_RUN", "").lower() in ("1", "true", "yes"),
        )
