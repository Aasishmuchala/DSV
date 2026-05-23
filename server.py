"""DSV Flask server — serves the static frontend and runs the measurement pipeline."""
from __future__ import annotations

import os, uuid, pathlib, tempfile, shutil
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS

app = Flask(__name__, static_folder=".")
CORS(app)

# Ensure uploads dir exists
UPLOAD_DIR = pathlib.Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


def run_pipeline(front_path: str, side_path: str, out_dir: pathlib.Path):
    """Import and run DSV pipeline."""
    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    from dsv.pipeline import run
    result = run(front_path, side_path, out_dir=str(out_dir))
    return result


@app.route("/")
def index():
    return send_file("index.html")


@app.route("/api/pipeline", methods=["POST"])
def api_pipeline():
    """
    Accept front + side image files, run pipeline, return results + overlay paths.
    """
    if "front" not in request.files or "side" not in request.files:
        return jsonify({"error": "Missing 'front' or 'side' file"}), 400

    front_file = request.files["front"]
    side_file = request.files["side"]

    if not front_file.filename or not side_file.filename:
        return jsonify({"error": "Empty filename"}), 400

    # Save to temp dir unique per run
    run_id = uuid.uuid4().hex[:8]
    run_dir = UPLOAD_DIR / run_id
    run_dir.mkdir(exist_ok=True)

    front_path = run_dir / "front.jpg"
    side_path = run_dir / "side.jpg"
    front_file.save(str(front_path))
    side_file.save(str(side_path))

    try:
        result = run_pipeline(str(front_path), str(side_path), run_dir)

        response = result.to_dict()
        response["run_id"] = run_id

        # Overlay paths (relative, frontend resolves from same origin)
        if result.front_overlay_path:
            response["overlay_front"] = f"/uploads/{run_id}/overlay_front.png"
        if result.side_overlay_path:
            response["overlay_side"] = f"/uploads/{run_id}/overlay_side.png"

        return jsonify(response), 200

    except Exception as exc:
        # Clean up on failure
        shutil.rmtree(run_dir, ignore_errors=True)
        return jsonify({"error": str(exc)}), 500


@app.route("/uploads/<run_id>/<path:filename>")
def serve_upload(run_id, filename):
    return send_from_directory(str(UPLOAD_DIR / run_id), filename)


if __name__ == "__main__":
    print("DSV server running at http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)