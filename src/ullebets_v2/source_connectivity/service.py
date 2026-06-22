from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
import json
import os
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ullebets_v2.jobs.job_runs import build_job_run_finished_update, build_job_run_started_doc
from ullebets_v2.parity.reports import build_audit_report_row, build_health_report_row


Transport = Callable[[str, dict[str, str], int], Any]

DEFAULT_BASE_URLS = {
    "sportapi7": "https://sportapi7.p.rapidapi.com",
    "sofascore": "https://sofascore.p.rapidapi.com",
    "sportApiRealTime": "https://sport-api-real-time.p.rapidapi.com",
    "sofascoreSportApi": "https://sofascore-sport-api.p.rapidapi.com",
    "sofasport": "https://sofasport.p.rapidapi.com",
}


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def yesterday_ymd_utc() -> str:
    return (utc_now() - timedelta(days=1)).date().isoformat()


def trim_slash(value: str) -> str:
    return str(value or "").rstrip("/")


def join_url(base: str, path: str, query: dict[str, Any] | None = None) -> str:
    root = f"{trim_slash(base)}/{str(path).lstrip('/')}"
    if not query:
        return root
    filtered = {key: value for key, value in query.items() if value not in (None, "", [])}
    return f"{root}?{urlencode(filtered)}" if filtered else root


def unique(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = str(value or "").strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        output.append(cleaned)
    return output


def load_rapidapi_keys(env: dict[str, str], max_keys: int = 10) -> list[str]:
    raw = [
        env.get("RAPIDAPI_KEY", ""),
        *str(env.get("RAPIDAPI_KEYS", "")).split(","),
        *(env.get(f"RAPIDAPI_KEY_{index}", "") for index in range(1, 21)),
    ]
    keys = unique([str(value) for value in raw])
    return keys[:max_keys] if max_keys > 0 else keys


def key_label(value: str | None) -> str | None:
    return f"...{str(value)[-4:]}" if value else None


def _safe_json_preview(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, list):
        return {"type": "array", "count": len(value)}
    if isinstance(value, dict):
        keys = list(value.keys())[:12]
        counts = {key: len(value[key]) for key in keys if isinstance(value.get(key), list)}
        return {"type": "object", "keys": keys, "counts": counts}
    return {"type": type(value).__name__, "value": str(value)[:160]}


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, list):
        return len(value) == 0
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, dict):
        return len(value) == 0
    return False


def _extract_scheduled(data: Any) -> Any:
    if isinstance(data, dict):
        for path in (("events",), ("data", "events"), ("data", "matches"), ("matches",), ("data",)):
            value: Any = data
            valid = True
            for key in path:
                if not isinstance(value, dict) or key not in value:
                    valid = False
                    break
                value = value[key]
            if valid and isinstance(value, list):
                return value
    return []


def _extract_stats(data: Any) -> Any:
    if isinstance(data, dict):
        return data.get("statistics") or data.get("data") or data
    return data


def fetch_json(
    url: str,
    *,
    headers: dict[str, str],
    timeout_seconds: int = 15,
    transport: Transport | None = None,
) -> dict[str, Any]:
    if transport is not None:
        response = transport(url, headers, timeout_seconds)
        return {
            "ok": int(getattr(response, "status", 0)) < 400,
            "status": getattr(response, "status", 0),
            "status_text": getattr(response, "status_text", ""),
            "data": getattr(response, "data", None),
        }
    request = Request(url, headers={"accept": "application/json, text/plain, */*", "user-agent": "ullebets-v2-connectivity/1.0", **headers})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = response.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(payload) if payload else None
            except json.JSONDecodeError:
                data = payload[:500] if payload else None
            return {
                "ok": int(getattr(response, "status", 200)) < 400,
                "status": int(getattr(response, "status", 200)),
                "status_text": getattr(response, "reason", ""),
                "data": data,
            }
    except HTTPError as exc:
        return {"ok": False, "status": exc.code, "status_text": str(exc.reason), "data": None}
    except URLError as exc:
        return {"ok": False, "status": 0, "status_text": str(exc.reason), "data": None}


@dataclass(frozen=True)
class EndpointCheck:
    name: str
    url: str
    query: dict[str, Any] | None
    kind: str


