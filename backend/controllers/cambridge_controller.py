
from flask import jsonify, request
from backend.services.cambridge_service import get_cambridge_pronunciation

def fetch_pronunciation():
    word = request.args.get('word', '').strip()
    if not word:
        return jsonify({"error": "Missing 'word' parameter"}), 400

    result = get_cambridge_pronunciation(word)
    if "error" in result:
        return jsonify(result), 500

    return jsonify(result)
