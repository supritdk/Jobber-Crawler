from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://jobber:jobber@localhost:5432/jobber_crawler"

    # LinkedIn
    linkedin_enabled: bool = True
    linkedin_rate_limit_rpm: int = 20
    linkedin_max_results: int = 1000
    linkedin_delay_seconds: float = 3.0

    # Naukri
    naukri_enabled: bool = True
    naukri_rate_limit_rpm: int = 30
    naukri_max_results: int = 1000

    # Indeed
    indeed_enabled: bool = False
    indeed_publisher_id: str = ""
    indeed_rate_limit_rpm: int = 30
    indeed_max_results: int = 1000

    # Workday
    workday_enabled: bool = True
    workday_tenant_urls: str = ""  # Comma-separated base URLs
    workday_rate_limit_rpm: int = 60
    workday_max_results: int = 500

    # Greenhouse
    greenhouse_enabled: bool = True
    greenhouse_board_tokens: str = ""  # Comma-separated board tokens
    greenhouse_rate_limit_rpm: int = 60
    greenhouse_max_results: int = 500

    # Scheduler
    scrape_concurrency: int = 3

    # Logging
    log_level: str = "INFO"
    log_json: bool = False

    model_config = {"env_file": ".env", "env_prefix": "JOBBER_"}

    def get_workday_urls(self) -> list[str]:
        if not self.workday_tenant_urls:
            return []
        return [u.strip() for u in self.workday_tenant_urls.split(",") if u.strip()]

    def get_greenhouse_tokens(self) -> list[str]:
        if not self.greenhouse_board_tokens:
            return []
        return [t.strip() for t in self.greenhouse_board_tokens.split(",") if t.strip()]


settings = Settings()
