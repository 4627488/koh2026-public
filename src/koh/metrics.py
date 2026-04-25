from __future__ import annotations

from collections import defaultdict
from threading import Lock
from time import perf_counter

from sqlalchemy import func
from sqlalchemy.orm import Session

from koh.db.models import MapTemplate, Match, Round, TestRun
from koh.site_config import get_or_create_site_config

_REQUEST_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
_metrics_lock = Lock()
_request_count: dict[tuple[str, str, str], float] = defaultdict(float)
_request_duration_sum: dict[tuple[str, str], float] = defaultdict(float)
_request_duration_count: dict[tuple[str, str], float] = defaultdict(float)
_request_duration_bucket: dict[tuple[str, str, float], float] = defaultdict(float)


def _escape_label_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _format_labels(labels: dict[str, str]) -> str:
    if not labels:
        return ""
    pairs = [f'{key}="{_escape_label_value(value)}"' for key, value in labels.items()]
    return "{" + ",".join(pairs) + "}"


def _metric_line(name: str, value: float, labels: dict[str, str] | None = None) -> str:
    return f"{name}{_format_labels(labels or {})} {value}"


def observe_http_request(method: str, path: str, status_code: int, duration_seconds: float) -> None:
    status = str(status_code)
    with _metrics_lock:
        _request_count[(method, path, status)] += 1
        _request_duration_sum[(method, path)] += duration_seconds
        _request_duration_count[(method, path)] += 1
        for bucket in _REQUEST_BUCKETS:
            if duration_seconds <= bucket:
                _request_duration_bucket[(method, path, bucket)] += 1


class RequestTimer:
    def __init__(self) -> None:
        self._started = perf_counter()

    def elapsed(self) -> float:
        return perf_counter() - self._started


def collect_competition_metrics(db: Session) -> dict:
    site_cfg = get_or_create_site_config(db)
    latest_round = db.query(Round).order_by(Round.id.desc()).first()
    latest_test_run = db.query(TestRun).order_by(TestRun.id.desc()).first()
    active_maps = db.query(MapTemplate).filter(MapTemplate.is_active.is_(True)).count()

    round_status_counts = {
        status: count
        for status, count in db.query(Round.status, func.count(Round.id)).group_by(Round.status).all()
    }
    match_status_counts = {
        status: count
        for status, count in db.query(Match.status, func.count(Match.id)).group_by(Match.status).all()
    }

    return {
        "phase": site_cfg.phase,
        "active_maps": active_maps,
        "current_round_id": latest_round.id if latest_round and site_cfg.phase != "test" else 0,
        "next_round_id": (latest_round.id + 1) if latest_round and site_cfg.phase != "test" else 0,
        "latest_test_run_id": latest_test_run.id if latest_test_run else 0,
        "round_status_counts": round_status_counts,
        "match_status_counts": match_status_counts,
    }


def render_metrics_text(
    *,
    service: str,
    version: str,
    phase: str,
    auto_round_enabled: bool,
    auto_round_state: str,
    active_maps: int,
    current_round_id: int,
    next_round_id: int,
    latest_test_run_id: int,
    round_status_counts: dict[str, int],
    match_status_counts: dict[str, int],
) -> str:
    lines = [
        "# HELP koh_http_requests_total Total number of HTTP requests handled by the API.",
        "# TYPE koh_http_requests_total counter",
    ]

    with _metrics_lock:
        request_count_items = sorted(_request_count.items())
        request_duration_count_items = sorted(_request_duration_count.items())
        request_duration_sum_items = sorted(_request_duration_sum.items())
        request_duration_bucket_items = sorted(_request_duration_bucket.items())

    for (method, path, status), value in request_count_items:
        lines.append(
            _metric_line(
                "koh_http_requests_total",
                value,
                {"method": method, "path": path, "status": status},
            )
        )

    lines.extend(
        [
            "# HELP koh_http_request_duration_seconds HTTP request latency in seconds.",
            "# TYPE koh_http_request_duration_seconds histogram",
        ]
    )
    for (method, path, bucket), value in request_duration_bucket_items:
        lines.append(
            _metric_line(
                "koh_http_request_duration_seconds_bucket",
                value,
                {"method": method, "path": path, "le": str(bucket)},
            )
        )
    for (method, path), value in request_duration_count_items:
        lines.append(
            _metric_line(
                "koh_http_request_duration_seconds_count",
                value,
                {"method": method, "path": path},
            )
        )
    for (method, path), value in request_duration_sum_items:
        lines.append(
            _metric_line(
                "koh_http_request_duration_seconds_sum",
                value,
                {"method": method, "path": path},
            )
        )

    lines.extend(
        [
            "# HELP koh_app_info Static application build information.",
            "# TYPE koh_app_info gauge",
            _metric_line("koh_app_info", 1, {"service": service, "version": version}),
            "# HELP koh_active_maps Number of active maps.",
            "# TYPE koh_active_maps gauge",
            _metric_line("koh_active_maps", active_maps),
            "# HELP koh_current_round_id Latest round id in competition mode, 0 when unavailable.",
            "# TYPE koh_current_round_id gauge",
            _metric_line("koh_current_round_id", current_round_id),
            "# HELP koh_next_round_id Next round id in competition mode, 0 when unavailable.",
            "# TYPE koh_next_round_id gauge",
            _metric_line("koh_next_round_id", next_round_id),
            "# HELP koh_latest_test_run_id Latest test run id, 0 when unavailable.",
            "# TYPE koh_latest_test_run_id gauge",
            _metric_line("koh_latest_test_run_id", latest_test_run_id),
            "# HELP koh_phase_info Current site phase.",
            "# TYPE koh_phase_info gauge",
        ]
    )
    for known_phase in ("competition", "test"):
        lines.append(_metric_line("koh_phase_info", 1 if phase == known_phase else 0, {"phase": known_phase}))

    lines.extend(
        [
            "# HELP koh_auto_round_enabled Whether auto round scheduling is enabled.",
            "# TYPE koh_auto_round_enabled gauge",
            _metric_line("koh_auto_round_enabled", 1 if auto_round_enabled else 0),
            "# HELP koh_auto_round_state Current auto round scheduler state.",
            "# TYPE koh_auto_round_state gauge",
        ]
    )
    known_auto_states = ("disabled", "unscheduled", "invalid", "before_start", "running", "finished")
    emitted_states = set()
    for known_state in known_auto_states:
        lines.append(
            _metric_line(
                "koh_auto_round_state",
                1 if auto_round_state == known_state else 0,
                {"state": known_state},
            )
        )
        emitted_states.add(known_state)
    if auto_round_state not in emitted_states:
        lines.append(_metric_line("koh_auto_round_state", 1, {"state": auto_round_state}))

    lines.extend(
        [
            "# HELP koh_round_status_count Number of rounds by status.",
            "# TYPE koh_round_status_count gauge",
        ]
    )
    for status, count in sorted(round_status_counts.items()):
        lines.append(_metric_line("koh_round_status_count", count, {"status": status}))

    lines.extend(
        [
            "# HELP koh_match_status_count Number of matches by status.",
            "# TYPE koh_match_status_count gauge",
        ]
    )
    for status, count in sorted(match_status_counts.items()):
        lines.append(_metric_line("koh_match_status_count", count, {"status": status}))

    return "\n".join(lines) + "\n"
