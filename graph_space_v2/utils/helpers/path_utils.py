import os
from typing import Optional

# Get the absolute path to the graph_space_v2 package directory
PACKAGE_DIR = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', '..'))


def get_data_dir() -> str:
    return os.path.join(PACKAGE_DIR, 'data')


def get_config_dir() -> str:
    return os.path.join(PACKAGE_DIR, 'config')


def get_data_file_path(filename: str) -> str:
    return os.path.join(get_data_dir(), filename)


def get_config_file_path(filename: str) -> str:
    return os.path.join(get_config_dir(), filename)


def get_user_data_path() -> str:
    return get_data_file_path('user_data.json')


def get_config_path() -> str:
    return get_config_file_path('config.json')


def ensure_dir_exists(path: str) -> None:
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def init_dirs() -> None:
    ensure_dir_exists(get_data_dir())
    ensure_dir_exists(get_config_dir())
    ensure_dir_exists(os.path.join(get_data_dir(), 'documents'))
    ensure_dir_exists(os.path.join(get_data_dir(), 'embeddings'))
    ensure_dir_exists(os.path.join(get_data_dir(), 'uploads'))
