"""
LiteLLM service wrapper with Langfuse integration for structured outputs
"""
import os
import logging
from typing import Optional, Dict, Any, List, TypeVar, Type
from functools import wraps
import litellm
from langfuse import Langfuse
from pydantic import BaseModel, ValidationError
from .config import Config

T = TypeVar('T', bound=BaseModel)

# Trace naming convention prefix
TRACE_PREFIX = "UC1_"

# Setup logger
logger = logging.getLogger("llm_service")


class LLMService:
    """Service for LLM calls using LiteLLM with Langfuse tracing"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        
        # Initialize Langfuse (optional)
        self.langfuse = None
        if self.config.LANGFUSE_PUBLIC_KEY and self.config.LANGFUSE_SECRET_KEY:
            try:
                self.langfuse = Langfuse(
                    public_key=self.config.LANGFUSE_PUBLIC_KEY,
                    secret_key=self.config.LANGFUSE_SECRET_KEY,
                    host=self.config.LANGFUSE_HOST
                )
                logger.info("[LLM] Langfuse tracing enabled")
            except Exception as e:
                logger.warning(f"[LLM] Langfuse initialization failed: {e}. Continuing without tracing.")
                self.langfuse = None
        else:
            logger.info("[LLM] Langfuse not configured. Tracing disabled.")
        
        # Configure LiteLLM
        # Set API keys if provided (LiteLLM supports multiple providers)
        if self.config.OPENAI_API_KEY:
            os.environ["OPENAI_API_KEY"] = self.config.OPENAI_API_KEY
        if self.config.ANTHROPIC_API_KEY:
            os.environ["ANTHROPIC_API_KEY"] = self.config.ANTHROPIC_API_KEY
        
        # Set default model
        litellm.set_verbose = False
        # Drop unsupported params for better compatibility across providers
        litellm.drop_params = True
    
    def test_langfuse_connection(self) -> bool:
        """Test Langfuse connection by creating a test trace"""
        if not self.langfuse:
            logger.warning("[LLM] Langfuse not initialized - check LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY")
            return False
        
        try:
            logger.info("[LLM] Testing Langfuse connection...")
            # Use start_span for trace (creates a top-level trace)
            test_span = self.langfuse.start_span(name="test_connection", metadata={"test": True})
            test_span.end()
            self.langfuse.flush()
            logger.info("[LLM] Langfuse connection test successful")
            return True
        except Exception as e:
            logger.error(f"[LLM] Langfuse connection test failed: {e}", exc_info=True)
            return False
    
    def _get_trace_name(self, base_name: str) -> str:
        """Get trace name with UC1_ prefix"""
        return f"{TRACE_PREFIX}{base_name}"
    
    def _adjust_temperature_for_model(self, model: str, temperature: float) -> float:
        """Adjust temperature based on model constraints"""
        # Some models have specific temperature requirements
        # LiteLLM handles most model-specific constraints automatically
        return temperature
    
    def completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        response_format: Optional[Dict[str, Any]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        trace_name: Optional[str] = None,
        trace_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make LLM completion call with Langfuse tracing
        
        Args:
            model: Model identifier (e.g., "gpt-4o", "anthropic/claude-3-opus")
            messages: List of message dicts with "role" and "content"
            response_format: Structured output format (for JSON mode)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            trace_name: Name for Langfuse trace
            trace_metadata: Additional metadata for trace
        
        Returns:
            LiteLLM response dict
        """
        trace_name_final = self._get_trace_name(trace_name or "llm_completion")
        
        logger.debug(f"[LLM] Starting completion - trace: {trace_name_final}, model: {model}")
        logger.debug(f"[LLM] Messages ({len(messages)}): {[msg.get('role', 'unknown') for msg in messages]}")
        
        # Optional Langfuse tracing
        trace_context_manager = None
        generation = None
        if self.langfuse:
            try:
                logger.info(f"[LLM] Creating Langfuse trace: {trace_name_final}")
                # Create top-level span as trace using context manager
                trace_context_manager = self.langfuse.start_as_current_span(
                    name=trace_name_final,
                    metadata=trace_metadata or {}
                )
                trace_context_manager.__enter__()  # Enter context manually
                # Create generation as observation within the trace context
                generation = self.langfuse.start_observation(
                    as_type='generation',
                    name="completion",
                    model=model,
                    input=messages,
                    model_parameters={
                        "temperature": temperature,
                        "max_tokens": max_tokens
                    }
                )
                logger.info(f"[LLM] Langfuse trace and generation created successfully")
            except Exception as e:
                logger.warning(f"[LLM] Langfuse tracing failed: {e}. Continuing without tracing.", exc_info=True)
                trace_context_manager = None
                generation = None
        else:
            logger.debug(f"[LLM] Langfuse not available, skipping trace creation")
        
        try:
            # Adjust temperature for model-specific constraints
            adjusted_temp = self._adjust_temperature_for_model(model, temperature)
            if adjusted_temp != temperature:
                logger.debug(f"[LLM] Adjusted temperature from {temperature} to {adjusted_temp} for model {model}")
            
            logger.debug(f"[LLM] Calling litellm.completion with model={model}, temp={adjusted_temp}")
            response = litellm.completion(
                model=model,
                messages=messages,
                temperature=adjusted_temp,
                max_tokens=max_tokens,
                response_format=response_format
            )
            
            logger.debug(f"[LLM] Received response - model: {response.model}, tokens: {response.usage.total_tokens if response.usage else 'unknown'}")
            
            # Extract content
            content = response.choices[0].message.content
            
            # Update Langfuse trace if available
            if generation:
                try:
                    generation.update(
                        output=content,
                        model=response.model,
                        usage_details={
                            "prompt_tokens": response.usage.prompt_tokens,
                            "completion_tokens": response.usage.completion_tokens,
                            "total_tokens": response.usage.total_tokens
                        }
                    )
                    generation.end()
                    logger.info(f"[LLM] Langfuse generation updated and ended successfully")
                except Exception as e:
                    logger.warning(f"[LLM] Failed to update Langfuse generation: {e}", exc_info=True)
            
            if trace_context_manager:
                try:
                    # Update metadata on the current span via context
                    current_span_id = self.langfuse.get_current_observation_id()
                    # Span will end automatically when context exits, but we can exit manually
                    trace_context_manager.__exit__(None, None, None)
                    logger.info(f"[LLM] Langfuse trace ended successfully")
                except Exception as e:
                    logger.warning(f"[LLM] Failed to end Langfuse trace: {e}", exc_info=True)
            
            # Flush Langfuse to ensure traces are sent
            if self.langfuse:
                try:
                    self.langfuse.flush()
                    logger.debug(f"[LLM] Langfuse flush completed")
                except Exception as e:
                    logger.warning(f"[LLM] Failed to flush Langfuse: {e}")
            
            logger.debug(f"[LLM] Completion successful - returning result")
            return {
                "content": content,
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            }
            
        except Exception as e:
            logger.error(f"[LLM] Completion failed: {e}", exc_info=True)
            if trace_context_manager:
                try:
                    trace_context_manager.__exit__(type(e), e, None)
                except:
                    pass
            if generation:
                try:
                    generation.end()
                except:
                    pass
            if self.langfuse:
                try:
                    self.langfuse.flush()
                except:
                    pass
            raise
    
    def structured_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        response_model: Type[T],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        trace_name: Optional[str] = None,
        trace_metadata: Optional[Dict[str, Any]] = None
    ) -> T:
        """
        Make structured LLM completion using Pydantic models
        
        Args:
            model: Model identifier
            messages: List of message dicts
            response_model: Pydantic model class for structured output
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            trace_name: Name for Langfuse trace
            trace_metadata: Additional metadata
        
        Returns:
            Parsed Pydantic model instance
        """
        # Use JSON mode for structured outputs
        # LiteLLM handles JSON mode for supported models automatically
        # For models that support response_format, use it; otherwise add to prompt
        response_format = {"type": "json_object"}
        # Add JSON schema instruction for better compatibility
        schema_json = response_model.model_json_schema()
        prompt_instruction = f"\n\nYou must respond with valid JSON matching this schema:\n{str(schema_json)}"
        json_instruction = "\n\nRespond with valid JSON only, no markdown formatting."
        # Add instructions to messages
        messages = messages + [{"role": "system", "content": prompt_instruction}, {"role": "user", "content": json_instruction}]
        
        trace_name_final = self._get_trace_name(trace_name or "structured_completion")
        
        logger.debug(f"[LLM] Starting structured completion - trace: {trace_name_final}, model: {model}, response_model: {response_model.__name__}")
        logger.debug(f"[LLM] Messages ({len(messages)}): {[msg.get('role', 'unknown') for msg in messages]}")
        
        # Optional Langfuse tracing
        trace_context_manager = None
        generation = None
        if self.langfuse:
            try:
                logger.info(f"[LLM] Creating Langfuse trace: {trace_name_final}")
                # Create top-level span as trace using context manager
                trace_context_manager = self.langfuse.start_as_current_span(
                    name=trace_name_final,
                    metadata={
                        **(trace_metadata or {}),
                        "response_model": response_model.__name__
                    }
                )
                trace_context_manager.__enter__()  # Enter context manually
                # Create generation as observation within the trace context
                generation = self.langfuse.start_observation(
                    as_type='generation',
                    name="structured_completion",
                    model=model,
                    input=messages
                )
                logger.info(f"[LLM] Langfuse trace and generation created successfully")
            except Exception as e:
                logger.warning(f"[LLM] Langfuse tracing failed: {e}. Continuing without tracing.", exc_info=True)
                trace_context_manager = None
                generation = None
        else:
            logger.debug(f"[LLM] Langfuse not available, skipping trace creation")
        
        try:
            # Adjust temperature for model-specific constraints
            adjusted_temp = self._adjust_temperature_for_model(model, temperature)
            if adjusted_temp != temperature:
                logger.debug(f"[LLM] Adjusted temperature from {temperature} to {adjusted_temp} for model {model}")
            
            logger.debug(f"[LLM] Calling litellm.completion (structured) with model={model}, temp={adjusted_temp}")
            response = litellm.completion(
                model=model,
                messages=messages,
                temperature=adjusted_temp,
                max_tokens=max_tokens,
                response_format=response_format
            )
            
            content = response.choices[0].message.content
            logger.debug(f"[LLM] Received structured response - model: {response.model}, content length: {len(content) if content else 0}")
            logger.debug(f"[LLM] Raw response (first 500 chars): {content[:500] if content else 'None'}")
            
            # Parse JSON and validate with Pydantic
            import json
            # Remove markdown code blocks if present
            content_clean = content.strip()
            if content_clean.startswith("```json"):
                content_clean = content_clean[7:]
            if content_clean.startswith("```"):
                content_clean = content_clean[3:]
            if content_clean.endswith("```"):
                content_clean = content_clean[:-3]
            content_clean = content_clean.strip()
            
            try:
                logger.debug(f"[LLM] Attempting to parse JSON from cleaned content (length: {len(content_clean)})")
                parsed_json = json.loads(content_clean)
                logger.debug(f"[LLM] JSON parsed successfully, validating with {response_model.__name__}")
                result = response_model(**parsed_json)
                logger.debug(f"[LLM] Pydantic validation successful")
            except (json.JSONDecodeError, ValidationError) as e:
                logger.warning(f"[LLM] Initial JSON parse failed: {e}")
                logger.debug(f"[LLM] Trying fallback: extract JSON from text")
                # Fallback: try to extract JSON from text
                import re
                json_match = re.search(r'\{.*\}', content_clean, re.DOTALL)
                if json_match:
                    logger.debug(f"[LLM] Found JSON match, length: {len(json_match.group())}")
                    parsed_json = json.loads(json_match.group())
                    result = response_model(**parsed_json)
                    logger.debug(f"[LLM] Fallback parse successful")
                else:
                    logger.error(f"[LLM] Could not extract JSON from response")
                    raise ValueError(f"Could not parse JSON from response: {str(e)}")
            
            # Update Langfuse trace if available
            if generation:
                try:
                    generation.update(
                        output=result.model_dump_json(),
                        model=response.model,
                        usage_details={
                            "prompt_tokens": response.usage.prompt_tokens,
                            "completion_tokens": response.usage.completion_tokens,
                            "total_tokens": response.usage.total_tokens
                        }
                    )
                    generation.end()
                    logger.info(f"[LLM] Langfuse generation updated and ended successfully")
                except Exception as e:
                    logger.warning(f"[LLM] Failed to update Langfuse generation: {e}", exc_info=True)
            
            if trace_context_manager:
                try:
                    trace_context_manager.__exit__(None, None, None)
                    logger.info(f"[LLM] Langfuse trace ended successfully")
                except Exception as e:
                    logger.warning(f"[LLM] Failed to end Langfuse trace: {e}", exc_info=True)
            
            # Flush Langfuse to ensure traces are sent
            if self.langfuse:
                try:
                    self.langfuse.flush()
                    logger.debug(f"[LLM] Langfuse flush completed")
                except Exception as e:
                    logger.warning(f"[LLM] Failed to flush Langfuse: {e}")
            
            logger.debug(f"[LLM] Structured completion successful - parsed {response_model.__name__}")
            return result
            
        except Exception as e:
            logger.error(f"[LLM] Structured completion failed: {e}")
            logger.debug(f"[LLM] Error details - trace: {trace_name_final}, model: {model}")
            if 'content' in locals():
                logger.debug(f"[LLM] Raw response (first 500 chars): {content[:500]}")
            if trace_context_manager:
                try:
                    trace_context_manager.__exit__(type(e), e, None)
                except:
                    pass
            if generation:
                try:
                    generation.end()
                except:
                    pass
            if self.langfuse:
                try:
                    self.langfuse.flush()
                except:
                    pass
            raise
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Convenience method for chat completions using configured chat model"""
        return self.completion(
            model=self.config.LITELLM_CHAT_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            trace_name="chat_completion",
            trace_metadata={"session_id": session_id} if session_id else None
        )
    
    def quiz_generation_completion(
        self,
        messages: List[Dict[str, str]],
        response_model: Type[T],
        temperature: float = 0.8,
        max_tokens: Optional[int] = None
    ) -> T:
        """Convenience method for quiz question generation using configured quiz model"""
        return self.structured_completion(
            model=self.config.LITELLM_QUIZ_MODEL,
            messages=messages,
            response_model=response_model,
            temperature=temperature,
            max_tokens=max_tokens,
            trace_name="quiz_generation"
        )

