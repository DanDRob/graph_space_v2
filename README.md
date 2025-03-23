# GraphSpace v2

A modular knowledge graph-based productivity assistant that helps you organize and retrieve information using advanced AI techniques including Graph Neural Networks (GNN) and Retrieval-Augmented Generation (RAG).

## Overview

GraphSpace v2 is a comprehensive knowledge management system that allows you to:

- Connect notes, tasks, documents, and contacts in a unified knowledge graph
- Leverage AI to find connections between disparate pieces of information
- Search and query your knowledge base using natural language
- Process and extract knowledge from various document formats
- Integrate with external services like Google Drive and Calendar
- Access your information through a clean web interface

The system combines traditional graph database concepts with modern AI approaches like embeddings, large language models, and graph neural networks to create a powerful productivity assistant.

## Core Features

### Knowledge Graph

- **Entity Management**: Create and manage notes, tasks, contacts, and documents
- **Relationship Discovery**: Automatically detect and establish connections between entities
- **Graph Visualization**: View your knowledge network visually to discover insights
- **Custom Relationships**: Define your own relationship types between entities

### AI Capabilities

- **Semantic Search**: Find information based on meaning, not just keywords
- **Natural Language Querying**: Ask questions about your knowledge graph in plain English
- **Content Analysis**: Extract entities, topics, and summaries from documents
- **Tag Generation**: Automatically generate tags for better organization
- **GNN-based Recommendations**: Get suggestions for related content using graph neural networks

### Document Processing

- **Multi-format Support**: Process PDF, DOCX, TXT, XLSX, and Markdown files
- **Content Extraction**: Extract and index text from all supported formats
- **Document Chunking**: Break large documents into manageable pieces for better retrieval
- **Metadata Extraction**: Automatically extract titles, authors, and other metadata

### Task Management

- **Priority-based Tasks**: Organize tasks by priority, status, and due dates
- **Project Organization**: Group tasks into projects for better management
- **Recurring Tasks**: Set up tasks that automatically repeat on schedule
- **Calendar Integration**: Sync tasks with Google Calendar or iCal

### External Integrations

- **Google Drive**: Access and process documents stored in Google Drive
- **Google Calendar**: Two-way synchronization with Google Calendar
- **iCal Support**: Import and export calendar data in iCal format
- **Extensible Framework**: Add your own integrations through a modular design

## Technical Architecture

GraphSpace v2 has been completely refactored with a modular architecture designed for extensibility and maintainability:

```
graph_space_v2/
│
├── core/                  # Core functionality
│   ├── models/            # Data models for notes, tasks, contacts
│   ├── graph/             # Knowledge graph implementation
│   └── services/          # Business logic services
│
├── ai/                    # AI components
│   ├── embedding/         # Text embedding and vector search
│   ├── llm/               # Language model integration
│   ├── gnn/               # Graph neural network implementation
│   └── rag/               # Retrieval-augmented generation
│
├── integrations/          # External integrations
│   ├── document/          # Document processing pipeline
│   ├── calendar/          # Calendar integration
│   └── google/            # Google API integration
│
├── api/                   # REST API
│   ├── routes/            # API endpoints
│   └── middleware/        # Request processing middleware
│
├── ui/                    # User interface
│   ├── templates/         # HTML templates
│   └── static/            # CSS, JS, and assets
│
└── utils/                 # Utility functions
    ├── config/            # Configuration handling
    ├── helpers/           # Helper utilities
    └── errors/            # Error handling
```

### Key Components

- **KnowledgeGraph**: The central component that manages all entities and relationships
- **EmbeddingService**: Handles text embeddings for semantic search and similarity
- **LLMService**: Provides access to language models for text generation and analysis
- **DocumentProcessor**: Processes various document formats and extracts knowledge
- **API Endpoints**: REST API for interacting with the system programmatically
- **Web Interface**: Clean, responsive UI for managing your knowledge graph

## Installation

### Prerequisites

- Python 3.8 or higher
- Pip package manager
- An API key for DeepSeek or OpenAI (optional, for enhanced LLM capabilities)
- Google API credentials (optional, for Google Drive/Calendar integration)

### Standard Installation

1. Clone this repository:

   ```bash
   git clone https://github.com/example/graph_space_v2.git
   cd graph_space_v2
   ```

2. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Development Installation

For development work, install as an editable package:

```bash
pip install -e .
```

### Environment Variables

Create a `.env` file in the root directory with the following variables:

```
DEEPSEEK_API_KEY=your_api_key_here
ENABLE_GOOGLE_INTEGRATION=false
SECRET_KEY=your_secret_key_for_jwt
```

## Configuration

GraphSpace v2 is highly configurable through the `config/config.json` file. Key configuration options include:

### API Settings

```json
"api": {
  "host": "127.0.0.1",
  "port": 5000,
  "debug": false
}
```

### LLM Configuration

```json
"llm": {
  "provider": "deepseek",
  "model": "deepseek-chat",
  "fallback_model": "meta-llama/Llama-3-8B-Instruct",
  "temperature": 0.7,
  "max_tokens": 500
}
```

### Embedding Settings

```json
"embedding": {
  "model": "sentence-transformers/all-mpnet-base-v2",
  "dimension": 768
}
```

### Document Processing

```json
"document_processing": {
  "chunk_size": 500,
  "overlap": 50,
  "max_workers": 4
}
```

### GNN Parameters

```json
"gnn": {
  "dimensions": 128,
  "learning_rate": 0.01,
  "epochs": 100,
  "walk_length": 10,
  "num_walks": 10
}
```

## Usage