def default_endpoint_checks(*, base_urls: dict[str, str], test_date: str, category_id: str, match_ids: list[str], public_base_url: str) -> list[EndpointCheck]:
    scheduled = [
        EndpointCheck("sportapi7-scheduled-global", join_url(base_urls["sportapi7"], f"/api/v1/sport/football/scheduled-events/{test_date}"), None, "scheduled"),
        EndpointCheck("sofascore-api-dojo-tournaments", join_url(base_urls["sofascore"], "/tournaments/get-scheduled-events", {"categoryId": category_id, "date": test_date}), None, "scheduled"),
        EndpointCheck("sport-api-real-time-tournaments", join_url(base_urls["sportApiRealTime"], "/tournaments/scheduled-events", {"categoryId": category_id, "date": test_date}), None, "scheduled"),
        EndpointCheck("sofascore-sport-scheduled-events", join_url(base_urls["sofascoreSportApi"], f"/api/sport/football/scheduled-events/{test_date}"), None, "scheduled"),
    ]
    stats: list[EndpointCheck] = []
    for match_id in match_ids:
        stats.extend(
            [
                EndpointCheck(f"sportapi7-event-statistics:{match_id}", join_url(base_urls["sportapi7"], f"/api/v1/event/{match_id}/statistics"), None, "statistics"),
                EndpointCheck(f"sofascore-event-statistics:{match_id}", join_url(base_urls["sofascore"], "/matches/get-statistics", {"matchId": match_id}), None, "statistics"),
                EndpointCheck(f"sport-api-real-time-event-statistics:{match_id}", join_url(base_urls["sportApiRealTime"], "/matches/statistics", {"matchId": match_id}), None, "statistics"),
                EndpointCheck(f"sofascore-sport-event-statistics:{match_id}", join_url(base_urls["sofascoreSportApi"], f"/api/event/{match_id}/statistics"), None, "statistics"),
                EndpointCheck(f"sofasport-event-statistics:{match_id}", join_url(base_urls["sofasport"], "/v1/events/statistics", {"event_id": match_id}), None, "statistics"),
                EndpointCheck(f"sofascore-public-event:{match_id}", join_url(public_base_url, f"/event/{match_id}"), None, "public"),
                EndpointCheck(f"sofascore-public-statistics:{match_id}", join_url(public_base_url, f"/event/{match_id}/statistics"), None, "public"),
            ]
        )
    return scheduled + stats


