#!/usr/bin/env python3
"""Verifikation der korrigierten Daten"""
import psycopg2
import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()
from backend.config import Config

config = Config()
conn = psycopg2.connect(config.build_psycopg2_dsn())

print("=" * 80)
print("VERIFIKATION: Prüfe korrigierte Daten")
print("=" * 80)

with conn.cursor() as cur:
    # Prüfe 2018-19
    cur.execute("""
        SELECT 
            c.name AS wettbewerb,
            COUNT(*) AS spiele
        FROM public.matches m
        JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
        JOIN public.seasons s ON sc.season_id = s.season_id
        JOIN public.competitions c ON sc.competition_id = c.competition_id
        WHERE s.label = '2018-19'
          AND (m.home_team_id = 1 OR m.away_team_id = 1)
          AND m.home_score IS NOT NULL
        GROUP BY c.name
        ORDER BY c.name;
    """)
    
    results = cur.fetchall()
    print("\nSaison 2018-19 - Wettbewerbe:")
    for row in results:
        print(f"  {row[0]}: {row[1]} Spiele")
    
    # Prüfe ob noch falsch klassifizierte Europapokal-Spiele existieren
    cur.execute("""
        SELECT COUNT(*) 
        FROM public.matches m
        JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
        JOIN public.competitions c ON sc.competition_id = c.competition_id
        WHERE c.name = 'Europapokal'
          AND m.source_file LIKE '%profirest%'
    """)
    
    result = cur.fetchone()
    print(f"\nNoch falsch klassifizierte Europapokal-Spiele: {result[0] if result else 0}")

conn.close()

