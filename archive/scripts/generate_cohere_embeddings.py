#!/usr/bin/env python3
"""
Generate and store Cohere embeddings for player and team names.

Uses Cohere's embed-v4.0 model to create 1024-dimensional embeddings
for fuzzy name matching and similarity search.

Usage:
    python generate_cohere_embeddings.py
    python generate_cohere_embeddings.py --batch-size 96
    python generate_cohere_embeddings.py --dry-run
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


class CohereEmbeddingGenerator:
    """Generate and store Cohere embeddings for names."""
    
    def __init__(self, dry_run: bool = False, batch_size: int = 96):
        self.dry_run = dry_run
        self.batch_size = min(batch_size, 96)  # Cohere max is 96
        
        # Initialize Cohere client
        api_key = os.getenv("COHERE_API_KEY")
        if not api_key:
            raise ValueError("COHERE_API_KEY not found in .env file")
        
        self.cohere_client = cohere.ClientV2(api_key=api_key)
        
        # Initialize Postgres connection
        db_url = os.getenv("DB_URL")
        if not db_url:
            raise ValueError("DB_URL not found in .env file")
        
        self.pg_conn = psycopg2.connect(db_url)
        
        # Statistics
        self.stats = {
            'players_processed': 0,
            'teams_processed': 0,
            'api_calls': 0,
            'total_tokens': 0
        }
    
    def close(self):
        """Close database connection."""
        self.pg_conn.close()
    
    def ensure_schema(self):
        """Ensure pgvector extension and embedding columns exist."""
        print("Setting up database schema...")
        
        with self.pg_conn.cursor() as cur:
            # Enable vector extension
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            
            # Add embedding columns if they don't exist
            cur.execute("""
                ALTER TABLE public.players 
                ADD COLUMN IF NOT EXISTS name_embedding vector(1024)
            """)
            
            cur.execute("""
                ALTER TABLE public.teams 
                ADD COLUMN IF NOT EXISTS name_embedding vector(1024)
            """)
        
        self.pg_conn.commit()
        print("  ✓ pgvector extension enabled")
        print("  ✓ Embedding columns added to players and teams")
    
    def create_indexes(self):
        """Create vector similarity indexes."""
        print("\nCreating vector similarity indexes...")
        
        with self.pg_conn.cursor() as cur:
            # HNSW indexes for efficient similarity search
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_players_name_embedding_hnsw 
                ON public.players 
                USING hnsw (name_embedding vector_cosine_ops)
            """)
            
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_teams_name_embedding_hnsw 
                ON public.teams 
                USING hnsw (name_embedding vector_cosine_ops)
            """)
        
        self.pg_conn.commit()
        print("  ✓ Created HNSW indexes for similarity search")
    
    def fetch_players(self) -> List[Tuple[int, str]]:
        """Fetch all players that need embeddings."""
        with self.pg_conn.cursor() as cur:
            cur.execute("""
                SELECT player_id, name 
                FROM public.players 
                WHERE name IS NOT NULL
                ORDER BY player_id
            """)
            return cur.fetchall()
    
    def fetch_teams(self) -> List[Tuple[int, str]]:
        """Fetch all teams that need embeddings."""
        with self.pg_conn.cursor() as cur:
            cur.execute("""
                SELECT team_id, name 
                FROM public.teams 
                WHERE name IS NOT NULL
                ORDER BY team_id
            """)
            return cur.fetchall()
    
    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a batch of texts using Cohere."""
        try:
            response = self.cohere_client.embed(
                texts=texts,
                model="embed-v4.0",
                input_type="search_document",  # For storing in database
                embedding_types=["float"],
                output_dimension=1024
            )
            
            self.stats['api_calls'] += 1
            
            # Extract float embeddings
            embeddings = response.embeddings.float_
            return embeddings
            
        except Exception as e:
            print(f"  ❌ Error generating embeddings: {e}")
            raise
    
    def update_player_embeddings(self, player_ids: List[int], embeddings: List[List[float]]):
        """Update player embeddings in database."""
        if self.dry_run:
            return
        
        with self.pg_conn.cursor() as cur:
            for player_id, embedding in zip(player_ids, embeddings):
                # Convert embedding to pgvector format
                vec_str = '[' + ','.join(str(x) for x in embedding) + ']'
                
                cur.execute("""
                    UPDATE public.players 
                    SET name_embedding = %s::vector
                    WHERE player_id = %s
                """, (vec_str, player_id))
        
        self.pg_conn.commit()
    
    def update_team_embeddings(self, team_ids: List[int], embeddings: List[List[float]]):
        """Update team embeddings in database."""
        if self.dry_run:
            return
        
        with self.pg_conn.cursor() as cur:
            for team_id, embedding in zip(team_ids, embeddings):
                # Convert embedding to pgvector format
                vec_str = '[' + ','.join(str(x) for x in embedding) + ']'
                
                cur.execute("""
                    UPDATE public.teams 
                    SET name_embedding = %s::vector
                    WHERE team_id = %s
                """, (vec_str, team_id))
        
        self.pg_conn.commit()
    
    def process_players(self):
        """Generate and store embeddings for all players."""
        print("\nProcessing player names...")
        
        players = self.fetch_players()
        total = len(players)
        print(f"  Found {total:,} players to process")
        
        if self.dry_run:
            print(f"  [DRY RUN] Would generate embeddings in {(total + self.batch_size - 1) // self.batch_size} batches")
            return
        
        # Process in batches
        for i in range(0, total, self.batch_size):
            batch = players[i:i + self.batch_size]
            batch_ids = [p[0] for p in batch]
            batch_names = [p[1] for p in batch]
            
            print(f"  Processing batch {i // self.batch_size + 1}/{(total + self.batch_size - 1) // self.batch_size} ({len(batch)} players)...", end="")
            
            # Generate embeddings
            embeddings = self.generate_embeddings_batch(batch_names)
            
            # Update database
            self.update_player_embeddings(batch_ids, embeddings)
            
            self.stats['players_processed'] += len(batch)
            print(f" ✓")
            
            # Rate limiting: small delay between batches
            if i + self.batch_size < total:
                time.sleep(0.1)
        
        print(f"  ✓ Completed {self.stats['players_processed']:,} players")
    
    def process_teams(self):
        """Generate and store embeddings for all teams."""
        print("\nProcessing team names...")
        
        teams = self.fetch_teams()
        total = len(teams)
        print(f"  Found {total} teams to process")
        
        if self.dry_run:
            print(f"  [DRY RUN] Would generate embeddings in {(total + self.batch_size - 1) // self.batch_size} batches")
            return
        
        # Process in batches (teams will likely fit in 1-2 batches)
        for i in range(0, total, self.batch_size):
            batch = teams[i:i + self.batch_size]
            batch_ids = [t[0] for t in batch]
            batch_names = [t[1] for t in batch]
            
            print(f"  Processing batch {i // self.batch_size + 1}/{(total + self.batch_size - 1) // self.batch_size} ({len(batch)} teams)...", end="")
            
            # Generate embeddings
            embeddings = self.generate_embeddings_batch(batch_names)
            
            # Update database
            self.update_team_embeddings(batch_ids, embeddings)
            
            self.stats['teams_processed'] += len(batch)
            print(f" ✓")
            
            # Rate limiting
            if i + self.batch_size < total:
                time.sleep(0.1)
        
        print(f"  ✓ Completed {self.stats['teams_processed']} teams")
    
    def verify_embeddings(self):
        """Verify embeddings were stored correctly."""
        print("\nVerifying embeddings...")
        
        with self.pg_conn.cursor() as cur:
            # Check players
            cur.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(name_embedding) as with_embeddings
                FROM public.players
            """)
            p_total, p_with_emb = cur.fetchone()
            
            # Check teams
            cur.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(name_embedding) as with_embeddings
                FROM public.teams
            """)
            t_total, t_with_emb = cur.fetchone()
        
        print(f"  Players: {p_with_emb:,} / {p_total:,} have embeddings ({100*p_with_emb/p_total:.1f}%)")
        print(f"  Teams: {t_with_emb} / {t_total} have embeddings ({100*t_with_emb/t_total:.1f}%)")
        
        if p_with_emb == p_total and t_with_emb == t_total:
            print("  ✅ All entities have embeddings!")
        else:
            print(f"  ⚠️  Some entities missing embeddings")
    
    def run(self):
        """Run complete embedding generation process."""
        print("=" * 80)
        print("COHERE EMBEDDING GENERATION - embed-v4.0")
        print("=" * 80)
        if self.dry_run:
            print("MODE: DRY RUN\n")
        else:
            print("MODE: LIVE\n")
        
        # Setup
        if not self.dry_run:
            self.ensure_schema()
        
        # Process entities
        self.process_players()
        self.process_teams()
        
        # Create indexes
        if not self.dry_run:
            self.create_indexes()
            self.verify_embeddings()
        
        # Print summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Players processed: {self.stats['players_processed']:,}")
        print(f"Teams processed: {self.stats['teams_processed']}")
        print(f"API calls made: {self.stats['api_calls']}")
        print("=" * 80)
        
        if self.dry_run:
            print("DRY RUN COMPLETE")
        else:
            print("✅ EMBEDDINGS GENERATED SUCCESSFULLY")
        print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Generate Cohere embeddings for players and teams")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--batch-size", type=int, default=96, help="Batch size (max 96)")
    args = parser.parse_args()
    
    try:
        generator = CohereEmbeddingGenerator(dry_run=args.dry_run, batch_size=args.batch_size)
        generator.run()
        generator.close()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()



