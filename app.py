import logging
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from google import genai
from google.genai import types

import chatbot_config as config

load_dotenv()
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("GEMINI_API_KEY is missing. Add it to the .env file.")

client = genai.Client(api_key=api_key)

generation_config = types.GenerateContentConfig(
    system_instruction=config.SYSTEM_PROMPT,
    temperature=config.TEMPERATURE,
    max_output_tokens=config.MAX_OUTPUT_TOKENS,
)


def build_contents(history, message):
    """Convert the chat history sent by the browser into Gemini contents."""
    roles = {"user": "user", "assistant": "model"}
    turns = []

    for item in history[-config.MAX_HISTORY_MESSAGES:]:
        role = roles.get(item.get("role"))
        text = str(item.get("text", "")).strip()
        if role and text:
            turns.append((role, text))

    # Gemini expects a conversation to begin with a user turn.
    while turns and turns[0][0] != "user":
        turns.pop(0)

    turns.append(("user", message))

    return [
        types.Content(role=role, parts=[types.Part.from_text(text=text)])
        for role, text in turns
    ]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()
    history = data.get("history", [])

    if not message:
        return jsonify({"error": "Please enter a question."}), 400
    if len(message) > config.MAX_MESSAGE_LENGTH:
        return jsonify({
            "error": f"Please keep your question under {config.MAX_MESSAGE_LENGTH} characters."
        }), 400
    if not isinstance(history, list):
        history = []

    try:
        response = client.models.generate_content(
            model=config.MODEL_NAME,
            contents=build_contents(history, message),
            config=generation_config,
        )
        reply = (response.text or "").strip() or config.EMPTY_RESPONSE_MESSAGE
        return jsonify({"reply": reply})
    except Exception:
        app.logger.exception("Gemini request failed")
        return jsonify({"error": config.SERVER_ERROR_MESSAGE}), 500


if __name__ == "__main__":
    app.run(debug=True)
