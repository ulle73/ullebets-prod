from __future__ import annotations

from collections import Counter
from typing import Any

from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


def _model_pipeline(model: Any) -> Pipeline:
    pipeline = getattr(model, "pipeline", None)
    if isinstance(pipeline, Pipeline):
        return pipeline
    wrapped_model = getattr(model, "model", None)
    if wrapped_model is not None and wrapped_model is not model:
        return _model_pipeline(wrapped_model)
    global_model = getattr(model, "global_model", None)
    pipeline = getattr(global_model, "pipeline", None)
    if isinstance(pipeline, Pipeline):
        return pipeline
    raise ValueError(
        "model artifact does not expose a supported sklearn pipeline"
    )


def _extract_model_domain(
    model: Any,
) -> dict[str, tuple[str, ...]]:
    ensemble_models = getattr(model, "models", None)
    if isinstance(ensemble_models, tuple) and ensemble_models:
        component_domains = [
            _extract_model_domain(component)
            for component in ensemble_models
        ]
        fields = set(component_domains[0])
        if any(
            set(domain) != fields
            for domain in component_domains[1:]
        ):
            raise ValueError(
                "ensemble components have incompatible domain fields"
            )
        return {
            field: tuple(
                value
                for value in component_domains[0][field]
                if all(
                    value in domain[field]
                    for domain in component_domains[1:]
                )
            )
            for field in sorted(fields)
        }

    pipeline = _model_pipeline(model)
    features = pipeline.named_steps.get("features")
    if not isinstance(features, ColumnTransformer):
        raise ValueError(
            "model pipeline has no fitted ColumnTransformer named features"
        )

    for name, transformer, columns in features.transformers_:
        if name != "categorical":
            continue
        if not isinstance(transformer, Pipeline):
            raise ValueError(
                "categorical transformer is not a fitted sklearn pipeline"
            )
        encoder = transformer.named_steps.get("onehot")
        if not isinstance(encoder, OneHotEncoder):
            raise ValueError(
                "categorical transformer has no fitted OneHotEncoder"
            )
        return {
            str(column): tuple(str(value) for value in categories)
            for column, categories in zip(
                columns,
                encoder.categories_,
                strict=True,
            )
        }
    raise ValueError("model pipeline has no categorical transformer")


def extract_categorical_training_domain(
    artifact: Any,
) -> dict[str, tuple[str, ...]]:
    model = getattr(artifact, "model", artifact)
    return _extract_model_domain(model)


def score_feature_value(
    score: dict[str, Any],
    field: str,
) -> Any:
    value = score.get(field)
    if value is not None:
        return value
    feature_values = score.get("feature_values")
    if isinstance(feature_values, dict):
        return feature_values.get(field)
    return None


def audit_score_domain(
    scores: list[dict[str, Any]],
    training_domain: dict[str, tuple[str, ...]],
) -> tuple[list[dict[str, Any]], dict[str, object]]:
    allowed = {
        field: set(values)
        for field, values in training_domain.items()
    }
    in_domain: list[dict[str, Any]] = []
    missing = Counter()
    unknown = Counter()

    for score in scores:
        row_valid = True
        for field, supported in allowed.items():
            value = score_feature_value(score, field)
            if value is None:
                missing[field] += 1
                row_valid = False
                continue
            normalized = str(value)
            if normalized not in supported:
                unknown[(field, normalized)] += 1
                row_valid = False
        if row_valid:
            in_domain.append(score)

    unknown_by_field: dict[str, dict[str, int]] = {}
    for (field, value), count in sorted(unknown.items()):
        unknown_by_field.setdefault(field, {})[value] = count
    return in_domain, {
        "status": (
            "ok"
            if len(in_domain) == len(scores)
            else "out_of_domain_scores_excluded"
        ),
        "scores_total": len(scores),
        "scores_in_domain": len(in_domain),
        "scores_out_of_domain": len(scores) - len(in_domain),
        "missing_category_counts": dict(sorted(missing.items())),
        "unknown_category_counts": unknown_by_field,
        "supported_categories": {
            field: list(values)
            for field, values in sorted(training_domain.items())
        },
    }
