import os
from pathlib import Path

from cryptography.fernet import Fernet

DB_FILE = Path(__file__).parent / "test.db"

os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{DB_FILE}")
os.environ.setdefault("FERNET_KEY", Fernet.generate_key().decode())
os.environ.setdefault("ENQUEUE_TASKS", "false")
os.environ.setdefault("COOKIE_SECURE", "false")
