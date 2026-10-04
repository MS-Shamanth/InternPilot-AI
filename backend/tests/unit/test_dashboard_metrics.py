"""Unit tests for the pure dashboard metric definitions (R6.2, R6.4, R6.5, design.md §7)."""

from datetime import UTC, date, datetime, timedelta

from app.core.clock import FixedClock
from app.services.application_status import CANONICAL_ORDER, ApplicationStatus
from app.services.dashboard_service import (
    ApplicationFact,
    BookmarkFact,
    DashboardMetrics,
    compute_metrics,
    response_rate,
)

CLOCK = FixedClock(datetime(2025, 1, 15, 9, 30, tzinfo=UTC))  # a Wednesday
TODAY = CLOCK.today()
NOW = CLOCK.now()
S = ApplicationStatus


def app(
    app_id: int,
    status: ApplicationStatus,
    *,
    applied_at: date | None = None,
    deadline: date | None = None,
    interview_date: datetime | None = None,
) -> ApplicationFact:
    return ApplicationFact(
        id=app_id,
        job_id=app_id * 10,
        status=status,
        applied_at=applied_at,
        deadline=deadline,
        interview_date=interview_date,
        title=f"Job {app_id}",
        company="Example Co",
    )


def metrics(
    *apps: ApplicationFact,
    scores: tuple[int, ...] = (),
    total_jobs: int = 0,
    bookmarks: tuple[BookmarkFact, ...] = (),
) -> DashboardMetrics:
    return compute_metrics(apps, scores, TODAY, NOW, total_jobs=total_jobs, bookmarks=bookmarks)


def test_compute_metrics_no_data_returns_zeros_and_full_lists() -> None:
    result = metrics()
    assert (result.total_jobs_discovered, result.matching_jobs, result.applications_submitted) == (
        0,
        0,
        0,
    )
    assert (result.interviews_scheduled, result.offers_received, result.response_rate) == (
        0,
        0,
        0.0,
    )
    assert result.upcoming_deadlines == ()
    assert [item.status for item in result.status_breakdown] == list(CANONICAL_ORDER)
    assert all(item.count == 0 for item in result.status_breakdown)
    assert len(result.applications_over_time) == 8
    assert [item.bucket.value for item in result.score_distribution] == [
        "0-19",
        "20-39",
        "40-59",
        "60-79",
        "80-100",
    ]


def test_compute_metrics_total_jobs_is_passed_through() -> None:
    assert metrics(total_jobs=7).total_jobs_discovered == 7


def test_compute_metrics_matching_jobs_counts_scores_at_least_60() -> None:
    assert metrics(scores=(59, 60, 100, 0)).matching_jobs == 2


def test_compute_metrics_submitted_includes_withdrawn_with_applied_at_only() -> None:
    result = metrics(
        app(1, S.SAVED),
        app(2, S.APPLIED),
        app(3, S.REJECTED),
        app(4, S.WITHDRAWN, applied_at=TODAY),
        app(5, S.WITHDRAWN),
        app(6, S.INTERESTED),
    )
    assert result.applications_submitted == 3


def test_compute_metrics_interviews_counts_status_or_future_date_once() -> None:
    future = NOW + timedelta(days=2)
    result = metrics(
        app(1, S.INTERVIEW, interview_date=future),
        app(2, S.APPLIED, interview_date=future),
        app(3, S.APPLIED, interview_date=NOW - timedelta(seconds=1)),
        app(4, S.OFFER, interview_date=future),
        app(5, S.ASSESSMENT, interview_date=NOW),
    )
    assert result.interviews_scheduled == 3


def test_compute_metrics_offers_counts_offer_status() -> None:
    assert metrics(app(1, S.OFFER), app(2, S.APPLIED)).offers_received == 1


def test_response_rate_rounds_half_up_to_one_decimal() -> None:
    assert response_rate(1, 3) == 33.3
    assert response_rate(1, 16) == 6.3  # 6.25 rounds up
    assert response_rate(0, 0) == 0.0


def test_compute_metrics_response_rate_uses_responded_over_submitted() -> None:
    result = metrics(app(1, S.APPLIED), app(2, S.INTERVIEW), app(3, S.REJECTED), app(4, S.SAVED))
    assert result.response_rate == 66.7


def test_compute_metrics_deadlines_window_statuses_order_and_kinds() -> None:
    result = metrics(
        app(1, S.APPLIED, deadline=TODAY + timedelta(days=14)),
        app(2, S.SAVED, deadline=TODAY),
        app(3, S.REJECTED, deadline=TODAY + timedelta(days=1)),
        app(4, S.INTERVIEW, deadline=TODAY + timedelta(days=15)),
        app(5, S.APPLIED, deadline=TODAY - timedelta(days=1)),
        bookmarks=(BookmarkFact(7, "Bookmarked", "Example Co", TODAY + timedelta(days=3)),),
    )
    assert [
        (item.job_id, item.days_left, item.kind.value) for item in result.upcoming_deadlines
    ] == [
        (20, 0, "application"),
        (7, 3, "bookmark"),
        (10, 14, "application"),
    ]
    assert result.upcoming_deadlines[1].application_id is None


def test_compute_metrics_deadlines_capped_at_eight() -> None:
    apps = [app(i, S.SAVED, deadline=TODAY + timedelta(days=i)) for i in range(1, 11)]
    assert len(metrics(*apps).upcoming_deadlines) == 8


def test_compute_metrics_status_breakdown_counts_each_status() -> None:
    result = metrics(app(1, S.APPLIED), app(2, S.APPLIED), app(3, S.OFFER))
    counts = {item.status: item.count for item in result.status_breakdown}
    assert counts[S.APPLIED] == 2
    assert counts[S.OFFER] == 1
    assert sum(counts.values()) == 3


def test_compute_metrics_applications_over_time_groups_by_iso_week() -> None:
    monday = date(2025, 1, 13)
    result = metrics(
        app(1, S.APPLIED, applied_at=TODAY),
        app(2, S.APPLIED, applied_at=monday),
        app(3, S.APPLIED, applied_at=monday - timedelta(days=1)),
        app(4, S.APPLIED, applied_at=monday - timedelta(weeks=8)),
    )
    weeks = result.applications_over_time
    assert weeks[0].week_start == monday - timedelta(weeks=7)
    assert weeks[-1].week_start == monday
    assert (weeks[-1].count, weeks[-2].count) == (2, 1)
    assert sum(week.count for week in weeks) == 3


def test_compute_metrics_score_distribution_bucket_edges() -> None:
    result = metrics(scores=(0, 19, 20, 39, 40, 59, 60, 79, 80, 100, 100))
    assert [item.count for item in result.score_distribution] == [2, 2, 2, 2, 3]
