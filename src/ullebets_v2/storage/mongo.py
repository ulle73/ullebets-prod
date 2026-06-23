from __future__ import annotations

from pymongo import MongoClient
from pymongo.database import Database

from ullebets_v2.config import V2Config
from ullebets_v2.safety import ensure_v2_database


def build_mongo_client(config: V2Config) -> MongoClient:
    if not config.mongo_uri:
        raise RuntimeError("MONGODB_URI is required for MongoDB operations.")
    return MongoClient(config.mongo_uri, tz_aware=True)


def get_database(config: V2Config) -> Database:
    ensure_v2_database(config)
    client = build_mongo_client(config)
    return client[config.mongo_db]


def get_named_database(config: V2Config, db_name: str) -> Database:
    client = build_mongo_client(config)
    return client[db_name]


def ping_database(config: V2Config) -> dict:
    database = get_database(config)
    return database.command("ping")
