#!/usr/bin/env python3
"""
Wendet Performance-Optimierungen auf die Datenbank an.

Erstellt Composite-Indizes für häufige Join-Patterns und aktualisiert
Tabellenstatistiken für bessere Query-Planung.

Usage:
    python apply_performance_indexes.py
"""

import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

load_dotenv()


def apply_indexes():
    """Erstelle alle Performance-Indizes."""
    
    indexes = [
        # Spieler-Queries
        ("idx_goals_player_match", "public.goals(player_id, match_id)", 
         "Tore pro Spieler und Spiel"),
        
        ("idx_lineups_player_match", "public.match_lineups(player_id, match_id)",
         "Einsätze pro Spieler"),
        
        ("idx_lineups_match_team", "public.match_lineups(match_id, team_id)",
         "Aufstellungen nach Mannschaft"),
        
        ("idx_cards_player_type", "public.cards(player_id, card_type)",
         "Karten pro Spieler nach Typ"),
        
        # Match-Queries
        ("idx_matches_season_date", "public.matches(season_competition_id, match_date)",
         "Spiele chronologisch pro Saison"),
        
        # Spielereignisse
        ("idx_goals_match_minute", "public.goals(match_id, minute)",
         "Tore chronologisch pro Spiel"),
        
        ("idx_cards_match_minute", "public.cards(match_id, minute)",
         "Karten chronologisch pro Spiel"),
        
        ("idx_subs_match_minute", "public.match_substitutions(match_id, minute)",
         "Einwechslungen chronologisch"),
        
        # Covering Indizes
        ("idx_players_id_covering", "public.players(player_id) INCLUDE (name, primary_position, nationality)",
         "Covering Index für Spieler-Lookups"),
        
        ("idx_teams_id_covering", "public.teams(team_id) INCLUDE (name, normalized_name)",
         "Covering Index für Team-Lookups"),
    ]
    
    # Partial Indizes für FSV Mainz
    partial_indexes = [
        ("idx_matches_fsv_home", 
         "public.matches(match_date, season_competition_id, home_score, away_score) WHERE home_team_id = 1",
         "Nur FSV Heimspiele"),
        
        ("idx_matches_fsv_away",
         "public.matches(match_date, season_competition_id, home_score, away_score) WHERE away_team_id = 1",
         "Nur FSV Auswärtsspiele"),
        
        ("idx_goals_fsv_team",
         "public.goals(player_id, match_id, minute) WHERE team_id = 1",
         "Nur FSV Tore"),
    ]
    
    print("=" * 80)
    print("PERFORMANCE-OPTIMIERUNG: INDIZES ERSTELLEN")
    print("=" * 80)
    print()
    
    conn = psycopg2.connect(os.getenv("DB_URL"))
    
    # Standard Indizes
    print("Erstelle Composite-Indizes:")
    print()
    
    for i, (index_name, definition, description) in enumerate(indexes, 1):
        with conn.cursor() as cur:
            sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {definition}"
            print(f"  [{i:2d}/{len(indexes)}] {index_name:35s}", end="")
            
            try:
                cur.execute(sql)
                conn.commit()
                print(f" ✓")
            except Exception as e:
                print(f" ⚠️  ({str(e)[:40]})")
    
    # Partial Indizes
    print()
    print("Erstelle Partial-Indizes (FSV-spezifisch):")
    print()
    
    for i, (index_name, definition, description) in enumerate(partial_indexes, 1):
        with conn.cursor() as cur:
            sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {definition}"
            print(f"  [{i}/{len(partial_indexes)}] {index_name:35s}", end="")
            
            try:
                cur.execute(sql)
                conn.commit()
                print(f" ✓")
            except Exception as e:
                print(f" ⚠️  ({str(e)[:40]})")
    
    # Aktualisiere Statistiken
    print()
    print("Aktualisiere Tabellenstatistiken:")
    print()
    
    tables_to_analyze = [
        'matches', 'players', 'goals', 'match_lineups', 
        'cards', 'teams', 'season_competitions', 'match_substitutions'
    ]
    
    for table in tables_to_analyze:
        with conn.cursor() as cur:
            print(f"  Analyzing {table:25s}", end="")
            try:
                cur.execute(f"ANALYZE public.{table}")
                conn.commit()
                print(" ✓")
            except Exception as e:
                print(f" ⚠️")
    
    conn.close()
    
    print()
    print("=" * 80)
    print("✅ OPTIMIERUNGEN ABGESCHLOSSEN")
    print("=" * 80)
    print()
    print(f"Composite-Indizes erstellt: {len(indexes)}")
    print(f"Partial-Indizes erstellt: {len(partial_indexes)}")
    print(f"Tabellen analyzed: {len(tables_to_analyze)}")
    print()
    print("Die Datenbank sollte nun deutlich schneller sein für:")
    print("  - Spielerstatistiken (Tore, Einsätze)")
    print("  - Saisonübersichten")
    print("  - Spieldetails mit Aufstellungen")
    print("  - Chronologische Abfragen")


def main():
    apply_indexes()


if __name__ == "__main__":
    main()



