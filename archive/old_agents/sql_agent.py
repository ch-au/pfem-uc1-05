import os
import sqlite3
from typing import Dict, Any
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.agent_toolkits.sql.base import create_sql_agent
from langchain.agents.agent_types import AgentType
from langchain.prompts import PromptTemplate
from langchain_cohere import ChatCohere, CohereEmbeddings
from config import Config

class FSVSQLAgent:
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
        
        # Create SQLDatabase instance
        self.db = SQLDatabase.from_uri(f"sqlite:///{db_path}")
    
    def _setup_agent(self):
        """Initialize the SQL agent with Cohere LLM"""
        if not self.config.COHERE_API_KEY:
            raise ValueError("COHERE_API_KEY environment variable not set")
        
        # Initialize Cohere LLM
        llm = ChatCohere(
            cohere_api_key=self.config.COHERE_API_KEY,
            model=self.config.LLM_MODEL,
            temperature=0.1
        )
        
        # Create SQL toolkit
        toolkit = SQLDatabaseToolkit(db=self.db, llm=llm)
        
        # Create custom prompt
        prompt_template = """
        You are an expert SQL analyst for FSV Mainz 05 football club data.
        
        Database Context:
        {schema_description}
        
        Available tools:
        - sql_db_list_tables: List all tables
        - sql_db_schema: Get schema for specific tables (format: table1,table2)  
        - sql_db_query: Execute SQL queries
        - sql_db_query_checker: Validate SQL syntax
        
        Rules:
        1. Always explore the schema first if unfamiliar with tables
        2. Use proper table and column names from the schema
        3. For goals/scoring queries, join Goals and Players tables
        4. For match queries, use Matches table with Opponents and Seasons
        5. Show actual SQL queries in your response
        
        Question: {input}
        
        Let's work through this step by step.
        {agent_scratchpad}
        """
        
        # Create agent with custom prompt
        self.agent = create_sql_agent(
            llm=llm,
            toolkit=toolkit,
            agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=5,
            prefix=prompt_template.format(
                schema_description=self.config.SCHEMA_DESCRIPTION,
                input="{input}",
                agent_scratchpad="{agent_scratchpad}"
            )
        )
    
    def query(self, question: str) -> Dict[str, Any]:
        """Process natural language query and return results"""
        try:
            # Add context to the question
            enhanced_question = f"""
            {self.config.FOOTBALL_CONTEXT}
            
            Database Schema:
            {self.config.SCHEMA_DESCRIPTION}
            
            User Question: {question}
            
            Please provide:
            1. The SQL query used
            2. A clear answer in natural language
            3. If showing tabular data, format it nicely
            """
            
            # Execute the agent
            result = self.agent.invoke({"input": enhanced_question})
            
            # Extract SQL query from the result if possible
            sql_query = self._extract_sql_from_result(result)
            
            return {
                "answer": result.get("output", "No answer generated"),
                "sql": sql_query,
                "success": True
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "success": False
            }
    
    def _extract_sql_from_result(self, result: Dict) -> str:
        """Try to extract SQL query from agent result"""
        output = result.get("output", "")
        
        # Look for SQL in the intermediate steps
        if "intermediate_steps" in result:
            for step in result["intermediate_steps"]:
                if isinstance(step, tuple) and len(step) >= 2:
                    action, observation = step
                    # Check if this was a SQL query action
                    if hasattr(action, "tool") and "sql_db_query" in str(action.tool):
                        if hasattr(action, "tool_input"):
                            query = action.tool_input.get("query", "") if isinstance(action.tool_input, dict) else str(action.tool_input)
                            if query.strip():
                                return query.strip()
        
        # Enhanced fallback: look for SQL patterns in output
        import re
        
        # Look for SQL code blocks
        sql_pattern = r'```sql\s*(.*?)\s*```'
        sql_match = re.search(sql_pattern, output, re.DOTALL | re.IGNORECASE)
        if sql_match:
            return sql_match.group(1).strip()
        
        # Look for SQL keywords in lines
        lines = output.split('\n')
        for line in lines:
            line_clean = line.strip()
            if re.match(r'^(SELECT|WITH|INSERT|UPDATE|DELETE)\s+', line_clean, re.IGNORECASE):
                return line_clean
        
        return "SQL query not captured"
    
    def get_schema_info(self) -> str:
        """Get database schema information"""
        return self.db.get_table_info()
    
    def test_connection(self) -> bool:
        """Test database connection"""
        try:
            result = self.db.run("SELECT COUNT(*) FROM Players LIMIT 1;")
            return True
        except Exception:
            return False