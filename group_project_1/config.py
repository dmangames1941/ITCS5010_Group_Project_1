import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is required. Add it to your .env file.")

BASE_DIR = Path(__file__).resolve().parent
KNOWN_MODELS_DIR = BASE_DIR / "known_models"
TEMPLATES_DIR = BASE_DIR / "templates"