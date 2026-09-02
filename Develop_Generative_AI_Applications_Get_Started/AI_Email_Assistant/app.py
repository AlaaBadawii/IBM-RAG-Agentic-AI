import time

from flask import Flask, jsonify, render_template, request

from config import MODELS
from services.ai_service import generate_email

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html", models=MODELS)


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(silent=True) or {}
    topic = (data.get("topic") or "").strip()
    tone = (data.get("tone") or "").strip()
    email_type = (data.get("email_type") or "").strip()
    model = (data.get("model") or "").strip()

    if not topic or not tone or not email_type or not model:
        return jsonify({"error": "Missing required fields: topic, tone, email_type, model"}), 400

    if model not in MODELS:
        return jsonify({"error": f"Unknown model '{model}'. Allowed: {', '.join(MODELS)}"}), 400

    start = time.time()
    try:
        result = generate_email(model_name=model, email_type=email_type, tone=tone, topic=topic)
    except Exception as exc:  # pragma: no cover - network/API failures
        app.logger.exception("Generation failed")
        return jsonify({"error": "Email generation failed", "detail": str(exc)}), 500

    duration_ms = round((time.time() - start) * 1000, 1)
    return jsonify({**result, "duration_ms": duration_ms})


if __name__ == "__main__":
    app.run(debug=True)