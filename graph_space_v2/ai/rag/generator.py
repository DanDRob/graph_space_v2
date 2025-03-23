from typing import Dict, List, Any, Optional, Union
import time

from graph_space_v2.ai.llm.llm_service import LLMService
from graph_space_v2.ai.rag.retriever import Retriever
from graph_space_v2.ai.llm.prompts import get_prompt, format_prompt_with_context


class Generator:
    """Generator component for the RAG system."""

    def __init__(
        self,
        llm_service: LLMService,
        retriever: Retriever
    ):
        """
        Initialize the generator.

        Args:
            llm_service: LLM service for generation
            retriever: Retriever for context retrieval
        """
        self.llm_service = llm_service
        self.retriever = retriever

    def generate_answer(
        self,
        query: str,
        top_k: int = 5,
        context_strategy: str = "hybrid",
        filters: Optional[Dict[str, Any]] = None,
        max_tokens: int = 500,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Generate an answer for a query using retrieved contexts.

        Args:
            query: Query text
            top_k: Number of contexts to retrieve
            context_strategy: Strategy for context retrieval
            filters: Optional filters to apply to retrieval
            max_tokens: Maximum number of tokens to generate
            temperature: Temperature for sampling

        Returns:
            Dictionary containing the answer and metadata
        """
        # Retrieve contexts
        contexts = self.retriever.retrieve(
            query=query,
            top_k=top_k,
            retrieval_type=context_strategy,
            filters=filters
        )

        # Extract context text
        context_text = self._format_contexts(contexts)

        # Generate answer
        answer = self.llm_service.generate_answer(
            query=query,
            context=context_text,
            max_tokens=max_tokens,
            temperature=temperature
        )

        return {
            "query": query,
            "answer": answer,
            "contexts": contexts,
            "metadata": {
                "context_strategy": context_strategy,
                "top_k": top_k,
                "timestamp": time.time()
            }
        }

    def _format_contexts(self, contexts: List[Dict[str, Any]]) -> str:
        """
        Format contexts for LLM input.

        Args:
            contexts: List of context dictionaries

        Returns:
            Formatted context text
        """
        formatted_contexts = []

        for i, context in enumerate(contexts):
            text = context["text"]
            metadata = context["metadata"]

            # Format based on entity type
            if metadata.get("type") == "note":
                title = metadata.get("title", "Untitled Note")
                formatted_contexts.append(f"[NOTE {i+1}: {title}]\n{text}")
            elif metadata.get("type") == "task":
                title = metadata.get("title", "Untitled Task")
                status = metadata.get("status", "")
                formatted_contexts.append(
                    f"[TASK {i+1}: {title} ({status})]\n{text}")
            else:
                # Default format
                formatted_contexts.append(f"[DOCUMENT {i+1}]\n{text}")

        return "\n\n".join(formatted_contexts)

    def generate_with_prompt_template(
        self,
        query: str,
        prompt_template: str,
        top_k: int = 5,
        context_strategy: str = "hybrid",
        filters: Optional[Dict[str, Any]] = None,
        max_tokens: int = 500,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Generate an answer using a specific prompt template.

        Args:
            query: Query text
            prompt_template: Prompt template name
            top_k: Number of contexts to retrieve
            context_strategy: Strategy for context retrieval
            filters: Optional filters to apply to retrieval
            max_tokens: Maximum number of tokens to generate
            temperature: Temperature for sampling

        Returns:
            Dictionary containing the answer and metadata
        """
        # Get the system prompt
        system_prompt = get_prompt(prompt_template)

        # Retrieve contexts
        contexts = self.retriever.retrieve(
            query=query,
            top_k=top_k,
            retrieval_type=context_strategy,
            filters=filters
        )

        # Extract context text
        context_text = self._format_contexts(contexts)

        # Format prompt with context and query
        prompt = f"{system_prompt}\n\nContext:\n{context_text}\n\nQuestion: {query}\n\nAnswer:"

        # Generate answer
        answer = self.llm_service.generate_text(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature
        )

        return {
            "query": query,
            "answer": answer,
            "contexts": contexts,
            "metadata": {
                "prompt_template": prompt_template,
                "context_strategy": context_strategy,
                "top_k": top_k,
                "timestamp": time.time()
            }
        }

    def summarize_document(
        self,
        document_text: str,
        max_tokens: int = 200,
        temperature: float = 0.5
    ) -> str:
        """
        Summarize a document.

        Args:
            document_text: Document text to summarize
            max_tokens: Maximum number of tokens in the summary
            temperature: Temperature for sampling

        Returns:
            Document summary
        """
        return self.llm_service.summarize_text(
            text=document_text,
            max_length=max_tokens
        )

    def extract_key_entities(
        self,
        text: str,
        max_tokens: int = 200,
        temperature: float = 0.3
    ) -> Dict[str, List[str]]:
        """
        Extract key entities from text.

        Args:
            text: Text to extract entities from
            max_tokens: Maximum number of tokens in the response
            temperature: Temperature for sampling

        Returns:
            Dictionary of entity types to lists of entities
        """
        return self.llm_service.extract_entities(text)
