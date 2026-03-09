from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "mysql+pymysql://root@localhost:3306/gastos_db"
    SECRET_KEY: str | None = None
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days
    GEMINI_API_KEY: str | None = None
    GROQ_API_KEY: str | None = None
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 20

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()

