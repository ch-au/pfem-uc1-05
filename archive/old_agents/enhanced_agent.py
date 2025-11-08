import os
import sqlite3
from typing import Dict, Any
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.agent_toolkits.sql.base import create_sql_agent
from langchain.agents.agent_types import AgentType
from langchain_cohere import ChatCohere
from langchain.prompts import PromptTemplate
from config import Config

class EnhancedSQLAgent:
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
        """Initialize the SQL agent with enhanced schema awareness"""
        if not self.config.COHERE_API_KEY:
            raise ValueError("COHERE_API_KEY environment variable not set")
        
        # Initialize Cohere LLM
        llm = ChatCohere(
            cohere_api_key=self.config.COHERE_API_KEY,
            model=self.config.LLM_MODEL,
            temperature=0.0  # More deterministic for SQL generation
        )
        
        # Create SQL toolkit
        toolkit = SQLDatabaseToolkit(db=self.db, llm=llm)
        
        # Enhanced schema-aware prompt
        schema_prompt = """
        You are a SQL expert for FSV Mainz 05 football database. 

        CRITICAL DATABASE SCHEMA RULES:
        
        1. MATCHES TABLE: match_id, season_id, opponent_id, is_home_game (boolean), mainz_goals, opponent_goals
           - NEVER use opponent_name directly in Matches table
           - Always JOIN with Opponents table: JOIN Opponents o ON m.opponent_id = o.opponent_id
        
        2. GOALS TABLE: goal_id, match_id, player_id, goal_minute, is_penalty, is_own_goal
           - NEVER use player_name directly in Goals table  
           - Always JOIN with Players table: JOIN Players p ON g.player_id = p.player_id
        
        3. COMMON JOIN PATTERNS:
           - Player goals: SELECT p.player_name, COUNT(*) FROM Goals g JOIN Players p ON g.player_id = p.player_id
           - Match opponents: SELECT o.opponent_name FROM Matches m JOIN Opponents o ON m.opponent_id = o.opponent_id
           - Away goals: WHERE m.is_home_game = false (use false, not 0)
           - Home goals: WHERE m.is_home_game = true (use true, not 1)
        
        4. FOR COMPLEX QUERIES:
           - Away goals by player: JOIN Goals->Players AND Goals->Matches->Opponents with is_home_game = false
           - Top scorers vs opponent: JOIN Goals->Players AND Goals->Matches->Opponents
        
        Before writing SQL, think through the joins needed:
        - Need player names? → JOIN Players table
        - Need opponent names? → JOIN Opponents table  
        - Need match context? → JOIN Matches table
        - Need season info? → JOIN Seasons table
        
        Always double-check your column names match the actual schema!
        """
        
        # Create agent with enhanced prompt
        self.agent = create_sql_agent(
            llm=llm,
            toolkit=toolkit,
            agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=3,
            prefix=schema_prompt
        )
    
    def query(self, question: str) -> Dict[str, Any]:
        """Process natural language query with enhanced schema guidance"""
        try:
            # Add schema reminders to the question
            enhanced_question = f"""
            Question: {question}
            
            SCHEMA REMINDER:
            - Matches table: opponent_id (FK to Opponents.opponent_id), is_home_game (boolean)
            - Goals table: player_id (FK to Players.player_id), match_id (FK to Matches.match_id)  
            - For opponent names: JOIN Matches m with Opponents o ON m.opponent_id = o.opponent_id
            - For player names: JOIN Goals g with Players p ON g.player_id = p.player_id
            - Away games: WHERE is_home_game = false
            
            Generate the correct SQL with proper JOINs.
            """
            
            # Execute the agent
            result = self.agent.invoke({"input": enhanced_question})
            
            # Extract SQL query
            sql_query = self._extract_sql_from_result(result)
            
            return {
                "answer": result.get("output", "No answer generated"),
                "sql": sql_query,
                "success": True
            }
            
        except Exception as e:
            error_msg = str(e)
            
            # Extract SQL from error for debugging
            sql_query = self._extract_sql_from_error(error_msg)
            
            # Provide schema-specific error guidance
            if "no such column" in error_msg:
                if "opponent_name" in error_msg:
                    helpful_msg = "❌ Schema Error: opponent_name is not in Matches table. Use: JOIN Opponents o ON m.opponent_id = o.opponent_id, then SELECT o.opponent_name"
                elif "player_name" in error_msg:
                    helpful_msg = "❌ Schema Error: player_name is not in Goals table. Use: JOIN Players p ON g.player_id = p.player_id, then SELECT p.player_name"
                else:
                    helpful_msg = f"❌ Column Error: {error_msg}. Check the database schema and use proper JOINs."
            else:
                helpful_msg = f"Query Error: {error_msg}"
            
            return {
                "error": helpful_msg,
                "sql": sql_query,
                "success": False
            }
    
    def _extract_sql_from_result(self, result: Dict) -> str:
        """Enhanced SQL extraction from agent result"""
        output = result.get("output", "")
        
        # Check intermediate steps first
        if "intermediate_steps" in result:
            for step in result["intermediate_steps"]:
                if isinstance(step, tuple) and len(step) >= 2:
                    action, observation = step
                    if hasattr(action, "tool") and "sql_db_query" in str(action.tool):
                        if hasattr(action, "tool_input"):
                            query = action.tool_input.get("query", "") if isinstance(action.tool_input, dict) else str(action.tool_input)
                            if query.strip():
                                return query.strip()
        
        # Enhanced pattern matching
        import re
        
        patterns = [
            r'```sql\s*(.*?)\s*```',
            r'```\s*(SELECT.*?)\s*```', 
            r'Action Input:\s*"(SELECT.*?)"',
            r'Query:\s*(SELECT.*?)(?:\n|$)',
            r'SQL:\s*(SELECT.*?)(?:\n|$)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, output, re.DOTALL | re.IGNORECASE)
            if match:
                sql = match.group(1).strip()
                # Clean up common formatting issues
                sql = sql.replace('\\n', ' ').replace('\\"', '"')
                return sql
        
        # Look for SELECT statements
        lines = output.split('\n')
        for line in lines:
            line_clean = line.strip()
            if re.match(r'^SELECT\s+', line_clean, re.IGNORECASE):
                return line_clean
        
        return "SQL query not captured"
    
    def _extract_sql_from_error(self, error_msg: str) -> str:
        """Extract SQL from error message"""
        import re
        
        sql_match = re.search(r'\[SQL: (.*?)\]', error_msg)
        if sql_match:
            return sql_match.group(1)
        
        return "SQL not available in error"
    
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