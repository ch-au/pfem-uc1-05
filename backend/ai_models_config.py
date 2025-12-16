"""
Zentrale AI-Modell-Konfiguration pro Prompt-Schritt
Liest die config/ai-models.config.json und stellt Modell-Zuweisungen bereit
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger("ai_models_config")

DEFAULT_OPENROUTER_MODEL = "google/gemini-2.5-flash-preview-09-2025"
DEFAULT_LITELLM_MODEL = "gemini/gemini-flash-latest"
DEFAULT_TIMEOUT_MS = 60000

@dataclass
class ModelConfig:
    """Konfiguration für einen einzelnen AI-Schritt"""
    description: str
    model: str
    provider: str
    temperature: float = 0.7
    max_tokens: int = 2000
    dimensions: Optional[int] = None

@dataclass 
class AIModelsConfig:
    """Gesamte AI-Modell-Konfiguration"""
    models: Dict[str, ModelConfig]
    defaults: Dict[str, Dict[str, Any]]
    available_models: Dict[str, list]

_cached_config: Optional[AIModelsConfig] = None
_config_loaded_from_file: bool = False

def _find_config_path() -> Path:
    """Findet den Pfad zur Config-Datei"""
    current = Path(__file__).parent
    
    possible_paths = [
        current.parent / "config" / "ai-models.config.json",
        current / "config" / "ai-models.config.json",
        Path("config") / "ai-models.config.json",
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    raise FileNotFoundError(
        f"ai-models.config.json nicht gefunden. Geprüfte Pfade: {possible_paths}"
    )

def _merge_with_defaults(raw_config: Dict[str, Any]) -> AIModelsConfig:
    """Merged geladene Config mit Defaults für fehlende Werte"""
    defaults = _get_default_config_internal()
    
    models = dict(defaults.models)
    for step_name, step_config in raw_config.get("models", {}).items():
        models[step_name] = ModelConfig(
            description=step_config.get("description", ""),
            model=step_config.get("model", DEFAULT_LITELLM_MODEL),
            provider=step_config.get("provider", "litellm"),
            temperature=step_config.get("temperature", 0.7),
            max_tokens=step_config.get("max_tokens", 2000),
            dimensions=step_config.get("dimensions")
        )
    
    raw_defaults = raw_config.get("defaults", {})
    merged_defaults = {
        "openrouter": {
            "fallback_model": raw_defaults.get("openrouter", {}).get("fallback_model", DEFAULT_OPENROUTER_MODEL),
            "timeout_ms": raw_defaults.get("openrouter", {}).get("timeout_ms", DEFAULT_TIMEOUT_MS)
        },
        "litellm": {
            "fallback_model": raw_defaults.get("litellm", {}).get("fallback_model", DEFAULT_LITELLM_MODEL),
            "timeout_ms": raw_defaults.get("litellm", {}).get("timeout_ms", DEFAULT_TIMEOUT_MS)
        }
    }
    
    return AIModelsConfig(
        models=models,
        defaults=merged_defaults,
        available_models=raw_config.get("available_models", {"openrouter": [], "litellm": []})
    )

def load_ai_models_config() -> AIModelsConfig:
    """Lädt die AI-Modell-Konfiguration aus der JSON-Datei"""
    global _cached_config, _config_loaded_from_file
    
    if _cached_config is not None and _config_loaded_from_file:
        return _cached_config
    
    try:
        config_path = _find_config_path()
        with open(config_path, 'r', encoding='utf-8') as f:
            raw_config = json.load(f)
        
        _cached_config = _merge_with_defaults(raw_config)
        _config_loaded_from_file = True
        
        logger.info(f"[AI Config] Konfiguration geladen von {config_path}")
        logger.info(f"[AI Config] Verfügbare Schritte: {list(_cached_config.models.keys())}")
        
        return _cached_config
        
    except FileNotFoundError as e:
        logger.warning(f"[AI Config] Config-Datei nicht gefunden: {e}. Verwende Defaults.")
        return _get_default_config_internal()
    except json.JSONDecodeError as e:
        logger.error(f"[AI Config] Fehler beim Parsen der Config: {e}. Verwende Defaults.")
        return _get_default_config_internal()

def get_model_for_step(step: str) -> ModelConfig:
    """Gibt die Modell-Konfiguration für einen bestimmten AI-Schritt zurück"""
    config = load_ai_models_config()
    
    if step in config.models:
        return config.models[step]
    
    logger.warning(f"[AI Config] Unbekannter Schritt '{step}', verwende Default-Modell")
    return ModelConfig(
        description="Default model",
        model=DEFAULT_LITELLM_MODEL,
        provider="litellm",
        temperature=0.7,
        max_tokens=2000
    )

def reload_config() -> None:
    """Cache leeren und Konfiguration neu laden"""
    global _cached_config, _config_loaded_from_file
    _cached_config = None
    _config_loaded_from_file = False
    load_ai_models_config()

def _get_default_config_internal() -> AIModelsConfig:
    """Gibt Default-Konfiguration zurück (ohne Cache zu setzen)"""
    return AIModelsConfig(
        models={
            "sql_generation": ModelConfig(
                description="SQL generation",
                model=DEFAULT_LITELLM_MODEL,
                provider="litellm",
                temperature=0.3,
                max_tokens=2000
            ),
            "quiz_generation": ModelConfig(
                description="Quiz generation", 
                model=DEFAULT_LITELLM_MODEL,
                provider="litellm",
                temperature=0.8,
                max_tokens=2000
            ),
            "chat": ModelConfig(
                description="Chat responses",
                model=DEFAULT_LITELLM_MODEL,
                provider="litellm",
                temperature=0.7,
                max_tokens=1500
            ),
            "explanation": ModelConfig(
                description="Explanations",
                model=DEFAULT_LITELLM_MODEL,
                provider="litellm",
                temperature=0.5,
                max_tokens=1000
            ),
            "embeddings": ModelConfig(
                description="Text embeddings",
                model="text-embedding-3-large",
                provider="openai",
                dimensions=3072
            )
        },
        defaults={
            "openrouter": {"fallback_model": DEFAULT_OPENROUTER_MODEL, "timeout_ms": DEFAULT_TIMEOUT_MS},
            "litellm": {"fallback_model": DEFAULT_LITELLM_MODEL, "timeout_ms": DEFAULT_TIMEOUT_MS}
        },
        available_models={"openrouter": [], "litellm": []}
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("Testing AI Models Config...")
    config = load_ai_models_config()
    
    print(f"\nVerfügbare Schritte:")
    for step_name, step_config in config.models.items():
        print(f"  - {step_name}: {step_config.model} (temp={step_config.temperature})")
    
    print(f"\nTest get_model_for_step('quiz_generation'):")
    quiz_model = get_model_for_step("quiz_generation")
    print(f"  Model: {quiz_model.model}")
    print(f"  Temperature: {quiz_model.temperature}")
    
    print(f"\nTest get_model_for_step('unknown_step'):")
    unknown_model = get_model_for_step("unknown_step")
    print(f"  Model: {unknown_model.model}")
