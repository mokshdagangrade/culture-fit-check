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

# one account per email
users_collection.create_index("email", unique=True)
