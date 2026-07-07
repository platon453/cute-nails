from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения, загружаются из .env файла."""

    bot_token: str
    admin_ids: str  # Через запятую: "123456789,987654321"

    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "cute_nails"
    db_pass: str = "cute_nails_secret"
    db_name: str = "cute_nails_db"
    
    proxy: str | None = None  # Например: "http://127.0.0.1:10808"

    @property
    def admin_id_list(self) -> list[int]:
        """Список ID админов, парсится из строки с запятыми."""
        return [int(x.strip()) for x in self.admin_ids.split(",") if x.strip()]

    @property
    def db_url(self) -> str:
        """URL подключения к PostgreSQL для asyncpg."""
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_pass}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

