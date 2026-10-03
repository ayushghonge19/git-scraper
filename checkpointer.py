"""MongoDB Checkpointer configuration for GitHub Memory Assistant.

Implements persistent LangGraph state using the official MongoDBSaver.
Supports:
1. Real MongoDB instances (Local `mongodb://localhost:27017` or MongoDB Atlas `mongodb+srv://...`).
2. Transparent local file-backed persistence fallback when a MongoDB daemon is not running locally.
"""

import atexit
import os
import pickle
from typing import Tuple
from dotenv import load_dotenv
import pymongo
from pymongo import MongoClient
from langgraph.checkpoint.mongodb import MongoDBSaver

load_dotenv()

LOCAL_CACHE_FILE = ".mongo_local_store.pkl"


def _patch_mongomock_if_needed():
    """Patches mongomock's BulkOperationBuilder for compatibility with MongoDBSaver."""
    try:
        import mongomock

        orig_add_update = mongomock.collection.BulkOperationBuilder.add_update

        def patched_add_update(self, selector, update, *args, **kwargs):
            kwargs.pop("sort", None)
            return orig_add_update(self, selector, update, *args, **kwargs)

        mongomock.collection.BulkOperationBuilder.add_update = patched_add_update
    except ImportError:
        pass


def _get_persisted_mongomock(cache_file: str = LOCAL_CACHE_FILE):
    """Loads a mongomock client restored from local disk cache for restart simulation."""
    import mongomock

    _patch_mongomock_if_needed()
    client = mongomock.MongoClient()

    if os.path.exists(cache_file):
        try:
            with open(cache_file, "rb") as f:
                saved_data = pickle.load(f)
                for db_name, collections in saved_data.items():
                    for coll_name, docs in collections.items():
                        if docs:
                            client[db_name][coll_name].insert_many(
                                [doc.copy() for doc in docs]
                            )
        except Exception:
            pass

    def _persist():
        try:
            data = {}
            for db_name in client.list_database_names():
                db = client[db_name]
                data[db_name] = {}
                for coll_name in db.list_collection_names():
                    data[db_name][coll_name] = list(db[coll_name].find())
            with open(cache_file, "wb") as f:
                pickle.dump(data, f)
        except Exception:
            pass

    atexit.register(_persist)
    return client, _persist


def get_checkpointer() -> Tuple[MongoDBSaver, str]:
    """Initializes and returns the official LangGraph MongoDBSaver.

    Returns:
        tuple[MongoDBSaver, str]: The checkpointer instance and a description of the backend.
    """
    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGODB_DB_NAME", "github_memory_assistant")
    force_mock = os.getenv("USE_MOCK_MONGO", "false").lower() in ("true", "1", "yes")

    if not force_mock:
        try:
            # Check connection with a 1.5 second timeout
            real_client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=1500)
            real_client.admin.command("ping")
            saver = MongoDBSaver(real_client, db_name=db_name)
            return saver, f"Connected to MongoDB ({mongodb_uri})"
        except Exception:
            pass

    # Seamless fallback to disk-persisted mock for local testing without requiring mongod daemon
    mock_client, save_func = _get_persisted_mongomock(LOCAL_CACHE_FILE)
    saver = MongoDBSaver(mock_client, db_name=db_name)
    saver._save_func = save_func
    return saver, "Using local persistent storage (.mongo_local_store.pkl - MongoDB compatible)"
