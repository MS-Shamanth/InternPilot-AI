"""Pure tests for job list parameters and pagination helpers (R2.5, R2.6, R2.13, §8.1)."""

import pytest
from pydantic import ValidationError

from app.schemas.job import JobListParams, JobSortKey, SortOrder
from app.services.job_service import page_slice, total_pages

pytestmark = pytest.mark.unit


def test_job_list_params_defaults_sort_by_match_score_desc() -> None:
    params = JobListParams()

    assert (params.sort, params.effective_order) == (JobSortKey.MATCH_SCORE, SortOrder.DESC)
    assert (params.page, params.page_size) == (1, 20)
    assert params.skill_names == ()


@pytest.mark.parametrize(
    ("sort", "expected"),
    [
        ("discovered_at", SortOrder.DESC),
        ("deadline", SortOrder.ASC),
        ("title", SortOrder.ASC),
        ("company", SortOrder.ASC),
        ("salary", SortOrder.DESC),
    ],
)
def test_job_list_params_effective_order_uses_key_default(sort: str, expected: SortOrder) -> None:
    assert JobListParams(sort=sort).effective_order is expected
    assert JobListParams(sort=sort, order="asc").effective_order is SortOrder.ASC


def test_job_list_params_skills_are_normalized_deduplicated_and_sorted() -> None:
    params = JobListParams(skills=" ReactJS, python,,React , Postgres ")

    assert params.skill_names == ("postgresql", "python", "react")


def test_job_list_params_blank_q_and_skills_mean_no_filter() -> None:
    params = JobListParams(q="   ", skills=" , ")

    assert params.q is None
    assert params.skill_names == ()


@pytest.mark.parametrize(
    "fields",
    [
        {"page": 0},
        {"page_size": 0},
        {"page_size": 101},
        {"sort": "popularity"},
        {"order": "up"},
        {"q": "x" * 101},
        {"min_score": -1},
        {"min_score": 101},
        {"work_mode": ["moon"]},
        {"skills": "react,(,)"},
        {"skills": ",".join(f"skill{n}" for n in range(11))},
        {"unknown": "1"},
    ],
)
def test_job_list_params_invalid_raise(fields: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        JobListParams.model_validate(fields)


def test_total_pages_rounds_up_and_is_zero_when_empty() -> None:
    assert [total_pages(total, 2) for total in (0, 1, 2, 3)] == [0, 1, 1, 2]


def test_page_slice_beyond_last_page_is_empty() -> None:
    items = [1, 2, 3]

    assert page_slice(items, 2, 2) == [3]
    assert page_slice(items, 3, 2) == []
