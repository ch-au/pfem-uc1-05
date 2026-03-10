"""
Configuration for the FSV data pipeline.
All paths are relative to the pipeline root (this file's parent).
Use .env for local settings; see .env.example.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from typing import Optional

# Pipeline root = directory containing this config
PIPELINE_ROOT = Path(__file__).resolve().parent
load_dotenv(PIPELINE_ROOT / ".env")

try:
    from psycopg2 import pool
except ImportError:
    pool = None


class Config:
    # SQLite (output of parser; input for sync)
    DATABASE_PATH = PIPELINE_ROOT / os.getenv("SQLITE_DB", "fsv_archive_complete.db")
    # HTML archive path (input for parser)
    ARCHIVE_PATH = PIPELINE_ROOT / os.getenv("FSVARCHIV_PATH", "fsvarchiv")

    # PostgreSQL (Neon or other)
    DB_URL = os.getenv("DATABASE_URL") or os.getenv("DB_URL")

    _pg_pool: Optional["pool.SimpleConnectionPool"] = None

    # Legacy embedding-related settings are retained for compatibility with archived scripts.
    COHERE_API_KEY = os.getenv("COHERE_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    COHERE_EMBED_MODEL = os.getenv("COHERE_EMBED_MODEL", "embed-v4.0")
    OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")
    # Default to the schema-compatible dimension used by this package.
    OPENAI_EMBEDDING_DIM = int(os.getenv("OPENAI_EMBEDDING_DIM", "1024"))

    # Postgres (for scripts that use PG_* env)
    PG_ENABLED = bool(DB_URL)
    PG_HOST = os.getenv("PG_HOST", "127.0.0.1")
    PG_PORT = int(os.getenv("PG_PORT", "5432"))
    PG_DATABASE = os.getenv("PG_DATABASE", "neondb")
    PG_USER = os.getenv("PG_USER", "postgres")
    PG_PASSWORD = os.getenv("PG_PASSWORD", "")
    PG_SCHEMA = os.getenv("PG_SCHEMA", "public")
    PG_SSLMODE = os.getenv("PG_SSLMODE", "require")

    def build_psycopg2_dsn(self) -> str:
        if self.DB_URL:
            parsed = urlparse(self.DB_URL)
            scheme = "postgresql" if parsed.scheme in ("postgres", "postgresql") else parsed.scheme
            query = parse_qs(parsed.query)
            if "sslmode" not in {k.lower() for k in query}:
                query["sslmode"] = [self.PG_SSLMODE]
            new_query = urlencode([(k, v[0]) for k, v in query.items()])
            return urlunparse((scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
        return (
            f"host={self.PG_HOST} port={self.PG_PORT} dbname={self.PG_DATABASE} "
            f"user={self.PG_USER} password={self.PG_PASSWORD} sslmode={self.PG_SSLMODE}"
        )

    def get_pg_pool(self):
        if pool is None:
            raise RuntimeError("psycopg2 is required for connection pooling")
        if Config._pg_pool is None:
            if not self.PG_ENABLED:
                raise RuntimeError("DATABASE_URL or DB_URL is required for Postgres")
            dsn = self.build_psycopg2_dsn()
            Config._pg_pool = pool.SimpleConnectionPool(minconn=2, maxconn=10, dsn=dsn)
        return Config._pg_pool

    def get_connection(self):
        return self.get_pg_pool().getconn()

    def return_connection(self, conn):
        self.get_pg_pool().putconn(conn)
