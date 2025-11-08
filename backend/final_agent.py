import os
import re
import json
import math
import unicodedata
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import psycopg2
import yaml
from langchain_community.utilities import SQLDatabase
from langchain_openai import OpenAIEmbeddings
from .config import Config
from .llm_service import LLMService

logger = logging.getLogger("final_agent")

class FinalSQLAgent:
    def __init__(self):
        self.config = Config()
        self.db = None
        self.llm_service = None
        self.pg_dsn: Optional[str] = None
        self.embeddings = None
        self._players_index: Dict[str, Dict[str, Any]] = {}
        self._opponents_index: Dict[str, Dict[str, Any]] = {}
        self._emb_cache_path = Path(__file__).parent / "name_embeddings_cache.json"
        self.prompts: Dict[str, Any] = self._load_prompts()
        self._setup_database()
        self._setup_llm()
        self._setup_embeddings()
    
    def _setup_database(self):
        """Initialize Postgres connection for LangChain SQLDatabase and raw queries."""
        if not self.config.PG_ENABLED:
            raise RuntimeError("Postgres is required. Set PG_ENABLED=true or configure DB_URL environment variable.")
        # Use Config connection helpers
        uri = self.config.build_sqlalchemy_uri()
        self.db = SQLDatabase.from_uri(uri)
        # Build psycopg2 DSN for raw execution
        self.pg_dsn = self.config.build_psycopg2_dsn()
    
    def _setup_llm(self):
        """Initialize LLM service with Langfuse tracing"""
        # Use LiteLLM default model (no API key required if using free models like Gemini)
        self.llm_service = LLMService(self.config)

    def _setup_embeddings(self):
        # Embeddings are optional - semantic hints work without them
        # If OpenAI API key is provided, use embeddings for better semantic search
        if self.config.OPENAI_API_KEY:
            try:
                self.embeddings = OpenAIEmbeddings(
                    api_key=self.config.OPENAI_API_KEY,
                    model=self.config.OPENAI_EMBEDDING_MODEL
                )
            except Exception as e:
                logger.warning(f"Failed to initialize embeddings: {e}. Continuing without embeddings.")
                self.embeddings = None
        else:
            self.embeddings = None
        # Lazy-load indices and cache
        # We rely on Postgres for both usage and pgvector.
        self._load_name_indices()
    
    def query(self, question: str) -> Dict[str, Any]:
        """Process natural language query using live schema, repair loop, and structured results."""
        try:
            schema_info = self._get_live_schema()
            hints = self._semantic_hints(question)
            resolved = self._resolve_entities(question, hints)
            sql_query, columns, rows, last_error = self._repair_loop(question, schema_info, hints, resolved)
            
            if sql_query and columns is not None:
                answer = self._generate_answer(sql_query, columns, rows, question)
                return {
                    "success": True,
                    "sql": sql_query,
                    "columns": columns,
                    "rows": rows,
                    "answer": answer
                }
            
            # Failed after repairs
            return {
                "success": False,
                "sql": sql_query or "No SQL generated",
                "error": last_error or "Query processing failed"
            }
        except Exception as e:
            return {"success": False, "error": f"Agent error: {str(e)}"}
    
    def _extract_sql_from_response(self, response: str) -> Optional[str]:
        """Extract SQL query from LLM response. Prefer JSON {"sql": "..."}; fallback to SQL text."""
        txt = (response or "").strip()

        # Try JSON code block
        json_block = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", txt, re.IGNORECASE)
        if json_block:
            try:
                import json
                obj = json.loads(json_block.group(1))
                if isinstance(obj, dict) and isinstance(obj.get("sql"), str):
                    return obj["sql"].strip()
            except Exception:
                pass

        # Try inline JSON
        inline = re.search(r"(\{\s*\"sql\"\s*:\s*\"[\s\S]*?\"\s*\})", txt)
        if inline:
            try:
                import json
                obj = json.loads(inline.group(1))
                if isinstance(obj, dict) and isinstance(obj.get("sql"), str):
                    return obj["sql"].strip()
            except Exception:
                pass

        # Legacy formats
        if txt.startswith('SQL:'):
            txt = txt[4:].strip()

        sql_pattern = r'```sql\s*(.*?)\s*```'
        sql_match = re.search(sql_pattern, txt, re.DOTALL | re.IGNORECASE)
        if sql_match:
            return sql_match.group(1).strip()

        code_pattern = r'```\s*(SELECT[\s\S]*?)\s*```'
        code_match = re.search(code_pattern, txt, re.DOTALL | re.IGNORECASE)
        if code_match:
            return code_match.group(1).strip()

        lines = txt.split('\n')
        sql_lines: List[str] = []
        in_sql = False
        for line in lines:
            line_clean = line.strip()
            if line_clean.upper().startswith('SELECT'):
                in_sql = True
                sql_lines = [line_clean]
            elif in_sql:
                if line_clean and not line_clean.startswith('#') and not line_clean.startswith('--'):
                    sql_lines.append(line_clean)
                else:
                    break
        if sql_lines:
            return ' '.join(sql_lines)
        if txt.upper().startswith('SELECT'):
            return txt
        return None
    
    def _get_live_schema(self) -> str:
        return self.db.get_table_info()
    
    def _build_sql_prompt(self, question: str, schema_info: str, previous_sql: Optional[str] = None, last_error: Optional[str] = None, hints: Optional[Dict[str, List[Tuple[str, str]]]] = None, resolved: Optional[Dict[str, List[str]]] = None) -> str:
        base_rules = self.prompts.get("sql", {}).get("base_rules", (
            "CRITICAL RULES (Postgres):\n"
            "- Return only JSON with key 'sql'. Example: {\"sql\": \"SELECT ...\"}.\n"
            "- Use exactly one SELECT statement.\n"
            "- Schema is in 'public'. Prefer fully qualified names (public.Matches etc.).\n"
            "- JOIN keys: Goals↔Players via player_id; Matches↔Opponents via opponent_id; Matches↔Seasons via season_id; Match_Lineups↔Players via player_id.\n"
            "- Additional tables available: public.Player_Careers (player career stations), public.Referees, public.Coaches.\n"
            "- Matches have no match_date; use Seasons.season_name.\n"
            "- Use Postgres SQL; use ILIKE for case-insensitive text filters.\n"
            "- Booleans are TRUE/FALSE. Use m.is_home_game = TRUE (home) or FALSE (away).\n"
            "- Avoid duplicate rows when joining detail tables: only join Goals/Match_Lineups if needed. Otherwise query just Matches. If join is required, aggregate (COUNT/SUM) or use DISTINCT ON (m.match_id) wisely.\n"
            "- Always add ORDER BY appropriate columns.\n"
            "- Ensure LIMIT 200 is present if many rows.\n"
            "- Use explicit table aliases: g=public.goals, p=public.players, m=public.matches, o=public.teams (for opponents), s=public.seasons, ml=public.match_lineups, sub=public.match_substitutions, pc=public.player_careers.\n"
            "- Minutes pattern: starters = COALESCE(ml.substituted_minute, 90); substitutes = 90 - first sub.minute where sub.player_in_id = ml.player_id for that match.\n"
            "- Karten: Für Gelb/Gelb-Rot/Rot nutze public.match_lineups: yellow_card_count (Anzahl), yellow_card (bool), red_card (bool), second_yellow (bool).\n"
            "- IMPORTANT: Goals table uses 'minute' (not 'goal_minute') and 'stoppage'. For stoppage time goals: use (g.minute > 90 OR (g.minute = 90 AND g.stoppage > 0)) or (g.minute + COALESCE(g.stoppage, 0)) > 90."
        ))
        patterns = self.prompts.get("sql", {}).get("patterns", (
            "COMMON PATTERNS (Postgres):\n"
            "-- Top scorers\n"
            "SELECT p.player_name, COUNT(g.goal_id) AS goals\n"
            "FROM public.Goals g JOIN public.Players p ON g.player_id = p.player_id\n"
            "GROUP BY p.player_id, p.player_name ORDER BY goals DESC LIMIT 200;\n\n"
            "-- Matches vs opponent name (avoid joining goals unless needed)\n"
            "SELECT s.season_name, m.gameday, o.opponent_name, m.is_home_game, m.mainz_goals, m.opponent_goals, m.result_string\n"
            "FROM public.Matches m JOIN public.Opponents o ON m.opponent_id = o.opponent_id JOIN public.Seasons s ON m.season_id = s.season_id\n"
            "WHERE o.opponent_name ILIKE '%' || :team || '%' ORDER BY s.season_name, m.gameday LIMIT 200;\n\n"
            "-- Career stations of a player\n"
            "SELECT p.player_name, pc.club_name, pc.start_year, pc.end_year, pc.appearances, pc.goals\n"
            "FROM public.Player_Careers pc JOIN public.Players p ON pc.player_id = p.player_id\n"
            "WHERE p.player_name ILIKE '%' || :name || '%' ORDER BY COALESCE(pc.start_year,0), COALESCE(pc.end_year,0) LIMIT 200;\n\n"
            "-- Yellow cards for a player (use cards table, remove duplicates)\n"
            "SELECT p.name,\n"
            "       COUNT(DISTINCT (c.match_id, c.player_id, COALESCE(c.minute, 0), c.card_type)) FILTER (WHERE c.card_type = 'yellow') AS yellow_cards,\n"
            "       COUNT(DISTINCT (c.match_id, c.player_id, COALESCE(c.minute, 0), c.card_type)) FILTER (WHERE c.card_type = 'second_yellow') AS second_yellow_cards,\n"
            "       COUNT(DISTINCT (c.match_id, c.player_id, COALESCE(c.minute, 0), c.card_type)) FILTER (WHERE c.card_type = 'red') AS red_cards\n"
            "FROM public.cards c JOIN public.players p ON c.player_id = p.player_id\n"
            "JOIN public.match_lineups ml ON c.match_id = ml.match_id AND c.player_id = ml.player_id\n"
            "WHERE p.name ILIKE '%' || :name || '%'\n"
            "GROUP BY p.player_id, p.name\n"
            "ORDER BY yellow_cards DESC LIMIT 200;\n\n"
            "-- Minutes helper CTE for appearances/minutes queries\n"
            "WITH minutes AS (\n"
            "  SELECT ml.player_id, ml.match_id,\n"
            "         CASE WHEN ml.is_starter = TRUE THEN COALESCE(ml.substituted_minute, 90)\n"
            "              ELSE 90 - COALESCE((SELECT MIN(sub2.minute) FROM public.Substitutions sub2\n"
            "                                   WHERE sub2.match_id = ml.match_id\n"
            "                                     AND sub2.player_in_id = ml.player_id), 90) END AS minutes_played\n"
            "  FROM public.Match_Lineups ml\n"
            ")\n\n"
        ))
        hints_str = ""
        if hints:
            pl = ", ".join([f"{pid}: {pname}" for pid, pname in hints.get("players", [])])
            op = ", ".join([f"{oid}: {oname}" for oid, oname in hints.get("opponents", [])])
            hints_str = (
                "SEMANTIC SEARCH HINTS (use these canonical entities if relevant):\n"
                f"Players (player_id: name): {pl}\n"
                f"Opponents (opponent_id: name): {op}\n\n"
            )
        resolved_str = ""
        if resolved and (resolved.get("player_ids") or resolved.get("opponent_ids")):
            pids = ",".join(resolved.get("player_ids", [])) or ""
            oids = ",".join(resolved.get("opponent_ids", [])) or ""
            resolved_str = (
                "RESOLVED ENTITIES (must prefer IDs over names in SQL when relevant):\n"
                f"player_ids: [{pids}]\n"
                f"opponent_ids: [{oids}]\n"
                "If the question is about specific players or opponents, add filters like WHERE p.player_id IN (...) or WHERE o.opponent_id IN (...).\n\n"
            )
        repair_context = ""
        if last_error:
            repair_context = (
                f"\nPrevious SQL:\n{previous_sql}\n\n"
                f"Error: {last_error}\n"
                f"Please correct the SQL strictly following the schema and rules. Return only JSON with the key 'sql'.\n"
            )
        prompt = (
            f"You are a precise SQL generator for an FSV Mainz 05 Postgres database.\n\n"
            f"LIVE SCHEMA:\n{schema_info}\n\n"
            f"{hints_str}{resolved_str}"
            f"{base_rules}\n\n{patterns}"
            f"Question: {question}\n"
            f"Return only a JSON object with a single key 'sql' and the SQL string as the value. No extra text.\n"
            f"Ensure LIMIT 200 is applied if many rows are expected.\n"
            f"{repair_context}"
        )
        return prompt
    
    def _ensure_select_and_limit(self, sql: str, default_limit: int = 200) -> str:
        sql = sql.strip().rstrip(";")
        # Only keep the first statement if multiple
        if ";" in sql:
            sql = sql.split(";")[0]
        if not sql.lower().startswith("select"):
            raise ValueError("Only SELECT statements are allowed")
        # Append LIMIT if not present
        if re.search(r"\blimit\b", sql, re.IGNORECASE) is None:
            sql = f"{sql} LIMIT {default_limit}"
        return sql
    
    def _execute_sql(self, sql: str) -> Tuple[List[str], List[List[Any]]]:
        if not self.pg_dsn:
            raise RuntimeError("Postgres DSN not set")
        with psycopg2.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall()
                columns = [desc.name for desc in cur.description] if cur.description else []
                return columns, [list(r) for r in rows]
    
    def _repair_loop(self, question: str, schema_info: str, hints: Optional[Dict[str, List[Tuple[str, str]]]] = None, resolved: Optional[Dict[str, List[str]]] = None, max_attempts: int = 3) -> Tuple[Optional[str], Optional[List[str]], Optional[List[List[Any]]], Optional[str]]:
        last_error: Optional[str] = None
        last_sql: Optional[str] = None
        used_resolved = resolved
        for attempt in range(max_attempts):
            prompt = self._build_sql_prompt(question, schema_info, previous_sql=last_sql, last_error=last_error, hints=hints, resolved=used_resolved)
            # Use LLMService with Langfuse tracing
            messages = [{"role": "user", "content": prompt}]
            response_format = {"type": "json_object"}  # Request JSON format for SQL
            response = self.llm_service.completion(
                model=self.config.LITELLM_DEFAULT_MODEL,
                messages=messages,
                response_format=response_format,
                temperature=0.0,  # Use deterministic temperature for SQL generation
                trace_name="sql_generation",
                trace_metadata={
                    "question": question,
                    "attempt": attempt + 1,
                    "max_attempts": max_attempts,
                    "has_hints": bool(hints),
                    "has_resolved": bool(used_resolved)
                }
            )
            candidate_sql = self._extract_sql_from_response(response.get("content", "") or "")
            if not candidate_sql:
                last_error = "LLM did not return SQL"
                continue
            try:
                sanitized = self._ensure_select_and_limit(candidate_sql)
                columns, rows = self._execute_sql(sanitized)
                # If zero rows but we used resolved filters, try once without them
                if rows and len(rows) > 0:
                    return sanitized, columns, rows, None
                if used_resolved and (used_resolved.get("player_ids") or used_resolved.get("opponent_ids")):
                    last_error = "No rows with ID filters; retry without filters"
                    used_resolved = None
                    last_sql = sanitized
                    continue
                return sanitized, columns, rows, None
            except Exception as e:
                last_error = str(e)
                last_sql = candidate_sql
                continue
        return last_sql, None, None, last_error
    
    def _generate_answer(self, sql: str, columns: List[str], rows: List[List[Any]], question: str) -> str:
        # Keep short: let the LLM summarize top results based on first up to 20 rows
        preview_rows = rows[:20]
        preview = {"columns": columns, "rows": preview_rows}
        instructions = self.prompts.get("answer", {}).get(
            "system_instructions",
            (
                "Formuliere die Antwort auf Deutsch.\n"
                "- Sei klar und informativ; ein leichter, humorvoller Ton ist erlaubt, aber nicht übertrieben.\n"
                "- Erzähle die wichtigsten Fakten in 1–3 Sätzen.\n"
                "- Wenn sinnvoll, liste die Top-Ergebnisse als kurze Stichpunkte (max. 5).\n"
                "- Weisen Sie darauf hin, dass unten eine Tabelle/Diagramm angezeigt wird, falls viele Zeilen vorhanden sind.\n\n"
            ),
        )
        prompt = (
            f"{instructions}\n"
            f"Frage: {question}\n"
            f"SQL: {sql}\n"
            f"Ergebnis-Vorschau (erste {len(preview_rows)} Zeilen): {preview}\n"
            "Gib nur den Fließtext der Antwort zurück, ohne Codeblöcke."
        )
        try:
            # Use LLMService with Langfuse tracing
            messages = [{"role": "user", "content": prompt}]
            response = self.llm_service.completion(
                model=self.config.LITELLM_DEFAULT_MODEL,
                messages=messages,
                temperature=0.7,
                trace_name="answer_generation",
                trace_metadata={
                    "question": question,
                    "sql": sql,
                    "row_count": len(rows)
                }
            )
            return response.get("content", "") or ""
        except Exception:
            return ""

    # ------------------------
    # Prompts loading
    # ------------------------
    def _load_prompts(self) -> Dict[str, Any]:
        """Load prompts from YAML. Falls back to defaults if file missing or invalid.

        Structure expected:
        sql:
          base_rules: |
            ...
          patterns: |
            ...
        answer:
          system_instructions: |
            ...
        """
        # Resolve prompts path from config or default alongside this file
        try:
            prompts_path = getattr(self.config, "PROMPTS_PATH", Path(__file__).parent / "prompts.yaml")
            prompts_path = Path(prompts_path)
        except Exception:
            prompts_path = Path(__file__).parent / "prompts.yaml"

        if prompts_path.exists():
            try:
                with open(prompts_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                # Ensure dict shape
                if not isinstance(data, dict):
                    return {}
                return data
            except Exception:
                return {}
        return {}

    # ------------------------
    # Embeddings + semantic hints
    # ------------------------
    def _normalize(self, s: str) -> str:
        s = unicodedata.normalize('NFKD', s)
        s = ''.join(ch for ch in s if not unicodedata.combining(ch))
        return s.lower().strip()

    def _load_name_indices(self) -> None:
        if not self.pg_dsn:
            return
        with psycopg2.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                # Use 'name' column instead of 'player_name' (new schema)
                cur.execute("SELECT player_id, name FROM public.players")
                for pid, pname in cur.fetchall():
                    self._players_index[str(pid)] = {"id": str(pid), "name": pname}
            with conn.cursor() as cur:
                # Check if Opponents table exists (may be called 'teams' in new schema)
                try:
                    cur.execute("SELECT opponent_id, opponent_name FROM public.opponents")
                    for oid, oname in cur.fetchall():
                        self._opponents_index[str(oid)] = {"id": str(oid), "name": oname}
                except Exception:
                    # Try 'teams' table if 'opponents' doesn't exist
                    try:
                        cur.execute("SELECT team_id, name FROM public.teams WHERE name != 'FSV Mainz 05'")
                        for tid, tname in cur.fetchall():
                            self._opponents_index[str(tid)] = {"id": str(tid), "name": tname}
                    except Exception:
                        pass  # If neither exists, continue without opponent index

    def _load_embeddings_cache(self) -> None:
        if not self._emb_cache_path.exists():
            return
        try:
            data = json.loads(self._emb_cache_path.read_text())
            players = data.get("players", {})
            for pid, entry in players.items():
                if pid in self._players_index:
                    self._players_index[pid].update({
                        "embedding": entry.get("embedding"),
                        "norm": entry.get("norm"),
                    })
            opponents = data.get("opponents", {})
            for oid, entry in opponents.items():
                if oid in self._opponents_index:
                    self._opponents_index[oid].update({
                        "embedding": entry.get("embedding"),
                        "norm": entry.get("norm"),
                    })
        except Exception:
            pass

    def _save_embeddings_cache(self) -> None:
        data = {
            "players": {pid: {"embedding": v.get("embedding"), "norm": v.get("norm")}
                         for pid, v in self._players_index.items() if v.get("embedding")},
            "opponents": {oid: {"embedding": v.get("embedding"), "norm": v.get("norm")}
                           for oid, v in self._opponents_index.items() if v.get("embedding")},
        }
        try:
            self._emb_cache_path.write_text(json.dumps(data))
        except Exception:
            pass

    def _batch_embed(self, texts: List[str]) -> List[List[float]]:
        if not self.embeddings:
            return [[] for _ in texts]
        return self.embeddings.embed_documents(texts)

    def _ensure_name_embeddings(self, max_new: int = 1000, batch_size: int = 128) -> None:
        if not self.embeddings:
            return
        missing: List[Tuple[str, str, str]] = []  # (kind, id, name)
        for pid, v in self._players_index.items():
            if not v.get("embedding"):
                missing.append(("player", pid, v["name"]))
                if len(missing) >= max_new:
                    break
        if len(missing) < max_new:
            for oid, v in self._opponents_index.items():
                if not v.get("embedding"):
                    missing.append(("opponent", oid, v["name"]))
                    if len(missing) >= max_new:
                        break
        if not missing:
            return
        # Compute in batches
        for i in range(0, len(missing), batch_size):
            chunk = missing[i:i+batch_size]
            vecs = self._batch_embed([t[2] for t in chunk])
            for (kind, ident, name), vec in zip(chunk, vecs):
                if not vec:
                    continue
                norm = math.sqrt(sum(x*x for x in vec)) or 1.0
                if kind == "player" and ident in self._players_index:
                    self._players_index[ident]["embedding"] = vec
                    self._players_index[ident]["norm"] = norm
                elif kind == "opponent" and ident in self._opponents_index:
                    self._opponents_index[ident]["embedding"] = vec
                    self._opponents_index[ident]["norm"] = norm
        self._save_embeddings_cache()

    def _cosine(self, a: List[float], b: List[float], b_norm: float) -> float:
        if not a or not b:
            return -1.0
        a_norm = math.sqrt(sum(x*x for x in a)) or 1.0
        dot = sum(x*y for x, y in zip(a, b))
        return dot / (a_norm * b_norm)

    def _semantic_hints(self, question: str) -> Dict[str, List[Tuple[str, str]]]:
        hints: Dict[str, List[Tuple[str, str]]] = {"players": [], "opponents": []}
        if self.config.PG_ENABLED:
            # Use pgvector for nearest neighbors
            try:
                conn = psycopg2.connect(self.config.build_psycopg2_dsn())
                try:
                    q_vec = self.embeddings.embed_query(question) if self.embeddings else []
                    if q_vec:
                        # Build pgvector literal
                        vec_lit = '[' + ','.join(str(x) for x in q_vec) + ']'
                        with conn.cursor() as cur:
                            query_players = (
                                f"SELECT entity_id, name FROM {self.config.PG_SCHEMA}.name_embeddings "
                                "WHERE kind = 'player' ORDER BY embedding <#> %s::vector LIMIT 5;"
                            )
                            cur.execute(query_players, (vec_lit,))
                            hints["players"] = [(str(eid), name) for eid, name in cur.fetchall()]
                        with conn.cursor() as cur:
                            query_opponents = (
                                f"SELECT entity_id, name FROM {self.config.PG_SCHEMA}.name_embeddings "
                                "WHERE kind = 'opponent' ORDER BY embedding <#> %s::vector LIMIT 5;"
                            )
                            cur.execute(query_opponents, (vec_lit,))
                            hints["opponents"] = [(str(eid), name) for eid, name in cur.fetchall()]
                finally:
                    conn.close()
            except Exception:
                pass
            return hints
        # Fallback: local vectors
        if not self.embeddings:
            return hints
        self._ensure_name_embeddings(max_new=3000)
        q_vec = self.embeddings.embed_query(question)
        player_scores: List[Tuple[float, str, str]] = []
        for pid, v in self._players_index.items():
            vec = v.get("embedding"); norm = v.get("norm")
            if vec and norm:
                sim = self._cosine(q_vec, vec, norm)
                player_scores.append((sim, pid, v["name"]))
        player_scores.sort(reverse=True)
        opponent_scores: List[Tuple[float, str, str]] = []
        for oid, v in self._opponents_index.items():
            vec = v.get("embedding"); norm = v.get("norm")
            if vec and norm:
                sim = self._cosine(q_vec, vec, norm)
                opponent_scores.append((sim, oid, v["name"]))
        opponent_scores.sort(reverse=True)
        hints["players"] = [(pid, name) for sim, pid, name in player_scores[:5] if sim >= 0.18]
        hints["opponents"] = [(oid, name) for sim, oid, name in opponent_scores[:5] if sim >= 0.18]
        return hints

    def _resolve_entities(self, question: str, hints: Dict[str, List[Tuple[str, str]]]) -> Dict[str, List[str]]:
        """Derive concrete player/opponent IDs to filter on, using simple string match + top semantic hits."""
        resolved: Dict[str, List[str]] = {"player_ids": [], "opponent_ids": []}
        qn = self._normalize(question)
        # Prefer exact-ish string matches among top semantic candidates
        for pid, name in hints.get("players", []):
            normalized_name = self._normalize(name)
            if normalized_name in qn or any(tok and tok in qn for tok in normalized_name.split() if len(tok) >= 3):
                resolved["player_ids"].append(pid)
        for oid, name in hints.get("opponents", []):
            normalized_name = self._normalize(name)
            if normalized_name in qn or any(tok and tok in qn for tok in normalized_name.split() if len(tok) >= 3):
                resolved["opponent_ids"].append(oid)
        # If no string match, do not force a filter (default = no filter)
        return resolved
    
    def test_connection(self) -> bool:
        """Test database connection"""
        try:
            # Try lowercase first (new schema), fallback to capitalized (old schema)
            try:
                _ = self.db.run("SELECT COUNT(*) FROM public.players LIMIT 1;")
            except Exception:
                _ = self.db.run("SELECT COUNT(*) FROM public.Players LIMIT 1;")
            return True
        except Exception:
            return False
    
    def get_schema_info(self) -> str:
        """Get database schema information"""
        return self.db.get_table_info()