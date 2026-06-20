from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pymongo import MongoClient

from ullebets_v1.config import PipelineConfig


DEFAULT_COLLECTIONS = (
    "teamstats",
    "unibet-backtest",
    "analysis-snapshots",
    "result-loop-bets",
    "closing-line-tracking",
)


@dataclass
class MongoCollectionSnapshot:
    name: str
    documents: list[dict[str, Any]]


class HistoricalMongoSource:
    def __init__(self, uri: str, db_name: str) -> None:
        self._client = MongoClient(uri, serverSelectionTimeoutMS=15000)
        self._db = self._client[db_name]
        self.db_name = db_name

    @classmethod
    def from_config(cls, config: PipelineConfig) -> "HistoricalMongoSource":
        if not config.mongo_uri:
            raise RuntimeError("MONGODB_URI missing in environment or .env.local")
        return cls(config.mongo_uri, config.mongo_db)

    def ping(self) -> None:
        self._client.admin.command("ping")

    def fetch_documents(
        self,
        collection_name: str,
        projection: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        cursor = self._db[collection_name].find({}, projection=projection)
        if limit is not None:
            cursor = cursor.limit(limit)
        return [self._normalize_document(document) for document in cursor]

    def iter_documents(
        self,
        collection_name: str,
        projection: dict[str, Any] | None = None,
        limit: int | None = None,
        batch_size: int = 100,
    ):
        cursor = self._db[collection_name].find({}, projection=projection, batch_size=batch_size)
        if limit is not None:
            cursor = cursor.limit(limit)
        for document in cursor:
            yield self._normalize_document(document)

    def estimated_count(self, collection_name: str) -> int:
        return int(self._db[collection_name].estimated_document_count())

    def fetch_snapshots(
        self,
        collection_names: tuple[str, ...] = DEFAULT_COLLECTIONS,
    ) -> list[MongoCollectionSnapshot]:
        snapshots: list[MongoCollectionSnapshot] = []
        for name in collection_names:
            snapshots.append(
                MongoCollectionSnapshot(
                    name=name,
                    documents=self.fetch_documents(collection_name=name, projection={"_id": 0}),
                )
            )
        return snapshots

    def _normalize_document(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._normalize_document(subvalue) for key, subvalue in value.items()}
        if isinstance(value, list):
            return [self._normalize_document(item) for item in value]
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return value
