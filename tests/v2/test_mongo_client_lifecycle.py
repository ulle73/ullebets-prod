from types import SimpleNamespace

from ullebets_v2.storage import mongo


def test_build_mongo_client_registers_process_exit_cleanup(monkeypatch) -> None:
    client = SimpleNamespace(close=lambda: None)
    registered = []
    monkeypatch.setattr(mongo, "MongoClient", lambda *args, **kwargs: client)
    monkeypatch.setattr(mongo.atexit, "register", registered.append)

    result = mongo.build_mongo_client(SimpleNamespace(mongo_uri="mongodb://example"))

    assert result is client
    assert registered == [client.close]
