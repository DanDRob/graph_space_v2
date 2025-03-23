#!/usr/bin/env python3
import os
import sys
import traceback

# Add the parent directory to the path so we can find the graph_space_v2 module
# Get the absolute path of this script
current_dir = os.path.dirname(os.path.abspath(__file__))
# Get the parent directory (which should contain graph_space_v2)
parent_dir = os.path.abspath(os.path.join(current_dir, '..'))
# Add both directories to Python path to ensure imports work correctly
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

print(f"Current directory: {current_dir}")
print(f"Parent directory: {parent_dir}")
print(f"Python path: {sys.path}")

# Try each import separately to identify the problematic one
try:
    print("Attempting to import KnowledgeGraph...")
    from graph_space_v2.core.graph.knowledge_graph import KnowledgeGraph
    print("Successfully imported KnowledgeGraph")
except ImportError as e:
    print(f"Error importing KnowledgeGraph: {e}")
    traceback.print_exc()

try:
    print("Attempting to import EmbeddingService...")
    from graph_space_v2.ai.embedding.embedding_service import EmbeddingService
    print("Successfully imported EmbeddingService")
except ImportError as e:
    print(f"Error importing EmbeddingService: {e}")
    traceback.print_exc()

try:
    print("Attempting to import LLMService...")
    from graph_space_v2.ai.llm.llm_service import LLMService
    print("Successfully imported LLMService")
except ImportError as e:
    print(f"Error importing LLMService: {e}")
    traceback.print_exc()

try:
    print("Attempting to import GraphSpace...")
    from graph_space_v2.graphspace import GraphSpace
    print("Successfully imported GraphSpace")
except ImportError as e:
    print(f"Error importing GraphSpace: {e}")
    traceback.print_exc()
    sys.exit(1)

# Import the path utilities
try:
    from graph_space_v2.utils.helpers.path_utils import init_dirs, get_user_data_path, get_config_path
except ImportError as e:
    print(f"Error importing path_utils: {e}")
    traceback.print_exc()
    sys.exit(1)


def main():
    """Main entry point for the GraphSpace application."""
    # Initialize all necessary directories
    init_dirs()

    # Create GraphSpace instance with paths from path_utils
    try:
        graphspace = GraphSpace(
            data_path=get_user_data_path(),
            config_path=get_config_path(),
            use_api=True,
            api_key=os.environ.get("DEEPSEEK_API_KEY"),
            use_google_drive=False
        )

        # Import web app and run it
        try:
            from graph_space_v2.api.app import run_app
            run_app(graphspace, host='127.0.0.1', debug=False)
        except ImportError as e:
            print(f"Error loading web interface: {e}")
            sys.exit(1)

    except Exception as e:
        print(f"\nError initializing GraphSpace: {e}")
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    print(f"Running from: {os.path.abspath(__file__)}")
    sys.exit(main())
