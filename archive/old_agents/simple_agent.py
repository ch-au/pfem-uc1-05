import os
import sqlite3
from typing import Dict, Any
from langchain_community.utilities import SQLDatabase
from langchain_community.tools import QuerySQLDatabaseTool
from langchain_openai import ChatOpenAI
from config import Config

class SimpleSQLAgent:
    def __init__(self):
        self.config = Config()
        self.db = None
        self.llm = None
        self._setup_database()
        self._setup_llm()
    
    def _setup_database(self):
        """Initialize SQLAlchemy database connection"""
        db_path = str(self.config.DATABASE_PATH)
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database not found at {db_path}")
        
        self.db = SQLDatabase.from_uri(f"sqlite:///{db_path}")
        self.query_tool = QuerySQLDatabaseTool(db=self.db)
    
    def _setup_llm(self):
        """Initialize OpenAI LLM"""
        if not self.config.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        
        self.llm = ChatOpenAI(
            api_key=self.config.OPENAI_API_KEY,
            model=self.config.OPENAI_MODEL
        )
    
    def query(self, question: str) -> Dict[str, Any]:
        """Process natural language query"""
        try:
            # Create enhanced prompt
            prompt = f"""
            Du bist ein SQL-Experte für FSV Mainz 05 Fußballdaten.
            
            Database Schema:
            {self.config.SCHEMA_DESCRIPTION}
            
            Verfügbare Tabellen: Goals, Players, Matches, Opponents, Seasons, Match_Lineups, Substitutions
            
            WICHTIGE SQL REGELN:
            - Verwende IMMER JOINs für Player- und Opponent-Namen
            - Für Spielernamen: JOIN Players p ON g.player_id = p.player_id
            - Für Gegnernamen: JOIN Opponents o ON m.opponent_id = o.opponent_id
            - Heimspiele: WHERE m.is_home_game = 1 oder = true
            - Auswärtsspiele: WHERE m.is_home_game = 0 oder = false
            
            Benutzer-Frage: {question}
            
            Antworte mit einer SQL Query. Verwende SQLite Syntax (nicht PostgreSQL).
            
            SQL Query:"""
            
            # Get SQL from LLM
            response = self.llm.invoke(prompt)
            sql_query = self._extract_sql_from_response(response.content)
            
            if sql_query:
                # Execute the SQL
                try:
                    result = self.query_tool.invoke(sql_query)
                    
                    # Generate natural language answer
            answer_prompt = f"""
                    Formuliere eine kurze Antwort auf Deutsch zur Frage: {question}
                    Nutze das Ergebnis der SQL-Abfrage {sql_query} mit den Daten: {result}
                    Hebe wichtige Zahlen in Stichpunkten hervor, falls vorhanden.
                    """
                    
                    answer_response = self.llm.invoke(answer_prompt)
                    
                    return {
                        "answer": answer_response.content,
                        "sql": sql_query,
                        "success": True,
                        "data": result
                    }
                except Exception as e:
                    return {
                        "error": f"SQL execution failed: {str(e)}",
                        "sql": sql_query,
                        "success": False
                    }
            else:
                return {
                    "error": "Could not generate SQL query",
                    "success": False
                }
                
        except Exception as e:
            return {
                "error": str(e),
                "success": False
            }
    
    def _extract_sql_from_response(self, response: str) -> str:
        """Extract SQL query from LLM response"""
        import re
        
        # Look for SQL code blocks
        sql_pattern = r'```sql\s*(.*?)\s*```'
        sql_match = re.search(sql_pattern, response, re.DOTALL | re.IGNORECASE)
        if sql_match:
            return sql_match.group(1).strip()
        
        # Look for lines starting with SELECT, WITH, etc.
        lines = response.split('\n')
        for line in lines:
            line_clean = line.strip()
            if re.match(r'^(SELECT|WITH|INSERT|UPDATE|DELETE)\s+', line_clean, re.IGNORECASE):
                # Try to capture multi-line SQL
                sql_lines = [line_clean]
                idx = lines.index(line)
                for next_line in lines[idx+1:]:
                    next_clean = next_line.strip()
                    if next_clean and not next_clean.startswith('Answer:') and not next_clean.startswith('Based on'):
                        sql_lines.append(next_clean)
                    else:
                        break
                return ' '.join(sql_lines)
        
        return None
    
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