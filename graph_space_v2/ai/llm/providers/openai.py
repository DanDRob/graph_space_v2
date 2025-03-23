from typing import Dict, List, Any, Optional, Union
import os
import json
import requests
from openai import OpenAI
import time

from graph_space_v2.ai.llm.llm_service import BaseLLMProvider
from graph_space_v2.utils.errors.exceptions import LLMError


class OpenaiProvider(BaseLLMProvider):
    """OpenAI API provider for LLM service."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gpt-3.5-turbo-0125",
        fallback_model_name: str = "gpt-3.5-turbo",
        use_api: bool = True,
        base_url: Optional[str] = None
    ):
        """
        Initialize the OpenAI provider.

        Args:
            api_key: OpenAI API key
            model_name: Name of the model to use
            fallback_model_name: Name of the model to use as fallback
            use_api: Whether to use the API
            base_url: Optional custom base URL for the API
        """
        self.model_name = model_name
        self.fallback_model_name = fallback_model_name
        self.use_api = use_api

        # Get API key from environment if not provided
        if api_key is None:
            api_key = os.environ.get("OPENAI_API_KEY")

        self.api_key = api_key

        # Initialize client if API key is available
        if self.api_key and self.use_api:
            kwargs = {"api_key": self.api_key}
            if base_url:
                kwargs["base_url"] = base_url
            self.client = OpenAI(**kwargs)
        else:
            self.client = None

    def generate_text(self, prompt: str, max_tokens: int = 500, temperature: float = 0.7) -> str:
        """
        Generate text from a prompt using OpenAI API.

        Args:
            prompt: Text prompt
            max_tokens: Maximum number of tokens to generate
            temperature: Temperature for sampling

        Returns:
            Generated text
        """
        if not self.client:
            raise LLMError("OpenAI client not initialized. API key required.")

        try:
            # Create a chat completion
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature
            )

            # Extract and return the generated text
            generated_text = response.choices[0].message.content
            return generated_text.strip()
        except Exception as e:
            # Try with fallback model
            try:
                response = self.client.chat.completions.create(
                    model=self.fallback_model_name,
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=max_tokens,
                    temperature=temperature
                )

                # Extract and return the generated text
                generated_text = response.choices[0].message.content
                return generated_text.strip()
            except Exception as fallback_e:
                raise LLMError(
                    f"Error generating text: {e}. Fallback error: {fallback_e}")

    def generate_with_context(self, query: str, context: str, max_tokens: int = 500, temperature: float = 0.7) -> str:
        """
        Generate text based on query and context using OpenAI API.

        Args:
            query: The question or query
            context: Context information for the query
            max_tokens: Maximum number of tokens to generate
            temperature: Temperature for sampling

        Returns:
            Generated text
        """
        if not self.client:
            raise LLMError("OpenAI client not initialized. API key required.")

        system_message = """You are a helpful assistant that accurately answers questions 
        based on the provided context information. If the question cannot be answered 
        based on the context, please acknowledge this rather than providing speculative answers.
        """

        try:
            # Create a chat completion with system, context and query
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": f"Context: {context}\n\nQuestion: {query}"}
                ],
                max_tokens=max_tokens,
                temperature=temperature
            )

            # Extract and return the generated text
            generated_text = response.choices[0].message.content
            return generated_text.strip()
        except Exception as e:
            # Try with fallback model
            try:
                response = self.client.chat.completions.create(
                    model=self.fallback_model_name,
                    messages=[
                        {"role": "system", "content": system_message},
                        {"role": "user",
                            "content": f"Context: {context}\n\nQuestion: {query}"}
                    ],
                    max_tokens=max_tokens,
                    temperature=temperature
                )

                # Extract and return the generated text
                generated_text = response.choices[0].message.content
                return generated_text.strip()
            except Exception as fallback_e:
                raise LLMError(
                    f"Error generating text with context: {e}. Fallback error: {fallback_e}")
