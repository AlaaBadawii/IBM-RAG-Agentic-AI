import time
import traceback

from flask import Flask, jsonify, render_template, request

from model import build_chain

app = Flask(__name__)


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/recommend", methods=["POST"])
def recommend():
    data = request.get_json(silent=True) or {}

    mood = data.get("mood", "").strip()
    if not mood:
        return jsonify({"error": "Please provide a 'mood' field."}), 400

    model_key = data.get("model", "llama")

    try:
        start = time.time()
        result = build_chain(model_key).invoke({"mood": mood})
        duration_ms = round((time.time() - start) * 1000)
        return jsonify({
            "recommendations": result["recommendations"],
            "model": model_key,
            "duration_ms": duration_ms,
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
