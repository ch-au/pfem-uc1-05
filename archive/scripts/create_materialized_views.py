#!/usr/bin/env python3
"""
Erstellt Materialized Views für häufig verwendete Aggregationen.

Materialized Views speichern vorbere

chnete Ergebnisse und beschleunigen
komplexe Aggregations-Queries erheblich.

Usage:
    python create_materialized_views.py
    python create_materialized_views.py --refresh  # Aktualisiere bestehende Views
"""

import argparse
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def create_player_stats_view():
    """Erstelle Materialized View für Spielerstatistiken."""
    
    sql = """
    CREATE MATERIALIZED VIEW IF NOT EXISTS public.player_statistics AS
    SELECT 
        p.player_id,
        p.name,
        p.nationality,
        p.primary_position,
        p.birth_date,
        
        -- Einsatzstatistiken
        COUNT(DISTINCT ml.match_id) as spiele_gesamt,
        COUNT(DISTINCT CASE WHEN ml.is_starter THEN ml.match_id END) as spiele_starelf,
        
        -- Torstatistiken
        COUNT(DISTINCT g.goal_id) as tore_gesamt,
        COUNT(DISTINCT CASE WHEN g.event_type = 'penalty' THEN g.goal_id END) as tore_elfmeter,
        COUNT(DISTINCT CASE WHEN g.event_type = 'own_goal' THEN g.goal_id END) as eigentore,
        
        -- Vorlagen
        COUNT(DISTINCT ga.goal_id) as vorlagen_gesamt,
        
        -- Karten
        COUNT(DISTINCT CASE WHEN c.card_type = 'yellow' THEN c.card_id END) as gelbe_karten,
        COUNT(DISTINCT CASE WHEN c.card_type = 'red' THEN c.card_id END) as rote_karten,
        COUNT(DISTINCT CASE WHEN c.card_type = 'second_yellow' THEN c.card_id END) as gelb_rote_karten,
        
        -- Zeitraum
        MIN(m.match_date) as erstes_spiel,
        MAX(m.match_date) as letztes_spiel,
        
        -- Berechnete Statistiken
        ROUND(
            COUNT(DISTINCT g.goal_id)::numeric / NULLIF(COUNT(DISTINCT ml.match_id), 0),
            3
        ) as tore_pro_spiel
        
    FROM public.players p
    LEFT JOIN public.match_lineups ml ON p.player_id = ml.player_id
    LEFT JOIN public.goals g ON p.player_id = g.player_id 
        AND (g.event_type IS NULL OR g.event_type != 'own_goal')
    LEFT JOIN public.goals ga ON p.player_id = ga.assist_player_id
    LEFT JOIN public.cards c ON p.player_id = c.player_id
    LEFT JOIN public.matches m ON ml.match_id = m.match_id
    GROUP BY p.player_id, p.name, p.nationality, p.primary_position, p.birth_date
    WITH DATA;
    
    -- Index auf die View
    CREATE UNIQUE INDEX IF NOT EXISTS idx_player_stats_player_id 
    ON public.player_statistics(player_id);
    
    CREATE INDEX IF NOT EXISTS idx_player_stats_goals 
    ON public.player_statistics(tore_gesamt DESC);
    
    CREATE INDEX IF NOT EXISTS idx_player_stats_appearances 
    ON public.player_statistics(spiele_gesamt DESC);
    """
    
    return sql


def create_match_details_view():
    """Erstelle Materialized View für vollständige Spieldetails."""
    
    sql = """
    CREATE MATERIALIZED VIEW IF NOT EXISTS public.match_details AS
    SELECT 
        m.match_id,
        s.label as saison,
        c.name as wettbewerb,
        m.match_date,
        m.matchday as spieltag,
        m.venue as stadion,
        m.attendance as zuschauer,
        
        -- Teams
        t_home.name as heimmannschaft,
        t_away.name as gastmannschaft,
        
        -- Ergebnisse
        m.home_score as tore_heim,
        m.away_score as tore_gast,
        m.halftime_home as halbzeit_heim,
        m.halftime_away as halbzeit_gast,
        
        -- Statistiken
        (SELECT COUNT(*) FROM public.goals WHERE match_id = m.match_id) as tore_gesamt,
        (SELECT COUNT(*) FROM public.cards WHERE match_id = m.match_id) as karten_gesamt,
        (SELECT COUNT(*) FROM public.match_substitutions WHERE match_id = m.match_id) as wechsel_gesamt,
        
        -- FSV Mainz Spiel?
        CASE 
            WHEN m.home_team_id = 1 THEN 'Heim'
            WHEN m.away_team_id = 1 THEN 'Auswärts'
            ELSE NULL
        END as fsv_heim_auswaerts,
        
        -- FSV Ergebnis
        CASE 
            WHEN m.home_team_id = 1 AND m.home_score > m.away_score THEN 'Sieg'
            WHEN m.away_team_id = 1 AND m.away_score > m.home_score THEN 'Sieg'
            WHEN m.home_score = m.away_score THEN 'Unentschieden'
            ELSE 'Niederlage'
        END as fsv_ergebnis
        
    FROM public.matches m
    JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
    JOIN public.seasons s ON sc.season_id = s.season_id
    JOIN public.competitions c ON sc.competition_id = c.competition_id
    JOIN public.teams t_home ON m.home_team_id = t_home.team_id
    JOIN public.teams t_away ON m.away_team_id = t_away.team_id
    WHERE m.home_team_id = 1 OR m.away_team_id = 1
    WITH DATA;
    
    -- Indizes auf die View
    CREATE UNIQUE INDEX IF NOT EXISTS idx_match_details_id 
    ON public.match_details(match_id);
    
    CREATE INDEX IF NOT EXISTS idx_match_details_date 
    ON public.match_details(match_date DESC);
    
    CREATE INDEX IF NOT EXISTS idx_match_details_saison 
    ON public.match_details(saison);
    
    CREATE INDEX IF NOT EXISTS idx_match_details_wettbewerb 
    ON public.match_details(wettbewerb);
    """
    
    return sql


