#!/usr/bin/env python3
"""Debug script to analyze Europapokal matches for Mainz 05 in 2018-19"""
import psycopg2
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()
from backend.config import Config

config = Config()

# Verbinde zur Datenbank
conn = psycopg2.connect(config.build_psycopg2_dsn())

print("=" * 80)
print("DEBUG: Europapokal-Spiele für Mainz 05 in Saison 2018-19")
print("=" * 80)

with conn.cursor() as cur:
    # Query 1: Alle Europapokal-Spiele
    cur.execute("""
        WITH mainz_team_ids AS (
            SELECT team_id 
            FROM public.teams 
            WHERE (normalized_name LIKE '%mainz%' OR name ILIKE '%mainz%')
               OR (name ILIKE '%fsv%' AND (name ILIKE '%05%' OR name ILIKE '%mainz%'))
               OR name = 'FSV'
        )
        SELECT 
            s.label AS saison,
            c.name AS wettbewerb,
            m.match_date AS datum,
            t_home.name AS heimmannschaft,
            t_away.name AS gastmannschaft,
            m.home_score AS tore_heim,
            m.away_score AS tore_gast,
            CASE 
                WHEN m.home_team_id IN (SELECT team_id FROM mainz_team_ids) THEN 'Heim'
                WHEN m.away_team_id IN (SELECT team_id FROM mainz_team_ids) THEN 'Auswärts'
                ELSE 'Unbekannt'
            END AS spielort,
            CASE 
                WHEN (m.home_team_id IN (SELECT team_id FROM mainz_team_ids) AND m.home_score > m.away_score)
                  OR (m.away_team_id IN (SELECT team_id FROM mainz_team_ids) AND m.away_score > m.home_score)
                THEN 'Sieg'
                WHEN m.home_score = m.away_score THEN 'Unentschieden'
                ELSE 'Niederlage'
            END AS ergebnis,
            m.round_name AS runde,
            m.matchday AS spieltag
        FROM public.matches m
        JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
        JOIN public.seasons s ON sc.season_id = s.season_id
        JOIN public.competitions c ON sc.competition_id = c.competition_id
        JOIN public.teams t_home ON m.home_team_id = t_home.team_id
        JOIN public.teams t_away ON m.away_team_id = t_away.team_id
        WHERE (m.home_team_id IN (SELECT team_id FROM mainz_team_ids) 
            OR m.away_team_id IN (SELECT team_id FROM mainz_team_ids))
          AND s.label = '2018-19'
          AND c.name = 'Europapokal'
          AND m.home_score IS NOT NULL 
          AND m.away_score IS NOT NULL
        ORDER BY m.match_date, m.matchday;
    """)
    
    results = cur.fetchall()
    print(f"\nGefundene Europapokal-Spiele: {len(results)}")
    print("-" * 80)
    for row in results:
        print(f"Saison: {row[0]}, Wettbewerb: {row[1]}")
        print(f"Datum: {row[2]}, {row[7]} ({row[8]})")
        print(f"{row[3]} {row[5]} : {row[6]} {row[4]}")
        print(f"Runde: {row[9]}, Spieltag: {row[10]}")
        print()
    
    # Query 2: Alle Wettbewerbe für 2018-19
    print("\n" + "=" * 80)
    print("DEBUG: Alle Wettbewerbe für Mainz 05 in Saison 2018-19")
    print("=" * 80)
    
    cur.execute("""
        WITH mainz_team_ids AS (
            SELECT team_id 
            FROM public.teams 
            WHERE (normalized_name LIKE '%mainz%' OR name ILIKE '%mainz%')
               OR (name ILIKE '%fsv%' AND (name ILIKE '%05%' OR name ILIKE '%mainz%'))
               OR name = 'FSV'
        )
        SELECT 
            c.name AS wettbewerb,
            COUNT(*) AS spiele_gesamt,
            COUNT(DISTINCT m.match_date) AS verschiedene_spieltage,
            MIN(m.match_date) AS erstes_spiel,
            MAX(m.match_date) AS letztes_spiel,
            STRING_AGG(DISTINCT m.round_name, ', ' ORDER BY m.round_name) AS runden
        FROM public.matches m
        JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
        JOIN public.seasons s ON sc.season_id = s.season_id
        JOIN public.competitions c ON sc.competition_id = c.competition_id
        WHERE (m.home_team_id IN (SELECT team_id FROM mainz_team_ids) 
            OR m.away_team_id IN (SELECT team_id FROM mainz_team_ids))
          AND s.label = '2018-19'
          AND m.home_score IS NOT NULL 
          AND m.away_score IS NOT NULL
        GROUP BY c.name
        ORDER BY spiele_gesamt DESC;
    """)
    
    results2 = cur.fetchall()
    print(f"\nWettbewerbe mit Spielen:")
    print("-" * 80)
    for row in results2:
        print(f"Wettbewerb: {row[0]}")
        print(f"  Spiele gesamt: {row[1]}")
        print(f"  Verschiedene Spieltage: {row[2]}")
        print(f"  Erstes Spiel: {row[3]}")
        print(f"  Letztes Spiel: {row[4]}")
        print(f"  Runden: {row[5]}")
        print()
    
    # Query 3: Prüfe auch Spiele OHNE Ergebnis
    print("\n" + "=" * 80)
    print("DEBUG: Europapokal-Spiele OHNE Ergebnis (möglicherweise fehlende Daten)")
    print("=" * 80)
    
    cur.execute("""
        WITH mainz_team_ids AS (
            SELECT team_id 
            FROM public.teams 
            WHERE (normalized_name LIKE '%mainz%' OR name ILIKE '%mainz%')
               OR (name ILIKE '%fsv%' AND (name ILIKE '%05%' OR name ILIKE '%mainz%'))
               OR name = 'FSV'
        )
        SELECT 
            COUNT(*) AS spiele_ohne_ergebnis
        FROM public.matches m
        JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
        JOIN public.seasons s ON sc.season_id = s.season_id
        JOIN public.competitions c ON sc.competition_id = c.competition_id
        WHERE (m.home_team_id IN (SELECT team_id FROM mainz_team_ids) 
            OR m.away_team_id IN (SELECT team_id FROM mainz_team_ids))
          AND s.label = '2018-19'
          AND c.name = 'Europapokal'
          AND (m.home_score IS NULL OR m.away_score IS NULL);
    """)
    
    result3 = cur.fetchone()
    print(f"Spiele ohne Ergebnis: {result3[0] if result3 else 0}")
    
    # Query 4: Prüfe die Quelle der Europapokal-Spiele
    print("\n" + "=" * 80)
    print("ANALYSE: Quelle der falsch klassifizierten Europapokal-Spiele")
    print("=" * 80)
    
    cur.execute("""
        WITH mainz_team_ids AS (
            SELECT team_id 
            FROM public.teams 
            WHERE (normalized_name LIKE '%mainz%' OR name ILIKE '%mainz%')
               OR (name ILIKE '%fsv%' AND (name ILIKE '%05%' OR name ILIKE '%mainz%'))
               OR name = 'FSV'
        )
        SELECT 
            m.source_file,
            sc.source_path,
            COUNT(*) AS anzahl_spiele,
            STRING_AGG(DISTINCT t_home.name || ' vs ' || t_away.name, ', ') AS gegner
        FROM public.matches m
        JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
        JOIN public.seasons s ON sc.season_id = s.season_id
        JOIN public.competitions c ON sc.competition_id = c.competition_id
        JOIN public.teams t_home ON m.home_team_id = t_home.team_id
        JOIN public.teams t_away ON m.away_team_id = t_away.team_id
        WHERE (m.home_team_id IN (SELECT team_id FROM mainz_team_ids) 
            OR m.away_team_id IN (SELECT team_id FROM mainz_team_ids))
          AND s.label = '2018-19'
          AND c.name = 'Europapokal'
        GROUP BY m.source_file, sc.source_path
        ORDER BY anzahl_spiele DESC;
    """)
    
    results4 = cur.fetchall()
    print("\nQuellen der Europapokal-Spiele:")
    print("-" * 80)
    for row in results4:
        print(f"Source File: {row[0]}")
        print(f"Source Path: {row[1]}")
        print(f"Anzahl Spiele: {row[2]}")
        print(f"Gegner: {row[3]}")
        print()

conn.close()

print("\n" + "=" * 80)
print("FAZIT:")
print("=" * 80)
print("Die 3 'Europapokal'-Spiele sind KEINE echten Europapokal-Spiele!")
print("Es handelt sich um Freundschaftsspiele gegen lokale/regionale Teams:")
print("  - DJK Phönix Schifferstadt (lokaler Verein)")
print("  - Auswahl Rhein-Nahe (regionale Auswahl)")
print("  - VfB Ginsheim (lokaler Verein)")
print("\nDiese Spiele wurden fälschlicherweise als 'Europapokal' klassifiziert.")
print("Wahrscheinlich wurden sie aus einer Datei geparst, die 'profiuefa' oder")
print("ähnlich heißt, aber eigentlich Freundschaftsspiele enthält.")
print("\nLÖSUNG:")
print("1. Diese Spiele sollten als 'Freundschaftsspiele' oder 'Sonstige' klassifiziert werden")
print("2. Die Query sollte diese falsch klassifizierten Spiele herausfiltern")
print("3. Der Parser sollte verbessert werden, um solche Spiele korrekt zu erkennen")
print("=" * 80)

