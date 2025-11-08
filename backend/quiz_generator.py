"""
Quiz question generator using AI and database queries
"""
import json
import uuid
from typing import Dict, Any, List, Optional, Tuple
import psycopg2
from .final_agent import FinalSQLAgent
from .llm_service import LLMService
from .models import QuizQuestion
from .config import Config


class QuizGenerator:
    """Service for generating quiz questions using AI"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.sql_agent = FinalSQLAgent()
        self.llm_service = LLMService(config)
        self.pg_dsn = self.config.build_psycopg2_dsn()
    
    def generate_question(
        self,
        topic: Optional[str] = None,
        difficulty: str = "medium"
    ) -> QuizQuestion:
        """
        Generate a quiz question using AI
        
        Steps:
        1. Generate SQL query to find interesting facts
        2. Execute query to get candidate answers
        3. Use LLM to formulate question and alternatives
        4. Validate and return structured question
        """
        # Step 1: Find interesting facts from database
        facts_query = self._generate_facts_query(topic, difficulty)
        
        if not facts_query:
            # Fallback: generate question without database query
            return self._generate_general_question(topic, difficulty)
        
        # Execute query to get data
        try:
            result = self.sql_agent.query(facts_query)
            if not result.get("success") or not result.get("rows"):
                # Fallback if query fails
                return self._generate_general_question(topic, difficulty)
            
            columns = result.get("columns", [])
            rows = result.get("rows", [])
            
            # Step 2: Use LLM to generate question from data
            question = self._generate_question_from_data(
                columns, rows, topic, difficulty, result.get("sql")
            )
            
            # Step 3: Validate question
            self._validate_question(question)
            
            return question
            
        except Exception as e:
            # Fallback on error
            return self._generate_general_question(topic, difficulty)
    
    def _generate_facts_query(self, topic: Optional[str], difficulty: str) -> Optional[str]:
        """Generate a natural language query to find interesting facts"""
        
        topic_prompts = {
            "easy": [
                "Wie viele Tore hat Mainz 05 in der Bundesliga insgesamt geschossen?",
                "Wer ist der Top-Torschütze von Mainz 05?",
                "Wie viele Spiele hat Mainz 05 in der Bundesliga gewonnen?",
                "Welcher Spieler hat die meisten Tore für Mainz 05 geschossen?",
            ],
            "medium": [
                "Welcher Spieler hat das schnellste Tor für Mainz 05 in der Bundesliga geschossen?",
                "Wer hat die meisten Tore in einer Saison für Mainz 05 geschossen?",
                "Welcher Spieler hat die meisten Minuten für Mainz 05 gespielt?",
                "Gegen welchen Gegner hat Mainz 05 am häufigsten gespielt?",
            ],
            "hard": [
                "Welcher Spieler hat das schnellste Tor in einem Bundesliga-Spiel für Mainz 05 geschossen?",
                "Wer ist der älteste Torschütze von Mainz 05?",
                "Welcher Spieler hatte die beste Tore pro Spiel Quote für Mainz 05?",
                "In welcher Saison hat Mainz 05 die meisten Tore geschossen?",
            ]
        }
        
        if topic:
            # Use topic-specific query
            query = f"Finde interessante Fakten über {topic} für Mainz 05"
        else:
            # Use difficulty-based query
            import random
            prompts = topic_prompts.get(difficulty, topic_prompts["medium"])
            query = random.choice(prompts)
        
        return query
    
    def _generate_question_from_data(
        self,
        columns: List[str],
        rows: List[List[Any]],
        topic: Optional[str],
        difficulty: str,
        sql_query: Optional[str]
    ) -> QuizQuestion:
        """Generate quiz question using LLM with structured output"""
        
        # Prepare data preview (first few rows)
        preview_rows = rows[:5]
        data_preview = {
            "columns": columns,
            "rows": preview_rows,
            "total_rows": len(rows)
        }
        
        # Build prompt
        system_prompt = """Du bist ein Quiz-Fragen-Generator für Mainz 05 Fußball-Verein.
Erstelle eine interessante Quiz-Frage basierend auf den bereitgestellten Daten.

WICHTIG:
- Die Frage muss auf Deutsch sein
- Sie muss interessant und herausfordernd sein
- Die korrekte Antwort muss aus den Daten stammen
- Die Alternativen müssen plausibel sein, aber falsch
- Unterschiedliche Schwierigkeitsgrade: easy (einfache Fakten), medium (spezifischere Fakten), hard (sehr spezifische oder seltene Fakten)
"""
        
        user_prompt = f"""Basierend auf folgenden Daten über Mainz 05, erstelle eine Quiz-Frage:

Schwierigkeitsgrad: {difficulty}
Thema: {topic or "Allgemein"}
Daten: {json.dumps(data_preview, ensure_ascii=False, indent=2)}

SQL Query verwendet: {sql_query or "N/A"}

