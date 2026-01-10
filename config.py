import logging
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    """
    Central configuration management for the Second Brain application.
    Uses Pydantic Settings for strict validation and environment mapping.
    """
    # Base Directory (Project Root)
    BASE_DIR: Path = Path(__file__).parent.resolve()

    # Paths
    OBSIDIAN_VAULT: Path = Field(default=BASE_DIR / "Education")
    CHROMA_DB_DIR: Path = Field(default=BASE_DIR / "obsidian_db")
    INBOX_DIR: Path = Field(default=BASE_DIR / "obsidian_db" / "_INBOX")
    TEMP_DIR: Path = Field(default=BASE_DIR / "temp_processing")

    # LLM Settings (Ollama)
    OLLAMA_URL: str = Field(default="http://localhost:11434")
    # Main "Brain" Model (High Intelligence, Polish Context) - Optimized for RTX 3060 (12GB)
    OLLAMA_MODEL: str = Field(default="SpeakLeash/bielik-11b-v2.3-instruct:Q5_K_M")
    # Fast "Worker" Model (Tagging, Metadata, Simple JSON) - Low VRAM usage
    OLLAMA_MODEL_FAST: str = Field(default="llama3.2:latest")
    
    # External APIs
    HF_TOKEN: Optional[str] = None

    # RAG Settings
    RAG_CHUNK_SIZE: int = Field(default=1000)
    RAG_CHUNK_OVERLAP: int = Field(default=200)
    EMBEDDING_MODEL: str = Field(default="mxbai-embed-large")

    # Security & Compliance
    STRICT_MODE: bool = Field(default=True)
    LOG_LEVEL: str = Field(default="INFO")

    # Load from .env file
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding='utf-8',
        extra="ignore"
    )

    def validate_paths(self):
        """Ensures critical directories exist."""
        self.OBSIDIAN_VAULT.mkdir(parents=True, exist_ok=True)
        self.CHROMA_DB_DIR.mkdir(parents=True, exist_ok=True)
        self.INBOX_DIR.mkdir(parents=True, exist_ok=True)
        self.TEMP_DIR.mkdir(parents=True, exist_ok=True)

    def setup_logging(self):
        """Configures standard Python logging with DORA/NIS2 tagging intent."""
        log_format = '%(asctime)s - %(name)s - %(levelname)s [%(tags)s] - %(message)s'
        
        # Custom logging filter for compliance tagging
        class ComplianceFilter(logging.Filter):
            def filter(self, record):
                if not hasattr(record, 'tags'):
                    record.tags = 'SYSTEM'
                return True

        handler = logging.StreamHandler()
        handler.addFilter(ComplianceFilter())
        
        file_handler = logging.FileHandler(self.BASE_DIR / "system.log")
        file_handler.addFilter(ComplianceFilter())

        logging.basicConfig(
            level=getattr(logging, self.LOG_LEVEL.upper()),
            format=log_format,
            handlers=[handler, file_handler]
        )
        
        # Suppress noisy libraries
        logging.getLogger("chromadb").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

# Initialize global config
ProjectConfig = Settings()
ProjectConfig.setup_logging()
ProjectConfig.validate_paths()

logger = logging.getLogger("Config")
logger.info("Configuration initialized via Pydantic.", extra={"tags": "COMPLIANCE-INIT"})