def create_season_summary_view():
    """Erstelle Materialized View für Saisonzusammenfassungen."""
    
    sql = """
    CREATE MATERIALIZED VIEW IF NOT EXISTS public.season_summary AS
    SELECT 
        s.season_id,
        s.label as saison,
        c.name as wettbewerb,
        
        -- Spielstatistiken
        COUNT(m.match_id) as spiele_gesamt,
        SUM(CASE 
            WHEN (m.home_team_id = 1 AND m.home_score > m.away_score) 
              OR (m.away_team_id = 1 AND m.away_score > m.home_score) 
            THEN 1 ELSE 0 
        END) as siege,
        SUM(CASE 
            WHEN m.home_score = m.away_score 
            THEN 1 ELSE 0 
        END) as unentschieden,
        SUM(CASE 
            WHEN (m.home_team_id = 1 AND m.home_score < m.away_score) 
              OR (m.away_team_id = 1 AND m.away_score < m.home_score) 
            THEN 1 ELSE 0 
        END) as niederlagen,
        
        -- Tore
        SUM(CASE WHEN m.home_team_id = 1 THEN m.home_score ELSE m.away_score END) as tore_geschossen,
        SUM(CASE WHEN m.home_team_id = 1 THEN m.away_score ELSE m.home_score END) as tore_kassiert,
        
        -- Spieler
        COUNT(DISTINCT ml.player_id) as spieler_eingesetzt,
        COUNT(DISTINCT g.player_id) as torschuetzen,
        
        -- Zeitraum
        MIN(m.match_date) as erstes_spiel,
        MAX(m.match_date) as letztes_spiel
        
    FROM public.seasons s
    JOIN public.season_competitions sc ON s.season_id = sc.season_id
    JOIN public.competitions c ON sc.competition_id = c.competition_id
    LEFT JOIN public.matches m ON sc.season_competition_id = m.season_competition_id
        AND (m.home_team_id = 1 OR m.away_team_id = 1)
    LEFT JOIN public.match_lineups ml ON m.match_id = ml.match_id
        AND ml.team_id = 1
    LEFT JOIN public.goals g ON m.match_id = g.match_id
        AND g.team_id = 1
    GROUP BY s.season_id, s.label, c.name
    WITH DATA;
    
    -- Indizes
    CREATE INDEX IF NOT EXISTS idx_season_summary_saison 
    ON public.season_summary(saison);
    
    CREATE INDEX IF NOT EXISTS idx_season_summary_wettbewerb 
    ON public.season_summary(wettbewerb);
    """
    
    return sql


def main():
    parser = argparse.ArgumentParser(description='Erstelle Materialized Views')
    parser.add_argument('--refresh', action='store_true', 
                       help='Aktualisiere bestehende Views')
    args = parser.parse_args()
    
    print("=" * 80)
    print("MATERIALIZED VIEWS ERSTELLEN")
    print("=" * 80)
    print()
    
    conn = psycopg2.connect(os.getenv("DB_URL"))
    
    views = [
        ('player_statistics', create_player_stats_view(), 'Spielerstatistiken'),
        ('match_details', create_match_details_view(), 'Spieldetails'),
        ('season_summary', create_season_summary_view(), 'Saisonzusammenfassungen')
    ]
    
    for view_name, sql, description in views:
        print(f"Erstelle: {description} ({view_name})")
        
        with conn.cursor() as cur:
            if args.refresh:
                # Refresh bestehende View
                try:
                    cur.execute(f"REFRESH MATERIALIZED VIEW public.{view_name}")
                    conn.commit()
                    print(f"  ✓ View aktualisiert")
                except Exception as e:
                    if 'does not exist' in str(e):
                        # View existiert nicht, erstelle sie
                        cur.execute(sql)
                        conn.commit()
                        print(f"  ✓ View erstellt")
                    else:
                        print(f"  ⚠️  Fehler: {e}")
            else:
                # Erstelle neue View
                try:
                    cur.execute(sql)
                    conn.commit()
                    print(f"  ✓ View erstellt mit Indizes")
                except Exception as e:
                    if 'already exists' in str(e):
                        print(f"  ℹ️  View existiert bereits (nutze --refresh zum Aktualisieren)")
                    else:
                        print(f"  ⚠️  Fehler: {e}")
    
    # Zeige Statistiken
    print()
    print("=" * 80)
    print("VIEW STATISTIKEN")
    print("=" * 80)
    print()
    
    with conn.cursor() as cur:
        for view_name, _, description in views:
            try:
                cur.execute(f"SELECT COUNT(*) FROM public.{view_name}")
                count = cur.fetchone()[0]
                print(f"  {view_name:25s} {count:6,} Zeilen")
            except:
                pass
    
    conn.close()
    
    print()
    print("=" * 80)
    print("✅ MATERIALIZED VIEWS BEREIT")
    print("=" * 80)
    print()
    print("Verwende die Views für schnelle Queries:")
    print("  - SELECT * FROM public.player_statistics WHERE tore_gesamt > 10")
    print("  - SELECT * FROM public.match_details WHERE saison = '2024-25'")
    print("  - SELECT * FROM public.season_summary ORDER BY siege DESC")
    print()
    print("Aktualisierung:")
    print("  python create_materialized_views.py --refresh")


if __name__ == "__main__":
    main()



