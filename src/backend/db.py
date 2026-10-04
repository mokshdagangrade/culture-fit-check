"""
MongoDB connection.

Reads MONGODB_URI from the environment (see .env.example). For local dev
you can run MongoDB locally (brew install mongodb-community, or Docker) or
use a free MongoDB Atlas cluster -- either works, just set MONGODB_URI.
"""

import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGODB_DB_NAME", "wavelength")

client = MongoClient(MONGODB_URI)
db = client[DB_NAME]

users_collection = db["users"]
feedback_collection = db["feedback"]
state_signals_collection = db["state_signals_daily"]
history_collection = db["history"]
history_collection.create_index([("user_id", 1), ("created_at", -1)])

# one account per email
users_collection.create_index("email", unique=True)
