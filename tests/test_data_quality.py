#!/usr/bin/env python3
"""
Test-Script zur Validierung der Datenqualität nach Parsing.

Prüft:
- Abdeckung von Spielen pro Saison
- Anzahl Spieler
- Anzahl Siege/Niederlagen/Unentschieden
- Inkonsistenzen bei Spieler- und Vereinsnamen
- Basis-Statistiken
"""

import sys
import sqlite3
from pathlib import Path
from collections import defaultdict
import re

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import Config
import psycopg2


class DataQualityTester:
    """Testet Datenqualität der geparsten Datenbank."""
    
    def __init__(self, db_type='sqlite', db_path='fsv_archive_complete.db'):
        self.db_type = db_type
        self.db_path = db_path
        self.issues = []
        
    def connect(self):
        """Stelle Verbindung zur Datenbank her."""
        if self.db_type == 'sqlite':
            self.conn = sqlite3.connect(self.db_path)
            self.cur = self.conn.cursor()
        else:
            config = Config()
            self.conn = psycopg2.connect(config.build_psycopg2_dsn())
            self.cur = self.conn.cursor()
    
    def close(self):
        """Schließe Datenbankverbindung."""
        if hasattr(self, 'cur'):
            self.cur.close()
        if hasattr(self, 'conn'):
            self.conn.close()
    
    def test_season_coverage(self):
        """Prüfe Abdeckung von Spielen pro Saison."""
        print("\n" + "=" * 80)
        print("1. SAISON-ABDECKUNG")
        print("=" * 80)
        
        if self.db_type == 'sqlite':
            self.cur.execute("""
                SELECT s.label, s.start_year, s.end_year,
                       COUNT(DISTINCT m.match_id) as matches,
                       COUNT(DISTINCT sc.competition_id) as competitions
                FROM seasons s
                LEFT JOIN season_competitions sc ON s.season_id = sc.season_id
                LEFT JOIN matches m ON sc.season_competition_id = m.season_competition_id
                GROUP BY s.season_id, s.label, s.start_year, s.end_year
                ORDER BY s.start_year
            """)
        else:
            self.cur.execute("""
                SELECT s.label, s.start_year, s.end_year,
                       COUNT(DISTINCT m.match_id) as matches,
                       COUNT(DISTINCT sc.competition_id) as competitions
                FROM public.seasons s
                LEFT JOIN public.season_competitions sc ON s.season_id = sc.season_id
                LEFT JOIN public.matches m ON sc.season_competition_id = m.season_competition_id
                GROUP BY s.season_id, s.label, s.start_year, s.end_year
                ORDER BY s.start_year
            """)
        
        results = self.cur.fetchall()
        
        total_seasons = len(results)
        seasons_with_matches = sum(1 for r in results if r[3] and r[3] > 0)
        total_matches = sum(r[3] or 0 for r in results)
        
        print(f"  Gesamt Saisons: {total_seasons}")
        print(f"  Saisons mit Spielen: {seasons_with_matches}")
        print(f"  Gesamt Spiele: {total_matches:,}")
        
        # Zeige Saisons ohne Spiele
        empty_seasons = [r for r in results if not r[3] or r[3] == 0]
        if empty_seasons:
            print(f"\n  ⚠️  {len(empty_seasons)} Saisons ohne Spiele:")
            for season in empty_seasons[:10]:
                print(f"    - {season[0]} ({season[1]}-{season[2]})")
        
        # Zeige Saisons mit sehr wenigen Spielen (verdächtig)
        suspicious_seasons = [r for r in results if r[3] and 0 < r[3] < 10]
        if suspicious_seasons:
            print(f"\n  ⚠️  {len(suspicious_seasons)} Saisons mit sehr wenigen Spielen (<10):")
            for season in suspicious_seasons[:10]:
                print(f"    - {season[0]}: {season[3]} Spiele")
        
        return {
            'total_seasons': total_seasons,
            'seasons_with_matches': seasons_with_matches,
            'total_matches': total_matches,
            'empty_seasons': len(empty_seasons),
            'suspicious_seasons': len(suspicious_seasons)
        }
    
    def test_player_statistics(self):
        """Prüfe Spieler-Statistiken."""
        print("\n" + "=" * 80)
        print("2. SPIELER-STATISTIKEN")
        print("=" * 80)
        
        if self.db_type == 'sqlite':
            self.cur.execute("SELECT COUNT(*) FROM players")
            total_players = self.cur.fetchone()[0]
            
            self.cur.execute("""
                SELECT COUNT(DISTINCT ml.player_id)
                FROM match_lineups ml
            """)
            players_in_lineups = self.cur.fetchone()[0]
            
            self.cur.execute("""
                SELECT COUNT(DISTINCT g.player_id)
                FROM goals g
            """)
            players_with_goals = self.cur.fetchone()[0]
        else:
            self.cur.execute("SELECT COUNT(*) FROM public.players")
            total_players = self.cur.fetchone()[0]
            
            self.cur.execute("""
                SELECT COUNT(DISTINCT ml.player_id)
                FROM public.match_lineups ml
            """)
            players_in_lineups = self.cur.fetchone()[0]
            
            self.cur.execute("""
                SELECT COUNT(DISTINCT g.player_id)
                FROM public.goals g
            """)
            players_with_goals = self.cur.fetchone()[0]
        
        print(f"  Gesamt Spieler: {total_players:,}")
        print(f"  Spieler in Aufstellungen: {players_in_lineups:,}")
        print(f"  Spieler mit Toren: {players_with_goals:,}")
        
        # Prüfe auf problematische Spielernamen
        if self.db_type == 'sqlite':
            self.cur.execute("""
                SELECT COUNT(*) FROM players
                WHERE name LIKE '%Trainer%'
                   OR name LIKE '%Schiedsrichter%'
                   OR name LIKE 'Tore %'
                   OR name LIKE 'FE,%'
                   OR name LIKE 'ET,%'
                   OR name LIKE 'HE,%'
            """)
        else:
            self.cur.execute("""
                SELECT COUNT(*) FROM public.players
                WHERE name LIKE '%Trainer%'
                   OR name LIKE '%Schiedsrichter%'
                   OR name LIKE 'Tore %'
                   OR name LIKE 'FE,%'
                   OR name LIKE 'ET,%'
                   OR name LIKE 'HE,%'
            """)
        problematic_names = self.cur.fetchone()[0]
        
        if problematic_names > 0:
            print(f"\n  ⚠️  {problematic_names} Spieler mit problematischen Namen gefunden")
            self.issues.append(f"{problematic_names} Spieler mit problematischen Namen")
        
        return {
            'total_players': total_players,
            'players_in_lineups': players_in_lineups,
            'players_with_goals': players_with_goals,
            'problematic_names': problematic_names
        }
    
    def test_match_results(self):
        """Prüfe Match-Ergebnisse (Siege, Niederlagen, Unentschieden)."""
        print("\n" + "=" * 80)
        print("3. MATCH-ERGEBNISSE (FSV Mainz 05)")
        print("=" * 80)
        
        # Finde alle Mainz-Team-IDs
        if self.db_type == 'sqlite':
            self.cur.execute("""
                SELECT team_id FROM teams
                WHERE (name LIKE '%Mainz%' AND name LIKE '%05%')
                   OR name = '1. FSV Mainz 05'
                   OR name LIKE 'FSV Mainz%'
                   OR name LIKE '%Mainzer%'
            """)
        else:
            self.cur.execute("""
                SELECT team_id FROM public.teams
                WHERE (name ILIKE '%Mainz%' AND name ILIKE '%05%')
                   OR name = '1. FSV Mainz 05'
                   OR name ILIKE 'FSV Mainz%'
                   OR name ILIKE '%Mainzer%'
            """)
        
        mainz_team_ids = [row[0] for row in self.cur.fetchall()]
        mainz_team_ids_str = ','.join(map(str, mainz_team_ids))
        
        if self.db_type == 'sqlite':
            self.cur.execute(f"""
                SELECT 
                    COUNT(*) as total_matches,
                    SUM(CASE WHEN (m.home_team_id IN ({mainz_team_ids_str}) AND m.home_score > m.away_score) 
                              OR (m.away_team_id IN ({mainz_team_ids_str}) AND m.away_score > m.home_score) 
                         THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN m.home_score = m.away_score THEN 1 ELSE 0 END) as draws,
                    SUM(CASE WHEN (m.home_team_id IN ({mainz_team_ids_str}) AND m.home_score < m.away_score) 
                              OR (m.away_team_id IN ({mainz_team_ids_str}) AND m.away_score < m.home_score) 
                         THEN 1 ELSE 0 END) as losses,
                    SUM(CASE WHEN m.home_team_id IN ({mainz_team_ids_str}) THEN m.home_score ELSE m.away_score END) as goals_for,
                    SUM(CASE WHEN m.home_team_id IN ({mainz_team_ids_str}) THEN m.away_score ELSE m.home_score END) as goals_against
                FROM matches m
                WHERE m.home_team_id IN ({mainz_team_ids_str}) OR m.away_team_id IN ({mainz_team_ids_str})
            """)
        else:
            self.cur.execute(f"""
                SELECT 
                    COUNT(*) as total_matches,
                    SUM(CASE WHEN (m.home_team_id IN ({mainz_team_ids_str}) AND m.home_score > m.away_score) 
                              OR (m.away_team_id IN ({mainz_team_ids_str}) AND m.away_score > m.home_score) 
                         THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN m.home_score = m.away_score THEN 1 ELSE 0 END) as draws,
                    SUM(CASE WHEN (m.home_team_id IN ({mainz_team_ids_str}) AND m.home_score < m.away_score) 
                              OR (m.away_team_id IN ({mainz_team_ids_str}) AND m.away_score < m.home_score) 
                         THEN 1 ELSE 0 END) as losses,
                    SUM(CASE WHEN m.home_team_id IN ({mainz_team_ids_str}) THEN m.home_score ELSE m.away_score END) as goals_for,
                    SUM(CASE WHEN m.home_team_id IN ({mainz_team_ids_str}) THEN m.away_score ELSE m.home_score END) as goals_against
                FROM public.matches m
                WHERE m.home_team_id IN ({mainz_team_ids_str}) OR m.away_team_id IN ({mainz_team_ids_str})
            """)
        
        result = self.cur.fetchone()
        total_matches, wins, draws, losses, goals_for, goals_against = result
        
        print(f"  Gesamt Spiele (FSV Mainz): {total_matches:,}")
        print(f"  Siege: {wins:,}")
        print(f"  Unentschieden: {draws:,}")
        print(f"  Niederlagen: {losses:,}")
        print(f"  Tore geschossen: {goals_for:,}")
        print(f"  Tore kassiert: {goals_against:,}")
        
        if total_matches:
            win_rate = (wins / total_matches) * 100
            print(f"  Siegquote: {win_rate:.1f}%")
        
        # Prüfe Konsistenz
        calculated_total = (wins or 0) + (draws or 0) + (losses or 0)
        if calculated_total != total_matches:
            print(f"\n  ⚠️  Inkonsistenz: Siege+Unentschieden+Niederlagen ({calculated_total}) != Gesamt ({total_matches})")
            self.issues.append("Inkonsistenz bei Match-Ergebnissen")
        
        return {
            'total_matches': total_matches,
            'wins': wins,
            'draws': draws,
            'losses': losses,
            'goals_for': goals_for,
            'goals_against': goals_against
        }
    
    def test_team_name_consistency(self):
        """Prüfe Konsistenz von Vereinsnamen."""
        print("\n" + "=" * 80)
        print("4. VEREINSNAMEN-KONSISTENZ")
        print("=" * 80)
        
        if self.db_type == 'sqlite':
            self.cur.execute("SELECT COUNT(*) FROM teams")
            total_teams = self.cur.fetchone()[0]
            
            # Finde nur echte Mainz-Teams (nicht andere Teams mit "05")
            self.cur.execute("""
                SELECT name FROM teams
                WHERE (name LIKE '%Mainz%' AND name LIKE '%05%')
                   OR name = '1. FSV Mainz 05'
                   OR name LIKE 'FSV Mainz%'
                   OR name LIKE '%Mainzer%'
                ORDER BY name
            """)
        else:
            self.cur.execute("SELECT COUNT(*) FROM public.teams")
            total_teams = self.cur.fetchone()[0]
            
            self.cur.execute("""
                SELECT name FROM public.teams
                WHERE (name ILIKE '%Mainz%' AND name ILIKE '%05%')
                   OR name = '1. FSV Mainz 05'
                   OR name ILIKE 'FSV Mainz%'
                   OR name ILIKE '%Mainzer%'
                ORDER BY name
            """)
        
        mainz_teams = self.cur.fetchall()
        
        print(f"  Gesamt Teams: {total_teams:,}")
        print(f"  Mainz-Teams: {len(mainz_teams)}")
        
        if len(mainz_teams) > 1:
            print(f"\n  ⚠️  {len(mainz_teams)} Mainz-Team-Varianten gefunden:")
            for (name,) in mainz_teams:
                print(f"    - {name}")
            self.issues.append(f"{len(mainz_teams)} Mainz-Team-Varianten (sollte 1 sein)")
        else:
            print(f"  ✓ Nur 1 Mainz-Team gefunden (korrekt)")
        
        # Prüfe auf problematische Team-Namen
        if self.db_type == 'sqlite':
            self.cur.execute("""
                SELECT COUNT(*) FROM teams
                WHERE name LIKE '%Trainer%'
                   OR name LIKE '%,%'
                   OR LENGTH(name) > 100
            """)
        else:
            self.cur.execute("""
                SELECT COUNT(*) FROM public.teams
                WHERE name LIKE '%Trainer%'
                   OR name LIKE '%,%'
                   OR LENGTH(name) > 100
            """)
        problematic_teams = self.cur.fetchone()[0]
        
        if problematic_teams > 0:
            print(f"\n  ⚠️  {problematic_teams} Teams mit problematischen Namen")
            self.issues.append(f"{problematic_teams} Teams mit problematischen Namen")
        
        return {
            'total_teams': total_teams,
            'mainz_teams': len(mainz_teams),
            'problematic_teams': problematic_teams
        }
    
    def test_player_name_consistency(self):
        """Prüfe Konsistenz von Spielernamen."""
        print("\n" + "=" * 80)
        print("5. SPIELERNAMEN-KONSISTENZ")
        print("=" * 80)
        
        if self.db_type == 'sqlite':
            # Finde Spieler mit ähnlichen Namen (potentielle Duplikate)
            self.cur.execute("""
                SELECT name, COUNT(*) as count
                FROM players
                GROUP BY normalized_name
                HAVING COUNT(*) > 1
                ORDER BY count DESC
                LIMIT 10
            """)
        else:
            self.cur.execute("""
                SELECT name, COUNT(*) as count
                FROM public.players
                GROUP BY normalized_name
                HAVING COUNT(*) > 1
                ORDER BY count DESC
                LIMIT 10
            """)
        
        duplicates = self.cur.fetchall()
        
        if duplicates:
            print(f"  ⚠️  {len(duplicates)} potentielle Duplikate gefunden (erste 10):")
            for name, count in duplicates:
                print(f"    - {name}: {count}x")
            self.issues.append(f"{len(duplicates)} potentielle Spieler-Duplikate")
        else:
            print(f"  ✓ Keine Duplikate gefunden")
        
        # Prüfe auf Namen mit Sonderzeichen am Anfang
        if self.db_type == 'sqlite':
            self.cur.execute("""
                SELECT COUNT(*) FROM players
                WHERE name LIKE '?%'
                   OR name LIKE '-%'
                   OR name LIKE '%.%'
            """)
        else:
            self.cur.execute("""
                SELECT COUNT(*) FROM public.players
                WHERE name LIKE '?%'
                   OR name LIKE '-%'
                   OR name LIKE '%.%'
            """)
        special_chars = self.cur.fetchone()[0]
        
        if special_chars > 0:
            print(f"\n  ⚠️  {special_chars} Spieler mit Sonderzeichen am Anfang")
            self.issues.append(f"{special_chars} Spieler mit Sonderzeichen am Anfang")
        
        return {
            'duplicates': len(duplicates),
            'special_chars': special_chars
        }
    
    def run_all_tests(self):
        """Führe alle Tests aus."""
        print("=" * 80)
        print("DATENQUALITÄTS-TEST")
        print("=" * 80)
        print(f"Datenbank: {self.db_path} ({self.db_type})")
        
        results = {}
        results['season_coverage'] = self.test_season_coverage()
        results['player_statistics'] = self.test_player_statistics()
        results['match_results'] = self.test_match_results()
        results['team_consistency'] = self.test_team_name_consistency()
        results['player_consistency'] = self.test_player_name_consistency()
        
        # Zusammenfassung
        print("\n" + "=" * 80)
        print("ZUSAMMENFASSUNG")
        print("=" * 80)
        
        if self.issues:
            print(f"\n⚠️  {len(self.issues)} Probleme gefunden:")
            for issue in self.issues:
                print(f"  - {issue}")
        else:
            print("\n✅ Keine kritischen Probleme gefunden!")
        
        return results


def main():
    """Hauptfunktion."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Teste Datenqualität')
    parser.add_argument('--db-type', choices=['sqlite', 'postgres'], default='sqlite',
                       help='Datenbank-Typ')
    parser.add_argument('--db-path', default='fsv_archive_complete.db',
                       help='Pfad zur SQLite-Datenbank (nur für sqlite)')
    
    args = parser.parse_args()
    
    tester = DataQualityTester(args.db_type, args.db_path)
    
    try:
        tester.connect()
        results = tester.run_all_tests()
        
        # Exit-Code basierend auf gefundenen Problemen
        sys.exit(1 if tester.issues else 0)
        
    except Exception as e:
        print(f"\n❌ FEHLER: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        tester.close()


if __name__ == '__main__':
    main()

