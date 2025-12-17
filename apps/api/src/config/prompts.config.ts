import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { createRequire } from 'module';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const require = createRequire(import.meta.url);

let yamlLoad: (content: string) => any;
try {
  const jsYaml = require('js-yaml');
  yamlLoad = jsYaml.load.bind(jsYaml);
} catch {
  yamlLoad = (content: string) => {
    try {
      return JSON.parse(content);
    } catch {
      throw new Error('Failed to parse prompts configuration (js-yaml not installed)');
    }
  };
}

export interface PromptLLMConfig {
  temperature: number;
  max_tokens: number;
  response_format: 'json' | 'text';
}

export interface PromptConfig {
  langfuse_name: string;
  langfuse_label?: string;
  fallback_file: string;
  model?: string;
  llm_config: PromptLLMConfig;
  description: string;
}

export interface EmbeddingsConfig {
  model: string;
  provider: 'openai' | 'cohere';
  dimensions: number;
  description: string;
}

export interface PromptsConfiguration {
  prompts: Record<string, PromptConfig>;
  embeddings?: EmbeddingsConfig;
  defaults: {
    default_model: string;
    fallback_dir: string;
    langfuse_enabled: boolean;
    retry_on_error: boolean;
    max_retries: number;
  };
  available_models?: {
    openrouter?: string[];
  };
}

const DEFAULT_EMBEDDINGS: EmbeddingsConfig = {
  model: 'text-embedding-3-large',
  provider: 'openai',
  dimensions: 3072,
  description: 'Default embeddings configuration'
};

class PromptsConfigLoader {
  private config: PromptsConfiguration | null = null;
  private configPath: string;

  constructor() {
    this.configPath = join(__dirname, '../../config/prompts.yaml');
  }

  load(forceReload: boolean = false): PromptsConfiguration {
    if (this.config && !forceReload) {
      return this.config;
    }

    try {
      const fileContents = readFileSync(this.configPath, 'utf8');
      this.config = yamlLoad(fileContents) as PromptsConfiguration;
      
      console.log(`✅ Loaded prompts configuration with ${Object.keys(this.config.prompts).length} prompts`);
      console.log(`📌 Default model: ${this.config.defaults.default_model}`);
      
      if (this.config.embeddings) {
        console.log(`🔢 Embeddings: ${this.config.embeddings.model} (${this.config.embeddings.dimensions}d)`);
      }
      
      return this.config;
    } catch (error) {
      console.error('Failed to load prompts.yaml:', error);
      throw new Error('Could not load prompts configuration');
    }
  }

  reload(): void {
    this.config = null;
    this.load(true);
    console.log('🔄 Prompts configuration reloaded from YAML');
  }

  getPromptConfig(promptKey: string): PromptConfig {
    const config = this.load();
    const promptConfig = config.prompts[promptKey];
    
    if (!promptConfig) {
      throw new Error(`Prompt configuration not found for key: ${promptKey}`);
    }
    
    return promptConfig;
  }

  getDefaults() {
    return this.load().defaults;
  }

  getAllPromptKeys(): string[] {
    return Object.keys(this.load().prompts);
  }

  getModelForPrompt(promptKey: string): string {
    const promptConfig = this.getPromptConfig(promptKey);
    return promptConfig.model || this.getDefaults().default_model;
  }

  getEmbeddingsConfig(): EmbeddingsConfig {
    const config = this.load();
    return config.embeddings || DEFAULT_EMBEDDINGS;
  }

  getAvailableModels(): string[] {
    const config = this.load();
    if (!config.available_models?.openrouter) {
      console.warn('⚠️ available_models.openrouter not defined in prompts.yaml');
    }
    return config.available_models?.openrouter || [];
  }
}

export const promptsConfig = new PromptsConfigLoader();
