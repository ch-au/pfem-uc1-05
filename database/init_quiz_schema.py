"""
Initialize quiz database schema
Run this script to create the quiz tables in Postgres
"""
import psycopg2
from pathlib import Path
from config import Config


def init_quiz_schema():
    """Create quiz tables in Postgres database"""
    config = Config()
    
    if not config.PG_ENABLED:
        raise RuntimeError("Postgres is required. Set PG_ENABLED=true or configure DB_URL environment variable.")
    
    schema_path = Path(__file__).parent.parent / "database" / "quiz_schema.sql"
    
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    
    schema_sql = schema_path.read_text()
    
    dsn = config.build_psycopg2_dsn()
    
    print("Connecting to database...")
    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            print("Creating quiz schema...")
            cur.execute(schema_sql)
            conn.commit()
            print("✓ Quiz schema created successfully!")
            
            # Verify tables were created
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name LIKE 'quiz_%' OR table_name LIKE 'chat_%'
                ORDER BY table_name;
            """)
            tables = [row[0] for row in cur.fetchall()]
            print(f"\nCreated tables: {', '.join(tables)}")


if __name__ == "__main__":
    init_quiz_schema()




