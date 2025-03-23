from flask import Blueprint, request, jsonify, current_app
from graph_space_v2.api.middleware.auth import token_required
from graph_space_v2.api.middleware.validation import validate_json_request, validate_required_fields

query_bp = Blueprint('query', __name__)


@query_bp.route('/query', methods=['POST'])
@token_required
@validate_json_request
@validate_required_fields('query')
def query():
    try:
        data = request.json
        user_query = data.get('query', '')

        graphspace = current_app.config['GRAPHSPACE']
        result = graphspace.ai.rag.query(user_query)

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@query_bp.route('/graph_data', methods=['GET'])
@token_required
def graph_data():
    try:
        graphspace = current_app.config['GRAPHSPACE']

        # Get nodes and edges data
        nodes = []
        for node_id, node_data in graphspace.core.graph.knowledge_graph.graph.nodes(data=True):
            node_type = node_data.get('type', 'unknown')
            node_info = {
                'id': node_id,
                'type': node_type,
                'label': node_data.get('title', node_data.get('name', f"Node {node_id}")),
                'data': node_data
            }
            nodes.append(node_info)

        edges = []
        for source, target, edge_data in graphspace.core.graph.knowledge_graph.graph.edges(data=True):
            edge_info = {
                'source': source,
                'target': target,
                'type': edge_data.get('relationship_type', 'unknown'),
                'data': edge_data
            }
            edges.append(edge_info)

        return jsonify({
            'nodes': nodes,
            'edges': edges
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@query_bp.route('/similar_nodes/<node_id>', methods=['GET'])
@token_required
def similar_nodes(node_id):
    try:
        graphspace = current_app.config['GRAPHSPACE']

        # Get number of results to return
        limit = request.args.get('limit', 5, type=int)

        # Find similar nodes based on embeddings
        similar_nodes = graphspace.ai.embedding.vector_store.find_similar(
            node_id,
            limit=limit
        )

        return jsonify({
            'node_id': node_id,
            'similar_nodes': similar_nodes
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@query_bp.route('/semantic_search', methods=['POST'])
@token_required
@validate_json_request
@validate_required_fields('query')
def semantic_search():
    try:
        data = request.json
        query_text = data.get('query', '')

        # Get optional parameters
        limit = data.get('limit', 5)
        node_types = data.get('node_types', None)  # Filter by node types

        graphspace = current_app.config['GRAPHSPACE']
        results = graphspace.ai.embedding.vector_store.search(
            query_text,
            limit=limit,
            filter_by_types=node_types
        )

        return jsonify({
            'query': query_text,
            'results': results
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@query_bp.route('/search', methods=['GET'])
@token_required
def search():
    try:
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
        results = graphspace.core.services.query_service.search(
            query=q,
            node_types=types,
            tags=tags,
            limit=limit
        )

        return jsonify({
            'query': q,
            'count': len(results),
            'results': results
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
