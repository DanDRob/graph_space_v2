from typing import Dict, List, Any, Optional, Union
import os
import importlib
import json
import time
from abc import ABC, abstractmethod
import logging # Added

from graph_space_v2.utils.errors.exceptions import LLMError, LLMServiceError


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate_text(self, prompt: str, max_tokens: int = 500, temperature: float = 0.7) -> str:
        """Generate text from a prompt."""
        pass

    @abstractmethod
    def generate_with_context(self, query: str, context: str, max_tokens: int = 500, temperature: float = 0.7) -> str:
        """Generate text based on query and context."""
        pass


class LLMService:
    """Service for interacting with large language models."""

    logger = logging.getLogger(__name__) # Added logger instance

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "deepseek-chat",
        fallback_model_name: str = "meta-llama/Llama-3-8B-Instruct",
        use_api: bool = True,
        provider: str = "deepseek"
    ):
        """
        Initialize the LLM service.

        Args:
            api_key: API key for the LLM provider
            model_name: Name of the model to use
            fallback_model_name: Name of the model to use as fallback
            use_api: Whether to use the API instead of local models
            provider: Provider name (openai, deepseek, local)
        """
        self.api_key = api_key
        self.model_name = model_name
        self.fallback_model_name = fallback_model_name
        self.use_api = use_api
        self.provider_name = provider
        self.enabled = True  # Default to enabled

        # Initialize provider
        self.provider = self._get_provider(provider)

        # Disable service if provider is DummyProvider or if API key is missing when required
        if isinstance(self.provider, DummyProvider):
            self.logger.critical("LLMService is operating with a DummyProvider. Disabling LLMService.")
            self.enabled = False
        elif self.use_api and self.provider_name not in ["local", "dummy"]: # Assuming 'local' and 'dummy' don't need API keys
            if not self.api_key:
                self.logger.warning(
                    f"LLMService disabled: API key not provided for '{self.provider_name}' provider (and use_api is True).")
                self.enabled = False
            else:
                 self.logger.info(f"LLMService initialized with provider '{self.provider_name}' and API key.")
        elif not self.use_api and self.provider_name == "local":
             self.logger.info(f"LLMService initialized with local provider '{self.provider_name}'.")
        else:
            self.logger.info(f"LLMService initialized with provider '{self.provider_name}'. API key check skipped or not applicable.")


        # Store system prompts
        self.system_prompts = {
            "tag_extraction": "Extract relevant tags from the following text. Return only the tags as a comma-separated list without explanations or additional text.",
            "summarization": "Summarize the following text concisely while preserving the key information.",
            "title_generation": "Generate a short, descriptive title for the following content. Return only the title without any explanations or additional text.",
            "answer_generation": "Answer the question based on the provided context. If you cannot answer based on the context, say so clearly."
        }

    def _get_provider(self, provider_name: str) -> BaseLLMProvider:
        """
        Get the LLM provider implementation.

        Args:
            provider_name: Name of the provider to use

        Returns:
            Provider implementation
        """
        try:
            # Try to import the provider module dynamically
            module_path = f"graph_space_v2.ai.llm.providers.{provider_name}"
            provider_module = importlib.import_module(module_path)

            # Get the provider class
            provider_class = getattr(
                provider_module, f"{provider_name.capitalize()}Provider")

            # Initialize the provider
            return provider_class(
                api_key=self.api_key,
                model_name=self.model_name,
                fallback_model_name=self.fallback_model_name,
                use_api=self.use_api
            )
        except (ImportError, AttributeError) as e:
            self.logger.error(f"Error initializing LLM provider '{provider_name}': {e}. Attempting fallback.", exc_info=True)

            # Fall back to local provider if available
            try:
                from graph_space_v2.ai.llm.providers.local_llm import LocalLLMProvider
                self.logger.info(f"Primary provider '{provider_name}' failed. Falling back to LocalLLMProvider with model '{self.fallback_model_name}'.")
                return LocalLLMProvider(
                    model_name=self.fallback_model_name,
                    use_api=False # Local provider implies not using external API in the same way
                )
            except ImportError:
                self.logger.warning("LocalLLMProvider not available as a fallback.")
                # No provider available, use a dummy provider
                self.logger.warning("No functional LLM provider found after primary and fallback attempts. Using DummyProvider.")
                dummy_provider = DummyProvider()
                # isinstance check is redundant as we just created it.
                self.logger.critical("LLMService is operating with a DummyProvider. All LLM-dependent functionality will be severely limited or non-operational.")
                return dummy_provider
        except Exception as e_init: # Catch any other error during provider initialization
            self.logger.critical(f"Critical error during initialization of LLM provider '{provider_name}': {e_init}. Using DummyProvider.", exc_info=True)
            return DummyProvider()


    def generate_text(self, prompt: str, max_tokens: int = 500, temperature: float = 0.7, retry_count: int = 2) -> str:
        """
        Generate text from a prompt.

        Args:
            prompt: Text prompt
            max_tokens: Maximum number of tokens to generate
            temperature: Temperature for sampling
            retry_count: Number of retries on failure

        Returns:
            Generated text
        """
        if not self.enabled:
            self.logger.warning("LLMService is disabled. Skipping generate_text operation. Returning empty string.")
            return ""

        # This check for DummyProvider is now partly handled by self.enabled, but can remain as a safeguard
        # or for more specific behavior if DummyProvider is sometimes used even when enabled=True (e.g. for specific tests)
        if isinstance(self.provider, DummyProvider):
             self.logger.warning("LLMService.generate_text is using DummyProvider. Text generation will be a placeholder.")
             return "Placeholder response from DummyProvider." # More explicit than empty string if Dummy is active
        try:
            return self.provider.generate_text(prompt, max_tokens, temperature)
        except Exception as e:
            self.logger.warning(f"Error generating text (prompt: '{prompt[:50]}...'). Attempting retry {retry_count}/{self.provider.retry_attempts if hasattr(self.provider, 'retry_attempts') else 2}.", exc_info=True)
            if retry_count > 0:
                time.sleep(1)  # Wait before retry
                return self.generate_text(prompt, max_tokens, temperature, retry_count - 1)
            self.logger.error(f"Failed to generate text for prompt '{prompt[:50]}...' after multiple retries: {e}", exc_info=True)
            raise LLMServiceError(f"Failed to generate text after multiple retries: {e}")


    def generate_answer(self, query: str, context: str, max_tokens: int = 500, temperature: float = 0.7) -> str:
        """
        Generate an answer to a question based on provided context.

        Args:
            query: The question to answer
            context: Context information for answering the question
            max_tokens: Maximum number of tokens to generate
            temperature: Temperature for sampling

        Returns:
            Generated answer
        """
        if not self.enabled:
            self.logger.warning("LLMService is disabled. Skipping generate_answer operation. Returning empty string.")
            return ""
        try:
            return self.provider.generate_with_context(query, context, max_tokens, temperature)
        except Exception as e:
            # Fallback to a simpler prompt
            system_prompt = self.system_prompts["answer_generation"]
            prompt = f"{system_prompt}\n\nContext: {context}\n\nQuestion: {query}\n\nAnswer:"
            # This call to generate_text will use its own retry logic and raise LLMServiceError if it fails.
            return self.generate_text(prompt, max_tokens, temperature)
        except LLMServiceError as e_service:
            self.logger.error(f"Failed to generate answer due to underlying text generation error: {e_service}", exc_info=True)
            raise LLMServiceError(f"Failed to generate answer due to text generation error: {e_service}")
        except Exception as e:
            self.logger.error(f"An unexpected error occurred while generating answer for query '{query[:50]}...': {e}", exc_info=True)
            raise LLMServiceError(f"An unexpected error occurred while generating answer: {e}")

    def extract_tags(self, text: str, max_tags: int = 5) -> List[str]:
        """
        Extract tags from a text.

        Args:
            text: Text to extract tags from
            max_tags: Maximum number of tags to extract

        Returns:
            List of extracted tags
        """
        if not self.enabled:
            self.logger.warning("LLMService is disabled. Skipping extract_tags operation. Returning empty list.")
            return []
        try:
            # Prepare prompt for tag extraction
            system_prompt = self.system_prompts["tag_extraction"]
            # Truncate text if it's too long
            if len(text) > 4000:
                text = text[:4000] + "..."

            prompt = f"{system_prompt}\n\nText: {text}\n\nTags:"

            # Generate tags
            response = self.generate_text(
                prompt, max_tokens=100, temperature=0.3)

            # Parse tags
            tags = []
            if response:
                # Clean up response (remove quotes, brackets, etc.)
                clean_response = response.replace('[', '').replace(
                    ']', '').replace('"', '').replace("'", "")

                # Split by comma or newline
                for tag in clean_response.split(','):
                    tag = tag.strip()
                    if tag and tag.lower() not in [t.lower() for t in tags]:
                        tags.append(tag)
                        if len(tags) >= max_tags:
                            break
            return tags
        except LLMServiceError as e_service:
            self.logger.error(f"Failed to extract tags due to underlying text generation error: {e_service}", exc_info=True)
            raise LLMServiceError(f"Failed to extract tags due to text generation error: {e_service}")
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during tag extraction for text '{text[:50]}...': {e}", exc_info=True)
            raise LLMServiceError(f"An unexpected error occurred during tag extraction: {e}")


    def generate_title(self, text: str, max_length: int = 50) -> str:
        """
        Generate a title for a text.

        Args:
            text: Text to generate title for
            max_length: Maximum length of the title

        Returns:
            Generated title
        """
        if not self.enabled:
            self.logger.warning("LLMService is disabled. Skipping generate_title operation. Returning 'Untitled'.")
            return "Untitled"
        try:
            # Prepare prompt for title generation
            system_prompt = self.system_prompts["title_generation"]
            # Truncate text if it's too long
            if len(text) > 4000:
                text = text[:4000] + "..."

            prompt = f"{system_prompt}\n\nContent: {text}\n\nTitle:"

            # Generate title
            title = self.generate_text(prompt, max_tokens=50, temperature=0.5)

            # Clean up title (remove quotes, etc.)
            title = title.strip().strip('"').strip()

            # Truncate if needed
            if len(title) > max_length:
                title = title[:max_length - 3] + "..."
            return title
        except LLMServiceError as e_service:
            self.logger.error(f"Failed to generate title due to underlying text generation error: {e_service}", exc_info=True)
            raise LLMServiceError(f"Failed to generate title due to text generation error: {e_service}")
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during title generation for text '{text[:50]}...': {e}", exc_info=True)
            raise LLMServiceError(f"An unexpected error occurred during title generation: {e}")


    def summarize_text(self, text: str, max_length: int = 200) -> str:
        """
        Summarize a text.

        Args:
            text: Text to summarize
            max_length: Maximum length of the summary

        Returns:
            Generated summary
        """
        if not self.enabled:
            self.logger.warning("LLMService is disabled. Skipping summarize_text operation. Returning 'Summary not available.'.")
            return "Summary not available."
        try:
            # Prepare prompt for summarization
            system_prompt = self.system_prompts["summarization"]
            # Truncate text if it's too long
            if len(text) > 6000:
                text = text[:6000] + "..."

            prompt = f"{system_prompt}\n\nText: {text}\n\nSummary:"

            # Generate summary
            summary = self.generate_text(
                prompt, max_tokens=200, temperature=0.5)

            # Clean up summary
            summary = summary.strip()

            # Truncate if needed
            if len(summary) > max_length:
                # Try to truncate at a sentence boundary
                truncated = summary[:max_length]
                last_period = truncated.rfind('.')
                if last_period > max_length * 0.7:  # Only truncate at sentence if we don't lose too much
                    return truncated[:last_period + 1]
                return truncated + "..."
            return summary
        except LLMServiceError as e_service:
            self.logger.error(f"Failed to summarize text due to underlying text generation error: {e_service}", exc_info=True)
            raise LLMServiceError(f"Failed to summarize text due to text generation error: {e_service}")
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during text summarization for text '{text[:50]}...': {e}", exc_info=True)
            raise LLMServiceError(f"An unexpected error occurred during text summarization: {e}")


    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """
        Extract named entities from a text.

        Args:
            text: Text to extract entities from

        Returns:
            Dictionary of entity types to lists of entities
        """
        if not self.enabled:
            self.logger.warning("LLMService is disabled. Skipping extract_entities operation. Returning empty dict.")
            return {}
        try:
            # Prepare prompt for entity extraction
            prompt = """Extract named entities from the following text. 
            Return them as a JSON object with keys for different entity types 
            (person, organization, location, date, etc.) and values as lists of entities.
            
            Text: {text}
            
            Entities (JSON format):"""

            # Truncate text if it's too long
            if len(text) > 4000:
                text = text[:4000] + "..."

            formatted_prompt = prompt.format(text=text)

            # Generate entities
            response = self.generate_text(
                formatted_prompt, max_tokens=200, temperature=0.3)

            # Parse JSON response
            try:
                # First try to find JSON block in response
                json_start = response.find('{')
                json_end = response.rfind('}')

                if json_start >= 0 and json_end > json_start:
                    json_str = response[json_start:json_end + 1]
                    entities = json.loads(json_str)
                    return entities
                else:
                    # Consider raising error if JSON structure is not found or is invalid
                    self.logger.error(f"Failed to parse JSON from LLM response for entity extraction. Response: {response[:100]}...")
                    raise LLMServiceError(f"Failed to parse JSON from LLM response for entity extraction. Response: {response[:100]}...")
            except json.JSONDecodeError as je:
                self.logger.error(f"Invalid JSON in LLM response for entity extraction: {je}. Response: {response[:100]}...", exc_info=True)
                raise LLMServiceError(f"Invalid JSON in LLM response for entity extraction: {je}. Response: {response[:100]}...")
        except LLMServiceError as e_service:
            self.logger.error(f"Failed to extract entities due to underlying text generation error: {e_service}", exc_info=True)
            raise LLMServiceError(f"Failed to extract entities due to text generation error: {e_service}")
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during entity extraction for text '{text[:50]}...': {e}", exc_info=True)
            raise LLMServiceError(f"An unexpected error occurred during entity extraction: {e}")


    def generate_summary(self, text: str, max_length: int = 200) -> str:
        """
        Generate a summary for a document. Alias to summarize_text method
        for DocumentProcessor compatibility.

        Args:
            text: Text to summarize
            max_length: Maximum length of the summary

        Returns:
            Generated summary
        """
        return self.summarize_text(text, max_length)


class DummyProvider(BaseLLMProvider):
    """Dummy provider for testing or when no LLM is available."""

    def generate_text(self, prompt: str, max_tokens: int = 500, temperature: float = 0.7) -> str:
        """Generate text from a prompt."""
        return "This is a placeholder response generated by the dummy provider."

    def generate_with_context(self, query: str, context: str, max_tokens: int = 500, temperature: float = 0.7) -> str:
        """Generate text based on query and context."""
        return f"Query: {query}\nThis is a placeholder response generated by the dummy provider."
