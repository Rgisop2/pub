import os
import json

# Load configuration from file if it exists, otherwise use environment variables
CONFIG_FILE = os.environ.get("CONFIG_FILE", "config.json")
BOT_CONFIG = {}

if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, 'r') as f:
            BOT_CONFIG = json.load(f)
    except Exception as e:
        print(f"Error loading config file: {e}")

# Common configuration for all bots
API_ID = int(BOT_CONFIG.get("api_id", os.environ.get("API_ID", "")))
API_HASH = BOT_CONFIG.get("api_hash", os.environ.get("API_HASH", ""))
DATABASE_URL = BOT_CONFIG.get("database_url", os.environ.get("DB_URI", ""))

# Make Bot Admin In Log Channel With Full Rights
LOG_CHANNEL = int(BOT_CONFIG.get("log_channel", os.environ.get("LOG_CHANNEL", "0")))

# Handle ADMINS as a list
if "admins" in BOT_CONFIG:
    ADMINS = BOT_CONFIG["admins"] if isinstance(BOT_CONFIG["admins"], list) else [BOT_CONFIG["admins"]]
else:
    admin_env = os.environ.get("ADMINS", "0")
    ADMINS = [int(admin_env)]

# Bot configurations
BOTS = []
if "bots" in BOT_CONFIG:
    BOTS = BOT_CONFIG["bots"]
else:
    # Fallback to single bot configuration from environment variables
    BOTS = [{
        "token": os.environ.get("BOT_TOKEN", ""),
        "db_name": os.environ.get("DB_NAME", "vjlinkchangerbot"),
        "version": "v1"  # Default version identifier
    }]

# For backward compatibility
BOT_TOKEN = BOTS[0]["token"] if BOTS else ""
DB_URI = DATABASE_URL
DB_NAME = BOTS[0]["db_name"] if BOTS else "vjlinkchangerbot"
