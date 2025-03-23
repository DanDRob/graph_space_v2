import os
from graph_space_v2.utils.helpers.path_utils import get_data_dir
from typing import Dict, Any

# Create paths relative to the data directory
DATA_DIR = get_data_dir()

# Default application configuration
DEFAULT_CONFIG = {
    "api": {
        "host": "127.0.0.1",
        "port": 5000,
        "debug": True
    },
    "database": {
        "type": "json",
        "path": os.path.join(DATA_DIR, "user_data.json"),
        "tasks_path": os.path.join(DATA_DIR, "tasks.json")
    },
    "storage": {
        "uploads_dir": os.path.join(DATA_DIR, "uploads"),
        "documents_dir": os.path.join(DATA_DIR, "documents"),
        "temp_dir": os.path.join(DATA_DIR, "temp"),
        "max_upload_size_mb": 16
    },
    "embedding": {
        "model": "sentence-transformers/all-mpnet-base-v2",
        "dimension": 768,
        "batch_size": 32
    },
    "llm": {
        "api_enabled": True,
        "provider": "deepseek",
        "api_base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "fallback_provider": "meta",
        "fallback_model": "meta-llama/Llama-3-8B-Instruct",
        "temperature": 0.7,
        "max_tokens": 1024
    },
    "document_processing": {
        "max_workers": 4,
        "chunk_size": 1000,
        "chunk_overlap": 200,
        "allowed_extensions": ["pdf", "docx", "txt", "md", "csv", "xlsx"]
    },
    "gnn": {
        "input_dim": 64,
        "hidden_dim": 128,
        "output_dim": 64,
        "learning_rate": 0.01,
        "epochs": 50,
        "batch_size": 64
    },
    "calendar": {
        "sync_enabled": False,
        "default_provider": "google",
        "sync_interval_minutes": 60
    },
    "logging": {
        "level": "INFO",
        "file": "logs/graphspace.log",
        "max_size_mb": 10,
        "backup_count": 5
    }
}


def get_default_config() -> Dict[str, Any]:
    return DEFAULT_CONFIG.copy()


def get_section_defaults(section: str) -> Dict[str, Any]:
    if section in DEFAULT_CONFIG:
        return DEFAULT_CONFIG[section].copy()
    return {}
