from typing import Dict, List, Any, Optional, Union
import os
import json
import time
import traceback

from graph_space_v2.ai.llm.llm_service import BaseLLMProvider
from graph_space_v2.utils.errors.exceptions import LLMError


class LocalLLMProvider(BaseLLMProvider):
    """Local LLM provider using HuggingFace Transformers."""

    def __init__(
        self,
        model_name: str = "meta-llama/Llama-3-8B-Instruct",
        fallback_model_name: str = None,
        use_api: bool = False,
        cache_dir: Optional[str] = None,
        device: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize the local LLM provider.

        Args:
            model_name: Name of the model to use
            fallback_model_name: Name of the model to use as fallback (unused for local)
            use_api: Whether to use API (if False, use local models)
            cache_dir: Directory for caching models
            device: Device to use (cpu, cuda, mps)
            **kwargs: Additional arguments
        """
        self.model_name = model_name
        self.fallback_model_name = fallback_model_name
        self.cache_dir = cache_dir
        self.device = device
        self.api_key = None  # Not needed for local models

        # Initialize model and tokenizer
        self.model = None
        self.tokenizer = None
        self.pipeline = None

        # Try to load the model if not using API
        if not use_api:
            self._load_model()

    def _load_model(self):
        """Load the model and tokenizer using transformers."""
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline, TextIteratorStreamer
            import torch

            # Determine device
            if self.device is None:
                self.device = "cuda" if torch.cuda.is_available() else "cpu"

            print(f"Loading model {self.model_name} on {self.device}...")

            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                cache_dir=self.cache_dir,
                padding_side="left"
            )

            # Load model with optimizations
            model_kwargs = {
                "torch_dtype": torch.float16 if self.device != "cpu" else torch.float32,
                "device_map": self.device
            }

            # For larger models, consider using bitsandbytes for quantization
            try:
                import bitsandbytes as bnb
                model_kwargs["load_in_8bit"] = True
                print("Using 8-bit quantization with bitsandbytes")
            except ImportError:
                print("bitsandbytes not available, using full precision model")

            # Load the model
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                cache_dir=self.cache_dir,
                **model_kwargs
            )

            # Create pipeline
            self.pipeline = pipeline(
                "text-generation",
                model=self.model,
                tokenizer=self.tokenizer,
                device=self.device
            )

            print(f"Model {self.model_name} loaded successfully")
        except Exception as e:
            print(f"Error loading local model: {e}")
            traceback.print_exc()
            self.model = None
            self.tokenizer = None
            self.pipeline = None

    def generate_text(self, prompt: str, max_tokens: int = 500, temperature: float = 0.7) -> str:
        """
        Generate text from a prompt using a local model.

        Args:
            prompt: Text prompt
            max_tokens: Maximum number of tokens to generate
            temperature: Temperature for sampling

        Returns:
            Generated text
        """
        if self.pipeline is None:
            raise LLMError("Local model not initialized correctly")

        try:
            # Generate text
            result = self.pipeline(
                prompt,
                max_new_tokens=max_tokens,
                temperature=temperature,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id,
                repetition_penalty=1.1,
                num_return_sequences=1
            )

            # Extract generated text
            generated_text = result[0]["generated_text"]

            # Remove the prompt from the beginning
            if generated_text.startswith(prompt):
                generated_text = generated_text[len(prompt):].strip()

            return generated_text
        except Exception as e:
            raise LLMError(f"Error generating text with local model: {e}")

    def generate_with_context(self, query: str, context: str, max_tokens: int = 500, temperature: float = 0.7) -> str:
        """
        Generate text based on query and context using a local model.

        Args:
            query: The question or query
            context: Context information for the query
            max_tokens: Maximum number of tokens to generate
            temperature: Temperature for sampling

        Returns:
            Generated text
        """
        # Construct a prompt with context and query
        prompt = f"""Answer the following question based on the provided context.
        
Context:
{context}

Question:
{query}

Answer:
"""
        return self.generate_text(prompt, max_tokens, temperature)
