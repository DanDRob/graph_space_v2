#!/usr/bin/env python3
import os
import sys
import traceback
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', stream=sys.stdout)
logger = logging.getLogger(__name__)

logger.info(
    f"Environment variables loaded. Google integration: {os.environ.get('ENABLE_GOOGLE_INTEGRATION', 'false')}")

# Add the parent directory to the path so we can find the graph_space_v2 module
# Get the absolute path of this script
current_dir = os.path.dirname(os.path.abspath(__file__))
# Get the parent directory (which should contain graph_space_v2)
parent_dir = os.path.abspath(os.path.join(current_dir, '..'))
# Add both directories to Python path to ensure imports work correctly
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

logger.info(f"Current directory: {current_dir}")
logger.info(f"Parent directory: {parent_dir}")
logger.debug(f"Python path: {sys.path}") # Changed to debug as it's verbose

# Try each import separately to identify the problematic one
try:
    logger.debug("Attempting to import KnowledgeGraph...")
    from graph_space_v2.core.graph.knowledge_graph import KnowledgeGraph
    logger.debug("Successfully imported KnowledgeGraph")
except ImportError as e:
    logger.error(f"Error importing KnowledgeGraph: {e}", exc_info=True)
    # traceback.print_exc() # Replaced by exc_info=True

try:
    logger.debug("Attempting to import EmbeddingService...")
    from graph_space_v2.ai.embedding.embedding_service import EmbeddingService
    logger.debug("Successfully imported EmbeddingService")
except ImportError as e:
    logger.error(f"Error importing EmbeddingService: {e}", exc_info=True)
    # traceback.print_exc()

try:
    logger.debug("Attempting to import LLMService...")
    from graph_space_v2.ai.llm.llm_service import LLMService
    logger.debug("Successfully imported LLMService")
except ImportError as e:
    logger.error(f"Error importing LLMService: {e}", exc_info=True)
    # traceback.print_exc()

try:
    logger.info("Attempting to import GraphSpace...") # Info level for key component
    from graph_space_v2.graphspace import GraphSpace
    logger.info("Successfully imported GraphSpace")
except ImportError as e:
    logger.critical(f"CRITICAL: Error importing GraphSpace: {e}", exc_info=True) # Critical as app cannot run
    # traceback.print_exc()
    sys.exit(1)

# Import the path utilities
try:
    logger.debug("Attempting to import path_utils...")
    from graph_space_v2.utils.helpers.path_utils import init_dirs, get_user_data_path, get_config_path, debug_data_file
    logger.debug("Successfully imported path_utils")
except ImportError as e:
    logger.critical(f"CRITICAL: Error importing path_utils: {e}", exc_info=True) # Critical for basic operation
    # traceback.print_exc()
    sys.exit(1)


def main():
    """Main entry point for the GraphSpace application."""
    # Initialize all necessary directories
    logger.info("Initializing directories...")
    init_dirs()
    logger.info("Directories initialized.")

    # Debug and fix the data file structure if needed
    logger.info("Checking data file structure...")
    debug_data_file()
    logger.info("Data file structure verified.")

    # Check if Google integration is enabled
    use_google_drive = os.environ.get(
        'ENABLE_GOOGLE_INTEGRATION', 'false').lower() == 'true'

    if use_google_drive:
        logger.info("Google integration is enabled. Authentication will happen when needed through the web interface.")
    else:
        logger.info("Google integration is disabled.")

    # Create GraphSpace instance with paths from path_utils
    try:
        logger.info("Creating GraphSpace instance...")
        graphspace = GraphSpace(
            data_path=get_user_data_path(),
            config_path=get_config_path(),
            use_api=True, # Assuming API usage for LLMs if applicable
            api_key=os.environ.get("DEEPSEEK_API_KEY"), # Example API key
            use_google_drive=use_google_drive
        )
        logger.info("GraphSpace instance created successfully.")

        # Import web app and run it
        try:
            logger.info("Attempting to run the web application...")
            from graph_space_v2.api.app import run_app
            run_app(graphspace, host='127.0.0.1', debug=False) # Consider debug=False for production
        except ImportError as e:
            logger.critical(f"CRITICAL: Error loading web interface (run_app): {e}", exc_info=True)
            sys.exit(1)
        except Exception as e_run_app: # Catch any error from run_app itself
            logger.critical(f"CRITICAL: Web application failed to run: {e_run_app}", exc_info=True)
            sys.exit(1)


    except Exception as e:
        logger.critical(f"\nCRITICAL: Error initializing GraphSpace or running the application: {e}", exc_info=True)
        # traceback.print_exc() # Replaced by exc_info=True in logger
        return 1

    return 0 # Success


if __name__ == "__main__":
    logger.info(f"Starting GraphSpace application from: {os.path.abspath(__file__)}")
    sys.exit(main())
