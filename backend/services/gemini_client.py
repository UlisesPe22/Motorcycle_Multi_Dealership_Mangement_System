"""
gemini_client.py — Initialises the Gemini API client.

All pipeline services import get_model() from here.
This keeps the API key loading and model configuration in one place.

Usage:
    from services.gemini_client import get_model
    model = get_model()
    response = model.generate_content(...)
"""

import os
from dotenv import load_dotenv
import google.generativeai as genai
from config import MODEL_NAME

# .env is one level above backend/
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))


def get_model():
    """
    Returns a configured Gemini 1.5 Flash model instance.
    Called fresh each time so config changes in .env are picked up
    without restarting the server.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY not found. "
            "Make sure it is set in your .env file at the project root."
        )

    genai.configure(api_key=api_key)

    model = genai.GenerativeModel(
        model_name= MODEL_NAME,
        generation_config={
            # Return pure JSON — no markdown, no explanation, no preamble.
            # Our Pydantic validators will parse the raw string directly.
            "response_mime_type": "application/json",
            "temperature": 0.1,   # low temperature = more deterministic output
                                  # important for structured data extraction
        }
    )
    return model