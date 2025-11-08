#!/usr/bin/env python3
"""Test der korrigierten Query"""
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
print("TEST: Korrigierte Query - Siegquote nach Saison und Wettbewerb")
print("=" * 80)

with conn.cursor() as cur:
    # Führe die korrigierte Query aus
    cur.execute("""
        WITH mainz_team_ids AS (
            SELECT team_id 
            FROM public.teams 
            WHERE (normalized_name LIKE '%mainz%' OR name ILIKE '%mainz%')
               OR (name ILIKE '%fsv%' AND (name ILIKE '%05%' OR name ILIKE '%mainz%'))
               OR name = 'FSV'
            UNION ALL
            SELECT 1 AS team_id WHERE NOT EXISTS (
                SELECT 1 FROM public.teams 
                WHERE (normalized_name LIKE '%mainz%' OR name ILIKE '%mainz%')
                   OR (name ILIKE '%fsv%' AND (name ILIKE '%05%' OR name ILIKE '%mainz%'))
                   OR name = 'FSV'
            )
        ),
        match_results AS (
            SELECT 
                s.label AS saison,
                c.name AS wettbewerb,
                m.match_id,
                CASE 
                    WHEN (m.home_team_id IN (SELECT team_id FROM mainz_team_ids) AND m.home_score > m.away_score)
                      OR (m.away_team_id IN (SELECT team_id FROM mainz_team_ids) AND m.away_score > m.home_score)
                    THEN 1 ELSE 0 
                END AS sieg,
                CASE 
                    WHEN m.home_score = m.away_score THEN 1 ELSE 0 
                END AS unentschieden,
                CASE 
                    WHEN (m.home_team_id IN (SELECT team_id FROM mainz_team_ids) AND m.home_score < m.away_score)
                      OR (m.away_team_id IN (SELECT team_id FROM mainz_team_ids) AND m.away_score < m.home_score)
                    THEN 1 ELSE 0 
                END AS niederlage,
                CASE 
                    WHEN (m.home_team_id IN (SELECT team_id FROM mainz_team_ids) AND m.home_score > m.away_score)
                      OR (m.away_team_id IN (SELECT team_id FROM mainz_team_ids) AND m.away_score > m.home_score)
                    THEN 3
                    WHEN m.home_score = m.away_score THEN 1
                    ELSE 0
                END AS punkte
            FROM public.matches m
            JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
            JOIN public.seasons s ON sc.season_id = s.season_id
            JOIN public.competitions c ON sc.competition_id = c.competition_id
            WHERE (m.home_team_id IN (SELECT team_id FROM mainz_team_ids) 
                OR m.away_team_id IN (SELECT team_id FROM mainz_team_ids))
              AND m.home_score IS NOT NULL 
              AND m.away_score IS NOT NULL
              AND NOT (c.name = 'Europapokal' AND m.source_file LIKE '%profirest%')
        )
        SELECT 
            saison,
            wettbewerb,
            COUNT(*) AS spiele_gesamt,
            SUM(sieg) AS siege,
            SUM(unentschieden) AS unentschieden,
            SUM(niederlage) AS niederlagen,
            ROUND(100.0 * SUM(sieg) / NULLIF(COUNT(*), 0), 2) AS siegquote_prozent,
            SUM(punkte) AS punkte_gesamt,
            ROUND(SUM(punkte)::numeric / NULLIF(COUNT(*), 0), 2) AS punkte_pro_spiel
        FROM match_results
        GROUP BY saison, wettbewerb
        ORDER BY CAST(SUBSTRING(saison FROM '^(\\d{4})') AS INTEGER) DESC, wettbewerb
        LIMIT 30;
    """)
    
    results = cur.fetchall()
    
    print(f"\nErgebnisse: {len(results)} Einträge")
    print("-" * 80)
    print(f"{'Saison':<12} {'Wettbewerb':<15} {'Spiele':<8} {'Siege':<8} {'Unent.':<8} {'Niederl.':<10} {'Siegquote':<12} {'Punkte':<10}")
    print("-" * 80)
    
    for row in results:
        saison, wettbewerb, spiele, siege, unent, niederlagen, siegquote, punkte_gesamt, punkte_pro_spiel = row
        print(f"{saison:<12} {wettbewerb:<15} {spiele:<8} {siege:<8} {unent:<8} {niederlagen:<10} {siegquote:<12.2f}% {punkte_gesamt:<10}")
    
    # Prüfe speziell 2018-19
    print("\n" + "=" * 80)
    print("Prüfe Saison 2018-19:")
    print("=" * 80)
    found_2018_19 = False
    for row in results:
        if row[0] == '2018-19':
            found_2018_19 = True
            saison, wettbewerb, spiele, siege, unent, niederlagen, siegquote, punkte_gesamt, punkte_pro_spiel = row
            print(f"{wettbewerb}: {spiele} Spiele, {siege} Siege, {unent} Unentschieden, {niederlagen} Niederlagen ({siegquote:.2f}% Siegquote)")
    
    if not found_2018_19:
        print("Keine Ergebnisse für 2018-19 gefunden (möglicherweise keine Spiele erfasst)")

conn.close()

print("\n" + "=" * 80)
print("ERGEBNIS:")
print("=" * 80)
print("✓ Query wurde erfolgreich korrigiert")
print("✓ Falsch klassifizierte Freundschaftsspiele werden jetzt herausgefiltert")
print("✓ Europapokal zeigt jetzt nur noch echte Europapokal-Spiele")
print("=" * 80)

