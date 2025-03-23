from flask import Blueprint, request, jsonify, current_app
from graph_space_v2.api.middleware.validation import validate_json_request, validate_required_fields
import traceback

query_bp = Blueprint('query', __name__)


@query_bp.route('/query', methods=['POST'])
@validate_json_request
@validate_required_fields('query')
def query():
    try:
        print("POST /query - Processing natural language query")
        data = request.json
        user_query = data.get('query', '')

        graphspace = current_app.config['GRAPHSPACE']
        result = graphspace.query(user_query)

        return jsonify(result)
    except Exception as e:
        print(f"Error processing query: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@query_bp.route('/graph_data', methods=['GET'])
def graph_data():
    try:
        print("GET /graph_data - Retrieving knowledge graph visualization data")
        graphspace = current_app.config['GRAPHSPACE']

        # Force a graph rebuild to ensure all connections are up-to-date
        print("Rebuilding graph to ensure all connections are up-to-date")
        graphspace.knowledge_graph.build_graph()

        # Get nodes and edges data
        nodes = []
        node_types = {}
        for node_id, node_data in graphspace.knowledge_graph.graph.nodes(data=True):
            node_type = node_data.get('type', 'unknown')
            node_types[node_type] = node_types.get(node_type, 0) + 1

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
                label = node_data.get(
                    'title', f"Document {node_id.split('_')[1]}")
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

        # Print detailed diagnostic information
        print(f"Retrieved {len(nodes)} nodes and {len(edges)} edges")
        print(f"Node types: {node_types}")
        print(f"Edge types: {edge_types}")

        if len(edges) == 0:
            print(
                "WARNING: No edges found in the graph. This will result in disconnected nodes.")
            if len(nodes) > 0:
                print(
                    f"There are {len(nodes)} nodes but no connections between them.")
                # For debugging: Check if data has potential connections
                has_tags = any('tags' in graphspace.knowledge_graph.graph.nodes[node]
                               for node in graphspace.knowledge_graph.graph.nodes)
                print(f"Nodes have tags attribute: {has_tags}")

        return jsonify({
            'nodes': nodes,
            'edges': edges,
            'stats': {
                'node_count': len(nodes),
                'edge_count': len(edges),
                'node_types': node_types,
                'edge_types': edge_types
            }
        })
    except Exception as e:
        print(f"Error retrieving graph data: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@query_bp.route('/similar_nodes/<node_id>', methods=['GET'])
def similar_nodes(node_id):
    try:
        print(f"GET /similar_nodes/{node_id} - Finding similar nodes")
        graphspace = current_app.config['GRAPHSPACE']

        # Get number of results to return
        limit = request.args.get('limit', 5, type=int)

        # Find similar nodes based on embeddings
        similar_nodes = graphspace.embedding_service.find_similar(
            node_id,
            limit=limit
        )

        print(f"Found {len(similar_nodes)} similar nodes")
        return jsonify({
            'node_id': node_id,
            'similar_nodes': similar_nodes
        })
    except Exception as e:
        print(f"Error finding similar nodes: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@query_bp.route('/semantic_search', methods=['POST'])
@validate_json_request
@validate_required_fields('query')
def semantic_search():
    try:
        print("POST /semantic_search - Performing semantic search")
        data = request.json
        query_text = data.get('query', '')

        # Get optional parameters
        limit = data.get('limit', 5)
        node_types = data.get('node_types', None)  # Filter by node types

        graphspace = current_app.config['GRAPHSPACE']
        results = graphspace.embedding_service.search(
            query_text,
            limit=limit,
            filter_by_types=node_types
        )

        print(f"Found {len(results)} results for semantic search")
        return jsonify({
            'query': query_text,
            'results': results
        })
    except Exception as e:
        print(f"Error performing semantic search: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@query_bp.route('/search', methods=['GET'])
def search():
    try:
        print("GET /search - Performing keyword search")
        # Get query parameters
        q = request.args.get('q', '')
        if not q:
            return jsonify({'error': 'Search query is required'}), 400

        # Optional filters
        types = request.args.get('types', '').split(
            ',') if request.args.get('types') else None
        tags = request.args.get('tags', '').split(
            ',') if request.args.get('tags') else None
        limit = request.args.get('limit', 10, type=int)

        graphspace = current_app.config['GRAPHSPACE']

        # Perform keyword-based search
        results = graphspace.query_service.text_search(
            query=q,
            entity_types=types,
            max_results=limit
        )

        print(f"Found {len(results)} results for keyword search")
        return jsonify({
            'query': q,
            'count': len(results),
            'results': results
        })
    except Exception as e:
        print(f"Error performing keyword search: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@query_bp.route('/search', methods=['GET'])
def search_all():
    try:
        query = request.args.get('q', '')
        max_results = int(request.args.get('max_results', '5'))

        if not query:
            return jsonify({'error': 'Query parameter "q" is required'}), 400

        graphspace = current_app.config['GRAPHSPACE']
        results = graphspace.query_service.search_all_entities(
            query, max_results)

        return jsonify({
            'query': query,
            'results': results
        })
    except Exception as e:
        print(f"Error in search_all: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
