import os
import logging
from pathlib import Path
from typing import Optional

class ProjectConfig:
    """
    Central configuration management for the Second Brain application.
    Adheres to 12-factor app principles using Environment Variables with safe defaults.
    """
    
    # Base Directory (Project Root)
    BASE_DIR: Path = Path(__file__).parent.resolve()
    
    # Critical Paths - Fail fast if permissions are wrong
    # Defaulting to local directories within the project for portability
    OBSIDIAN_VAULT: Path = Path(os.getenv("OBSIDIAN_VAULT", BASE_DIR / "Education"))
    DB_DIR: Path = Path(os.getenv("CHROMA_DB_DIR", BASE_DIR / "obsidian_db"))
    TEMP_DIR: Path = Path(os.getenv("TEMP_DIR", BASE_DIR / "temp_processing"))

    # LLM Settings (Ollama)
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "bielik:latest")
    
    # External APIs
    HF_TOKEN: Optional[str] = os.getenv("HF_TOKEN") # Required for PyAnnote

    # RAG Settings
    CHUNK_SIZE: int = int(os.getenv("RAG_CHUNK_SIZE", 1000))
    CHUNK_OVERLAP: int = int(os.getenv("RAG_CHUNK_OVERLAP", 200))

    # Security & Compliance
    # Enables strict validation of URLs and inputs
    STRICT_MODE: bool = os.getenv("STRICT_MODE", "True").lower() == "true"

    @classmethod
    def setup_logging(cls):
        """Configures standard Python logging (Point 6 of Audit)."""
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            handlers=[
                logging.StreamHandler(),  # Output to console (Docker/Systemd friendly)
                logging.FileHandler(cls.BASE_DIR / "system.log")  # Persistent log
            ]
        )
        # Suppress noisy libraries
        logging.getLogger("chromadb").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)

    @classmethod
    def validate_paths(cls):
        """Ensures critical directories exist."""
        cls.OBSIDIAN_VAULT.mkdir(parents=True, exist_ok=True)
        cls.DB_DIR.mkdir(parents=True, exist_ok=True)
        cls.TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Initialize immediately on import
ProjectConfig.setup_logging()
ProjectConfig.validate_paths()
logger = logging.getLogger("Config")
logger.info(f"Configuration loaded. Root: {ProjectConfig.BASE_DIR}")
