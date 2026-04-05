import requests
import json  # Import the json library
from .base import LLMProviderBase, register_provider


@register_provider('ollama')
class OllamaProvider(LLMProviderBase):

    def __init__(self, provider_config):
        super().__init__(provider_config)

        self.base_url = provider_config.base_url or "http://localhost:11434"
        self.model = provider_config.model_name

    def stream(self, prompt):
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": True
                },
                stream=True
            )
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    try:
                        decoded_line = line.decode('utf-8')
                        data = json.loads(decoded_line)

                        if 'response' in data and data['response']:
                            yield data['response']

                        if data.get('done', False):
                            break

                    except json.JSONDecodeError:
                        print(f"Warning: Could not decode JSON from line: {line.decode('utf-8')}")
                    except Exception as e:
                        print(f"An unexpected error occurred processing a line: {e}")

        except requests.exceptions.RequestException as e:
            yield f"Error: Could not connect to Ollama at {self.base_url}. Please ensure Ollama is running."
        except Exception as e:
            yield f"An unexpected error occurred: {e}"
