"""`GET /api/recommendations` (R7, design.md §7, §8)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import CurrentUser, SessionDep
from app.schemas.job import Recommendation
from app.services.recommendation_service import DEFAULT_RECOMMENDATION_LIMIT, RecommendationService

RECOMMENDATION_LIMIT_MAX = 20

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


def get_recommendation_service(session: SessionDep) -> RecommendationService:
    return RecommendationService(session)


RecommendationServiceDep = Annotated[RecommendationService, Depends(get_recommendation_service)]
Limit = Annotated[int, Query(ge=1, le=RECOMMENDATION_LIMIT_MAX)]


@router.get("")
def list_recommendations(
    user: CurrentUser,
    service: RecommendationServiceDep,
    limit: Limit = DEFAULT_RECOMMENDATION_LIMIT,
) -> list[Recommendation]:
    """Best-fit non-hidden jobs not yet applied to (no application or Saved/Interested)."""
    return service.recommend(user, limit)
