import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()

BOT_TOKEN = os.getenv("MESAI_BOT_TOKEN") or "8804393580:AAGFphSEbL2PNSYtxF8NecEDUsQmzV1nDu0"
DB_PATH = BASE_DIR / "mesai.db"

# Çalışanlar
WORKERS = ["erkan", "mirza"]

# Firmalar (Sadece isim ve takma adlar, maaş/bütçe yok)
DEFAULT_COMPANIES = {
    "medobet": {
        "display_name": "Medobet",
        "aliases": ["medobet", "medo"],
        "cutoff_day": 15
    },
    "mito": {
        "display_name": "Mito",
        "aliases": ["mito", "mitobet"],
        "cutoff_day": 20
    },
    "panter": {
        "display_name": "Panter",
        "aliases": ["panter"],
        "cutoff_day": 1
    }
}
