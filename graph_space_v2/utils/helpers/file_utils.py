import os
import json
import shutil
import tempfile
from typing import Dict, List, Any, Optional, Union, BinaryIO
from pathlib import Path
import hashlib
import mimetypes


def ensure_dir(directory: str) -> None:
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        directory: Directory path to create
    """
    os.makedirs(directory, exist_ok=True)


def get_file_extension(filename: str) -> str:
    """
    Get the file extension from a filename.

    Args:
        filename: Filename to get extension from

    Returns:
        File extension (lowercase) without the dot
    """
    return os.path.splitext(filename)[1].lower().lstrip('.')


def is_allowed_file(filename: str, allowed_extensions: List[str]) -> bool:
    """
    Check if a file has an allowed extension.

    Args:
        filename: Filename to check
        allowed_extensions: List of allowed extensions

    Returns:
        True if the file has an allowed extension, False otherwise
    """
    return get_file_extension(filename) in allowed_extensions


def get_mime_type(filename: str) -> str:
    """
    Get the MIME type of a file.

    Args:
        filename: Filename to check

    Returns:
        MIME type
    """
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type or 'application/octet-stream'


def save_json(data: Any, filepath: str) -> None:
    """
    Save data to a JSON file.

    Args:
        data: Data to save
        filepath: Path to save to
    """
    ensure_dir(os.path.dirname(filepath))
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_json(filepath: str, default: Any = None) -> Any:
    """
    Load data from a JSON file.

    Args:
        filepath: Path to load from
        default: Default value if file doesn't exist or is invalid

    Returns:
        Loaded data or default value
    """
    if not os.path.exists(filepath):
        return default

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return default


def file_hash(filepath: str, algorithm: str = 'md5') -> str:
    """
    Calculate the hash of a file.

    Args:
        filepath: Path to the file
        algorithm: Hash algorithm to use

    Returns:
        Hexadecimal hash string
    """
    if not os.path.exists(filepath):
        return ""

    hasher = hashlib.new(algorithm)
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_file_size(filepath: str, format: str = 'bytes') -> Union[int, str]:
    """
    Get the size of a file.

    Args:
        filepath: Path to the file
        format: Format to return the size in ('bytes', 'kb', 'mb', 'gb')

    Returns:
        File size in the specified format
    """
    if not os.path.exists(filepath):
        return 0

    size_bytes = os.path.getsize(filepath)

    if format == 'bytes':
        return size_bytes
    elif format == 'kb':
        return f"{size_bytes / 1024:.2f} KB"
    elif format == 'mb':
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    elif format == 'gb':
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
    else:
        return size_bytes


def create_temp_file(data: Union[str, bytes], suffix: Optional[str] = None) -> str:
    """
    Create a temporary file with the given content.

    Args:
        data: Data to write to the file
        suffix: Optional file suffix

    Returns:
        Path to the temporary file
    """
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp:
        if isinstance(data, str):
            temp.write(data.encode('utf-8'))
        else:
            temp.write(data)
        return temp.name


def delete_file(filepath: str) -> bool:
    """
    Delete a file if it exists.

    Args:
        filepath: Path to the file

    Returns:
        True if file was deleted, False otherwise
    """
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            return True
        except OSError:
            return False
    return False


def copy_file(src: str, dst: str, overwrite: bool = True) -> bool:
    """
    Copy a file from source to destination.

    Args:
        src: Source path
        dst: Destination path
        overwrite: Whether to overwrite existing files

    Returns:
        True if file was copied, False otherwise
    """
    if not os.path.exists(src):
        return False

    if os.path.exists(dst) and not overwrite:
        return False

    try:
        ensure_dir(os.path.dirname(dst))
        shutil.copy2(src, dst)
        return True
    except OSError:
        return False
