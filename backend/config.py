import os
from pathlib import Path
from dotenv import load_dotenv
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from psycopg2 import pool
from typing import Optional

# Load environment variables from .env file
load_dotenv()

class Config:
    # Database
    DATABASE_PATH = Path(__file__).parent / "fsv_archive_complete.db"
    # Optional unified Postgres URL (e.g., Neon): postgres://user:pass@host:port/db?sslmode=require
    DB_URL = os.getenv("DB_URL")
    
    # Connection pool (singleton)
    _pg_pool: Optional[pool.SimpleConnectionPool] = None
    
    # API Keys (will be set via environment variables)
    COHERE_API_KEY = os.getenv("COHERE_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    
    # Model configurations  
    COHERE_EMBED_MODEL = "embed-v4.0"
    LLM_MODEL = "command-r-plus"  # Cohere model (legacy)
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-nano")
    OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")
    OPENAI_EMBEDDING_DIM = int(os.getenv("OPENAI_EMBEDDING_DIM", "3072"))
    
    # LiteLLM Configuration
    LITELLM_DEFAULT_MODEL = os.getenv("LITELLM_DEFAULT_MODEL", "gemini/gemini-flash-latest")
    LITELLM_CHAT_MODEL = os.getenv("LITELLM_CHAT_MODEL", "gemini/gemini-flash-latest")
    LITELLM_QUIZ_MODEL = os.getenv("LITELLM_QUIZ_MODEL", "gemini/gemini-flash-latest")
    
    # Langfuse Configuration
    LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
    LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
    LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    # Postgres (optional) for pgvector embeddings store
    # Auto-enable if DB_URL provided
    PG_ENABLED = (os.getenv("PG_ENABLED", "false").lower() in ("1", "true", "yes")) or bool(os.getenv("DB_URL"))
    PG_HOST = os.getenv("PG_HOST", "127.0.0.1")
    PG_PORT = int(os.getenv("PG_PORT", "5432"))
    PG_DATABASE = os.getenv("PG_DATABASE", "fsv05")
    PG_USER = os.getenv("PG_USER", "postgres")
    PG_PASSWORD = os.getenv("PG_PASSWORD", "postgres")
    PG_SCHEMA = os.getenv("PG_SCHEMA", "public")
    PG_SSLMODE = os.getenv("PG_SSLMODE", "require")
    
    # Database schema description for the LLM
    SCHEMA_DESCRIPTION = """
    FSV Mainz 05 Football Database Schema:
    
    Tables:
    - Seasons: Contains season information (season_name, league_name, total_matches)
    - Matches: All FSV matches (gameday, is_home_game, mainz_goals, opponent_goals, result_string)
    - Opponents: Teams FSV played against (opponent_name)
    - Players: All FSV players (player_name)
    - Goals: Detailed goal information (goal_minute, is_penalty, is_own_goal, score_at_time)
    - Match_Lineups: Player appearances (is_starter, is_captain, jersey_number, substituted_minute, yellow_card, red_card)
    - Substitutions: All substitution events (minute, player_in_id, player_out_id)
    
    Key Statistics:
    - 109 seasons, 2,774 matches, 8,136 players, 6,288 goals
    - Data covers 1905-2025 with complete modern era coverage
    - Top scorer: Bopp with 100 goals
    """

    # Prompts configuration
    # Path to prompts YAML file; can be overridden via PROMPTS_PATH env var
    PROMPTS_PATH = Path(os.getenv("PROMPTS_PATH", str(Path(__file__).parent / "prompts.yaml")))
    
    FOOTBALL_CONTEXT = """
    This is FSV Mainz 05 football club data. Key context:
    - FSV Mainz 05 is a German football club founded in 1905
    - Home games: is_home_game = true, Away games: is_home_game = false
    - Goals can be penalties (is_penalty = true) or own goals (is_own_goal = true)
    - Players can be starters (is_starter = true) or substitutes
    - Match results show FSV goals vs opponent goals
    - Season names like "2023-24" represent the 2023-2024 season
    """

    def build_psycopg2_dsn(self) -> str:
        """Build a psycopg2 DSN/URI, preferring DB_URL and ensuring sslmode."""
        if self.DB_URL:
            parsed = urlparse(self.DB_URL)
            # Normalize scheme for psycopg2
            scheme = "postgresql" if parsed.scheme in ("postgres", "postgresql") else parsed.scheme
            query = parse_qs(parsed.query)
            lowered = {k.lower(): v for k, v in query.items()}
            if "sslmode" not in lowered:
                query["sslmode"] = [self.PG_SSLMODE]
            new_query = urlencode([(k, v[0]) for k, v in query.items()])
            return urlunparse((scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
        return (
            f"host={self.PG_HOST} port={self.PG_PORT} dbname={self.PG_DATABASE} "
            f"user={self.PG_USER} password={self.PG_PASSWORD} sslmode={self.PG_SSLMODE}"
        )

    def build_sqlalchemy_uri(self) -> str:
        """Build SQLAlchemy URI, preferring DB_URL and ensuring driver + sslmode."""
        if self.DB_URL:
            parsed = urlparse(self.DB_URL)
            query = parse_qs(parsed.query)
            lowered = {k.lower(): v for k, v in query.items()}
            if "sslmode" not in lowered:
                query["sslmode"] = [self.PG_SSLMODE]
            new_query = urlencode([(k, v[0]) for k, v in query.items()])
            scheme = "postgresql+psycopg2"
            return urlunparse((scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
        return (
            f"postgresql+psycopg2://{self.PG_USER}:{self.PG_PASSWORD}@{self.PG_HOST}:{self.PG_PORT}/{self.PG_DATABASE}?sslmode={self.PG_SSLMODE}"
        )
    
    def get_pg_pool(self) -> pool.SimpleConnectionPool:
        """Get or create connection pool for Postgres."""
        if Config._pg_pool is None:
            if not self.PG_ENABLED:
                raise RuntimeError("Postgres is required for connection pooling")
            
            dsn = self.build_psycopg2_dsn()
            Config._pg_pool = pool.SimpleConnectionPool(
                minconn=2,
                maxconn=10,
                dsn=dsn
            )
        return Config._pg_pool
    
    def get_connection(self):
        """Get a connection from the pool."""
        return self.get_pg_pool().getconn()
    
    def return_connection(self, conn):
        """Return a connection to the pool."""
        self.get_pg_pool().putconn(conn)