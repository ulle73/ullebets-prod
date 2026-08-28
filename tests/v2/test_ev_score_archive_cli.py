from scripts.forward_v2.evaluate_ev_score_archive import _load_scores_for_models


class Cursor(list):
    pass


class Collection:
    def __init__(self) -> None:
        self.queries = []

    def find(self, query, projection=None):
        self.queries.append((query, projection))
        return Cursor([{"model_id": query["model_id"]}])


def test_score_archive_loads_each_model_with_an_indexable_equality_query() -> None:
    collection = Collection()

    rows = _load_scores_for_models(collection, ["v3", "v4"])

    assert [row["model_id"] for row in rows] == ["v3", "v4"]
    assert [query for query, _projection in collection.queries] == [
        {"model_id": "v3"},
        {"model_id": "v4"},
    ]
