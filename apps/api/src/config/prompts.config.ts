import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { createRequire } from 'module';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const require = createRequire(import.meta.url);

// Lazy/optional YAML loader (falls back to JSON.parse if js-yaml is unavailable)
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
  model?: string;  // Optional: Override default model for this prompt
  llm_config: PromptLLMConfig;
  description: string;
}

export interface PromptsConfiguration {
  prompts: Record<string, PromptConfig>;
  defaults: {
    default_model: string;  // Default model for all prompts
    fallback_dir: string;
    langfuse_enabled: boolean;
    retry_on_error: boolean;
    max_retries: number;
  };
}

class PromptsConfigLoader {
  private config: PromptsConfiguration | null = null;
  private configPath: string;

  constructor() {
    this.configPath = join(__dirname, '../../config/prompts.yaml');
  }

  /**
   * Load YAML configuration (with hot-reload support)
   * Set forceReload=true to reload from disk
   */
  load(forceReload: boolean = false): PromptsConfiguration {
    if (this.config && !forceReload) {
      return this.config;
    }

    try {
      const fileContents = readFileSync(this.configPath, 'utf8');
      this.config = yamlLoad(fileContents) as PromptsConfiguration;
      
      console.log(`✅ Loaded prompts configuration with ${Object.keys(this.config.prompts).length} prompts`);
      console.log(`📌 Default model: ${this.config.defaults.default_model}`);
      return this.config;
    } catch (error) {
      console.error('Failed to load prompts.yaml:', error);
      throw new Error('Could not load prompts configuration');
    }
  }

  /**
   * Force reload configuration from disk
   */
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

  /**
   * Get the model to use for a specific prompt
   * Returns prompt-specific model if defined, otherwise default model
   */
  getModelForPrompt(promptKey: string): string {
    const promptConfig = this.getPromptConfig(promptKey);
    return promptConfig.model || this.getDefaults().default_model;
  }
}

// Singleton instance
export const promptsConfig = new PromptsConfigLoader();
