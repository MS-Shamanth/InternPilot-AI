"""Dashboard API contract (R6, design.md §7, §8.3); mirrors `Dashboard` in `types/api.ts`."""

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from app.schemas.common import UtcDateTime
from app.services.application_status import ApplicationStatus


class DeadlineKind(StrEnum):
    APPLICATION = "application"
    BOOKMARK = "bookmark"


class ActivityType(StrEnum):
    APPLICATION_CREATED = "application_created"
    STATUS_CHANGED = "status_changed"
    APPLICATION_UPDATED = "application_updated"
    APPLICATION_DELETED = "application_deleted"
    JOB_BOOKMARKED = "job_bookmarked"
    JOB_HIDDEN = "job_hidden"
    PROFILE_UPDATED = "profile_updated"
    JOBS_INGESTED = "jobs_ingested"


class ScoreBucket(StrEnum):
    B0_19 = "0-19"
    B20_39 = "20-39"
    B40_59 = "40-59"
    B60_79 = "60-79"
    B80_100 = "80-100"


class UpcomingDeadline(BaseModel):
    job_id: int
    application_id: int | None
    title: str
    company: str
    deadline: date
    days_left: int
    kind: DeadlineKind


class ActivityItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: ActivityType
    message: str
    job_id: int | None
    application_id: int | None
    created_at: UtcDateTime


class TopRecommendation(BaseModel):
    job_id: int
    title: str
    company: str
    location: str
    score: int


class StatusCount(BaseModel):
    status: ApplicationStatus
    count: int


class WeeklyApplicationCount(BaseModel):
    week_start: date
    count: int


class ScoreBucketCount(BaseModel):
    bucket: ScoreBucket
    count: int


class Dashboard(BaseModel):
    total_jobs_discovered: int
    matching_jobs: int
    applications_submitted: int
    interviews_scheduled: int
    offers_received: int
    response_rate: float
    upcoming_deadlines: list[UpcomingDeadline]
    recent_activity: list[ActivityItem]
    top_recommendations: list[TopRecommendation]
    status_breakdown: list[StatusCount]
    applications_over_time: list[WeeklyApplicationCount]
    score_distribution: list[ScoreBucketCount]
