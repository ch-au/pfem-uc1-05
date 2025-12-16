import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

const DEFAULT_OPENROUTER_MODEL = 'google/gemini-2.5-flash-preview-09-2025';
const DEFAULT_LITELLM_MODEL = 'gemini/gemini-flash-latest';
const DEFAULT_TIMEOUT_MS = 60000;

export interface ModelConfig {
  description: string;
  model: string;
  provider: 'openrouter' | 'litellm' | 'openai';
  temperature?: number;
  max_tokens?: number;
  dimensions?: number;
}

export interface AIModelsConfig {
  models: {
    sql_generation: ModelConfig;
    quiz_generation: ModelConfig;
    chat: ModelConfig;
    explanation: ModelConfig;
    embeddings: ModelConfig;
    [key: string]: ModelConfig;
  };
  defaults: {
    openrouter: {
      fallback_model: string;
      timeout_ms: number;
    };
    litellm: {
      fallback_model: string;
      timeout_ms: number;
    };
  };
  available_models: {
    openrouter: string[];
    litellm: string[];
  };
}

let cachedConfig: AIModelsConfig | null = null;
let configLoadedFromFile = false;

export function loadAIModelsConfig(): AIModelsConfig {
  if (cachedConfig && configLoadedFromFile) {
    return cachedConfig;
  }

  const configPath = join(__dirname, '../../../../config/ai-models.config.json');
  
  try {
    const configContent = readFileSync(configPath, 'utf-8');
    const rawConfig = JSON.parse(configContent);
    
    cachedConfig = mergeWithDefaults(rawConfig);
    configLoadedFromFile = true;
    console.log('[AI Config] Loaded AI models configuration from', configPath);
    return cachedConfig;
  } catch (error) {
    console.warn('[AI Config] Could not load ai-models.config.json, using defaults:', error);
    return getDefaultConfig();
  }
}

function mergeWithDefaults(rawConfig: Partial<AIModelsConfig>): AIModelsConfig {
  const defaults = getDefaultConfig();
  
  return {
    models: {
      ...defaults.models,
      ...(rawConfig.models || {})
    },
    defaults: {
      openrouter: {
        fallback_model: rawConfig.defaults?.openrouter?.fallback_model || DEFAULT_OPENROUTER_MODEL,
        timeout_ms: rawConfig.defaults?.openrouter?.timeout_ms || DEFAULT_TIMEOUT_MS
      },
      litellm: {
        fallback_model: rawConfig.defaults?.litellm?.fallback_model || DEFAULT_LITELLM_MODEL,
        timeout_ms: rawConfig.defaults?.litellm?.timeout_ms || DEFAULT_TIMEOUT_MS
      }
    },
    available_models: {
      openrouter: rawConfig.available_models?.openrouter || [],
      litellm: rawConfig.available_models?.litellm || []
    }
  };
}

export function getModelForStep(step: keyof AIModelsConfig['models']): ModelConfig {
  const config = loadAIModelsConfig();
  
  if (config.models[step]) {
    return config.models[step];
  }
  
  return {
    description: 'Default model',
    model: DEFAULT_OPENROUTER_MODEL,
    provider: 'openrouter',
    temperature: 0.7,
    max_tokens: 2000
  };
}

export function reloadConfig(): void {
  cachedConfig = null;
  configLoadedFromFile = false;
  loadAIModelsConfig();
}

function getDefaultConfig(): AIModelsConfig {
  return {
    models: {
      sql_generation: {
        description: 'SQL generation',
        model: DEFAULT_OPENROUTER_MODEL,
        provider: 'openrouter',
        temperature: 0.3,
        max_tokens: 2000
      },
      quiz_generation: {
        description: 'Quiz generation',
        model: DEFAULT_OPENROUTER_MODEL,
        provider: 'openrouter',
        temperature: 0.8,
        max_tokens: 2000
      },
      chat: {
        description: 'Chat responses',
        model: DEFAULT_OPENROUTER_MODEL,
        provider: 'openrouter',
        temperature: 0.7,
        max_tokens: 1500
      },
      explanation: {
        description: 'Explanations',
        model: DEFAULT_OPENROUTER_MODEL,
        provider: 'openrouter',
        temperature: 0.5,
        max_tokens: 1000
      },
      embeddings: {
        description: 'Text embeddings',
        model: 'text-embedding-3-large',
        provider: 'openai',
        dimensions: 3072
      }
    },
    defaults: {
      openrouter: {
        fallback_model: DEFAULT_OPENROUTER_MODEL,
        timeout_ms: DEFAULT_TIMEOUT_MS
      },
      litellm: {
        fallback_model: DEFAULT_LITELLM_MODEL,
        timeout_ms: DEFAULT_TIMEOUT_MS
      }
    },
    available_models: {
      openrouter: [],
      litellm: []
    }
  };
}
