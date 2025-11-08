import os
import sqlite3
from typing import Dict, Any
from langchain_community.utilities import SQLDatabase
from langchain_cohere import ChatCohere
from langchain_cohere.sql_agent import create_sql_agent
from config import Config

class ImprovedSQLAgent:
    def __init__(self):
        self.config = Config()
        self.db = None
        self.agent = None
        self._setup_database()
        self._setup_agent()
    
    def _setup_database(self):
        """Initialize SQLAlchemy database connection"""
        db_path = str(self.config.DATABASE_PATH)
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database not found at {db_path}")
        
        self.db = SQLDatabase.from_uri(f"sqlite:///{db_path}")
    
    def _setup_agent(self):
        """Initialize the SQL agent with Cohere"""
        if not self.config.COHERE_API_KEY:
            raise ValueError("COHERE_API_KEY environment variable not set")
        
        # Initialize Cohere LLM
        llm = ChatCohere(
            cohere_api_key=self.config.COHERE_API_KEY,
            model=self.config.LLM_MODEL,
            temperature=0.1
        )
        
        # Enhanced schema context
        schema_context = f"""
        FSV Mainz 05 Football Database - IMPORTANT TABLE RELATIONSHIPS:
        
        TABLES AND COLUMNS:
        
        1. Players: player_id (PK), player_name, player_link
        2. Opponents: opponent_id (PK), opponent_name, opponent_link  
        3. Seasons: season_id (PK), season_name, league_name, total_matches
        4. Matches: match_id (PK), season_id (FK), opponent_id (FK), gameday, is_home_game (boolean), mainz_goals, opponent_goals, result_string
        5. Goals: goal_id (PK), match_id (FK), player_id (FK), goal_minute, is_penalty (boolean), is_own_goal (boolean), assisted_by_player_id (FK), score_at_time
        6. Match_Lineups: lineup_id (PK), match_id (FK), player_id (FK), is_starter (boolean), is_captain (boolean), jersey_number, substituted_minute, yellow_card (boolean), red_card (boolean)
        7. Substitutions: substitution_id (PK), match_id (FK), minute, player_in_id (FK), player_out_id (FK)
        
        CRITICAL JOIN PATTERNS:
        - For opponent names: JOIN Matches m ON ... JOIN Opponents o ON m.opponent_id = o.opponent_id
        - For player names: JOIN Goals g ON ... JOIN Players p ON g.player_id = p.player_id  
        - For season info: JOIN Matches m ON ... JOIN Seasons s ON m.season_id = s.season_id
        - Home games: WHERE m.is_home_game = true, Away games: WHERE m.is_home_game = false
        
        IMPORTANT: 
        - Matches table has opponent_id (not opponent_name) - always join with Opponents table
        - Goals table has player_id (not player_name) - always join with Players table
        - Use proper boolean values: true/false (not 1/0)
        
        {self.config.FOOTBALL_CONTEXT}
        """
        
        # Create agent with enhanced configuration
        self.agent = create_sql_agent(
            llm=llm,
            db=self.db,
            prompt_prefix=schema_context,
            verbose=True,
            max_execution_time=30,
            max_iterations=5
        )
    
    def query(self, question: str) -> Dict[str, Any]:
        """Process natural language query and return results"""
        try:
            # Add explicit instruction for complex queries
            enhanced_question = f"""
            {question}
            
            IMPORTANT REMINDERS:
            - To get opponent names, JOIN Matches with Opponents table on opponent_id
            - To get player names, JOIN Goals with Players table on player_id
            - Use m.is_home_game = true for home games, false for away games
            - Always include the actual SQL query in your response
            """
            
            # Execute the agent
            result = self.agent.invoke({"input": enhanced_question})
            
            # Extract information from result
            output = result.get("output", "")
            sql_query = self._extract_sql_from_output(output)
            
            return {
                "answer": output,
                "sql": sql_query,
                "success": True
            }
            
        except Exception as e:
            error_msg = str(e)
            
            # Try to extract SQL from error for debugging
            sql_query = self._extract_sql_from_error(error_msg)
            
            # Provide helpful error message
            if "no such column" in error_msg:
                helpful_msg = f"Database schema error: {error_msg}. Remember to join tables properly - Matches table uses opponent_id (join with Opponents), Goals table uses player_id (join with Players)."
            else:
                helpful_msg = f"Query error: {error_msg}"
            
            return {
                "error": helpful_msg,
                "sql": sql_query,
                "success": False
            }
    
    def _extract_sql_from_output(self, output: str) -> str:
        """Extract SQL query from agent output"""
        import re
        
        # Look for SQL code blocks
        sql_patterns = [
            r'```sql\s*(.*?)\s*```',
            r'```\s*(SELECT.*?)\s*```',
            r'Query:\s*(SELECT.*?)(?:\n|$)',
            r'SQL:\s*(SELECT.*?)(?:\n|$)'
        ]
        
        for pattern in sql_patterns:
            match = re.search(pattern, output, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # Look for SELECT statements in the output
        lines = output.split('\n')
        for line in lines:
            line_clean = line.strip()
            if re.match(r'^SELECT\s+', line_clean, re.IGNORECASE):
                return line_clean
        
        return "SQL query not found in response"
    
    def _extract_sql_from_error(self, error_msg: str) -> str:
        """Extract SQL from error message"""
        import re
        
        # Look for SQL in error message
        sql_match = re.search(r'\[SQL: (.*?)\]', error_msg)
        if sql_match:
            return sql_match.group(1)
        
        return "SQL not available"
    
    def test_connection(self) -> bool:
        """Test database connection"""
        try:
            result = self.db.run("SELECT COUNT(*) FROM Players LIMIT 1;")
            return True
        except Exception:
            return False
    
    def get_schema_info(self) -> str:
        """Get database schema information"""
        return self.db.get_table_info()