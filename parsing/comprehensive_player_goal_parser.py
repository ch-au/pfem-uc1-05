import os
import sqlite3
import re
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Tuple
import traceback
import unicodedata

class ComprehensivePlayerGoalParser:
    """
    Phase 2: Extract players and goals from individual match pages
    """
    
    def __init__(self, db_name='fsv_archive_complete.db'):
        self.db_name = db_name
        self.conn = sqlite3.connect(db_name)
        self.c = self.conn.cursor()
        
        # Statistics
        self.stats = {
            'matches_processed': 0,
            'matches_with_data': 0,
            'players_found': 0,
            'goals_found': 0,
            'errors': []
        }
        
        # Add new tables for players and goals
        self.init_player_tables()
    
    def init_player_tables(self):
        """Create player and goal tables"""
        
        # Players table
        self.c.execute("""
            CREATE TABLE IF NOT EXISTS Players (
                player_id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_name TEXT UNIQUE,
                player_link TEXT
            )
        """)
        
        # Match lineups table
        self.c.execute("""
            CREATE TABLE IF NOT EXISTS Match_Lineups (
                lineup_id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER,
                player_id INTEGER,
                is_starter BOOLEAN,
                is_captain BOOLEAN,
                jersey_number INTEGER,
                substituted_minute INTEGER,
                yellow_card BOOLEAN,
                red_card BOOLEAN,
                FOREIGN KEY (match_id) REFERENCES Matches (match_id),
                FOREIGN KEY (player_id) REFERENCES Players (player_id)
            )
        """)
        
        # Goals table
        self.c.execute("""
            CREATE TABLE IF NOT EXISTS Goals (
                goal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER,
                player_id INTEGER,
                goal_minute INTEGER,
                is_penalty BOOLEAN,
                is_own_goal BOOLEAN,
                assisted_by_player_id INTEGER,
                score_at_time TEXT,
                FOREIGN KEY (match_id) REFERENCES Matches (match_id),
                FOREIGN KEY (player_id) REFERENCES Players (player_id),
                FOREIGN KEY (assisted_by_player_id) REFERENCES Players (player_id)
            )
        """)
        
        # Substitutions table
        self.c.execute("""
            CREATE TABLE IF NOT EXISTS Substitutions (
                substitution_id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER,
                minute INTEGER,
                player_in_id INTEGER,
                player_out_id INTEGER,
                FOREIGN KEY (match_id) REFERENCES Matches (match_id),
                FOREIGN KEY (player_in_id) REFERENCES Players (player_id),
                FOREIGN KEY (player_out_id) REFERENCES Players (player_id)
            )
        """)
        
        self.conn.commit()
    
    def _normalize_player_name(self, raw: str) -> str:
        """Normalize player name strings extracted from HTML.

        - Remove leading jersey numbers and punctuation (e.g., "4 Klopp", "13. Müller")
        - Collapse excessive whitespace and commas
        - Strip quotes and trailing punctuation
        - Normalize unicode accents (NFKD)
        - Keep only letters, spaces, common hyphens/apostrophes within words
        """
        if not raw:
            return ""
        text = raw.strip()
        # Remove leading jersey numbers like "4 ", "13. ", "10) ", "10-"
        text = re.sub(r"^\s*\d+[\)\.]?\s+", "", text)
        # Remove trailing jersey numbers if mistakenly appended
        text = re.sub(r"\s+\d+$", "", text)
        # Remove extra commas directly next to name
        text = re.sub(r"[,;]+", " ", text)
        # Normalize unicode accents
        text = unicodedata.normalize('NFKD', text)
        text = ''.join(ch for ch in text if not unicodedata.combining(ch))
        # Keep letters, spaces, hyphens, apostrophes
        text = re.sub(r"[^A-Za-z\-\'\s]", " ", text)
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def get_or_create_player(self, player_name: str, player_link: str = None) -> Optional[int]:
        """Get player ID or create new player"""
        if not player_name:
            return None
        
        # Clean player name aggressively to avoid artifacts like "4 Klopp"
        player_name = self._normalize_player_name(player_name)
        if not player_name:
            return None
        
        # Check if player exists
        self.c.execute("SELECT player_id FROM Players WHERE player_name = ?", (player_name,))
        result = self.c.fetchone()
        
        if result:
            return result[0]
        else:
            # Create new player
            self.c.execute("INSERT INTO Players (player_name, player_link) VALUES (?, ?)",
                          (player_name, player_link))
            self.stats['players_found'] += 1
            return self.c.lastrowid
    
    def parse_lineup(self, match_id: int, soup: BeautifulSoup):
        """Extract player lineup from match page"""
        # Find FSV lineup (usually in the second table of player names)
        tables = soup.find_all('table')
        fsv_players = []
        
        for table in tables:
            # Look for tables with player links
            player_links = table.find_all('a', href=re.compile(r'../spieler/'))
            if player_links:
                for link in player_links:
                    # Some HTML encodes jersey number inside the link text; normalize it away
                    player_name = self._normalize_player_name(link.get_text(strip=True))
                    player_href = link.get('href')
                    
                    # Check for captain (bold)
                    is_captain = link.find_parent('b') is not None
                    
                    # Check for cards and substitutions
                    parent_td = link.find_parent('td')
                    if parent_td:
                        parent_text = parent_td.get_text()
                        yellow_card = '🟨' in parent_text or 'gelbekarte' in str(parent_td)
                        red_card = '🟥' in parent_text or 'rotekarte' in str(parent_td)
                        is_sub = 'raus' in str(parent_td)
                        
                        # Extract jersey number if present at the very start of the cell
                        number_match = re.search(r'^(\s*)(\d+)', parent_text)
                        jersey_number = int(number_match.group(2)) if number_match else None
                        
                        # Get player ID
                        player_id = self.get_or_create_player(player_name, player_href)
                        
                        if player_id:
                            # Store in lineup
                            self.c.execute("""
                                INSERT INTO Match_Lineups 
                                (match_id, player_id, is_starter, is_captain, jersey_number, 
                                 yellow_card, red_card)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (match_id, player_id, True, is_captain, jersey_number, 
                                  yellow_card, red_card))
                            
                            fsv_players.append(player_name)
        
        return fsv_players
    
    def parse_goals(self, match_id: int, soup: BeautifulSoup):
        """Extract goals from match page"""
        goals_found = 0
        
        # Find "Tore" section
        tore_header = soup.find('b', string=re.compile(r'Tore', re.IGNORECASE))
        if not tore_header:
            return goals_found
        
        # Get the table after "Tore"
        goal_table = tore_header.find_next('table')
        if not goal_table:
            # Sometimes goals are in text format after the header
            next_element = tore_header.find_next_sibling()
            if next_element:
                goal_text = next_element.get_text() if next_element else ""
            else:
                goal_text = ""
        else:
            goal_text = goal_table.get_text()
        
        # Check for special cases
        if "nicht überliefert" in goal_text or "keine" in goal_text:
            return goals_found
        
        # Parse goals from table cells or text
        if goal_table:
            cells = goal_table.find_all('td')
            for cell in cells:
                goal_entry = cell.get_text(strip=True)
                if goal_entry and re.search(r'\d+\.', goal_entry):
                    # Parse goal entry like "70. 3:1 Behrens (Becker)"
                    match = re.match(r'(\d+)\.\s*(\d+:\d+)\s*([^(]+)(?:\s*\(([^)]+)\))?', goal_entry)
                    if match:
                        minute = int(match.group(1))
                        score = match.group(2)
                        scorer_text = match.group(3).strip()
                        assister_text = match.group(4).strip() if match.group(4) else None
                        
                        # Check if it's a penalty
                        is_penalty = 'Elfmeter' in goal_entry or 'FE' in goal_entry or '11m' in goal_entry
                        
                        # Extract scorer name from link if available
                        scorer_link = cell.find('a', href=re.compile(r'../spieler/'))
                        if scorer_link:
                            scorer_name = scorer_link.get_text(strip=True)
                            scorer_href = scorer_link.get('href')
                        else:
                            scorer_name = scorer_text
                            scorer_href = None
                        
                        # Get player IDs
                        scorer_id = self.get_or_create_player(scorer_name, scorer_href)
                        assister_id = self.get_or_create_player(assister_text) if assister_text else None
                        
                        if scorer_id:
                            # Store goal
                            self.c.execute("""
                                INSERT INTO Goals 
                                (match_id, player_id, goal_minute, is_penalty, 
                                 assisted_by_player_id, score_at_time)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (match_id, scorer_id, minute, is_penalty, assister_id, score))
                            
                            goals_found += 1
                            self.stats['goals_found'] += 1
        
        return goals_found
    
    def parse_substitutions(self, match_id: int, soup: BeautifulSoup):
        """Extract substitutions from match page"""
        subs_found = 0
        
        # Look for substitution patterns like "60. van den Berg für Kohr"
        all_text = soup.get_text()
        sub_pattern = r'(\d+)\.\s+([^f]+)\s+für\s+([^\n]+)'
        
        for match in re.finditer(sub_pattern, all_text):
            minute = int(match.group(1))
            player_in = match.group(2).strip()
            player_out = match.group(3).strip()
            
            # Clean player names
            player_in = re.sub(r'\s+', ' ', player_in).strip()
            player_out = re.sub(r'\s+', ' ', player_out).strip()
            
            # Get player IDs
            player_in_id = self.get_or_create_player(player_in)
            player_out_id = self.get_or_create_player(player_out)
            
            if player_in_id and player_out_id:
                self.c.execute("""
                    INSERT INTO Substitutions 
                    (match_id, minute, player_in_id, player_out_id)
                    VALUES (?, ?, ?, ?)
                """, (match_id, minute, player_in_id, player_out_id))
                
                subs_found += 1
        
        return subs_found
    
    def process_match(self, match_id: int, match_url: str):
        """Process a single match detail page"""
        if not match_url or not os.path.exists(match_url):
            return False
        
        try:
            with open(match_url, 'r', encoding='utf-8', errors='ignore') as f:
                soup = BeautifulSoup(f, 'lxml')
            
            # Parse lineup
            players = self.parse_lineup(match_id, soup)
            
            # Parse goals
            goals = self.parse_goals(match_id, soup)
            
            # Parse substitutions
            subs = self.parse_substitutions(match_id, soup)
            
            if players or goals:
                self.stats['matches_with_data'] += 1
                return True
            
            return False
            
        except Exception as e:
            self.stats['errors'].append(f"Match {match_id}: {str(e)}")
            return False
    
    def run(self, limit: int = None):
        """Process all matches"""
        print("=" * 80)
        print("PHASE 2: PLAYER AND GOAL EXTRACTION")
        print("=" * 80)
        
        # Get all matches with URLs
        query = """
            SELECT m.match_id, m.match_details_url, s.season_name, o.opponent_name
            FROM Matches m
            JOIN Seasons s ON m.season_id = s.season_id
            JOIN Opponents o ON m.opponent_id = o.opponent_id
            WHERE m.match_details_url IS NOT NULL
            ORDER BY s.season_name DESC, m.gameday
        """
        if limit:
            query += f" LIMIT {limit}"
        
        matches = self.c.execute(query).fetchall()
        total_matches = len(matches)
        
        print(f"Found {total_matches} matches to process")
        print("-" * 80)
        
        for i, (match_id, match_url, season, opponent) in enumerate(matches, 1):
            if i % 100 == 0:
                print(f"\nProgress: {i}/{total_matches} matches processed")
                print(f"Players found: {self.stats['players_found']}, Goals found: {self.stats['goals_found']}")
                self.conn.commit()
            
            if self.process_match(match_id, match_url):
                if i <= 10 or i % 100 == 0:  # Show first 10 and every 100th
                    print(f"  ✓ Match {match_id}: {season} vs {opponent}")
            
            self.stats['matches_processed'] += 1
        
        self.conn.commit()
        self.print_statistics()
    
    def print_statistics(self):
        """Print final statistics"""
        print("\n" + "=" * 80)
        print("EXTRACTION STATISTICS")
        print("=" * 80)
        print(f"Matches processed: {self.stats['matches_processed']}")
        print(f"Matches with data: {self.stats['matches_with_data']}")
        print(f"Players found: {self.stats['players_found']}")
        print(f"Goals found: {self.stats['goals_found']}")
        print(f"Errors: {len(self.stats['errors'])}")
        
        # Database statistics
        total_players = self.c.execute("SELECT COUNT(*) FROM Players").fetchone()[0]
        total_goals = self.c.execute("SELECT COUNT(*) FROM Goals").fetchone()[0]
        total_lineups = self.c.execute("SELECT COUNT(*) FROM Match_Lineups").fetchone()[0]
        total_subs = self.c.execute("SELECT COUNT(*) FROM Substitutions").fetchone()[0]
        
        print(f"\nDatabase totals:")
        print(f"  Total players: {total_players}")
        print(f"  Total goals: {total_goals}")
        print(f"  Total lineup entries: {total_lineups}")
        print(f"  Total substitutions: {total_subs}")
        
        # Top scorers
        top_scorers = self.c.execute("""
            SELECT p.player_name, COUNT(g.goal_id) as goals
            FROM Goals g
            JOIN Players p ON g.player_id = p.player_id
            GROUP BY p.player_id
            ORDER BY goals DESC
            LIMIT 10
        """).fetchall()
        
        if top_scorers:
            print("\nTop 10 Goal Scorers:")
            for i, (player, goals) in enumerate(top_scorers, 1):
                print(f"  {i}. {player}: {goals} goals")
    
    def close(self):
        """Close database connection"""
        self.conn.close()


def main():
    parser = ComprehensivePlayerGoalParser()
    
    # Process first 100 matches as a test
    print("Processing first 100 matches as a test...")
    parser.run(limit=100)
    
    # Ask if user wants to continue
    response = input("\nContinue with all matches? (y/n): ")
    if response.lower() == 'y':
        parser = ComprehensivePlayerGoalParser()
        parser.run()
    
    parser.close()
    print("\n✅ Player and goal extraction complete!")


if __name__ == '__main__':
    main()
