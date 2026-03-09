"""Application configuration settings"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Application
    APP_NAME: str = "Trinity Agent API"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"
    
    # Security
    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION_USE_OPENSSL_RAND_HEX_32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    # CORS
    CORS_ORIGINS: list = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ]
    
    # Database (SQLite for local dev, PostgreSQL for production)
    POSTGRES_USER: str = "trinity"
    POSTGRES_PASSWORD: str = "trinity_pass"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "trinity_db"
    USE_SQLITE: bool = True  # Set to False when using PostgreSQL
    
    @property
    def DATABASE_URL(self) -> str:
        if self.USE_SQLITE:
            return "sqlite:///./trinity.db"
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    # Neo4j Graph Database
    NEO4J_URI: str = "bolt://neo4j:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "trinity_neo4j"
    
    # ChromaDB Vector Database
    CHROMA_HOST: str = "chromadb"
    CHROMA_PORT: int = 8000
    CHROMA_PERSIST_DIR: str = "./chroma_data"
    
    # Redis (for background tasks)
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    
    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    # LLM / Agent Settings
    OLLAMA_BASE_URL: str = "http://ollama:11434"
    LLM_MODEL_ID: str = "WhiteRabbitNeo/Llama-3.1-WhiteRabbitNeo-2-8B:latest"
    USE_LANGGRAPH: bool = True
    USE_LANGCHAIN: bool = True
    MAX_RETRIES: int = 3
    EXECUTION_TIMEOUT: int = 30
    ENABLE_SELF_HEALING: bool = True
    CIRCUIT_BREAKER_ENABLED: bool = True

    # CVE feed ingestion and automation
    NVD_API_KEY: str = ""
    NVD_BASE_URL: str = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    NVD_RESULTS_PER_PAGE: int = 2000
    CVE_SYNC_INTERVAL_HOURS: int = 6
    N8N_WEBHOOK_URL: str = ""
    
    # Groq Cloud API (Testing fallback only - WhiteRabbitNeo is production)
    # Get free API key from https://console.groq.com
    GROQ_API_KEY: str = ""
    USE_GROQ_FOR_TESTING: bool = False  # Set True when Ollama is too slow
    
    # Scan Settings
    SCOPE_SUBNET: str = "192.168.1.0/24"
    BLOCKED_COMMANDS: list[str] = [
        "-T5", "--script=dos", "rm -rf", "format",
        "| bash", "| sh", "| python", "| perl",  # Pipe to shell execution
        "mkfs", "dd if=", ":(){:|:&};:",  # Destructive commands
    ]

    @property
    def DEFAULT_ALLOWED_SUBNET(self) -> str:
        """Retained for backward compatibility with legacy settings usage."""

        return self.SCOPE_SUBNET
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
