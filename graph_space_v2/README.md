# GraphSpace v2

A modular knowledge graph-based productivity assistant that helps you organize and retrieve information using Graph Neural Networks (GNN) and Retrieval-Augmented Generation (RAG).

## Features

- **Personal Knowledge Graph**: Connect notes, tasks, and contacts in a graph structure
- **AI-Enhanced Retrieval**: Find relevant information using GNN-based embeddings
- **Smart Querying**: Ask natural language questions about your knowledge graph
- **Relationship Discovery**: Automatically find connections between items
- **Document Processing**: Extract knowledge from uploaded documents (PDF, DOCX, TXT)
- **Google Integration**: Connect with Google Drive and Google Calendar
- **Modern UI**: Clean, responsive interface for easy knowledge management

## Architecture

GraphSpace v2 has been completely refactored with a modular architecture:

```
graph_space_v2/
│
├── core/                  # Core functionality
│   ├── models/            # Data models
│   ├── graph/             # Graph structure and operations
│   └── services/          # Business logic
│
├── ai/                    # AI components
│   ├── embedding/         # Vector embeddings
│   ├── llm/               # Language model integration
│   ├── gnn/               # Graph neural networks
│   └── rag/               # Retrieval-augmented generation
│
├── integrations/          # External integrations
│   ├── document/          # Document processing
│   ├── calendar/          # Calendar integration
│   └── google/            # Google API integration
│
├── api/                   # REST API
│   ├── routes/            # API endpoints
│   └── middleware/        # Request processing
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

## Installation

1. Clone this repository
2. Install the dependencies:

```bash
cd graph_space_v2
pip install -r requirements.txt
```

Alternatively, install as a package:

```bash
pip install -e .
```

## Configuration

The application is configured through `config/config.json`. You can customize:

- API settings
- Database paths
- LLM providers and models
- Embedding models
- Document processing settings
- GNN parameters
- Calendar integration

## Usage

Run the web interface:

```bash
cd graph_space_v2
python run.py
```

Or if installed as a package:

```bash
graphspace
```

Then open your browser to http://localhost:5000

## Data Storage

- Main knowledge graph: `data/user_data.json`
- Task data: `data/tasks.json`
- Document storage: `data/documents/`
- Temporary files: `data/temp/`
- Uploaded files: `data/uploads/`

## API Documentation

The application provides a RESTful API with the following endpoints:

- `/api/notes` - Manage notes
- `/api/tasks` - Manage tasks
- `/api/contacts` - Manage contacts
- `/api/documents` - Manage documents
- `/api/query` - Query the knowledge graph
- `/api/similar_nodes/<node_id>` - Find similar nodes
- `/api/semantic_search` - Search by semantic meaning
- `/api/search` - Keyword-based search
- `/api/graph_data` - Get graph visualization data

## Technology Stack

- **Backend**: Python, Flask
- **Graph Database**: NetworkX
- **Embeddings**: Sentence Transformers
- **LLM**: OpenAI API, DeepSeek
- **GNN**: PyTorch Geometric
- **Frontend**: HTML, CSS, JavaScript, Bootstrap 5
- **Authentication**: JWT

## Requirements

- Python 3.8+
- See requirements.txt for full dependencies

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
