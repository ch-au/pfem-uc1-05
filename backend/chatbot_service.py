"""
Chatbot service for conversational Q&A about Mainz 05 history
Integrates data queries (SQL) with general knowledge Q&A
"""
import uuid
import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import psycopg2
import psycopg2.extras
from .final_agent import FinalSQLAgent
from .llm_service import LLMService
from .models import ChatResponse, ChatMessage
from .config import Config

logger = logging.getLogger("chatbot_service")


class ChatbotService:
    """Service for chatbot interactions with session management"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.sql_agent = FinalSQLAgent()
        self.llm_service = LLMService(config)
        # Use connection pooling instead of creating new connections each time
        try:
            self.use_pool = True
            self.config.get_pg_pool()  # Initialize pool
        except:
            self.use_pool = False
            self.pg_dsn = self.config.build_psycopg2_dsn()
    
    def create_session(self, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Create a new chat session"""
        session_id = str(uuid.uuid4())
        
        if self.use_pool:
            conn = self.config.get_connection()
            try:
                with conn.cursor() as cur:
                    # Convert dict to JSON for JSONB column
                    metadata_json = psycopg2.extras.Json(metadata or {})
                    cur.execute("""
                        INSERT INTO public.chat_sessions (session_id, metadata)
                        VALUES (%s, %s)
                    """, (session_id, metadata_json))
                    conn.commit()
            finally:
                self.config.return_connection(conn)
        else:
            with psycopg2.connect(self.pg_dsn) as conn:
                with conn.cursor() as cur:
                    metadata_json = psycopg2.extras.Json(metadata or {})
                    cur.execute("""
                        INSERT INTO public.chat_sessions (session_id, metadata)
                        VALUES (%s, %s)
                    """, (session_id, metadata_json))
                    conn.commit()
        
        return session_id
    
    def get_session_history(self, session_id: str, limit: Optional[int] = None) -> List[ChatMessage]:
        """Retrieve chat history for a session
        
        Args:
            session_id: Session ID
            limit: Optional limit on number of messages to fetch (for performance)
        """
        if self.use_pool:
            conn = self.config.get_connection()
            try:
                with conn.cursor() as cur:
                    if limit:
                        # Use parameterized query - LIMIT must be integer, validate it
                        cur.execute("""
                            SELECT role, content, metadata, created_at
                            FROM public.chat_messages
                            WHERE session_id = %s
                            ORDER BY created_at DESC
                            LIMIT %s
                        """, (session_id, limit))
                    else:
                        cur.execute("""
                            SELECT role, content, metadata, created_at
                            FROM public.chat_messages
                            WHERE session_id = %s
                            ORDER BY created_at ASC
                        """, (session_id,))
                    
                    messages = []
                    rows = cur.fetchall()
                    # Reverse if we used DESC order (when limit is used)
                    if limit:
                        rows = reversed(rows)
                    for row in rows:
                        messages.append(ChatMessage(
                            role=row[0],
                            content=row[1],
                            metadata=row[2],
                            timestamp=row[3]
                        ))
                return messages
            finally:
                self.config.return_connection(conn)
        else:
            with psycopg2.connect(self.pg_dsn) as conn:
                with conn.cursor() as cur:
                    if limit:
                        cur.execute("""
                            SELECT role, content, metadata, created_at
                            FROM public.chat_messages
                            WHERE session_id = %s
                            ORDER BY created_at DESC
                            LIMIT %s
                        """, (session_id, limit))
                    else:
                        cur.execute("""
                            SELECT role, content, metadata, created_at
                            FROM public.chat_messages
                            WHERE session_id = %s
                            ORDER BY created_at ASC
                        """, (session_id,))
                    
                    messages = []
                    rows = cur.fetchall()
                    # Reverse if we used DESC order (when limit is used)
                    if limit:
                        rows = reversed(rows)
                    for row in rows:
                        messages.append(ChatMessage(
                            role=row[0],
                            content=row[1],
                            metadata=row[2],
                            timestamp=row[3]
                        ))
            
            return messages
    
    def _is_data_query(self, question: str, chat_history: List[ChatMessage]) -> bool:
        """Determine if question requires database query"""
        # Simple heuristic: check for data-related keywords
        data_keywords = [
            "statistik", "statistiken", "daten", "tabelle", "liste",
            "wie viele", "anzahl", "spieler", "spiel", "saison",
            "tore", "torschütze", "tabelle", "spieltag", "punkte",
            "statistisch", "rekord", "rekorde", "meiste", "wenigste",
            "wann", "wo", "gegen wen", "welcher", "welche"
        ]
        
        question_lower = question.lower()
        return any(keyword in question_lower for keyword in data_keywords)
    
    def _update_session(self, session_id: str, cur=None):
        """Update session timestamp and extend expiry
        
        Args:
            session_id: Session ID
            cur: Optional cursor (if provided, use existing transaction)
        """
        if cur is not None:
            # Use existing cursor/transaction
            cur.execute("""
                UPDATE public.chat_sessions
                SET updated_at = CURRENT_TIMESTAMP,
                    expires_at = CURRENT_TIMESTAMP + INTERVAL '1 hour'
                WHERE session_id = %s
            """, (session_id,))
            return
        
        # Standalone operation
        if self.use_pool:
            conn = self.config.get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE public.chat_sessions
                        SET updated_at = CURRENT_TIMESTAMP,
                            expires_at = CURRENT_TIMESTAMP + INTERVAL '1 hour'
                        WHERE session_id = %s
                    """, (session_id,))
                    conn.commit()
            finally:
                self.config.return_connection(conn)
        else:
            with psycopg2.connect(self.pg_dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE public.chat_sessions
                        SET updated_at = CURRENT_TIMESTAMP,
                            expires_at = CURRENT_TIMESTAMP + INTERVAL '1 hour'
                        WHERE session_id = %s
                    """, (session_id,))
                    conn.commit()
    
    def _save_message(self, session_id: str, role: str, content: str, metadata: Optional[Dict[str, Any]] = None, cur=None):
        """Save message to database
        
        Args:
            session_id: Session ID
            role: Message role (user/assistant)
            content: Message content
            metadata: Optional metadata dict
            cur: Optional cursor (if provided, use existing transaction)
        """
        metadata_json = psycopg2.extras.Json(metadata or {})
        
        if cur is not None:
            # Use existing cursor/transaction
            cur.execute("""
                INSERT INTO public.chat_messages (session_id, role, content, metadata)
                VALUES (%s, %s, %s, %s)
            """, (session_id, role, content, metadata_json))
            return
        
        # Standalone operation
        if self.use_pool:
            conn = self.config.get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO public.chat_messages (session_id, role, content, metadata)
                        VALUES (%s, %s, %s, %s)
                    """, (session_id, role, content, metadata_json))
                    conn.commit()
            finally:
                self.config.return_connection(conn)
        else:
            with psycopg2.connect(self.pg_dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO public.chat_messages (session_id, role, content, metadata)
                        VALUES (%s, %s, %s, %s)
                    """, (session_id, role, content, metadata_json))
                    conn.commit()
    
    def process_message(
        self,
        session_id: str,
        user_message: str,
        chat_history: Optional[List[ChatMessage]] = None
    ) -> ChatResponse:
        """
        Process user message and return response
        
        Optimized version that batches database operations to reduce round-trips.
        
        Args:
            session_id: Chat session ID
            user_message: User's message
            chat_history: Optional chat history (will fetch if not provided)
        
        Returns:
            ChatResponse with answer and metadata
        """
        # Batch: Get chat history + update session + save user message in one transaction
        # Only fetch last 20 messages (we only use last 10 anyway, but fetch a bit more for context)
        if chat_history is None:
            chat_history = self.get_session_history(session_id, limit=20)
        
        # Batch database operations: update session + save user message in one transaction
        metadata_json = psycopg2.extras.Json({})
        
        if self.use_pool:
            conn = self.config.get_connection()
            try:
                with conn.cursor() as cur:
                    # Update session timestamp
                    cur.execute("""
                        UPDATE public.chat_sessions
                        SET updated_at = CURRENT_TIMESTAMP,
                            expires_at = CURRENT_TIMESTAMP + INTERVAL '1 hour'
                        WHERE session_id = %s
                    """, (session_id,))
                    
                    # Save user message
                    cur.execute("""
                        INSERT INTO public.chat_messages (session_id, role, content, metadata)
                        VALUES (%s, %s, %s, %s)
                    """, (session_id, "user", user_message, metadata_json))
                    
                    conn.commit()
            finally:
                self.config.return_connection(conn)
        else:
            with psycopg2.connect(self.pg_dsn) as conn:
                with conn.cursor() as cur:
                    # Update session timestamp
                    cur.execute("""
                        UPDATE public.chat_sessions
                        SET updated_at = CURRENT_TIMESTAMP,
                            expires_at = CURRENT_TIMESTAMP + INTERVAL '1 hour'
                        WHERE session_id = %s
                    """, (session_id,))
                    
                    # Save user message
                    cur.execute("""
                        INSERT INTO public.chat_messages (session_id, role, content, metadata)
                        VALUES (%s, %s, %s, %s)
                    """, (session_id, "user", user_message, metadata_json))
                    
                    conn.commit()
        
        # Determine if this is a data query
        is_data_query = self._is_data_query(user_message, chat_history)
        
        if is_data_query:
            # Use SQL agent for data queries
            logger.debug(f"[CHAT] Executing SQL query for: {user_message[:100]}")
            result = self.sql_agent.query(user_message)
            
            if result.get("success"):
                logger.debug(f"[CHAT] SQL query successful - rows: {len(result.get('rows', []))}")
                answer = result.get("answer", "Die Daten wurden erfolgreich abgerufen.")
                
                response = ChatResponse(
                    answer=answer,
                    sources=[{
                        "type": "sql_query",
                        "sql": result.get("sql"),
                        "columns": result.get("columns"),
                        "row_count": len(result.get("rows", []))
                    }],
                    confidence=0.95,  # High confidence for data queries
                    is_data_query=True,
                    sql_query=result.get("sql")
                )
            else:
                logger.warning(f"[CHAT] SQL query failed, falling back to general LLM: {result.get('error')}")
                # Fallback to general LLM if SQL fails
                response = self._general_qa(user_message, chat_history, session_id)
                response.is_data_query = False
        else:
            # Use general LLM for conversational questions
            logger.debug(f"[CHAT] Using general LLM for conversational question")
            response = self._general_qa(user_message, chat_history, session_id)
        
        # Save assistant response (separate operation after response is ready)
        self._save_message(
            session_id,
            "assistant",
            response.answer,
            {
                "is_data_query": response.is_data_query,
                "sql_query": response.sql_query,
                "confidence": response.confidence,
                "sources": response.sources
            }
        )
        
        return response
    
    def _general_qa(
        self,
        question: str,
        chat_history: List[ChatMessage],
        session_id: str
    ) -> ChatResponse:
        """Handle general knowledge questions using LLM"""
        
        logger.debug(f"[CHAT] Building context for general QA - history: {len(chat_history)} messages")
        
        # Build context from chat history
        context_messages = []
        
        # Add system context
        system_prompt = f"""Du bist ein hilfreicher Assistent für Fragen zur Geschichte von Mainz 05 (1. FSV Mainz 05).
        
{self.config.FOOTBALL_CONTEXT}

Antworte auf Deutsch, sei freundlich und informativ. Wenn du dir nicht sicher bist, sage das auch.
"""
        context_messages.append({"role": "system", "content": system_prompt})
        
        # Add recent chat history (last 10 messages to avoid token limits)
        recent_history = chat_history[-10:] if len(chat_history) > 10 else chat_history
        logger.debug(f"[CHAT] Using {len(recent_history)} recent messages from history")
        for msg in recent_history:
            if msg.role in ["user", "assistant"]:
                context_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
        
        # Add current question
        context_messages.append({"role": "user", "content": question})
        
        logger.debug(f"[CHAT] Calling LLM with {len(context_messages)} total messages")
        
        # Get LLM response
        llm_response = self.llm_service.chat_completion(
            messages=context_messages,
            temperature=0.7,
            session_id=session_id
        )
        
        answer = llm_response["content"]
        logger.debug(f"[CHAT] Received LLM response - length: {len(answer)} chars")
        
        return ChatResponse(
            answer=answer,
            confidence=0.8,  # Moderate confidence for general Q&A
            is_data_query=False
        )

