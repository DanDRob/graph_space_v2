from typing import Dict, List, Any, Optional

# Task-specific system prompts for different language model interactions
SYSTEM_PROMPTS = {
    # General conversation prompt
    "general": """You are a helpful assistant that provides accurate, concise information. 
    You are polite, respectful, and focused on addressing the user's needs effectively.""",

    # Query processing prompt
    "query": """You are an assistant that helps users find information in a knowledge graph.
    Analyze the query and help extract its intent and key entities.""",

    # Tag extraction prompt
    "tag_extraction": """Extract relevant tags or keywords from the provided text.
    Return a comma-separated list of tags without explanations or additional text.
    Focus on topics, entities, concepts, and themes that best categorize the content.
    Tags should be concise (1-3 words each) and capture the essence of the content.""",

    # Title generation prompt
    "title_generation": """Generate a concise, descriptive title for the provided content.
    The title should be no more than 10 words, capture the main topic, and be engaging.
    Return only the title without any explanations or additional text.""",

    # Summarization prompt
    "summarization": """Summarize the provided text in a concise manner while preserving the key information.
    Focus on main points, important facts, and conclusions.
    The summary should be significantly shorter than the original text but maintain the essential meaning.""",

    # Question answering prompt
    "question_answering": """Answer the question based on the provided context.
    If the context does not contain enough information to answer the question properly, 
    say so clearly rather than making up information.
    Cite relevant parts of the context to support your answer.""",

    # Relationship identification prompt
    "relationship_identification": """Analyze the provided text and identify relationships between entities.
    Look for connections such as:
    - Person to organization (works for, founded, etc.)
    - Person to person (colleague, friend, reports to, etc.)
    - Entity to concept (is part of, belongs to, etc.)
    - Temporal relationships (before, after, during)
    Return the relationships in a structured format.""",

    # Content classification prompt
    "content_classification": """Classify the provided content according to the following categories:
    1. Type (note, task, contact, document, etc.)
    2. Priority (high, medium, low)
    3. Domain (personal, work, academic, etc.)
    4. Complexity (simple, moderate, complex)
    Return the classifications with brief explanations for each.""",

    # Task extraction prompt
    "task_extraction": """Extract actionable tasks or to-do items from the provided text.
    For each task, identify:
    1. The action to be performed
    2. Any deadline or timing information
    3. Assigned person (if mentioned)
    4. Priority indicators (if mentioned)
    Return the tasks in a list format.""",

    # Entity extraction prompt
    "entity_extraction": """Extract named entities from the provided text.
    Include categories such as:
    - People
    - Organizations
    - Locations
    - Dates and times
    - Products
    - Events
    Return the entities grouped by category in a structured format.""",

    # Content expansion prompt
    "content_expansion": """Expand on the provided brief text to create a more detailed and comprehensive version.
    Maintain the original meaning and intent while adding relevant details, examples, or explanations.
    The expanded content should be well-structured and coherent."""
}


def get_prompt(prompt_type: str, default: Optional[str] = None) -> str:
    """
    Get a system prompt by type.

    Args:
        prompt_type: Type of prompt to retrieve
        default: Default prompt to return if type not found

    Returns:
        System prompt text
    """
    return SYSTEM_PROMPTS.get(prompt_type, default or SYSTEM_PROMPTS["general"])


def format_prompt_with_context(system_prompt: str, user_query: str, context: str) -> Dict[str, Any]:
    """
    Format a prompt with system message, user query, and context.

    Args:
        system_prompt: System prompt text
        user_query: User's query or question
        context: Context information

    Returns:
        Formatted messages for LLM API
    """
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {user_query}"}
    ]


def format_tag_extraction_prompt(content: str) -> str:
    """
    Format a prompt for tag extraction.

    Args:
        content: Content to extract tags from

    Returns:
        Formatted prompt
    """
    system_prompt = get_prompt("tag_extraction")
    return f"{system_prompt}\n\nText:\n{content}\n\nTags:"


def format_summarization_prompt(content: str) -> str:
    """
    Format a prompt for summarization.

    Args:
        content: Content to summarize

    Returns:
        Formatted prompt
    """
    system_prompt = get_prompt("summarization")
    return f"{system_prompt}\n\nText:\n{content}\n\nSummary:"


def format_title_generation_prompt(content: str) -> str:
    """
    Format a prompt for title generation.

    Args:
        content: Content to generate title for

    Returns:
        Formatted prompt
    """
    system_prompt = get_prompt("title_generation")
    return f"{system_prompt}\n\nContent:\n{content}\n\nTitle:"
