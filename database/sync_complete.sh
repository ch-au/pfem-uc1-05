#!/bin/bash
#
# Complete SQLite to PostgreSQL sync for FSV Mainz 05 Archive
#
# This script exports the complete SQLite database and imports it to PostgreSQL (Neon)
# It handles all data including the new profirest matches and enriched coach names.
#
# Usage:
#   export DATABASE_URL="postgresql://neondb_owner:npg_DMd2QfUZJmy1@ep-steep-voice-a9u47j2b-pooler.gwc.azure.neon.tech/neondb?sslmode=require"
#   bash database/sync_complete.sh

set -e  # Exit on error

SQLITE_DB="fsv_archive_complete.db"
BACKUP_DIR="database/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "========================================================================"
echo "FSV MAINZ 05 ARCHIVE - COMPLETE POSTGRESQL SYNC"
echo "========================================================================"
echo ""

# Check prerequisites
if [ -z "$DATABASE_URL" ]; then
    echo "❌ ERROR: DATABASE_URL environment variable not set"
    echo "   Please set it to your PostgreSQL connection string"
    exit 1
fi

if [ ! -f "$SQLITE_DB" ]; then
    echo "❌ ERROR: SQLite database not found: $SQLITE_DB"
    exit 1
fi

echo "📊 Database Statistics:"
echo "   SQLite DB: $SQLITE_DB ($(du -h $SQLITE_DB | cut -f1))"
sqlite3 $SQLITE_DB "SELECT '   Matches: ' || COUNT(*) FROM matches;"
sqlite3 $SQLITE_DB "SELECT '   Players: ' || COUNT(*) || ' (' || SUM(CASE WHEN name LIKE '% %' THEN 1 ELSE 0 END) || ' with full names)' FROM players;"
sqlite3 $SQLITE_DB "SELECT '   Coaches: ' || COUNT(*) || ' (' || SUM(CASE WHEN name LIKE '% %' THEN 1 ELSE 0 END) || ' with full names)' FROM coaches;"
sqlite3 $SQLITE_DB "SELECT '   Teams: ' || COUNT(*) FROM teams;"
sqlite3 $SQLITE_DB "SELECT '   Profirest: ' || COUNT(*) || ' matches' FROM matches WHERE source_file LIKE '%profirest%';"
echo ""

# Create backup directory
mkdir -p $BACKUP_DIR

echo "📦 Step 1: Exporting SQLite data to SQL dump..."
sqlite3 $SQLITE_DB .dump > $BACKUP_DIR/fsv_archive_${TIMESTAMP}.sql
echo "   ✓ Exported to: $BACKUP_DIR/fsv_archive_${TIMESTAMP}.sql"

echo ""
echo "🔄 Step 2: Converting SQLite SQL to PostgreSQL format..."

# Create PostgreSQL-compatible dump
cat > $BACKUP_DIR/fsv_archive_postgres_${TIMESTAMP}.sql << 'HEADER'
-- FSV Mainz 05 Archive - PostgreSQL Import
-- Generated from SQLite database
-- Contains complete match archive including profirest matches

BEGIN;

-- Drop existing data (if any)
TRUNCATE TABLE match_notes, cards, goals, match_substitutions, match_lineups,
                match_referees, match_coaches, matches, season_squads,
                coach_careers, player_careers, player_aliases, season_competitions,
                coaches, players, referees, seasons, competitions, teams
                CASCADE;

HEADER

# Convert SQLite dump to PostgreSQL
# Remove SQLite-specific commands and convert syntax
sed -E \
    -e '/^BEGIN TRANSACTION;/d' \
    -e '/^COMMIT;/d' \
    -e '/^PRAGMA/d' \
    -e '/^CREATE TABLE sqlite_sequence/,/;/d' \
    -e '/INSERT INTO "sqlite_sequence"/d' \
    -e 's/AUTOINCREMENT/SERIAL/g' \
    -e 's/INTEGER PRIMARY KEY/SERIAL PRIMARY KEY/g' \
    -e 's/UNIQUE//g' \
    $BACKUP_DIR/fsv_archive_${TIMESTAMP}.sql | \
    grep -v "^CREATE TABLE" >> $BACKUP_DIR/fsv_archive_postgres_${TIMESTAMP}.sql

echo "COMMIT;" >> $BACKUP_DIR/fsv_archive_postgres_${TIMESTAMP}.sql

echo "   ✓ PostgreSQL dump created: $BACKUP_DIR/fsv_archive_postgres_${TIMESTAMP}.sql"

echo ""
echo "⚠️  MANUAL SYNC REQUIRED"
echo ""
echo "Due to schema differences between SQLite and PostgreSQL, manual import is recommended:"
echo ""
echo "1. Review the PostgreSQL schema in your Neon database"
echo "2. Adjust column names (id vs *_id) as needed"
echo "3. Use the CSV export method for safer import:"
echo ""
echo "   # Export from SQLite to CSV"
echo "   sqlite3 $SQLITE_DB -csv -header 'SELECT * FROM matches' > matches.csv"
echo "   sqlite3 $SQLITE_DB -csv -header 'SELECT * FROM players' > players.csv"
echo "   sqlite3 $SQLITE_DB -csv -header 'SELECT * FROM coaches' > coaches.csv"
echo ""
echo "   # Import to PostgreSQL"
echo "   psql \$DATABASE_URL -c \"\\COPY matches FROM 'matches.csv' CSV HEADER\""
echo "   psql \$DATABASE_URL -c \"\\COPY players FROM 'players.csv' CSV HEADER\""
echo "   psql \$DATABASE_URL -c \"\\COPY coaches FROM 'coaches.csv' CSV HEADER\""
echo ""
echo "4. Or use the Python sync script:"
echo "   python database/sync_to_postgres.py --dry-run"
echo "   python database/sync_to_postgres.py"
echo ""
echo "✅ SQLite database is ready for sync!"
echo "   Location: $SQLITE_DB"
echo "   Backup: $BACKUP_DIR/fsv_archive_${TIMESTAMP}.sql"
