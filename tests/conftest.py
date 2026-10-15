import os
import sys

# Set before any project import so db.py / load_dotenv never point tests at a real database.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault("GROQ_API_KEY", "test-key")
os.environ["AUTH_SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-hs256"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # lets tests share helpers
