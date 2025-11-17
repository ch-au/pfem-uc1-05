import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import yaml from 'js-yaml';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

export interface PromptLLMConfig {
  temperature: number;
  max_tokens: number;
  response_format: 'json' | 'text';
}

export interface PromptConfig {
  langfuse_name: string;
  langfuse_label?: string;
  fallback_file: string;
  llm_config: PromptLLMConfig;
  description: string;
}

export interface PromptsConfiguration {
  prompts: Record<string, PromptConfig>;
  defaults: {
    fallback_dir: string;
    langfuse_enabled: boolean;
    retry_on_error: boolean;
    max_retries: number;
  };
}

class PromptsConfigLoader {
  private config: PromptsConfiguration | null = null;

  load(): PromptsConfiguration {
    if (this.config) {
      return this.config;
    }

    try {
      const configPath = join(__dirname, '../../config/prompts.yaml');
      const fileContents = readFileSync(configPath, 'utf8');
      this.config = yaml.load(fileContents) as PromptsConfiguration;
      
      console.log(`✅ Loaded prompts configuration with ${Object.keys(this.config.prompts).length} prompts`);
      return this.config;
    } catch (error) {
      console.error('Failed to load prompts.yaml:', error);
      throw new Error('Could not load prompts configuration');
    }
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
}

// Singleton instance
export const promptsConfig = new PromptsConfigLoader();
