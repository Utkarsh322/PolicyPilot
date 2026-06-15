import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Project root path
ROOT_DIR = Path(__file__).resolve().parent.parent

# Centralized Settings
DATA_DIR = ROOT_DIR / os.getenv("DATA_DIR", "data")
POLICIES_DIR = ROOT_DIR / os.getenv("POLICIES_DIR", "data/policies")
DB_DIR = ROOT_DIR / os.getenv("DB_DIR", "data/chromadb")
EVAL_QA_PATH = ROOT_DIR / os.getenv("EVAL_QA_PATH", "data/eval_qa.json")

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
POLICIES_DIR.mkdir(parents=True, exist_ok=True)
DB_DIR.mkdir(parents=True, exist_ok=True)

# Chunking & Indexing Config
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 500))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 50))

# Retrieval Config
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", 0.35))
HYBRID_SEMANTIC_WEIGHT = float(os.getenv("HYBRID_SEMANTIC_WEIGHT", 0.7))
HYBRID_KEYWORD_WEIGHT = float(os.getenv("HYBRID_KEYWORD_WEIGHT", 0.3))

# LLM Config
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock").lower()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# SQLite Compatibility check
try:
    import sqlite3
    # Check version if needed, or print warning if sqlite is too old
    # Chroma requires >= 3.35.0. If we run into issues, we can import pysqlite3 as sqlite3
    if sqlite3.sqlite_version_info < (3, 35, 0):
        try:
            import sys
            __import__('pysqlite3')
            sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
            print("Patched sqlite3 using pysqlite3 due to older SQLite version.")
        except ImportError:
            print(f"WARNING: SQLite version is {sqlite3.sqlite_version}, ChromaDB requires >= 3.35.0. "
                  f"Please install pysqlite3-binary if database initialization fails.")
except ImportError:
    pass
