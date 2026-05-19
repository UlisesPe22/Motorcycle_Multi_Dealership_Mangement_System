"""
gemini_client.py — Initialises the Gemini API client.

All pipeline services import get_model() from here.
This keeps the API key loading in one place.

Usage:
    from services.gemini_client import get_model
    client = get_model()
    # client is passed to call_gemini_image / call_gemini_pdf in main_pipeline
"""

import os
from dotenv import load_dotenv
from google import genai

# .env is one level above backend/
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))


def get_model():
    """
    Returns a configured Gemini client instance.
    Called fresh each time so config changes in .env are picked up
    without restarting the server.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY not found. "
            "Make sure it is set in your .env file at the project root."
        )
    client = genai.Client(api_key=api_key)
    return client
