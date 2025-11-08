#!/usr/bin/env python3
"""
Comprehensive Quality Checks for FSV Mainz 05 Database

This script performs sanity checks and statistical validation:
1. Data volume checks (matches per season, goals per match)
2. Data range validation (reasonable scores, dates)
3. Consistency checks (goals match lineups, etc.)
4. Outlier detection (unusual performances)
5. Historical facts validation

Usage:
    python database_quality_checks.py
"""

import os
from datetime import datetime
import psycopg2
from dotenv import load_dotenv

load_dotenv()


class QualityChecker:
    """Comprehensive database quality checker."""
    
    def __init__(self):
        self.conn = psycopg2.connect(os.getenv("DB_URL"))
        self.warnings = []
        self.errors = []
        self.info = []
        
    def close(self):
        self.conn.close()
    
    def log_error(self, msg):
        self.errors.append(f"❌ ERROR: {msg}")
        print(f"❌ {msg}")
    
    def log_warning(self, msg):
        self.warnings.append(f"⚠️  WARNING: {msg}")
        print(f"⚠️  {msg}")
    
    def log_info(self, msg):
        self.info.append(f"✓ {msg}")
        print(f"✓ {msg}")
    
    def check_data_volumes(self):
        """Check overall data volumes."""
        print("\n" + "=" * 100)
        print("1. DATA VOLUME CHECKS")
        print("=" * 100)
        
        with self.conn.cursor() as cur:
            # Total counts
            cur.execute("SELECT COUNT(*) FROM public.seasons")
            seasons = cur.fetchone()[0]
            self.log_info(f"Total seasons: {seasons}")
            
            cur.execute("SELECT COUNT(*) FROM public.matches")
            matches = cur.fetchone()[0]
            self.log_info(f"Total matches: {matches:,}")
            
            cur.execute("SELECT COUNT(*) FROM public.players")
            players = cur.fetchone()[0]
            self.log_info(f"Total players: {players:,}")
            
            cur.execute("SELECT COUNT(*) FROM public.goals")
            goals = cur.fetchone()[0]
            self.log_info(f"Total goals: {goals:,}")
            
            # Average checks
            avg_per_season = matches / seasons if seasons > 0 else 0
            self.log_info(f"Average matches per season: {avg_per_season:.1f}")
            
            avg_goals_per_match = goals / matches if matches > 0 else 0
            self.log_info(f"Average goals per match: {avg_goals_per_match:.2f}")
            
            if avg_goals_per_match < 1.5 or avg_goals_per_match > 4.0:
                self.log_warning(f"Unusual average goals per match: {avg_goals_per_match:.2f} (expected 2-3)")
    
    def check_season_consistency(self):
        """Check consistency of matches per season."""
        print("\n" + "=" * 100)
        print("2. SEASON CONSISTENCY CHECKS")
        print("=" * 100)
        
        with self.conn.cursor() as cur:
            # Bundesliga seasons should have 34 matches (modern era)
            cur.execute("""
                SELECT 
                    s.label,
                    s.start_year,
                    c.name as competition,
                    COUNT(m.match_id) as match_count
                FROM public.seasons s
                JOIN public.season_competitions sc ON s.season_id = sc.season_id
                JOIN public.competitions c ON sc.competition_id = c.competition_id
                LEFT JOIN public.matches m ON sc.season_competition_id = m.season_competition_id
                WHERE c.name = 'Bundesliga'
                AND s.start_year >= 1963  -- Modern Bundesliga era
                GROUP BY s.label, s.start_year, c.name
                ORDER BY s.start_year DESC
                LIMIT 20
            """)
            
            print("\nRecent Bundesliga Seasons (should have 34 matches):")
            for row in cur.fetchall():
                season, start_year, comp, count = row
                if count == 34:
                    print(f"  ✓ {season}: {count} matches")
                elif count == 0:
                    print(f"  ⚠️  {season}: {count} matches (no data yet)")
                else:
                    print(f"  ⚠️  {season}: {count} matches (expected 34)")
                    self.log_warning(f"Bundesliga {season} has {count} matches (expected 34)")
            
            # Check for seasons with unusually few/many matches
            cur.execute("""
                SELECT 
                    s.label,
                    c.name,
                    COUNT(m.match_id) as match_count
                FROM public.seasons s
                JOIN public.season_competitions sc ON s.season_id = sc.season_id
                JOIN public.competitions c ON sc.competition_id = c.competition_id
                LEFT JOIN public.matches m ON sc.season_competition_id = m.season_competition_id
                GROUP BY s.label, c.name
                HAVING COUNT(m.match_id) > 50 OR (COUNT(m.match_id) < 10 AND COUNT(m.match_id) > 0)
                ORDER BY match_count DESC
            """)
            
            unusual = cur.fetchall()
            if unusual:
                print("\nSeasons with unusual match counts:")
                for row in unusual:
                    season, comp, count = row
                    print(f"  {season} ({comp}): {count} matches")
                    if count > 50:
                        self.log_warning(f"{season} {comp} has {count} matches (unusually high)")
    
    def check_score_reasonableness(self):
        """Check for unreasonable scores."""
        print("\n" + "=" * 100)
        print("3. SCORE REASONABLENESS CHECKS")
        print("=" * 100)
        
        with self.conn.cursor() as cur:
            # Check for extremely high scores (possible data errors)
            cur.execute("""
                SELECT 
                    m.match_id,
                    s.label as season,
                    m.match_date,
                    t_home.name as home,
                    t_away.name as away,
                    m.home_score,
                    m.away_score,
                    (m.home_score + m.away_score) as total_goals
                FROM public.matches m
                JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
                JOIN public.seasons s ON sc.season_id = s.season_id
                JOIN public.teams t_home ON m.home_team_id = t_home.team_id
                JOIN public.teams t_away ON m.away_team_id = t_away.team_id
                WHERE m.home_score > 10 OR m.away_score > 10
                ORDER BY total_goals DESC
                LIMIT 10
            """)
            
            high_scores = cur.fetchall()
            if high_scores:
                print("\nMatches with scores > 10 (verify these are correct):")
                for row in high_scores:
                    match_id, season, date, home, away, h_score, a_score, total = row
                    print(f"  [{match_id}] {season} {date}: {home} {h_score}:{a_score} {away} (Total: {total})")
                    if total > 15:
                        self.log_warning(f"Very high score: {home} {h_score}:{a_score} {away}")
            else:
                self.log_info("No extremely high scores found")
            
            # Check for mismatched scores vs goals
            cur.execute("""
                SELECT 
                    m.match_id,
                    s.label,
                    t_home.name,
                    t_away.name,
                    m.home_score,
                    m.away_score,
                    COUNT(CASE WHEN g.team_id = m.home_team_id THEN 1 END) as home_goals_count,
                    COUNT(CASE WHEN g.team_id = m.away_team_id THEN 1 END) as away_goals_count
                FROM public.matches m
                JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
                JOIN public.seasons s ON sc.season_id = s.season_id
                JOIN public.teams t_home ON m.home_team_id = t_home.team_id
                JOIN public.teams t_away ON m.away_team_id = t_away.team_id
                LEFT JOIN public.goals g ON m.match_id = g.match_id AND g.event_type != 'own_goal'
                GROUP BY m.match_id, s.label, t_home.name, t_away.name, m.home_score, m.away_score
                HAVING 
                    (m.home_score IS NOT NULL AND COUNT(CASE WHEN g.team_id = m.home_team_id THEN 1 END) != m.home_score)
                    OR (m.away_score IS NOT NULL AND COUNT(CASE WHEN g.team_id = m.away_team_id THEN 1 END) != m.away_score)
                LIMIT 10
            """)
            
            mismatches = cur.fetchall()
            if mismatches:
                print("\nMatches where goal count doesn't match final score:")
                for row in mismatches:
                    match_id, season, home, away, h_score, a_score, h_goals, a_goals = row
                    print(f"  [{match_id}] {season}: {home} {h_score}:{a_score} {away}")
                    print(f"    Score: {h_score}:{a_score} | Goals recorded: {h_goals}:{a_goals}")
                    self.log_warning(f"Match {match_id}: Score {h_score}:{a_score} but recorded goals {h_goals}:{a_goals}")
            else:
                self.log_info("Goal counts match final scores (where both exist)")
    
    def check_player_performance_outliers(self):
        """Check for unusual player performances."""
        print("\n" + "=" * 100)
        print("4. PLAYER PERFORMANCE OUTLIERS")
        print("=" * 100)
        
        with self.conn.cursor() as cur:
            # Players with most goals in a single match
            cur.execute("""
                SELECT 
                    p.name,
                    s.label as season,
                    m.match_date,
                    t_home.name as home,
                    t_away.name as away,
                    COUNT(*) as goals_in_match
                FROM public.goals g
                JOIN public.players p ON g.player_id = p.player_id
                JOIN public.matches m ON g.match_id = m.match_id
                JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
                JOIN public.seasons s ON sc.season_id = s.season_id
                JOIN public.teams t_home ON m.home_team_id = t_home.team_id
                JOIN public.teams t_away ON m.away_team_id = t_away.team_id
                WHERE g.event_type != 'own_goal' OR g.event_type IS NULL
                GROUP BY p.name, s.label, m.match_date, t_home.name, t_away.name
                HAVING COUNT(*) >= 4
                ORDER BY goals_in_match DESC
                LIMIT 10
            """)
            
            hat_tricks = cur.fetchall()
            if hat_tricks:
                print("\nPlayers with 4+ goals in a single match:")
                for row in hat_tricks:
                    name, season, date, home, away, goals = row
                    print(f"  {name}: {goals} goals in {home} vs {away} ({season}, {date})")
                    if goals >= 5:
                        self.log_info(f"Exceptional performance: {name} scored {goals} goals in one match")
            else:
                print("  No players with 4+ goals in a single match")
            
            # Top scorers overall
            cur.execute("""
                SELECT 
                    p.name,
                    COUNT(*) as total_goals,
                    COUNT(DISTINCT m.match_id) as matches,
                    ROUND(COUNT(*)::numeric / NULLIF(COUNT(DISTINCT m.match_id), 0), 2) as goals_per_match
                FROM public.goals g
                JOIN public.players p ON g.player_id = p.player_id
                JOIN public.matches m ON g.match_id = m.match_id
                WHERE g.event_type != 'own_goal' OR g.event_type IS NULL
                GROUP BY p.name
                ORDER BY total_goals DESC
                LIMIT 10
            """)
            
            print("\nTop 10 Goal Scorers (All Time):")
            for row in cur.fetchall():
                name, goals, matches, gpm = row
                print(f"  {name:30s} {goals:4d} goals in {matches:4d} matches ({gpm} per match)")
    
    def check_historical_facts(self):
        """Verify known historical facts."""
        print("\n" + "=" * 100)
        print("5. HISTORICAL FACTS VALIDATION")
        print("=" * 100)
        
        with self.conn.cursor() as cur:
            # Check founding year (FSV Mainz 05 founded in 1905)
            cur.execute("""
                SELECT MIN(start_year) as first_season
                FROM public.seasons s
                JOIN public.teams t ON s.team_id = t.team_id
                WHERE t.name LIKE '%Mainz%' OR t.name = 'FSV'
            """)
            result = cur.fetchone()
            if result and result[0]:
                first_season = result[0]
                print(f"\nFirst recorded season: {first_season}")
                if first_season <= 1905:
                    self.log_info(f"First season {first_season} aligns with club founding (1905)")
                else:
                    self.log_warning(f"First season {first_season} is after club founding (1905)")
            
            # Check for Bundesliga promotion (2004-05 season)
            cur.execute("""
                SELECT s.label, c.name, COUNT(m.match_id) as matches
                FROM public.seasons s
                JOIN public.season_competitions sc ON s.season_id = sc.season_id
                JOIN public.competitions c ON sc.competition_id = c.competition_id
                LEFT JOIN public.matches m ON sc.season_competition_id = m.season_competition_id
                WHERE s.label = '2004-05' AND c.name = 'Bundesliga'
                GROUP BY s.label, c.name
            """)
            
            result = cur.fetchone()
            if result:
                season, comp, matches = result
                print(f"\n2004-05 Bundesliga (First Bundesliga season): {matches} matches")
                if matches > 0:
                    self.log_info("FSV Mainz 05's first Bundesliga season (2004-05) is recorded")
            else:
                self.log_warning("2004-05 Bundesliga season not found (should be first Bundesliga season)")
            
            # Check UEFA participation
            cur.execute("""
                SELECT DISTINCT s.label
                FROM public.seasons s
                JOIN public.season_competitions sc ON s.season_id = sc.season_id
                JOIN public.competitions c ON sc.competition_id = c.competition_id
                WHERE c.name LIKE '%UEFA%' OR c.name LIKE '%Europa%' OR c.name = 'Europapokal'
                ORDER BY s.label
            """)
            
            euro_seasons = cur.fetchall()
            if euro_seasons:
                print(f"\nEuropean competition participations ({len(euro_seasons)} seasons):")
                for row in euro_seasons:
                    print(f"  {row[0]}")
                self.log_info(f"Found {len(euro_seasons)} European competition participations")
            else:
                self.log_warning("No European competition participations found")
    
    def check_data_consistency(self):
        """Check internal data consistency."""
        print("\n" + "=" * 100)
        print("6. DATA CONSISTENCY CHECKS")
        print("=" * 100)
        
        with self.conn.cursor() as cur:
            # Check for matches without lineups
            cur.execute("""
                SELECT 
                    s.label,
                    s.start_year,
                    COUNT(DISTINCT m.match_id) as matches_without_lineups
                FROM public.matches m
                JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
                JOIN public.seasons s ON sc.season_id = s.season_id
                LEFT JOIN public.match_lineups ml ON m.match_id = ml.match_id
                WHERE ml.lineup_id IS NULL
                AND s.start_year >= 2000  -- Modern era should have lineups
                GROUP BY s.label, s.start_year
                HAVING COUNT(DISTINCT m.match_id) > 0
                ORDER BY s.start_year DESC
                LIMIT 10
            """)
            
            no_lineups = cur.fetchall()
            if no_lineups:
                print("\nModern matches (2000+) without lineups:")
                for row in no_lineups:
                    season, start_year, count = row
                    print(f"  {season}: {count} matches")
                    self.log_warning(f"{season} has {count} matches without lineups")
            else:
                self.log_info("All modern matches (2000+) have lineup data")
            
            # Check for goals without corresponding scorers in lineups
            cur.execute("""
                SELECT COUNT(DISTINCT g.goal_id)
                FROM public.goals g
                LEFT JOIN public.match_lineups ml ON g.match_id = ml.match_id AND g.player_id = ml.player_id
                WHERE ml.lineup_id IS NULL
                AND g.event_type != 'own_goal'
            """)
            
            goals_without_lineup = cur.fetchone()[0]
            if goals_without_lineup > 0:
                print(f"\nGoals scored by players not in lineup: {goals_without_lineup}")
                self.log_warning(f"{goals_without_lineup} goals scored by players not in match lineups")
            else:
                self.log_info("All goal scorers appear in match lineups")
            
            # Check halftime scores
            cur.execute("""
                SELECT 
                    m.match_id,
                    s.label,
                    m.halftime_home,
                    m.halftime_away,
                    m.home_score,
                    m.away_score
                FROM public.matches m
                JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
                JOIN public.seasons s ON sc.season_id = s.season_id
                WHERE m.halftime_home > m.home_score OR m.halftime_away > m.away_score
                LIMIT 5
            """)
            
            bad_halftime = cur.fetchall()
            if bad_halftime:
                print("\nMatches where halftime score > final score:")
                for row in bad_halftime:
                    match_id, season, ht_h, ht_a, ft_h, ft_a = row
                    print(f"  [{match_id}] {season}: HT {ht_h}:{ht_a}, FT {ft_h}:{ft_a}")
                    self.log_error(f"Match {match_id}: Halftime score exceeds final score")
            else:
                self.log_info("Halftime scores are consistent with final scores")
    
    def check_temporal_consistency(self):
        """Check date and time consistency."""
        print("\n" + "=" * 100)
        print("7. TEMPORAL CONSISTENCY CHECKS")
        print("=" * 100)
        
        with self.conn.cursor() as cur:
            # Check for future dates
            cur.execute("""
                SELECT 
                    m.match_id,
                    s.label,
                    m.match_date,
                    t_home.name,
                    t_away.name
                FROM public.matches m
                JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
                JOIN public.seasons s ON sc.season_id = s.season_id
                JOIN public.teams t_home ON m.home_team_id = t_home.team_id
                JOIN public.teams t_away ON m.away_team_id = t_away.team_id
                WHERE m.match_date > CURRENT_DATE
                ORDER BY m.match_date
                LIMIT 10
            """)
            
            future_matches = cur.fetchall()
            if future_matches:
                print("\nScheduled future matches:")
                for row in future_matches:
                    match_id, season, date, home, away = row
                    print(f"  [{match_id}] {date}: {home} vs {away} ({season})")
                self.log_info(f"Found {len(future_matches)} scheduled future matches")
            else:
                self.log_info("No future matches found (all are historical)")
            
            # Check for matches with dates outside their season
            cur.execute("""
                SELECT 
                    m.match_id,
                    s.label,
                    s.start_year,
                    s.end_year,
                    EXTRACT(YEAR FROM m.match_date) as match_year,
                    m.match_date
                FROM public.matches m
                JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
                JOIN public.seasons s ON sc.season_id = s.season_id
                WHERE m.match_date IS NOT NULL
                AND EXTRACT(YEAR FROM m.match_date) NOT IN (s.start_year, s.end_year)
                LIMIT 10
            """)
            
            date_mismatches = cur.fetchall()
            if date_mismatches:
                print("\nMatches with dates outside their season range:")
                for row in date_mismatches:
                    match_id, season, start, end, match_year, date = row
                    print(f"  [{match_id}] {season} ({start}-{end}): Match date {date} (year {int(match_year)})")
                    self.log_warning(f"Match {match_id} date {date} outside season {season} range")
            else:
                self.log_info("All match dates align with their season years")
    
    def generate_summary_statistics(self):
        """Generate overall summary statistics."""
        print("\n" + "=" * 100)
        print("8. SUMMARY STATISTICS")
        print("=" * 100)
        
        with self.conn.cursor() as cur:
            # Competition breakdown
            cur.execute("""
                SELECT 
                    c.name,
                    COUNT(DISTINCT sc.season_id) as seasons,
                    COUNT(m.match_id) as matches,
                    SUM(m.home_score + m.away_score) as total_goals
                FROM public.competitions c
                JOIN public.season_competitions sc ON c.competition_id = sc.competition_id
                LEFT JOIN public.matches m ON sc.season_competition_id = m.season_competition_id
                GROUP BY c.name
                ORDER BY matches DESC
            """)
            
            print("\nMatches by Competition:")
            for row in cur.fetchall():
                comp, seasons, matches, goals = row
                avg_goals = goals / matches if matches > 0 and goals else 0
                print(f"  {comp:20s} {seasons:3d} seasons, {matches:5d} matches, {avg_goals:.2f} goals/match")
            
            # Era breakdown
            cur.execute("""
                SELECT 
                    CASE 
                        WHEN s.start_year < 1950 THEN 'Pre-1950'
                        WHEN s.start_year < 1970 THEN '1950-1969'
                        WHEN s.start_year < 1990 THEN '1970-1989'
                        WHEN s.start_year < 2010 THEN '1990-2009'
                        ELSE '2010+'
                    END as era,
                    COUNT(DISTINCT s.season_id) as seasons,
                    COUNT(m.match_id) as matches
                FROM public.seasons s
                LEFT JOIN public.season_competitions sc ON s.season_id = sc.season_id
                LEFT JOIN public.matches m ON sc.season_competition_id = m.season_competition_id
                GROUP BY era
                ORDER BY MIN(s.start_year)
            """)
            
            print("\nMatches by Era:")
            for row in cur.fetchall():
                era, seasons, matches = row
                print(f"  {era:15s} {seasons:3d} seasons, {matches:5d} matches")
    
    def print_final_report(self):
        """Print final validation report."""
        print("\n" + "=" * 100)
        print("QUALITY CHECK SUMMARY")
        print("=" * 100)
        
        print(f"\n✓ Checks passed: {len(self.info)}")
        print(f"⚠️  Warnings: {len(self.warnings)}")
        print(f"❌ Errors: {len(self.errors)}")
        
        if self.errors:
            print("\n" + "=" * 100)
            print("ERRORS FOUND:")
            print("=" * 100)
            for error in self.errors:
                print(error)
        
        if self.warnings:
            print("\n" + "=" * 100)
            print("WARNINGS:")
            print("=" * 100)
            for warning in self.warnings[:20]:  # Show first 20
                print(warning)
            if len(self.warnings) > 20:
                print(f"... and {len(self.warnings) - 20} more warnings")
        
        print("\n" + "=" * 100)
        if not self.errors:
            print("✅ DATABASE QUALITY: GOOD - No critical errors found!")
        else:
            print("⚠️  DATABASE QUALITY: NEEDS ATTENTION - Please review errors")
        print("=" * 100)
    
    def run_all_checks(self):
        """Run all quality checks."""
        print("=" * 100)
        print("FSV MAINZ 05 DATABASE QUALITY CHECKS")
        print("=" * 100)
        print(f"Check Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        self.check_data_volumes()
        self.check_season_consistency()
        self.check_score_reasonableness()
        self.check_player_performance_outliers()
        self.check_historical_facts()
        self.check_data_consistency()
        self.check_temporal_consistency()
        self.generate_summary_statistics()
        
        self.print_final_report()


def main():
    checker = QualityChecker()
    try:
        checker.run_all_checks()
    finally:
        checker.close()


if __name__ == "__main__":
    main()