### Running the Web Interface

Start the web server:

```bash
python run.py
```

Or if installed as a package:

```bash
graphspace
```

Then open your browser to http://localhost:5000

### API Usage

GraphSpace v2 provides a RESTful API for programmatic access to all features:

#### Notes API

```bash
# Create a note
curl -X POST http://localhost:5000/api/notes \
  -H "Content-Type: application/json" \
  -d '{"title": "My Note", "content": "This is a test note", "tags": ["test", "example"]}'

# Get all notes
curl http://localhost:5000/api/notes
```

#### Tasks API

```bash
# Create a task
curl -X POST http://localhost:5000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"title": "My Task", "description": "This is a test task", "due_date": "2023-12-31T23:59:59", "priority": "high"}'

# Get all tasks
curl http://localhost:5000/api/tasks
```

#### Document Processing

```bash
# Process a document
curl -X POST http://localhost:5000/api/documents/process \
  -F "file=@/path/to/document.pdf" \
  -F "metadata={\"tags\": [\"important\", \"reference\"]}"
```

#### Semantic Search

```bash
# Search across all entities
curl http://localhost:5000/api/search?q=machine%20learning&limit=5
```

## Data Storage

GraphSpace v2 uses a combination of file-based storage and in-memory graph representation:

- **Graph Structure**: NetworkX graph object in memory
- **Main Knowledge Graph**: `data/user_data.json`
- **Document Storage**: `data/documents/`
- **Document Metadata**: `data/documents/metadata.json`
- **Embeddings**: `data/embeddings/`
- **Uploads**: `data/uploads/`
- **Temporary Files**: `data/temp/`

## API Reference

### Notes Endpoints

- `GET /api/notes` - List all notes
- `GET /api/notes/{id}` - Get note by ID
- `POST /api/notes` - Create new note
- `PUT /api/notes/{id}` - Update note
- `DELETE /api/notes/{id}` - Delete note

### Tasks Endpoints

- `GET /api/tasks` - List all tasks
- `GET /api/tasks/{id}` - Get task by ID
- `POST /api/tasks` - Create new task
- `PUT /api/tasks/{id}` - Update task
- `DELETE /api/tasks/{id}` - Delete task
- `GET /api/tasks/status/{status}` - Get tasks by status
- `GET /api/tasks/project/{project}` - Get tasks by project
- `GET /api/tasks/overdue` - Get overdue tasks
- `GET /api/tasks/due-soon` - Get tasks due soon

### Contacts Endpoints

- `GET /api/contacts` - List all contacts
- `GET /api/contacts/{id}` - Get contact by ID
- `POST /api/contacts` - Create new contact
- `PUT /api/contacts/{id}` - Update contact
- `DELETE /api/contacts/{id}` - Delete contact

### Documents Endpoints

- `GET /api/documents` - List all documents
- `GET /api/documents/{id}` - Get document by ID
- `POST /api/documents/process` - Process and add a document
- `DELETE /api/documents/{id}` - Delete document
- `POST /api/documents/process-directory` - Process all documents in a directory

### Search and Query Endpoints

- `GET /api/search` - Search across all entities
- `GET /api/semantic-search` - Search by semantic meaning
- `GET /api/query` - Natural language query processing
- `GET /api/similar-nodes/{id}` - Find nodes similar to the given ID
- `GET /api/graph-data` - Get graph visualization data

### Authentication Endpoints

- `POST /api/auth/login` - Authenticate and get JWT token
- `GET /api/auth/status` - Check authentication status

### Integration Endpoints

- `GET /api/integrations/google/auth` - Authenticate with Google
- `GET /api/integrations/google/drive/files` - List Google Drive files
- `POST /api/integrations/google/drive/process` - Process Google Drive file
- `GET /api/integrations/calendar/events` - Get calendar events
- `POST /api/integrations/calendar/sync` - Synchronize with calendar

## Technology Stack

- **Backend**: Python 3.8+, Flask
- **Graph Database**: NetworkX
- **Embeddings**: Sentence Transformers
- **LLM Integration**: OpenAI API, DeepSeek
- **GNN**: PyTorch Geometric
- **Vector Search**: FAISS
- **Document Processing**: PyPDF2, python-docx, pdfminer.six
- **Frontend**: HTML, CSS, JavaScript, Bootstrap 5
- **Authentication**: JWT
- **Google Integration**: Google API Python Client

## Dependencies

Key dependencies include:

- **torch** & **torch-geometric**: For graph neural network implementation
- **networkx**: For graph data structure
- **sentence-transformers**: For text embeddings
- **faiss-cpu**: For vector similarity search
- **langchain**: For RAG implementation
- **openai**: For LLM API access
- **flask**: For web server and API
- **PyPDF2** & **python-docx**: For document processing
- **google-api-python-client**: For Google integration
- **icalendar**: For calendar integration

For a complete list, see `requirements.txt`.

## Contributing

Contributions are welcome! Here's how you can contribute:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Make your changes
4. Run tests: `pytest`
5. Commit your changes: `git commit -m 'Add new feature'`
6. Push to the branch: `git push origin feature/new-feature`
7. Submit a pull request

## License

GraphSpace v2 is released under the MIT License. See the LICENSE file for details.

## Project Status

GraphSpace v2 is currently in beta. While all core functionality is implemented and working, some advanced features are still under active development.

## Future Enhancements

- Mobile application for on-the-go access
- Enhanced GNN models for better relationship discovery
- Collaboration features for team knowledge sharing
- Integration with more external services
- Advanced visualization options for knowledge exploration
- Offline mode with synchronization
