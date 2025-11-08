#!/usr/bin/env python3
"""
Compute and upsert name embeddings (players, opponents) into Postgres table public.name_embeddings.
Falls back to reading names from SQLite if Postgres unavailable.
"""

import json
import math
import sqlite3
from pathlib import Path
from typing import Iterable, List, Tuple

import psycopg2
from langchain_openai import OpenAIEmbeddings

from config import Config


def fetch_names_pg(cfg: Config) -> Tuple[List[Tuple[str, int, str]], List[Tuple[str, int, str]]]:
    players: List[Tuple[str, int, str]] = []
    opponents: List[Tuple[str, int, str]] = []
    with psycopg2.connect(cfg.build_psycopg2_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT player_id, player_name FROM public.Players ORDER BY player_id")
            for pid, name in cur.fetchall():
                players.append(("player", int(pid), name))
        with conn.cursor() as cur:
            cur.execute("SELECT opponent_id, opponent_name FROM public.Opponents ORDER BY opponent_id")
            for oid, name in cur.fetchall():
                opponents.append(("opponent", int(oid), name))
    return players, opponents


def fetch_names_sqlite(sqlite_path: Path) -> Tuple[List[Tuple[str, int, str]], List[Tuple[str, int, str]]]:
    players: List[Tuple[str, int, str]] = []
    opponents: List[Tuple[str, int, str]] = []
    conn = sqlite3.connect(str(sqlite_path))
    try:
        cur = conn.cursor()
        try:
            for pid, name in cur.execute("SELECT player_id, player_name FROM Players ORDER BY player_id").fetchall():
                players.append(("player", int(pid), name))
        except Exception:
            pass
        try:
            for oid, name in cur.execute("SELECT opponent_id, opponent_name FROM Opponents ORDER BY opponent_id").fetchall():
                opponents.append(("opponent", int(oid), name))
        except Exception:
            pass
    finally:
        conn.close()
    return players, opponents


def ensure_vector_extension(cfg: Config) -> None:
    with psycopg2.connect(cfg.build_psycopg2_dsn()) as conn, conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {cfg.PG_SCHEMA}.name_embeddings (
                kind TEXT NOT NULL,
                entity_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                embedding vector({cfg.OPENAI_EMBEDDING_DIM}),
                PRIMARY KEY(kind, entity_id)
            );
            """
        )


def upsert_embeddings(cfg: Config, rows: List[Tuple[str, int, str, List[float]]]) -> None:
    with psycopg2.connect(cfg.build_psycopg2_dsn()) as conn:
        with conn.cursor() as cur:
            for kind, entity_id, name, vec in rows:
                if not vec:
                    continue
                vec_lit = '[' + ','.join(str(x) for x in vec) + ']'
                cur.execute(
                    f"""
                    INSERT INTO {cfg.PG_SCHEMA}.name_embeddings (kind, entity_id, name, embedding)
                    VALUES (%s, %s, %s, %s::vector)
                    ON CONFLICT (kind, entity_id) DO UPDATE SET name = EXCLUDED.name, embedding = EXCLUDED.embedding;
                    """,
                    (kind, entity_id, name, vec_lit),
                )


def chunked(iterable: Iterable, size: int):
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def main():
    cfg = Config()
    ensure_vector_extension(cfg)
    embedder = OpenAIEmbeddings(api_key=cfg.OPENAI_API_KEY, model=cfg.OPENAI_EMBEDDING_MODEL)

    players: List[Tuple[str, int, str]] = []
    opponents: List[Tuple[str, int, str]] = []
    try:
        p, o = fetch_names_pg(cfg)
        players.extend(p)
        opponents.extend(o)
    except Exception:
        # Fallback to SQLite
        if cfg.DATABASE_PATH.exists():
            p, o = fetch_names_sqlite(cfg.DATABASE_PATH)
            players.extend(p)
            opponents.extend(o)

    all_rows = players + opponents
    if not all_rows:
        print("No names found to embed.")
        return

    for batch in chunked(all_rows, 128):
        names = [name for _, _, name in batch]
        vecs = embedder.embed_documents(names)
        rows = [(kind, ent_id, name, vec) for (kind, ent_id, name), vec in zip(batch, vecs)]
        upsert_embeddings(cfg, rows)

    print(f"Upserted embeddings for {len(all_rows)} names.")


if __name__ == "__main__":
    main()



