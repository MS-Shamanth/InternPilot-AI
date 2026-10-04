"""Unit tests for resume extraction, outputs and suggestion rules (R8.3, R8.5, design.md §9)."""

import pytest

from app.schemas.resume import (
    ResumeMissingSkill,
    ResumeRelevantProject,
    ResumeSource,
    ResumeSuggestionRule,
)
from app.services.matching.skill_catalog import CATALOG
from app.services.resume_analysis import (
    build_suggestions,
    extract_resume_skills,
    link_in_resume,
    missing_keywords,
    numeric_token_count,
    resume_views,
    word_count,
)

pytestmark = pytest.mark.unit

LONG_NUMERIC_RESUME = " ".join(["word"] * 300) + " 10 20% 3x"


def skills(text: str, extra: tuple[str, ...] = ()) -> frozenset[str]:
    return extract_resume_skills(resume_views(text), extra)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("go to market", frozenset()),
        ("Built services in Go", frozenset({"go"})),
        ("Golang microservices", frozenset({"go"})),
        ("built REST APIs", frozenset({"rest apis"})),
        ("the rest of the team", frozenset()),
        ("R and Python", frozenset({"r", "python"})),
        ("javascript only", frozenset({"javascript"})),
        ("C++ and C# tools", frozenset({"c++", "c#"})),
        ("Shipped Node.js and ReactJS apps", frozenset({"node.js", "react"})),
        ("ml pipelines in js", frozenset()),
        ("ML pipelines in JS", frozenset({"machine learning", "javascript"})),
    ],
)
def test_extract_resume_skills_text_returns_expected(text: str, expected: frozenset[str]) -> None:
    assert skills(text) == expected


def test_extract_resume_skills_extra_catalog_term_detected() -> None:
    assert skills("Used Airflow DAGs daily", ("airflow",)) == {"airflow"}


def test_extract_resume_skills_whitespace_and_nfkc_normalized() -> None:
    assert skills("\uff30\uff59\uff54\uff48\uff4f\uff4e and machine\n\tlearning") == {
        "python",
        "machine learning",
    }


def test_word_and_numeric_counts() -> None:
    resume = resume_views("Cut latency 40% across 3 services in 2024 alone")
    assert word_count(resume) == 9
    assert numeric_token_count(resume) == 3


def test_missing_keywords_frequency_catalog_stopwords_and_order() -> None:
    description = (
        "Kafka pipelines. Kafka streaming. Pipelines with docker. The the the. Rare term. Python."
    )
    resume = resume_views("I write python")
    assert missing_keywords(description, resume, frozenset(CATALOG)) == [
        "kafka",
        "pipelines",
        "docker",
    ]


def test_missing_keywords_capped_at_fifteen() -> None:
    description = " ".join(f"term{chr(97 + i)} term{chr(97 + i)}" for i in range(20))
    assert len(missing_keywords(description, resume_views("x"), frozenset())) == 15


def test_link_in_resume_ignores_scheme_www_and_slash() -> None:
    resume = resume_views("See github.com/demo for code")
    assert link_in_resume("https://www.github.com/demo/", resume)
    assert not link_in_resume("https://github.com/other", resume)


def rules(**overrides: object) -> list[tuple[ResumeSuggestionRule, list[str]]]:
    values: dict[str, object] = {
        "missing": [],
        "projects": [],
        "keywords": [],
        "resume": resume_views(LONG_NUMERIC_RESUME),
        "links": {},
    }
    values.update(overrides)
    return [(item.rule, item.evidence) for item in build_suggestions(**values)]


def test_build_suggestions_no_differences_returns_nothing() -> None:
    assert rules() == []


def test_build_suggestions_skill_rules_ordered_by_rule_then_evidence() -> None:
    missing = [
        ResumeMissingSkill(skill="SQL", is_required=True, in_profile=True),
        ResumeMissingSkill(skill="Docker", is_required=False, in_profile=True),
        ResumeMissingSkill(skill="React", is_required=True, in_profile=False),
        ResumeMissingSkill(skill="Figma", is_required=False, in_profile=False),
    ]
    suggestions = build_suggestions(
        missing=missing,
        projects=[],
        keywords=[],
        resume=resume_views(LONG_NUMERIC_RESUME),
        links={},
    )
    assert [(item.rule, item.evidence) for item in suggestions] == [
        (ResumeSuggestionRule.ADD_PROFILE_SKILL, ["Docker"]),
        (ResumeSuggestionRule.ADD_PROFILE_SKILL, ["SQL"]),
        (ResumeSuggestionRule.GAP_REQUIRED_SKILL, ["React"]),
    ]
    assert "which this role prefers" in suggestions[0].message
    assert "which this role requires" in suggestions[1].message


def test_build_suggestions_mention_project_only_when_not_mentioned() -> None:
    projects = [
        ResumeRelevantProject(
            name="Tracker", matched_skills=["React", "SQL"], mentioned_in_resume=False
        ),
        ResumeRelevantProject(name="Blog", matched_skills=["React"], mentioned_in_resume=True),
    ]
    suggestions = build_suggestions(
        missing=[],
        projects=projects,
        keywords=[],
        resume=resume_views(LONG_NUMERIC_RESUME),
        links={},
    )
    assert len(suggestions) == 1
    assert suggestions[0].message == 'Mention your project "Tracker"; it uses React, SQL.'


def test_build_suggestions_keywords_need_three_and_show_top_five() -> None:
    assert rules(keywords=["a1", "b1"]) == []
    keywords = ["k1", "k2", "k3", "k4", "k5", "k6"]
    assert rules(keywords=keywords) == [
        (ResumeSuggestionRule.ADD_KEYWORDS, ["k1", "k2", "k3", "k4", "k5"])
    ]


def test_build_suggestions_quantify_below_three_numbers() -> None:
    resume = resume_views(" ".join(["word"] * 300) + " 10 20%")
    assert rules(resume=resume) == [(ResumeSuggestionRule.QUANTIFY, ["2"])]


@pytest.mark.parametrize(
    ("words", "rule"),
    [(149, ResumeSuggestionRule.LENGTH_SHORT), (1201, ResumeSuggestionRule.LENGTH_LONG)],
)
def test_build_suggestions_length_rules(words: int, rule: ResumeSuggestionRule) -> None:
    resume = resume_views(" ".join(["word"] * (words - 3)) + " 1 2 3")
    suggestions = build_suggestions(missing=[], projects=[], keywords=[], resume=resume, links={})
    assert [(item.rule, item.evidence) for item in suggestions] == [(rule, [str(words)])]
    assert suggestions[0].message == (
        f"Resume has {words} words; aim for 300\u2013900 for early-career roles."
    )


def test_build_suggestions_length_bounds_inclusive() -> None:
    for words in (150, 1200):
        resume = resume_views(" ".join(["word"] * (words - 3)) + " 1 2 3")
        assert rules(resume=resume) == []


def test_build_suggestions_add_links_for_absent_links() -> None:
    resume = resume_views(LONG_NUMERIC_RESUME + " github.com/demo")
    links = {"GitHub": "https://github.com/demo", "portfolio": "https://demo.example.com"}
    suggestions = build_suggestions(
        missing=[], projects=[], keywords=[], resume=resume, links=links
    )
    assert [(item.rule, item.message) for item in suggestions] == [
        (ResumeSuggestionRule.ADD_LINKS, "Add your portfolio link.")
    ]


def test_resume_source_values_match_contract() -> None:
    assert [source.value for source in ResumeSource] == ["request", "profile"]