Erstelle eine Quiz-Frage mit:
- Einer interessanten Frage auf Deutsch
- Der korrekten Antwort (muss aus den Daten stammen)
- 3 plausiblen, aber falschen Alternativen
- Einer kurzen Erklärung
- Einer passenden Schwierigkeitseinstufung
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        question = self.llm_service.quiz_generation_completion(
            messages=messages,
            response_model=QuizQuestion,
            temperature=0.8
        )
        
        # Add metadata
        question.sql_query = sql_query
        question.metadata = {
            "data_preview": data_preview,
            "topic": topic
        }
        
        # Calculate evidence score (simpler: check if answer exists in data)
        question.evidence_score = self._calculate_evidence_score(
            question.correct_answer, columns, rows
        )
        
        return question
    
    def _generate_general_question(
        self,
        topic: Optional[str],
        difficulty: str
    ) -> QuizQuestion:
        """Fallback: generate question without database query"""
        
        system_prompt = """Du bist ein Quiz-Fragen-Generator für Mainz 05 Fußball-Verein.
Erstelle eine interessante Quiz-Frage basierend auf allgemeinem Wissen über Mainz 05.
"""
        
        user_prompt = f"""Erstelle eine Quiz-Frage über Mainz 05:

Schwierigkeitsgrad: {difficulty}
Thema: {topic or "Allgemein"}

Die Frage sollte:
- Interessant und herausfordernd sein
- Auf Deutsch formuliert sein
- 3 plausible falsche Alternativen haben
- Eine kurze Erklärung enthalten
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        question = self.llm_service.quiz_generation_completion(
            messages=messages,
            response_model=QuizQuestion,
            temperature=0.8
        )
        
        # Lower evidence score for general questions
        question.evidence_score = 70.0
        question.metadata = {"topic": topic, "source": "general_knowledge"}
        
        return question
    
    def _validate_question(self, question: QuizQuestion):
        """Validate generated question"""
        # Ensure alternatives are distinct
        all_answers = [question.correct_answer] + question.alternatives
        if len(all_answers) != len(set(all_answers)):
            raise ValueError("Answers must be distinct")
        
        # Ensure we have exactly 3 alternatives
        if len(question.alternatives) != 3:
            raise ValueError("Must have exactly 3 alternatives")
        
        # Ensure difficulty is valid
        if question.difficulty not in ["easy", "medium", "hard"]:
            question.difficulty = "medium"
    
    def _calculate_evidence_score(
        self,
        correct_answer: str,
        columns: List[str],
        rows: List[List[Any]]
    ) -> float:
        """Calculate evidence score based on answer presence in data"""
        answer_lower = correct_answer.lower()
        
        # Check if answer appears in any row
        for row in rows:
            for cell in row:
                if cell and answer_lower in str(cell).lower():
                    return 95.0  # High confidence if found
        
        return 75.0  # Medium confidence if not found
    
    def save_question(self, question: QuizQuestion) -> str:
        """Save question to database and return question_id"""
        question_id = str(uuid.uuid4())
        
        with psycopg2.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO public.quiz_questions (
                        question_id, question_text, correct_answer, alternatives,
                        explanation, difficulty, topic, evidence_score,
                        sql_query, metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    question_id,
                    question.question_text,
                    question.correct_answer,
                    json.dumps(question.alternatives),
                    question.explanation,
                    question.difficulty,
                    question.topic,
                    question.evidence_score,
                    question.sql_query,
                    json.dumps(question.metadata or {})
                ))
                conn.commit()
        
        return question_id
    
    def get_question_from_pool(
        self,
        topic: Optional[str] = None,
        difficulty: str = "medium",
        limit: int = 1
    ) -> List[QuizQuestion]:
        """Retrieve questions from database pool"""
        with psycopg2.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT question_id, question_text, correct_answer, alternatives,
                           explanation, difficulty, topic, evidence_score,
                           sql_query, metadata
                    FROM public.quiz_questions
                    WHERE 1=1
                """
                params = []
                
                if topic:
                    query += " AND topic = %s"
                    params.append(topic)
                
                if difficulty:
                    query += " AND difficulty = %s"
                    params.append(difficulty)
                
                query += " ORDER BY RANDOM() LIMIT %s"
                params.append(limit)
                
                cur.execute(query, params)
                
                questions = []
                for row in cur.fetchall():
                    questions.append(QuizQuestion(
                        question_text=row[1],
                        correct_answer=row[2],
                        alternatives=json.loads(row[3]) if isinstance(row[3], str) else row[3],
                        explanation=row[4],
                        difficulty=row[5],
                        topic=row[6],
                        evidence_score=float(row[7]) if row[7] else None,
                        sql_query=row[8],
                        metadata=json.loads(row[9]) if isinstance(row[9], str) else row[9]
                    ))
        
        return questions




