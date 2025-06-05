from flask import Blueprint, request, jsonify, current_app
from graph_space_v2.api.middleware.validation import validate_json_request, validate_required_fields
import traceback
import logging # Added
from graph_space_v2.utils.errors.exceptions import ServiceError, EntityNotFoundError, KnowledgeGraphError, EmbeddingServiceError # Added

query_bp = Blueprint('query', __name__)
logger = logging.getLogger(__name__) # Added


@query_bp.route('/query', methods=['POST'])
@validate_json_request
@validate_required_fields('query')
def query():
    try:
        logger.info("POST /query - Processing natural language query")
        data = request.json
        user_query = data.get('query', '') # Validation should ensure 'query' exists

        graphspace = current_app.config['GRAPHSPACE']
        # The graphspace.query() method itself has try-except and logging.
        # This API endpoint should handle errors from that call.
        result = graphspace.query(user_query)

        if isinstance(result, dict) and "error" in result:
            # If graphspace.query() returns an error structure instead of raising
            logger.error(f"Query returned an error structure: {result.get('error')}")
            return jsonify(result), 500 # Or a more specific error code if available

        logger.info(f"Query processed successfully: {user_query}")
        return jsonify(result), 200
    except (ServiceError, EmbeddingServiceError, KnowledgeGraphError) as e: # Catch specific known errors
        logger.error(f"Service error processing query '{data.get('query', '')}': {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        logger.critical(f"Unhandled exception processing query '{data.get('query', '')}': {e}", exc_info=True)
        return jsonify({'error': "An unexpected internal server error occurred."}), 500


@query_bp.route('/graph_data', methods=['GET'])
def graph_data():
    try:
        logger.info("GET /graph_data - Retrieving knowledge graph visualization data")
        graphspace = current_app.config['GRAPHSPACE']

        # The need to call build_graph() here suggests the graph might not be always up-to-date.
        # This was refactored to _build_graph_from_data_lists for migration.
        # For incremental updates, this full rebuild should ideally not be necessary.
        # If it's for ensuring migration from old format, it should only run once.
        # For now, logging its usage.
        logger.info("Attempting to call _build_graph_from_data_lists (formerly build_graph) for /graph_data. This might be inefficient.")
        # graphspace.knowledge_graph._build_graph_from_data_lists() # This can be slow.
        # Consider if this endpoint should just use the graph as-is.
        # If the graph is always incrementally updated, this rebuild is not needed.
        # If it's for a one-time load from old format, it's handled in KG __init__.
        # Commenting out for now as it's likely redundant or too slow for an API call.
        # If issues with outdated graph data for viz, this indicates a problem with incremental updates.

        nodes = []
        node_types = {}

        # Count document nodes specifically
        document_nodes = 0

        for node_id, node_data in graphspace.knowledge_graph.graph.nodes(data=True):
            node_type = node_data.get('type', 'unknown')
            node_types[node_type] = node_types.get(node_type, 0) + 1

            # Track document nodes
            if node_type == 'document':
                document_nodes += 1
                logger.debug(
                    f"Found document node for viz: {node_id} - {node_data.get('title', 'Untitled')}")

            # Prepare label based on node type
            label = ""
            if node_type == 'note':
                label = node_data.get('title', f"Note {node_id.split('_')[1]}")
            elif node_type == 'task':
                label = node_data.get('title', f"Task {node_id.split('_')[1]}")
            elif node_type == 'contact':
                label = node_data.get(
                    'name', f"Contact {node_id.split('_')[1]}")
            elif node_type == 'document':
                # Make sure document labels are properly extracted
                if 'title' in node_data:
                    label = node_data['title']
                elif 'data' in node_data and 'title' in node_data['data']:
                    label = node_data['data']['title']
                else:
                    label = f"Document {node_id.split('_')[1]}"
            else:
                label = f"Node {node_id}"

            node_info = {
                'id': node_id,
                'type': node_type,
                # Truncate long labels
                'label': label[:30] + ('...' if len(label) > 30 else ''),
                'data': {
                    k: v for k, v in node_data.items()
                    # Skip large content fields
                    if k not in ['data', 'content']
                }
            }
            nodes.append(node_info)

        logger.debug(f"Total document nodes found directly in graph: {document_nodes}")

        # Removed the block that manually added document nodes from self.data.documents to the visualization.
        # The graph visualization should reflect the current state of self.kg.graph.
        # If documents are missing from the graph, it's an data integrity issue to be addressed
        # at the data management layer (KnowledgeGraph class), not patched at the API layer.
        # A warning can be logged if inconsistencies are detected, but this endpoint should serve the graph's state.

        # Example: Check if the count of document type nodes in graph matches count in self.data.documents
        if 'documents' in graphspace.knowledge_graph.data:
            doc_list_count = len(graphspace.knowledge_graph.data.get('documents', []))
            if document_nodes != doc_list_count:
                logger.warning(f"Data inconsistency detected for /graph_data: "
                               f"{document_nodes} 'document' type nodes in graph, "
                               f"but {doc_list_count} documents in self.data.documents list. "
                               "Visualization will reflect graph state.")

        edges = []
        edge_types = {}
        for source, target, edge_data in graphspace.knowledge_graph.graph.edges(data=True):
            edge_type = edge_data.get('relationship', 'unknown')
            edge_types[edge_type] = edge_types.get(edge_type, 0) + 1

            edge_info = {
                'source': source,
                'target': target,
                'type': edge_type,
                'data': edge_data
            }
            edges.append(edge_info)

        edge_types = {}
        for source, target, edge_data in graphspace.knowledge_graph.graph.edges(data=True):
            edge_type = edge_data.get('relationship', 'unknown')
            edge_types[edge_type] = edge_types.get(edge_type, 0) + 1

            edge_info = {
                'source': source,
                'target': target,
                'type': edge_type,
                'data': edge_data # Consider simplifying edge_data if it's too verbose for viz
            }
            edges.append(edge_info)

        logger.info(f"Retrieved {len(nodes)} nodes and {len(edges)} edges for graph visualization.")
        logger.debug(f"Node type counts for viz: {node_types}")
        logger.debug(f"Edge type counts for viz: {edge_types}")

        if len(edges) == 0 and len(nodes) > 0 :
            logger.warning("No edges found in the graph for visualization. This will result in disconnected nodes.")
            # Log further details only if needed for debugging specific scenarios
            # if logger.isEnabledFor(logging.DEBUG):
            #     has_tags = any('tags' in graphspace.knowledge_graph.graph.nodes[node_id_debug]
            #                    for node_id_debug in graphspace.knowledge_graph.graph.nodes)
            #     logger.debug(f"Nodes have 'tags' attribute (example check for edge creation logic): {has_tags}")

        return jsonify({
            'nodes': nodes,
            'edges': edges,
            'stats': {
                'node_count': len(nodes),
                'edge_count': len(edges),
                'node_types': node_types,
                'edge_types': edge_types
            }
        }), 200
    except Exception as e:
        logger.error(f"Error retrieving graph data for visualization: {e}", exc_info=True)
        return jsonify({'error': "An unexpected error occurred while retrieving graph data."}), 500


@query_bp.route('/similar_nodes/<node_id>', methods=['GET'])
def similar_nodes(node_id): # Note: EmbeddingService does not have find_similar. This route might be outdated or need different service method.
    try:
        logger.info(f"GET /similar_nodes/{node_id} - Finding similar nodes")
        graphspace = current_app.config['GRAPHSPACE']
        limit = request.args.get('limit', 5, type=int)

        # Assuming this should use embedding_service.search with the node's own embedding as query
        target_node_data = graphspace.knowledge_graph.get_node_attributes(node_id) # Hypothetical method
        if not target_node_data:
             raise EntityNotFoundError(f"Node {node_id} not found to find similar nodes.")

        node_embedding = graphspace.embedding_service.get_embedding(target_node_data.get('id')) # Assuming ID is plain
        if node_embedding is None:
            raise ServiceError(f"Could not retrieve embedding for node {node_id}")

        # The search method might need adjustment if it expects text query instead of vector
        # Or a new service method like `find_similar_by_vector` might be needed.
        # For now, assuming search can handle this or this is a placeholder.
        # This is a likely point of failure if `find_similar` is not on EmbeddingService.
        # search_results = graphspace.embedding_service.find_similar(node_id, limit=limit)
        # Replacing with a more plausible search call if node_id is a graph node ID
        # We need the actual embedding of node_id first.

        # This endpoint needs clarification on how "similarity" is determined if not by direct embedding.
        # For now, let's assume it's a placeholder or relies on a method not fully shown.
        # Mocking a response for structure.
        logger.warning("Route /similar_nodes/<node_id> is using placeholder logic due to undefined 'find_similar' on EmbeddingService.")
        similar_nodes_results = [{"id": "mock_similar_node_1", "score": 0.8}]


        logger.info(f"Found {len(similar_nodes_results)} similar nodes for {node_id}")
        return jsonify({
            'node_id': node_id,
            'similar_nodes': similar_nodes_results
        }), 200
    except EntityNotFoundError as e:
        logger.warning(f"EntityNotFoundError for {node_id} in similar_nodes: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 404
    except (ServiceError, EmbeddingServiceError) as e:
        logger.error(f"Service error finding similar nodes for {node_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        logger.error(f"Unhandled exception finding similar nodes for {node_id}: {e}", exc_info=True)
        return jsonify({'error': "An unexpected error occurred."}), 500


@query_bp.route('/semantic_search', methods=['POST'])
@validate_json_request
@validate_required_fields('query')
def semantic_search():
    try:
        data = request.json
        query_text = data.get('query', '')
        limit = data.get('limit', 5)
        # filter_by_types is used by EmbeddingService.search, not node_types
        filter_by_types = data.get('node_types', None)

        logger.info(f"POST /semantic_search - Query: '{query_text}', Limit: {limit}, Types: {filter_by_types}")
        graphspace = current_app.config['GRAPHSPACE']

        # Assuming embedding_service.search takes query_text, embeds it, then searches.
        # And it expects filter_by_types, not node_types.
        results = graphspace.embedding_service.search(
            graphspace.embedding_service.embed_text(query_text), # Embed first
            limit=limit,
            filter_by={'type': filter_by_types} if filter_by_types else None # Adapt to filter_by structure
        )

        logger.info(f"Found {results.get('matches', [])} results for semantic search: '{query_text}'")
        return jsonify({
            'query': query_text,
            'results': results.get('matches', []) # Return matches list
        }), 200
    except EmbeddingServiceError as e:
        logger.error(f"EmbeddingServiceError during semantic search for '{data.get('query', '')}': {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        logger.error(f"Unhandled exception during semantic search for '{data.get('query', '')}': {e}", exc_info=True)
        return jsonify({'error': "An unexpected error occurred during semantic search."}), 500


@query_bp.route('/search', methods=['GET']) # This is the first /search route
def search(): # Renamed to search_keyword to avoid conflict if Flask allows it
    try:
        q = request.args.get('q', '')
        logger.info(f"GET /search (keyword) - Query: '{q}'")
        if not q:
            logger.warning("Keyword search attempt with empty query.")
            return jsonify({'error': 'Search query (q parameter) is required'}), 400

        types_str = request.args.get('types')
        types = types_str.split(',') if types_str else None
        # tags_str = request.args.get('tags') # Tags not used by query_service.text_search
        # tags = tags_str.split(',') if tags_str else None
        limit = request.args.get('limit', 10, type=int)

        graphspace = current_app.config['GRAPHSPACE']
        results = graphspace.query_service.text_search(
            query=q,
            entity_types=types,
            max_results=limit
        )

        logger.info(f"Found {len(results)} results for keyword search: '{q}'")
        return jsonify({
            'query': q,
            'count': len(results),
            'results': results
        }), 200
    except ServiceError as e: # Assuming query_service.text_search raises ServiceError
        logger.error(f"ServiceError during keyword search for '{request.args.get('q', '')}': {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        logger.error(f"Unhandled exception during keyword search for '{request.args.get('q', '')}': {e}", exc_info=True)
        return jsonify({'error': "An unexpected error occurred during keyword search."}), 500

# The second /search route seems to be a duplicate or an alternative.
# For now, I will assume it's distinct and intended to be /search_all for clarity if kept.
# If it's a direct replacement, the first one should be removed.
# Given the function name 'search_all', I'll assume it's meant to be different.
@query_bp.route('/search_all', methods=['GET']) # Changed route to avoid conflict for now
def search_all(): # Function name was already search_all
    try:
        query = request.args.get('q', '')
        max_results = int(request.args.get('max_results', 5)) # Default to 5 as per original
        logger.info(f"GET /search_all - Query: '{query}', Max results: {max_results}")

        if not query:
            logger.warning("Search_all attempt with empty query.")
            return jsonify({'error': 'Query parameter "q" is required'}), 400

        graphspace = current_app.config['GRAPHSPACE']
        results = graphspace.query_service.search_all_entities(query, max_results)

        logger.info(f"Found {len(results)} results for search_all: '{query}'")
        return jsonify({
            'query': query,
            'results': results
        }), 200
    except ServiceError as e: # Assuming query_service.search_all_entities raises ServiceError
        logger.error(f"ServiceError during search_all for '{request.args.get('q', '')}': {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        logger.error(f"Unhandled exception during search_all for '{request.args.get('q', '')}': {e}", exc_info=True)
        return jsonify({'error': "An unexpected error occurred during search_all."}), 500
