import os
import json
from typing import Optional

# Get the absolute path to the graph_space_v2 package directory
PACKAGE_DIR = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', '..'))

# Default data directory
DEFAULT_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), 'data')

# Default config directory
DEFAULT_CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), 'config')


def get_data_dir() -> str:
    """
    Get the data directory path.

    Returns:
        Path to the data directory
    """
    return DEFAULT_DATA_DIR


def get_config_dir() -> str:
    """
    Get the config directory path.

    Returns:
        Path to the config directory
    """
    return DEFAULT_CONFIG_DIR


def get_data_file_path(filename: str) -> str:
    return os.path.join(get_data_dir(), filename)


def get_config_file_path(filename: str) -> str:
    return os.path.join(get_config_dir(), filename)


def get_user_data_path() -> str:
    """
    Get the path to the user data file.

    Returns:
        Path to the user data file
    """
    data_dir = get_data_dir()
    ensure_dir_exists(data_dir)
    return os.path.join(data_dir, 'user_data.json')


def get_config_path() -> str:
    """
    Get the path to the config file.

    Returns:
        Path to the config file
    """
    config_dir = get_config_dir()
    ensure_dir_exists(config_dir)
    return os.path.join(config_dir, 'config.json')


def ensure_dir_exists(dir_path: str) -> None:
    """
    Ensure that a directory exists, creating it if necessary.

    Args:
        dir_path: Path to the directory
    """
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)


def init_dirs() -> None:
    """
    Initialize all necessary directories.
    """
    # Create data directory
    data_dir = get_data_dir()
    print(f"Ensuring data directory exists: {data_dir}")
    ensure_dir_exists(data_dir)
    print(f"Data directory exists: {os.path.exists(data_dir)}")

    # Create uploads directory
    uploads_dir = os.path.join(data_dir, 'uploads')
    print(f"Ensuring uploads directory exists: {uploads_dir}")
    ensure_dir_exists(uploads_dir)
    print(f"Uploads directory exists: {os.path.exists(uploads_dir)}")

    # Create documents directory
    documents_dir = os.path.join(data_dir, 'documents')
    print(f"Ensuring documents directory exists: {documents_dir}")
    ensure_dir_exists(documents_dir)
    print(f"Documents directory exists: {os.path.exists(documents_dir)}")

    # Create temp directory
    temp_dir = os.path.join(data_dir, 'temp')
    print(f"Ensuring temp directory exists: {temp_dir}")
    ensure_dir_exists(temp_dir)
    print(f"Temp directory exists: {os.path.exists(temp_dir)}")

    # Create an empty user data file if it doesn't exist
    user_data_path = get_user_data_path()
    if not os.path.exists(user_data_path) or os.path.getsize(user_data_path) == 0:
        print(f"Creating empty user data file: {user_data_path}")
        with open(user_data_path, 'w') as f:
            json.dump({"notes": [], "tasks": [], "contacts": []}, f)
        print(f"User data file created: {os.path.exists(user_data_path)}")


def debug_data_file() -> dict:
    """
    Read the data file and return its contents for debugging.
    Also fixes the file if it's corrupted or empty.

    Returns:
        The data from the file or a new empty data structure
    """
    data_path = get_user_data_path()

    # Check if file exists
    if not os.path.exists(data_path):
        print(f"Data file not found at {data_path}, creating new one")
        init_dirs()  # This will create the file with default structure

    # Try to read the file
    try:
        with open(data_path, 'r') as f:
            content = f.read().strip()
            if not content:  # Empty file
                print(
                    f"Data file at {data_path} is empty, initializing with default structure")
                data = {"notes": [], "tasks": [],
                        "contacts": [], "documents": []}
                with open(data_path, 'w') as fw:
                    json.dump(data, fw, indent=2)
                return data
            else:
                data = json.loads(content)
                # Check if documents array exists
                if "documents" not in data:
                    print(f"Adding missing documents array to data file")
                    data["documents"] = []
                    with open(data_path, 'w') as fw:
                        json.dump(data, fw, indent=2)
                return data
    except json.JSONDecodeError:
        print(
            f"Data file at {data_path} is corrupted, initializing with default structure")
        data = {"notes": [], "tasks": [], "contacts": [], "documents": []}
        with open(data_path, 'w') as fw:
            json.dump(data, fw, indent=2)
        return data
    except Exception as e:
        print(f"Error reading data file: {e}")
        return {"notes": [], "tasks": [], "contacts": [], "documents": []}
