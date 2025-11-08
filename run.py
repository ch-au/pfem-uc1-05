#!/usr/bin/env python3
"""
Startup script for FSV Mainz 05 SQL Assistant (FastAPI + OpenAI + optional pgvector)
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv


def setup_logging(log_file: Path) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    fmt = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding="utf-8")
    ]
    logging.basicConfig(level=logging.INFO, format=fmt, datefmt=datefmt, handlers=handlers)


def check_requirements() -> bool:
    logger = logging.getLogger("run")
    logger.info("Checking requirements...")

    db_path = Path(__file__).parent / "fsv_archive_complete.db"
    if not db_path.exists():
        logger.error("Database not found at %s", db_path)
        logger.info("Please ensure fsv_archive_complete.db is in the app directory")
        return False
    logger.info("Database found at %s", db_path)

    # OpenAI API key is optional - LiteLLM uses default model (e.g., Gemini) if not set
    # Only needed for embeddings or if you want to use OpenAI models specifically
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        logger.info("OpenAI API key configured (optional - used for embeddings)")
    else:
        logger.info("Using LiteLLM default model (no OpenAI API key required)")

    # Optional: check pgvector connectivity
    if os.getenv("PG_ENABLED", "false").lower() in ("1", "true", "yes"):
        try:
            import psycopg2
            from backend.config import Config
            cfg = Config()
            dsn = (
                f"host={cfg.PG_HOST} port={cfg.PG_PORT} dbname={cfg.PG_DATABASE} "
                f"user={cfg.PG_USER} password={cfg.PG_PASSWORD}"
            )
            with psycopg2.connect(dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
            logger.info("Postgres connection OK (%s:%s/%s)", cfg.PG_HOST, cfg.PG_PORT, cfg.PG_DATABASE)
        except Exception as e:
            logger.warning("Postgres check failed: %s", e)

    return True


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Run FSV Mainz 05 SQL Assistant server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--log-file", default=str(Path(__file__).parent / "logs" / "server.log"))
    args = parser.parse_args()

    setup_logging(Path(args.log_file))
    logger = logging.getLogger("run")

    logger.info("🏆 FSV Mainz 05 SQL Assistant")
    logger.info("Starting with host=%s port=%s reload=%s", args.host, args.port, args.reload)

    if not check_requirements():
        sys.exit(1)

    logger.info("Starting server at http://%s:%s", args.host, args.port)

    import uvicorn

    # Use import string for reload to work properly
    if args.reload:
        uvicorn.run(
            "backend.app:app",
            host=args.host,
            port=args.port,
            log_level="info",
            reload=True,
        )
    else:
        from backend.app import app
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            log_level="info",
            reload=False,
        )


if __name__ == "__main__":
    main()