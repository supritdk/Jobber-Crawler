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

    # Scrape profile
    # Roles: comma-separated job titles to search for
    scrape_roles: str = "Senior Software Engineer"
    # Sources: comma-separated list of enabled sources to run
    scrape_sources: str = "linkedin"
    # Locations: semicolon-separated entries, each as "City,Country"
    # e.g. "Bengaluru,India;Mumbai,India;Remote,"
    scrape_locations: str = "Bengaluru,India"
    # Only return jobs posted within this many hours (None = no filter)
    scrape_freshness_hours: int = 24
    # Max jobs to fetch per role/location/source combination
    scrape_max_results: int = 100

    # Scheduler
    scrape_concurrency: int = 3

    # Logging
    log_level: str = "INFO"
    log_json: bool = False

    model_config = {"env_file": ".env", "env_prefix": "JOBBER_"}

    def get_scrape_roles(self) -> list[str]:
        return [r.strip() for r in self.scrape_roles.split(",") if r.strip()]

    def get_scrape_sources(self) -> list[str]:
        return [s.strip() for s in self.scrape_sources.split(",") if s.strip()]

    def get_scrape_locations(self) -> list[dict]:
        """Parse JOBBER_SCRAPE_LOCATIONS into a list of {"city": ..., "country": ...} dicts."""
        locations = []
        for entry in self.scrape_locations.split(";"):
            entry = entry.strip()
            if not entry:
                continue
            parts = entry.split(",", 1)
            city = parts[0].strip()
            country = parts[1].strip() if len(parts) > 1 else ""
            locations.append({"city": city, "country": country})
        return locations

    def get_workday_urls(self) -> list[str]:
        if not self.workday_tenant_urls:
            return []
        return [u.strip() for u in self.workday_tenant_urls.split(",") if u.strip()]

    def get_greenhouse_tokens(self) -> list[str]:
        if not self.greenhouse_board_tokens:
            return []
        return [t.strip() for t in self.greenhouse_board_tokens.split(",") if t.strip()]


settings = Settings()
