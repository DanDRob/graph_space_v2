class GraphSpaceError(Exception):
    """Base exception for all GraphSpace errors."""
    pass


class ConfigError(GraphSpaceError):
    """Raised when there is an error with configuration."""
    pass


class KnowledgeGraphError(GraphSpaceError):
    """Raised when there is an error with the knowledge graph."""
    pass


class ModelError(GraphSpaceError):
    """Raised when there is an error with a model."""
    pass


class ServiceError(GraphSpaceError):
    """Raised when there is an error with a service."""
    pass


class EntityNotFoundError(GraphSpaceError):
    """Raised when an entity is not found."""
    pass


class AuthenticationError(GraphSpaceError):
    """Raised when there is an authentication error."""
    pass


class DocumentProcessingError(GraphSpaceError):
    """Raised when there is an error processing a document."""
    pass


class APIError(GraphSpaceError):
    """Raised when there is an error with an API."""
    pass


class EmbeddingError(GraphSpaceError):
    """Raised when there is an error with an embedding."""
    pass


class NoteServiceError(ServiceError):
    """Raised for errors specific to the NoteService."""
    pass


class TaskServiceError(ServiceError):
    """Raised for errors specific to the TaskService."""
    pass


class EmbeddingServiceError(ServiceError):
    """Raised for errors specific to the EmbeddingService."""
    pass


class LLMServiceError(ServiceError):
    """Raised for errors specific to the LLMService."""
    pass


class LLMError(GraphSpaceError):
    """Raised when there is an error with a language model."""
    pass


class IntegrationError(GraphSpaceError):
    """Raised when there is an error with an external integration."""
    pass
