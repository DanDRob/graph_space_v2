import os
import json
import re
from typing import Dict, Any
from graph_space_v2.utils.helpers.path_utils import ensure_dir_exists, get_config_path, get_data_dir


class ConfigLoader:
    """Utility class for loading configuration files."""

    def __init__(self, config_path: str):
        """
        Initialize the ConfigLoader.

        Args:
            config_path: Path to the configuration file
        """
        self.config_path = config_path

    def load_config(self) -> Dict[str, Any]:
        """
        Load configuration from a JSON file or create a default one.

        Returns:
            Dictionary containing the configuration
        """
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    config = json.load(f)
                    # Process any template variables in the config
                    return self._process_template_vars(config)
            except Exception as e:
                print(f"Error loading config: {e}, using defaults")

        # Default configuration
        default_config = {
            "embedding": {
                "model": "sentence-transformers/all-mpnet-base-v2",
                "dimension": 768
            },
            "llm": {
                "api_enabled": True,
                "model": "deepseek-ai/deepseek-chat-v1",
                "fallback_model": "meta-llama/Llama-3-8B-Instruct"
            },
            "document_processing": {
                "max_workers": 4,
                "chunk_size": 1000
            }
        }

        # Save default config
        ensure_dir_exists(os.path.dirname(self.config_path))
        with open(self.config_path, "w") as f:
            json.dump(default_config, f, indent=2)

        return default_config

    def _process_template_vars(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process template variables in config strings.

        Args:
            config: The configuration dictionary

        Returns:
            Processed configuration with template variables replaced
        """
        # Convert to JSON and back to easily find and replace all string values
        config_str = json.dumps(config)

        # Replace variables
        var_map = {
            "${data_dir}": get_data_dir(),
            "${config_dir}": os.path.dirname(self.config_path)
        }

        for var, value in var_map.items():
            config_str = config_str.replace(var, value.replace("\\", "\\\\"))

        # Convert back to dict
        return json.loads(config_str)

    def save_config(self, config: Dict[str, Any]) -> None:
        """
        Save configuration to file.

        Args:
            config: Configuration dictionary to save
        """
        ensure_dir_exists(os.path.dirname(self.config_path))
        with open(self.config_path, "w") as f:
            json.dump(config, f, indent=2)

    def update_config(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update configuration with new values.

        Args:
            updates: Dictionary containing updates to apply

        Returns:
            Updated configuration dictionary
        """
        config = self.load_config()

        # Deep update the configuration
        def update_nested_dict(d, u):
            for k, v in u.items():
                if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                    update_nested_dict(d[k], v)
                else:
                    d[k] = v

        update_nested_dict(config, updates)
        self.save_config(config)
        return config