def run_source_connectivity_audit(
    *,
    source_workflow: str,
    test_date: str | None = None,
    category_id: str = "34",
    match_ids: list[str] | None = None,
    max_keys: int = 10,
    env: dict[str, str] | None = None,
    transport: Transport | None = None,
    database: Any | None = None,
    dry_run: bool = False,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    now = generated_at or utc_now()
    env_map = dict(os.environ if env is None else env)
    rapidapi_keys = load_rapidapi_keys(env_map, max_keys=max_keys)
    base_urls = {
        "sportapi7": trim_slash(env_map.get("RAPIDAPI_SPORTAPI7_BASE_URL", DEFAULT_BASE_URLS["sportapi7"])),
        "sofascore": trim_slash(env_map.get("RAPIDAPI_SOFASCORE_BASE_URL", DEFAULT_BASE_URLS["sofascore"])),
        "sportApiRealTime": trim_slash(env_map.get("RAPIDAPI_SPORT_API_REAL_TIME_BASE_URL", DEFAULT_BASE_URLS["sportApiRealTime"])),
        "sofascoreSportApi": trim_slash(env_map.get("RAPIDAPI_SOFASCORE_SPORT_API_BASE_URL", DEFAULT_BASE_URLS["sofascoreSportApi"])),
        "sofasport": trim_slash(env_map.get("RAPIDAPI_SOFASPORT_BASE_URL", DEFAULT_BASE_URLS["sofasport"])),
    }
    public_base_url = trim_slash(env_map.get("SOFASCORE_PUBLIC_API_BASE_URL", "https://api.sofascore.com/api/v1"))
    checks = default_endpoint_checks(
        base_urls=base_urls,
        test_date=test_date or yesterday_ymd_utc(),
        category_id=category_id,
        match_ids=match_ids or ["15235566", "14065562", "14083306"],
        public_base_url=public_base_url,
    )

    endpoint_results: list[dict[str, Any]] = []
    for check in checks:
        if check.kind == "public":
            fetch_result = fetch_json(check.url, headers={}, timeout_seconds=15, transport=transport)
            transformed = fetch_result["data"] if "statistics" in check.name else (fetch_result["data"].get("event") if isinstance(fetch_result["data"], dict) else fetch_result["data"])
            endpoint_results.append(
                {
                    "endpoint": check.name,
                    "kind": check.kind,
                    "ok": bool(fetch_result["ok"]) and not _is_empty(transformed),
                    "http_ok": bool(fetch_result["ok"]),
                    "status": fetch_result["status"] or fetch_result["status_text"],
                    "empty": _is_empty(transformed),
                    "key": None,
                    "preview": _safe_json_preview(transformed or fetch_result["data"]),
                    "url": check.url,
                }
            )
            continue

        if not rapidapi_keys:
            endpoint_results.append(
                {
                    "endpoint": check.name,
                    "kind": check.kind,
                    "ok": False,
                    "http_ok": False,
                    "status": "NO_KEYS",
                    "empty": True,
                    "key": None,
                    "preview": None,
                    "url": check.url,
                }
            )
            continue

        success = None
        for api_key in rapidapi_keys:
            result = fetch_json(
                check.url,
                headers={"x-rapidapi-key": api_key, "x-rapidapi-host": check.url.split("/")[2]},
                timeout_seconds=15,
                transport=transport,
            )
            transformed = _extract_scheduled(result["data"]) if check.kind == "scheduled" else _extract_stats(result["data"])
            row = {
                "endpoint": check.name,
                "kind": check.kind,
                "ok": bool(result["ok"]) and not _is_empty(transformed),
                "http_ok": bool(result["ok"]),
                "status": result["status"] or result["status_text"],
                "empty": _is_empty(transformed),
                "key": key_label(api_key),
                "preview": _safe_json_preview(transformed or result["data"]),
                "url": check.url,
            }
            endpoint_results.append(row)
            if row["ok"]:
                success = row
                break
        if success is None and endpoint_results:
            pass

    success_count = sum(1 for row in endpoint_results if row["ok"])
    empty_count = sum(1 for row in endpoint_results if row["http_ok"] and row["empty"])
    no_key_count = sum(1 for row in endpoint_results if row["status"] == "NO_KEYS")
    failure_count = sum(1 for row in endpoint_results if not row["http_ok"] and row["status"] != "NO_KEYS")
    findings: list[str] = []
    if no_key_count:
        findings.append("missing_rapidapi_keys")
    if empty_count:
        findings.append("empty_payloads_detected")
    if failure_count:
        findings.append("failed_endpoint_requests")
    status = "ok" if not findings else "warn"
    report_date = now.date().isoformat()
    audit_rows = [
        build_audit_report_row(
            audit_type="source_connectivity",
            scope_key=source_workflow,
            status=status,
            metrics={
                "endpoint_count": len(endpoint_results),
                "success_count": success_count,
                "empty_count": empty_count,
                "no_key_count": no_key_count,
                "failure_count": failure_count,
                "kind_counts": dict(Counter(row["kind"] for row in endpoint_results)),
            },
            findings=findings,
            report_date=report_date,
        )
    ]
    health_rows = [
        build_health_report_row(
            job_name="audit_source_connectivity",
            status=status,
            summary="RapidAPI/source connectivity audit completed.",
            metrics={
                "endpoint_count": len(endpoint_results),
                "success_count": success_count,
                "failure_count": failure_count,
                "empty_count": empty_count,
                "no_key_count": no_key_count,
            },
            report_date=report_date,
        )
    ]
    summary: dict[str, Any] = {
        "job": "audit_source_connectivity",
        "test_date": test_date or yesterday_ymd_utc(),
        "category_id": category_id,
        "match_ids": match_ids or ["15235566", "14065562", "14083306"],
        "endpoint_results": endpoint_results,
        "audit_reports": len(audit_rows),
        "health_reports": len(health_rows),
        "audit_status_counts": dict(Counter(row["status"] for row in audit_rows)),
        "health_status_counts": dict(Counter(row["status"] for row in health_rows)),
    }
    if dry_run:
        summary["audit_rows"] = audit_rows
        summary["health_rows"] = health_rows
        return summary
    if database is None:
        raise RuntimeError("database is required when dry_run is False.")

    run_doc = build_job_run_started_doc(
        job_name="audit_source_connectivity",
        source_workflow=source_workflow,
        target_window={"test_date": test_date or yesterday_ymd_utc()},
        job_args={"dry_run": False, "category_id": category_id, "match_ids": match_ids or []},
    )
    database["job_runs"].insert_one(run_doc)
    job_metrics = {key: value for key, value in summary.items() if key not in {"endpoint_results", "audit_rows", "health_rows"}}
    try:
        for row in audit_rows:
            database["audit_reports"].update_one(
                {"audit_type": row["audit_type"], "scope_key": row["scope_key"], "report_date": row["report_date"]},
                {"$set": row},
                upsert=True,
            )
        for row in health_rows:
            database["health_reports"].update_one(
                {"job_name": row["job_name"], "report_date": row["report_date"]},
                {"$set": row},
                upsert=True,
            )
        database["job_runs"].update_one(
            {"run_id": run_doc["run_id"]},
            build_job_run_finished_update(status="succeeded", metrics=job_metrics),
        )
    except Exception as exc:
        database["job_runs"].update_one(
            {"run_id": run_doc["run_id"]},
            build_job_run_finished_update(
                status="failed",
                metrics=job_metrics,
                error={"type": type(exc).__name__, "message": str(exc)},
            ),
        )
        raise
    summary["audit_rows"] = audit_rows
    summary["health_rows"] = health_rows
    return summary

