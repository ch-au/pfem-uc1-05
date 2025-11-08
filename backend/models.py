"""
Pydantic models for structured LLM outputs
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class SQLQueryResponse(BaseModel):
    """Structured response for NL to SQL conversion"""
    sql: str = Field(description="The generated SQL query")
    explanation: Optional[str] = Field(None, description="Brief explanation of the query")


class QuizQuestion(BaseModel):
    """Structured quiz question with alternatives"""
    question_text: str = Field(description="The quiz question in German")
    correct_answer: str = Field(description="The correct answer")
    alternatives: List[str] = Field(description="List of 3 alternative incorrect answers")
    explanation: Optional[str] = Field(None, description="Brief explanation of the correct answer")
    difficulty: str = Field(description="Difficulty level: easy, medium, hard")
    topic: Optional[str] = Field(None, description="Topic category (e.g., players, matches, history)")
    evidence_score: Optional[float] = Field(None, ge=0.0, le=100.0, description="Confidence score (0-100)")
    sql_query: Optional[str] = Field(None, description="SQL query used to find the answer")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class ChatResponse(BaseModel):
    """Structured chatbot response"""
    answer: str = Field(description="The answer text in German")
    sources: Optional[List[Dict[str, Any]]] = Field(None, description="Data sources used (SQL queries, tables)")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence score (0-1)")
    is_data_query: bool = Field(description="Whether this required database query")
    sql_query: Optional[str] = Field(None, description="SQL query used if is_data_query is True")


class QuizGameCreate(BaseModel):
    """Request model for creating a quiz game"""
    topic: Optional[str] = None
    difficulty: str = Field("medium", description="easy, medium, or hard")
    num_rounds: int = Field(10, ge=1, le=50, description="Number of quiz rounds")
    player_names: List[str] = Field(description="List of player names")


class QuizAnswer(BaseModel):
    """Model for submitting a quiz answer"""
    player_name: str = Field(description="Name of the player submitting answer")
    answer: str = Field(description="The selected answer")
    time_taken: float = Field(ge=0.0, description="Time taken in seconds")


class ChatMessage(BaseModel):
    """Chat message model"""
    role: str = Field(description="role: user or assistant")
    content: str = Field(description="Message content")
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

