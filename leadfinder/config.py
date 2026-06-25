from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    google_places_api_key: str = ""
    database_path: str = "leadfinder.db"
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

settings = Settings()
