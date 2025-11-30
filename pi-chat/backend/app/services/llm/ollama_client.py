"""
Ollama Client - Integration with Ollama for local and frontier LLM models
"""

from typing import List, Dict, Any, Optional, AsyncIterator
import httpx
from loguru import logger

from app.core.config import settings


class OllamaClient:
    """Client for interacting with Ollama LLM server"""

    def __init__(self):
        """Initialize Ollama client"""
        self.base_url = settings.ollama.base_url.rstrip("/")
        self.default_model = settings.ollama.default_model
        self.temperature = settings.ollama.temperature_default
        self.max_tokens = settings.ollama.max_tokens

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=120.0,
        )

        logger.info(f"Ollama client initialized: {self.base_url}")

    async def list_models(self) -> List[Dict[str, Any]]:
        """
        List available models in Ollama

        Returns:
            List of model dictionaries
        """
        try:
            response = await self.client.get("/api/tags")
            response.raise_for_status()
            data = response.json()
            return data.get("models", [])

        except Exception as e:
            logger.error(f"Error listing models: {e}")
            return []

    async def generate(
        self,
        prompt: str,
        model: str = None,
        system: str = None,
        temperature: float = None,
        max_tokens: int = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate completion from Ollama

        Args:
            prompt: Input prompt
            model: Model name (defaults to configured model)
            system: System message
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stream: Enable streaming

        Returns:
            Response dictionary
        """
        try:
            model = model or self.default_model
            temperature = temperature or self.temperature
            max_tokens = max_tokens or self.max_tokens

            payload = {
                "model": model,
                "prompt": prompt,
                "stream": stream,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                }
            }

            if system:
                payload["system"] = system

            response = await self.client.post("/api/generate", json=payload)
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Error generating completion: {e}")
            raise

    async def generate_stream(
        self,
        prompt: str,
        model: str = None,
        system: str = None,
        temperature: float = None,
        max_tokens: int = None,
    ) -> AsyncIterator[str]:
        """
        Generate streaming completion from Ollama

        Args:
            prompt: Input prompt
            model: Model name
            system: System message
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Yields:
            Generated text chunks
        """
        try:
            model = model or self.default_model
            temperature = temperature or self.temperature
            max_tokens = max_tokens or self.max_tokens

            payload = {
                "model": model,
                "prompt": prompt,
                "stream": True,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                }
            }

            if system:
                payload["system"] = system

            async with self.client.stream("POST", "/api/generate", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        import json
                        data = json.loads(line)
                        if "response" in data:
                            yield data["response"]

        except Exception as e:
            logger.error(f"Error in streaming generation: {e}")
            raise

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        temperature: float = None,
        max_tokens: int = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        Chat completion using Ollama

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            model: Model name
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stream: Enable streaming

        Returns:
            Response dictionary
        """
        try:
            model = model or self.default_model
            temperature = temperature or self.temperature
            max_tokens = max_tokens or self.max_tokens

            payload = {
                "model": model,
                "messages": messages,
                "stream": stream,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                }
            }

            response = await self.client.post("/api/chat", json=payload)
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Error in chat completion: {e}")
            raise

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        temperature: float = None,
        max_tokens: int = None,
    ) -> AsyncIterator[str]:
        """
        Streaming chat completion

        Args:
            messages: List of message dictionaries
            model: Model name
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Yields:
            Generated text chunks
        """
        try:
            model = model or self.default_model
            temperature = temperature or self.temperature
            max_tokens = max_tokens or self.max_tokens

            payload = {
                "model": model,
                "messages": messages,
                "stream": True,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                }
            }

            async with self.client.stream("POST", "/api/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        import json
                        data = json.loads(line)
                        if "message" in data and "content" in data["message"]:
                            yield data["message"]["content"]

        except Exception as e:
            logger.error(f"Error in streaming chat: {e}")
            raise

    async def embed(
        self,
        text: str,
        model: str = "nomic-embed-text"
    ) -> List[float]:
        """
        Generate embeddings for text

        Args:
            text: Input text
            model: Embedding model name

        Returns:
            Embedding vector
        """
        try:
            payload = {
                "model": model,
                "prompt": text,
            }

            response = await self.client.post("/api/embeddings", json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("embedding", [])

        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise

    async def pull_model(self, model: str) -> bool:
        """
        Pull a model from Ollama library

        Args:
            model: Model name to pull

        Returns:
            True if successful
        """
        try:
            payload = {"name": model}
            response = await self.client.post("/api/pull", json=payload)
            response.raise_for_status()
            logger.success(f"Model {model} pulled successfully")
            return True

        except Exception as e:
            logger.error(f"Error pulling model {model}: {e}")
            return False

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
        logger.info("Ollama client closed")
