#!/usr/bin/env python3
"""
Generate Cohere embeddings for players, teams, and coaches.

Uses Cohere's embed-v4.0 model to create 1024-dimensional embeddings
for semantic search and fuzzy name matching.

Usage:
    python database/generate_embeddings.py --dry-run
    python database/generate_embeddings.py
    python database/generate_embeddings.py --batch-size 50
"""

import argparse
import os
import sys
import time
from typing import List, Tuple
import cohere
import psycopg2
from dotenv import load_dotenv

load_dotenv()

POSTGRES_URL = "postgresql://neondb_owner:npg_TUR24rnpzgGf@ep-muddy-scene-a9tpn6pu-pooler.gwc.azure.neon.tech/neondb?sslmode=require"


class EmbeddingGenerator:
    """Generate and store Cohere embeddings for names."""

    def __init__(self, dry_run: bool = False, batch_size: int = 50):
        self.dry_run = dry_run
        self.batch_size = min(batch_size, 96)  # Cohere max is 96

        # Initialize Cohere client
        api_key = os.getenv("COHERE_API_KEY")
        if not api_key:
            raise ValueError("COHERE_API_KEY not found in environment")

        self.cohere_client = cohere.ClientV2(api_key=api_key)

        # Initialize Postgres connection
        self.pg_conn = psycopg2.connect(POSTGRES_URL)

        # Statistics
        self.stats = {
            'players_processed': 0,
            'teams_processed': 0,
            'coaches_processed': 0,
            'api_calls': 0,
            'errors': 0
        }

    def close(self):
        """Close database connection."""
        self.pg_conn.close()

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings from Cohere API."""
        if not texts:
            return []

        try:
            response = self.cohere_client.embed(
                texts=texts,
                model="embed-v4.0",
                input_type="search_document",
                embedding_types=["float"]
            )
            self.stats['api_calls'] += 1
            return [emb for emb in response.embeddings.float_]
        except Exception as e:
            print(f"  ERROR getting embeddings: {e}")
            self.stats['errors'] += 1
            return []

    def generate_player_embeddings(self):
        """Generate embeddings for all players without them."""
        print("\n" + "=" * 60)
        print("Generating player embeddings...")

        with self.pg_conn.cursor() as cur:
            # Get players without embeddings
            cur.execute("""
                SELECT player_id, name
                FROM players
                WHERE name_embedding IS NULL
                ORDER BY player_id
            """)
            players = cur.fetchall()

        if not players:
            print("  All players already have embeddings")
            return

        print(f"  Found {len(players)} players without embeddings")

        if self.dry_run:
            print(f"  Would generate embeddings for {len(players)} players")
            self.stats['players_processed'] = len(players)
            return

        # Process in batches
        for i in range(0, len(players), self.batch_size):
            batch = players[i:i + self.batch_size]
            player_ids = [p[0] for p in batch]
            names = [p[1] for p in batch]

            embeddings = self.get_embeddings(names)

            if embeddings:
                with self.pg_conn.cursor() as cur:
                    for player_id, embedding in zip(player_ids, embeddings):
                        cur.execute(
                            "UPDATE players SET name_embedding = %s WHERE player_id = %s",
                            (embedding, player_id)
                        )
                self.pg_conn.commit()
                self.stats['players_processed'] += len(embeddings)

            # Progress
            processed = min(i + self.batch_size, len(players))
            print(f"  Progress: {processed}/{len(players)} players", end='\r')

            # Rate limiting
            time.sleep(0.1)

        print(f"\n  Completed: {self.stats['players_processed']} player embeddings")

    def generate_team_embeddings(self):
        """Generate embeddings for all teams without them."""
        print("\n" + "=" * 60)
        print("Generating team embeddings...")

        with self.pg_conn.cursor() as cur:
            cur.execute("""
                SELECT team_id, name
                FROM teams
                WHERE name_embedding IS NULL
                ORDER BY team_id
            """)
            teams = cur.fetchall()

        if not teams:
            print("  All teams already have embeddings")
            return

        print(f"  Found {len(teams)} teams without embeddings")

        if self.dry_run:
            print(f"  Would generate embeddings for {len(teams)} teams")
            self.stats['teams_processed'] = len(teams)
            return

        # Process in batches
        for i in range(0, len(teams), self.batch_size):
            batch = teams[i:i + self.batch_size]
            team_ids = [t[0] for t in batch]
            names = [t[1] for t in batch]

            embeddings = self.get_embeddings(names)

            if embeddings:
                with self.pg_conn.cursor() as cur:
                    for team_id, embedding in zip(team_ids, embeddings):
                        cur.execute(
                            "UPDATE teams SET name_embedding = %s WHERE team_id = %s",
                            (embedding, team_id)
                        )
                self.pg_conn.commit()
                self.stats['teams_processed'] += len(embeddings)

            processed = min(i + self.batch_size, len(teams))
            print(f"  Progress: {processed}/{len(teams)} teams", end='\r')
            time.sleep(0.1)

        print(f"\n  Completed: {self.stats['teams_processed']} team embeddings")

    def generate_coach_embeddings(self):
        """Generate embeddings for all coaches without them."""
        print("\n" + "=" * 60)
        print("Generating coach embeddings...")

        with self.pg_conn.cursor() as cur:
            cur.execute("""
                SELECT coach_id, name
                FROM coaches
                WHERE name_embedding IS NULL
                ORDER BY coach_id
            """)
            coaches = cur.fetchall()

        if not coaches:
            print("  All coaches already have embeddings")
            return

        print(f"  Found {len(coaches)} coaches without embeddings")

        if self.dry_run:
            print(f"  Would generate embeddings for {len(coaches)} coaches")
            self.stats['coaches_processed'] = len(coaches)
            return

        # Process in batches
        for i in range(0, len(coaches), self.batch_size):
            batch = coaches[i:i + self.batch_size]
            coach_ids = [c[0] for c in batch]
            names = [c[1] for c in batch]

            embeddings = self.get_embeddings(names)

            if embeddings:
                with self.pg_conn.cursor() as cur:
                    for coach_id, embedding in zip(coach_ids, embeddings):
                        cur.execute(
                            "UPDATE coaches SET name_embedding = %s WHERE coach_id = %s",
                            (embedding, coach_id)
                        )
                self.pg_conn.commit()
                self.stats['coaches_processed'] += len(embeddings)

            processed = min(i + self.batch_size, len(coaches))
            print(f"  Progress: {processed}/{len(coaches)} coaches", end='\r')
            time.sleep(0.1)

        print(f"\n  Completed: {self.stats['coaches_processed']} coach embeddings")

    def create_vector_indexes(self):
        """Create HNSW indexes for fast similarity search."""
        print("\n" + "=" * 60)
        print("Creating vector similarity indexes...")

        if self.dry_run:
            print("  Would create HNSW indexes for players, teams, coaches")
            return

        with self.pg_conn.cursor() as cur:
            # Players index
            print("  Creating players HNSW index...")
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_players_embedding_hnsw
                ON players
                USING hnsw (name_embedding vector_cosine_ops)
            """)

            # Teams index
            print("  Creating teams HNSW index...")
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_teams_embedding_hnsw
                ON teams
                USING hnsw (name_embedding vector_cosine_ops)
            """)

            # Coaches index
            print("  Creating coaches HNSW index...")
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_coaches_embedding_hnsw
                ON coaches
                USING hnsw (name_embedding vector_cosine_ops)
            """)

        self.pg_conn.commit()
        print("  Vector indexes created successfully")

    def run(self):
        """Run complete embedding generation."""
        print("=" * 70)
        print("COHERE EMBEDDING GENERATION")
        print("=" * 70)

        if self.dry_run:
            print("\n*** DRY RUN MODE ***\n")

        self.generate_player_embeddings()
        self.generate_team_embeddings()
        self.generate_coach_embeddings()
        self.create_vector_indexes()

        # Summary
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"  Players:    {self.stats['players_processed']:>6,} embeddings")
        print(f"  Teams:      {self.stats['teams_processed']:>6,} embeddings")
        print(f"  Coaches:    {self.stats['coaches_processed']:>6,} embeddings")
        print(f"  API calls:  {self.stats['api_calls']:>6,}")
        print(f"  Errors:     {self.stats['errors']:>6,}")

        total = (self.stats['players_processed'] +
                 self.stats['teams_processed'] +
                 self.stats['coaches_processed'])
        print(f"\n  TOTAL:      {total:>6,} embeddings generated")


def main():
    parser = argparse.ArgumentParser(description="Generate Cohere embeddings")
    parser.add_argument("--dry-run", action="store_true", help="Preview without generating")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size (max 96)")
    args = parser.parse_args()

    generator = EmbeddingGenerator(dry_run=args.dry_run, batch_size=args.batch_size)

    try:
        generator.run()
    finally:
        generator.close()


if __name__ == "__main__":
    main()
