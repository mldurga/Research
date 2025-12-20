"""
Ollama Client Module
Interfaces with Ollama service for text processing and data extraction.
Designed for secure ADNOC environment.
"""

import json
import logging
from typing import Dict, Any, List, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class OllamaClient:
    """Client for interacting with Ollama service."""

    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        """
        Initialize the Ollama client.

        Args:
            config: Configuration dictionary
            logger: Logger instance
        """
        self.config = config
        self.logger = logger

        # Ollama configuration
        self.base_url = config['ollama']['base_url'].rstrip('/')
        self.model = config['ollama']['model']
        self.timeout = config['ollama']['timeout']
        self.temperature = config['ollama'].get('temperature', 0.1)
        self.system_prompt = config['ollama']['system_prompt']

        # Setup session with retries
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """
        Create requests session with retry logic.

        Returns:
            Configured requests session
        """
        session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def check_connection(self) -> bool:
        """
        Check if Ollama service is reachable.

        Returns:
            True if service is reachable, False otherwise
        """
        try:
            response = self.session.get(
                f"{self.base_url}/api/tags",
                timeout=10
            )
            response.raise_for_status()

            self.logger.info("Successfully connected to Ollama service")
            return True

        except requests.exceptions.ConnectionError:
            self.logger.error(f"Cannot connect to Ollama at {self.base_url}")
            return False
        except Exception as e:
            self.logger.error(f"Error checking Ollama connection: {e}")
            return False

    def list_models(self) -> List[str]:
        """
        List available models in Ollama.

        Returns:
            List of model names
        """
        try:
            response = self.session.get(
                f"{self.base_url}/api/tags",
                timeout=10
            )
            response.raise_for_status()

            data = response.json()
            models = [model['name'] for model in data.get('models', [])]

            self.logger.info(f"Available models: {models}")
            return models

        except Exception as e:
            self.logger.error(f"Error listing models: {e}")
            return []

    def extract_data_from_text(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Use Ollama to extract structured data from text.

        Args:
            text: Input text to process

        Returns:
            Extracted data as dictionary or None if failed
        """
        try:
            self.logger.info("Sending text to Ollama for data extraction")

            # Prepare the prompt
            prompt = f"""
Based on the following text, extract all relevant data points for the PI System.

Text:
{text}

Instructions:
- Extract tag names, values, timestamps, and units
- Return data as a JSON array of objects
- Each object should have: tag_name, value, timestamp (if available), unit (if available)
- If no data found, return an empty array

Return only valid JSON, no additional text.
"""

            # Call Ollama API
            response = self.session.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "system": self.system_prompt,
                    "stream": False,
                    "options": {
                        "temperature": self.temperature
                    }
                },
                timeout=self.timeout
            )

            response.raise_for_status()
            result = response.json()

            # Extract the response
            generated_text = result.get('response', '')

            if not generated_text:
                self.logger.warning("Ollama returned empty response")
                return None

            # Try to parse JSON from response
            extracted_data = self._parse_json_response(generated_text)

            if extracted_data:
                self.logger.info(f"Successfully extracted {len(extracted_data)} data points")
                return extracted_data
            else:
                self.logger.warning("Could not parse JSON from Ollama response")
                return None

        except requests.exceptions.Timeout:
            self.logger.error("Ollama request timed out")
            return None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Ollama request failed: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error extracting data from text: {e}")
            return None

    def _parse_json_response(self, text: str) -> Optional[List[Dict[str, Any]]]:
        """
        Parse JSON from Ollama response text.

        Args:
            text: Response text from Ollama

        Returns:
            Parsed JSON data or None
        """
        try:
            # Try direct JSON parsing
            data = json.loads(text)

            # Ensure it's a list
            if isinstance(data, dict):
                data = [data]
            elif not isinstance(data, list):
                return None

            return data

        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            try:
                # Look for JSON in code blocks
                if '```json' in text:
                    start = text.find('```json') + 7
                    end = text.find('```', start)
                    json_text = text[start:end].strip()
                elif '```' in text:
                    start = text.find('```') + 3
                    end = text.find('```', start)
                    json_text = text[start:end].strip()
                else:
                    # Try to find JSON array or object
                    json_text = text.strip()

                data = json.loads(json_text)

                if isinstance(data, dict):
                    data = [data]
                elif not isinstance(data, list):
                    return None

                return data

            except Exception as e:
                self.logger.error(f"Could not parse JSON from response: {e}")
                self.logger.debug(f"Response text: {text[:500]}")
                return None

    def generate_completion(self, prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
        """
        Generate a completion using Ollama.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt (defaults to configured system prompt)

        Returns:
            Generated text or None if failed
        """
        try:
            response = self.session.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "system": system_prompt or self.system_prompt,
                    "stream": False,
                    "options": {
                        "temperature": self.temperature
                    }
                },
                timeout=self.timeout
            )

            response.raise_for_status()
            result = response.json()

            generated_text = result.get('response', '')
            return generated_text if generated_text else None

        except Exception as e:
            self.logger.error(f"Error generating completion: {e}")
            return None

    def extract_with_custom_prompt(self, text: str, custom_prompt: str) -> Optional[str]:
        """
        Extract data using a custom prompt.

        Args:
            text: Input text
            custom_prompt: Custom extraction prompt

        Returns:
            Generated response or None
        """
        try:
            full_prompt = f"{custom_prompt}\n\nText:\n{text}"
            return self.generate_completion(full_prompt)

        except Exception as e:
            self.logger.error(f"Error with custom extraction: {e}")
            return None

    def validate_model_available(self) -> bool:
        """
        Check if the configured model is available.

        Returns:
            True if model is available, False otherwise
        """
        try:
            models = self.list_models()
            available = self.model in models

            if not available:
                self.logger.warning(f"Model '{self.model}' not found. Available models: {models}")

            return available

        except Exception as e:
            self.logger.error(f"Error validating model: {e}")
            return False
