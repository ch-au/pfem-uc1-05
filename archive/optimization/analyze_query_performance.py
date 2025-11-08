#!/usr/bin/env python3
"""
Analysiere Datenbankperformance und identifiziere Optimierungsmöglichkeiten.

Dieser Script:
1. Führt typische Queries aus und misst die Ausführungszeit
2. Analysiert Query-Pläne (EXPLAIN ANALYZE)
3. Identifiziert fehlende Indizes
4. Empfiehlt Composite-Indizes für häufige Join-Patterns

Usage:
    python analyze_query_performance.py
"""

import os
import time
from typing import List, Tuple
import psycopg2
from dotenv import load_dotenv

load_dotenv()


class PerformanceAnalyzer:
    """Analysiert und optimiert Datenbankperformance."""
    
    def __init__(self):
        self.conn = psycopg2.connect(os.getenv("DB_URL"))
        self.results = []
        
    def close(self):
        self.conn.close()
    
    def measure_query(self, name: str, query: str, explain: bool = False) -> dict:
        """Führt Query aus und misst Performance."""
        with self.conn.cursor() as cur:
            # EXPLAIN ANALYZE für detaillierte Analyse
            if explain:
                start = time.time()
                cur.execute(f"EXPLAIN ANALYZE {query}")
                explain_output = cur.fetchall()
                elapsed = (time.time() - start) * 1000
                
                return {
                    'name': name,
                    'time_ms': elapsed,
                    'explain': explain_output
                }
            else:
                start = time.time()
                cur.execute(query)
                result = cur.fetchall()
                elapsed = (time.time() - start) * 1000
                
                return {
                    'name': name,
                    'time_ms': elapsed,
                    'rows': len(result)
                }
    
    def test_common_queries(self):
        """Teste häufig verwendete Query-Patterns."""
        print("=" * 80)
        print("PERFORMANCE-ANALYSE: HÄUFIGE QUERIES")
        print("=" * 80)
        print()
        
        queries = [
            # Query 1: Spielerstatistiken (mehrere Joins)
            (
                "Spielerstatistiken (Goals + Lineups)",
                """
                SELECT 
                    p.name,
                    COUNT(DISTINCT g.goal_id) as tore,
                    COUNT(DISTINCT ml.match_id) as spiele
                FROM public.players p
                LEFT JOIN public.goals g ON p.player_id = g.player_id
                LEFT JOIN public.match_lineups ml ON p.player_id = ml.player_id
                GROUP BY p.player_id, p.name
                ORDER BY tore DESC
                LIMIT 100
                """
            ),
            
            # Query 2: Spiele einer Saison (Join über 4 Tabellen)
            (
                "Bundesliga-Spiele 2023-24",
                """
                SELECT 
                    m.match_date,
                    t_home.name,
                    t_away.name,
                    m.home_score,
                    m.away_score
                FROM public.matches m
                JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
                JOIN public.competitions c ON sc.competition_id = c.competition_id
                JOIN public.seasons s ON sc.season_id = s.season_id
                JOIN public.teams t_home ON m.home_team_id = t_home.team_id
                JOIN public.teams t_away ON m.away_team_id = t_away.team_id
                WHERE c.name = 'Bundesliga' AND s.label = '2023-24'
                ORDER BY m.match_date
                """
            ),
            
            # Query 3: Tore mit Torschützen und Assists (komplexer Join)
            (
                "Tore mit Torschützen (letzte 100)",
                """
                SELECT 
                    m.match_date,
                    p_scorer.name as torschuetze,
                    p_assist.name as vorlage,
                    g.minute,
                    t.name as mannschaft
                FROM public.goals g
                JOIN public.matches m ON g.match_id = m.match_id
                JOIN public.players p_scorer ON g.player_id = p_scorer.player_id
                LEFT JOIN public.players p_assist ON g.assist_player_id = p_assist.player_id
                JOIN public.teams t ON g.team_id = t.team_id
                ORDER BY m.match_date DESC
                LIMIT 100
                """
            ),
            
            # Query 4: Aufstellungen mit Spielern (großer Join)
            (
                "Match Lineups (letztes Spiel)",
                """
                SELECT 
                    p.name,
                    ml.shirt_number,
                    ml.is_starter,
                    p.primary_position,
                    t.name as mannschaft
                FROM public.match_lineups ml
                JOIN public.players p ON ml.player_id = p.player_id
                JOIN public.teams t ON ml.team_id = t.team_id
                WHERE ml.match_id = (SELECT MAX(match_id) FROM public.matches)
                ORDER BY t.name, ml.is_starter DESC, ml.shirt_number
                """
            ),
            
            # Query 5: Aggregation über mehrere Tabellen
            (
                "Saisonstatistiken (komplex)",
                """
                SELECT 
                    s.label,
                    s.start_year,
                    c.name as wettbewerb,
                    COUNT(m.match_id) as spiele,
                    COUNT(DISTINCT ml.player_id) as spieler,
                    COUNT(DISTINCT g.goal_id) as tore
                FROM public.seasons s
                JOIN public.season_competitions sc ON s.season_id = sc.season_id
                JOIN public.competitions c ON sc.competition_id = c.competition_id
                LEFT JOIN public.matches m ON sc.season_competition_id = m.season_competition_id
                LEFT JOIN public.match_lineups ml ON m.match_id = ml.match_id
                LEFT JOIN public.goals g ON m.match_id = g.match_id
                WHERE s.start_year >= 2020
                GROUP BY s.label, s.start_year, c.name
                ORDER BY s.start_year DESC, c.name
                """
            )
        ]
        
        for name, query in queries:
            result = self.measure_query(name, query)
            self.results.append(result)
            
            if result['time_ms'] > 100:
                marker = "🔴"
            elif result['time_ms'] > 50:
                marker = "🟡"
            else:
                marker = "🟢"
            
            print(f"{marker} {name:40s} {result['time_ms']:6.1f}ms ({result['rows']} Zeilen)")
        
        print()
    
    def analyze_table_statistics(self):
        """Analysiere Tabellenstatistiken."""
        print("=" * 80)
        print("TABELLENSTATISTIKEN")
        print("=" * 80)
        print()
        
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    schemaname,
                    tablename,
                    n_tup_ins as inserts,
                    n_tup_upd as updates,
                    n_tup_del as deletes,
                    n_live_tup as live_rows,
                    n_dead_tup as dead_rows,
                    last_vacuum,
                    last_autovacuum,
                    last_analyze,
                    last_autoanalyze
                FROM pg_stat_user_tables
                WHERE schemaname = 'public'
                ORDER BY n_live_tup DESC
                LIMIT 10
            """)
            
            print("Top 10 Tabellen nach Größe:")
            print()
            for row in cur.fetchall():
                schema, table, ins, upd, dels, live, dead, vac, autovac, ana, autoana = row
                print(f"  {table:25s} {live:8,} Zeilen, {dead:6,} dead rows")
                
                if dead > live * 0.1:
                    print(f"    ⚠️  Viele dead rows ({dead:,}) - VACUUM empfohlen")
    
    def check_missing_indexes(self):
        """Identifiziere fehlende Indizes."""
        print("\n" + "=" * 80)
        print("FEHLENDE INDIZES")
        print("=" * 80)
        print()
        
        with self.conn.cursor() as cur:
            # Prüfe Sequential Scans
            cur.execute("""
                SELECT 
                    schemaname,
                    tablename,
                    seq_scan,
                    seq_tup_read,
                    idx_scan,
                    idx_tup_fetch,
                    CASE 
                        WHEN seq_scan > 0 THEN ROUND((100.0 * idx_scan) / NULLIF(seq_scan + idx_scan, 0), 1)
                        ELSE 0
                    END as index_usage_percent
                FROM pg_stat_user_tables
                WHERE schemaname = 'public'
                AND seq_scan > 0
                ORDER BY seq_scan DESC
                LIMIT 10
            """)
            
            print("Tabellen mit hohen Sequential Scans:")
            print("(Niedrige Index-Nutzung deutet auf fehlende Indizes hin)")
            print()
            
            for row in cur.fetchall():
                schema, table, seq, seq_read, idx, idx_fetch, idx_pct = row
                
                if idx_pct and idx_pct < 50:
                    marker = "🔴"
                elif idx_pct and idx_pct < 80:
                    marker = "🟡"
                else:
                    marker = "🟢"
                
                print(f"{marker} {table:25s} Seq: {seq:6,}, Index-Nutzung: {idx_pct or 0:5.1f}%")
    
    def recommend_composite_indexes(self):
        """Empfehle Composite-Indizes basierend auf Join-Patterns."""
        print("\n" + "=" * 80)
        print("EMPFOHLENE COMPOSITE-INDIZES")
        print("=" * 80)
        print()
        
        recommendations = [
            # Für Spielerstatistik-Queries
            {
                'table': 'goals',
                'columns': ['player_id', 'match_id'],
                'reason': 'Häufiger Join: Tore pro Spieler und Spiel'
            },
            {
                'table': 'match_lineups',
                'columns': ['player_id', 'match_id'],
                'reason': 'Häufiger Join: Aufstellungen pro Spieler'
            },
            {
                'table': 'match_lineups',
                'columns': ['match_id', 'team_id'],
                'reason': 'Spielaufstellungen nach Mannschaft filtern'
            },
            
            # Für Saison-Queries
            {
                'table': 'matches',
                'columns': ['season_competition_id', 'match_date'],
                'reason': 'Spiele nach Saison und Datum sortieren'
            },
            {
                'table': 'matches',
                'columns': ['match_date', 'home_team_id'],
                'reason': 'Heimspiele chronologisch'
            },
            {
                'table': 'matches',
                'columns': ['match_date', 'away_team_id'],
                'reason': 'Auswärtsspiele chronologisch'
            },
            
            # Für Tor-Queries
            {
                'table': 'goals',
                'columns': ['match_id', 'minute'],
                'reason': 'Tore pro Spiel chronologisch'
            },
            {
                'table': 'goals',
                'columns': ['player_id', 'match_id', 'minute'],
                'reason': 'Spielertore in Spielen'
            },
            
            # Für Karten-Queries
            {
                'table': 'cards',
                'columns': ['match_id', 'minute'],
                'reason': 'Karten pro Spiel chronologisch'
            },
            {
                'table': 'cards',
                'columns': ['player_id', 'card_type'],
                'reason': 'Spielerkarten nach Typ'
            },
            
            # Für Saison-Competition Joins
            {
                'table': 'season_competitions',
                'columns': ['season_id', 'competition_id'],
                'reason': 'Bereits UNIQUE constraint - Index vorhanden'
            }
        ]
        
        print("Empfohlene Indizes für bessere Join-Performance:")
        print()
        
        for rec in recommendations:
            cols = ', '.join(rec['columns'])
            print(f"  {rec['table']:25s} ({cols})")
            print(f"    → {rec['reason']}")
            print()
        
        return recommendations
    
    def generate_optimization_sql(self, recommendations: List[dict]) -> str:
        """Generiere SQL für Composite-Indizes."""
        sql_statements = []
        
        sql_statements.append("-- Composite-Indizes für Join-Performance")
        sql_statements.append("")
        
        for rec in recommendations:
            if rec['table'] == 'season_competitions' and 'season_id' in rec['columns']:
                # Dieser Index existiert bereits durch UNIQUE constraint
                continue
            
            cols = '_'.join(rec['columns'])
            index_name = f"idx_{rec['table']}_{cols}"
            columns = ', '.join(rec['columns'])
            
            sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON public.{rec['table']}({columns});"
            sql_statements.append(f"-- {rec['reason']}")
            sql_statements.append(sql)
            sql_statements.append("")
        
        return '\n'.join(sql_statements)
    
    def run_analysis(self):
        """Führe vollständige Performance-Analyse durch."""
        print("=" * 80)
        print("DATENBANK PERFORMANCE-ANALYSE")
        print("=" * 80)
        print()
        
        # Test queries
        self.test_common_queries()
        
        # Table statistics
        self.analyze_table_statistics()
        
        # Missing indexes
        self.check_missing_indexes()
        
        # Recommendations
        recommendations = self.recommend_composite_indexes()
        
        # Generate SQL
        print("=" * 80)
        print("OPTIMIERUNGS-SQL GENERIERT")
        print("=" * 80)
        print()
        
        sql = self.generate_optimization_sql(recommendations)
        
        # Speichere SQL
        with open('optimize_database.sql', 'w') as f:
            f.write(sql)
        
        print("✓ SQL-Befehle gespeichert in: optimize_database.sql")
        print()
        
        # Summary
        print("=" * 80)
        print("ZUSAMMENFASSUNG")
        print("=" * 80)
        
        slow_queries = [r for r in self.results if r.get('time_ms', 0) > 100]
        if slow_queries:
            print(f"\n⚠️  {len(slow_queries)} langsame Queries (>100ms) gefunden")
            print("   Empfehlung: Führe optimize_database.sql aus")
        else:
            print("\n✓ Alle Queries unter 100ms")
            print("  Performance ist gut!")


def main():
    analyzer = PerformanceAnalyzer()
    try:
        analyzer.run_analysis()
    finally:
        analyzer.close()


if __name__ == "__main__":
    main()

